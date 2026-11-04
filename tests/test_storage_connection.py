"""SQLite connections are released after each transaction."""
import sqlite3

import pytest

from app import storage


def test_connection_closes_after_success(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB", tmp_path / "proof.sqlite3")
    with storage.connection() as db:
        db.execute("CREATE TABLE example (id INTEGER)")
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute("SELECT 1")


def test_connection_closes_after_error(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB", tmp_path / "proof.sqlite3")
    with pytest.raises(RuntimeError):
        with storage.connection() as db:
            db.execute("CREATE TABLE example (id INTEGER)")
            raise RuntimeError("abort")
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute("SELECT 1")
