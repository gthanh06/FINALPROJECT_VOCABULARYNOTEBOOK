# app/db.py — the only place that knows how to reach PostgreSQL.
#
# DATABASE_URL is the single switch between environments:
#   local / Compose : postgresql://vocab:vocab@db:5432/vocab
#   production      : the Supabase connection string, set as a Render env var
# It is never written in the code or committed to Git.
import os
import time

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]  # crash at start if it is missing

CONNECT_ATTEMPTS = 3
CONNECT_TIMEOUT = 5  # seconds per attempt
RETRY_DELAY = 1.0  # seconds, doubled after each failed attempt


class DatabaseUnavailable(Exception):
    """The database did not answer after every retry (e.g. Supabase project paused)."""


def connect(url: str = DATABASE_URL) -> psycopg.Connection:
    # A free Supabase project that is waking up can refuse the first connections,
    # so we retry a few times before giving up with a friendly error.
    delay = RETRY_DELAY
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            return psycopg.connect(
                url,
                connect_timeout=CONNECT_TIMEOUT,
                row_factory=dict_row,
                # Supabase's pooler (port 6543) does not support prepared statements.
                prepare_threshold=None,
            )
        except psycopg.OperationalError as err:
            # The detail goes to the logs, not to the browser (it can contain the host).
            print(f"db connect attempt {attempt}/{CONNECT_ATTEMPTS} failed: {err}")
            if attempt == CONNECT_ATTEMPTS:
                raise DatabaseUnavailable from err
            time.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")
