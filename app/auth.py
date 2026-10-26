# app/auth.py — register, log in, log out, and the "who is calling" dependency.
#
# POST /api/auth/register   create an account (starts with the starter words), logs in
# POST /api/auth/login      email + password -> session cookie
# POST /api/auth/logout     deletes the session
# GET  /api/auth/me         the logged-in user, or 401
#
# The session lives in an HttpOnly cookie, so page JavaScript cannot read it, and
# SameSite=Lax keeps other sites from sending it with their POST/PATCH/DELETE requests.
import os
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.db import connect
from app.repository import DuplicateEmail, UserRepository
from app.schemas import LoginIn, RegisterIn, User
from app.security import (
    SESSION_COOKIE,
    SESSION_DAYS,
    hash_password,
    new_session_token,
    token_hash,
    verify_password,
)

# Browsers only send a Secure cookie over HTTPS: on for Render, off for http://localhost.
SECURE_COOKIE = os.environ.get("APP_ENV") == "production"

# Checked when the email is unknown, so "no such user" takes as long as "wrong password".
DUMMY_HASH = hash_password("not-a-real-password")

router = APIRouter(prefix="/api/auth")


def get_conn() -> Iterator[psycopg.Connection]:
    # One connection per request, shared by every dependency that asks for it.
    # Leaving the "with" commits, an exception rolls back.
    with connect() as conn:
        yield conn


def get_users(conn: Annotated[psycopg.Connection, Depends(get_conn)]) -> UserRepository:
    return UserRepository(conn)


Users = Annotated[UserRepository, Depends(get_users)]


def current_user(request: Request, users: Users) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    user = users.get_session_user(token_hash(token)) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập")
    return user


CurrentUser = Annotated[dict, Depends(current_user)]


def start_session(response: Response, users: Users, user_id: int) -> None:
    token = new_session_token()
    users.create_session(token_hash(token), user_id, SESSION_DAYS)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=SECURE_COOKIE,
    )


@router.post("/register", response_model=User, status_code=201)
def register(body: RegisterIn, response: Response, users: Users):
    try:
        user = users.create_user(
            body.email.strip(), body.display_name.strip(), hash_password(body.password)
        )
    except DuplicateEmail:
        raise HTTPException(status_code=409, detail="Email này đã được đăng ký") from None
    users.copy_starter_words(user["id"])
    start_session(response, users, user["id"])
    return user


@router.post("/login", response_model=User)
def login(body: LoginIn, response: Response, users: Users):
    user = users.get_user_by_email(body.email.strip())
    ok = verify_password(body.password, user["password_hash"] if user else DUMMY_HASH)
    if user is None or not ok:
        # Same message either way, so the form does not reveal which emails exist.
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    start_session(response, users, user["id"])
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, users: Users):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        users.delete_session(token_hash(token))
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax", secure=SECURE_COOKIE)
    return response


@router.get("/me", response_model=User)
def me(user: CurrentUser):
    return user
