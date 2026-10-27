import os
import pytest
from fastapi.testclient import TestClient
from app import storage as s


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(s, "DB", tmp_path / "test.sqlite3")
    monkeypatch.setenv("ANALYSIS_MODE", "offline_demo")
    s.initialize()
    from app.main import app
    with TestClient(app) as client:
        yield client
