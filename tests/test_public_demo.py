import base64

import pytest

from app.main import validate_demo_settings


def login_header(username, password):
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def test_open_local_mode(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/health").status_code == 200


def test_public_demo_requires_login_and_protects_api(client, monkeypatch, tmp_path):
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    monkeypatch.setenv("DEMO_USERNAME", "judge")
    monkeypatch.setenv("DEMO_PASSWORD", "example-password-not-for-production")
    monkeypatch.setenv("SAMEPAGE_DB", str(tmp_path / "test.sqlite3"))
    assert client.get("/healthz").status_code == 200
    assert client.get("/").status_code == 401
    assert client.get("/api/health").status_code == 401
    assert client.post("/api/cases", json={}).status_code == 401
    assert client.get("/", headers=login_header("judge", "bad")).status_code == 401
    assert client.get("/", headers=login_header("jüdge", "example-password-not-for-production")).status_code == 401
    assert client.get("/", headers=login_header("judge", "example-password-not-for-production")).status_code == 200
    check = client.get("/api/health", headers=login_header("judge", "example-password-not-for-production"))
    assert check.status_code == 200
    assert check.json()["restricted_demo"] is True
    assert check.headers["cache-control"] == "no-store"
    assert check.headers["referrer-policy"] == "no-referrer"


def test_bad_config_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    monkeypatch.setenv("DEMO_PASSWORD", "short")
    monkeypatch.setenv("SAMEPAGE_DB", str(tmp_path / "test.sqlite3"))
    with pytest.raises(RuntimeError, match="16 characters"):
        validate_demo_settings()


def test_public_demo_requires_persistent_path(monkeypatch):
    monkeypatch.setenv("PUBLIC_DEMO", "1")
    monkeypatch.setenv("DEMO_PASSWORD", "example-password-not-for-production")
    monkeypatch.delenv("SAMEPAGE_DB", raising=False)
    with pytest.raises(RuntimeError, match="SAMEPAGE_DB"):
        validate_demo_settings()
