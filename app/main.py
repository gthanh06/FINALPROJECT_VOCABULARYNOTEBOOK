# app/main.py — Vocabulary Notebook (EN–VN) API.
#
# /            web UI (app/static/index.html: list, add, edit, review pages)
# /health      fast platform health check, touches nothing (Render points here)
# /health/db   proves the database connection
# /api/info    app name, version and environment
# /api/...     CRUD for words and review logs (app/routes.py)
import os
from pathlib import Path

import psycopg
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import DatabaseUnavailable, connect
from app.routes import router

APP_VERSION = "0.1.0"
APP_ENV = os.environ.get("APP_ENV", "development")
STATIC_DIR = Path(__file__).resolve().parent / "static"

DB_DOWN_MESSAGE = "Cơ sở dữ liệu đang khởi động hoặc tạm ngưng, vui lòng thử lại sau ít giây."

app = FastAPI(title="vocab-notebook")
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(DatabaseUnavailable)
@app.exception_handler(psycopg.OperationalError)
def database_down(request, exc):
    # Supabase paused / unreachable: a friendly 503 instead of a 500 stack trace.
    print("database unavailable:", repr(exc))
    return JSONResponse(status_code=503, content={"detail": DB_DOWN_MESSAGE})


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")


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
