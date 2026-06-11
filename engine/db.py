"""
PostgreSQL connection helper — SQLAlchemy engine for reads, psycopg2 for writes.
"""

import os
from contextlib import contextmanager
from functools import lru_cache

import pandas as pd
import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text


@lru_cache(maxsize=1)
def _engine():
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise ValueError("DATABASE_URL not set")
    return create_engine(url)


def _url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        raise ValueError("DATABASE_URL not set")
    return url


@contextmanager
def get_conn():
    """Yield a committed-or-rolled-back psycopg2 connection."""
    conn = psycopg2.connect(_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_df(sql: str, params=None) -> pd.DataFrame:
    """Run a SELECT and return a DataFrame (uses SQLAlchemy engine)."""
    with _engine().connect() as conn:
        return pd.read_sql(text(sql) if params is None else sql, conn, params=params)


def execute(sql: str, params=None) -> None:
    """Run a single DML statement."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def execute_batch(sql: str, rows: list) -> None:
    """Run a DML statement for each row in rows (fast bulk insert)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, rows)
