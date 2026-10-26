# app/main.py — Vocabulary Notebook (EN–VN) API.
#
# /            web UI (app/static/index.html: list, add, edit, review pages)
# /health      fast platform health check, touches nothing (Render points here)
# /health/db   proves the database connection
# /api/info    app name, version and environment
# /api/auth/.. register, login, logout, me (app/auth.py)
# /api/...     CRUD for words and review logs, per user (app/routes.py)
import hashlib
import os
from pathlib import Path

import psycopg
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.auth import router as auth_router
from app.db import DatabaseUnavailable, connect
from app.routes import router

APP_VERSION = "0.1.0"
APP_ENV = os.environ.get("APP_ENV", "development")
STATIC_DIR = Path(__file__).resolve().parent / "static"


def versioned_index() -> str:
    # index.html links app.js / style.css as "...?v=<hash of their content>", so a new
    # deploy changes the URLs and no browser (Safari especially) keeps running a stale copy.
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    for name in ("style.css", "app.js"):
        version = hashlib.sha256((STATIC_DIR / name).read_bytes()).hexdigest()[:10]
        html = html.replace(f'"/static/{name}"', f'"/static/{name}?v={version}"')
    return html


INDEX_HTML = versioned_index()

DB_DOWN_MESSAGE = "The database is starting up or paused. Please try again in a few seconds."

app = FastAPI(title="vocab-notebook")
app.include_router(auth_router)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def revalidate_ui(request: Request, call_next):
    # The browser must check for a new index.html / app.js / style.css on every load,
    # otherwise after a deploy it keeps running the old UI against the new API.
    # Unchanged files still come back as a cheap 304 thanks to the ETag.
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.exception_handler(DatabaseUnavailable)
@app.exception_handler(psycopg.OperationalError)
def database_down(request, exc):
    # Supabase paused / unreachable: a friendly 503 instead of a 500 stack trace.
    print("database unavailable:", repr(exc))
    return JSONResponse(status_code=503, content={"detail": DB_DOWN_MESSAGE})


@app.get("/", include_in_schema=False)
def home():
    return HTMLResponse(INDEX_HTML)


@app.get("/api/info")
def info():
    return {"app": "vocab-notebook", "status": "running", "version": APP_VERSION, "env": APP_ENV}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    with connect() as conn:
        n = conn.execute("SELECT count(*) AS n FROM words").fetchone()["n"]
    return {"db": "ok", "words": n}
