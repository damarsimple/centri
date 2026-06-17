"""Shared sqlite access + a tiny schema registry.

Each persistence module calls `register_schema(SQL)` at import; `init_all()` then
creates every registered table. Keeps one connection style across the app.
"""
import sqlite3
import threading
from contextlib import contextmanager

from . import config

lock = threading.Lock()
_schemas = []


def register_schema(sql):
    _schemas.append(sql)


@contextmanager
def session():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_all():
    with session() as conn:
        for sql in _schemas:
            conn.executescript(sql)
