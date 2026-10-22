# Dockerfile — image for the Vocabulary Notebook web app (API + UI).
#
# Same image locally (compose.yaml) and on Render. Only DATABASE_URL changes.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Dependencies first so code changes do not reinstall them.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations

# Do not run as root inside the container.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# Render injects PORT; locally it defaults to 8000.
ENV PORT=8000
EXPOSE 8000

# Apply pending migrations, then serve. --proxy-headers so the app sees HTTPS behind Render.
CMD ["sh", "-c", "python -m app.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
