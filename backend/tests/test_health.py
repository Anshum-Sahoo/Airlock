from pathlib import Path
from fastapi.testclient import TestClient

import pytest
from pydantic import ValidationError

from backend.app.config import Settings


def test_health_matches_contract(client):
    response = client.get("/api/health", headers={"Host": "127.0.0.1"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["prod_db_connected"] is True
    assert body["meta_db_connected"] is True
    assert body["prod_invoice_count"] == 500
    assert body["active_sessions"] == 0
    assert body["contracts_loaded"] is True
    assert body["timestamp"].endswith("Z")


def test_health_endpoint_is_read_only(client):
    before = client.get("/api/health", headers={"Host": "127.0.0.1"}).json()
    after = client.get("/api/health", headers={"Host": "127.0.0.1"}).json()
    assert before["prod_invoice_count"] == after["prod_invoice_count"]


@pytest.mark.parametrize(
    "origins",
    [
        "*",
        "https://example.com/path",
        "https://example.com?",
        "https://example.com#",
        "ftp://example.com",
        "https://example.com:bad",
        "http://example.com:",
        "http://localhost:3000,",
        "",
    ],
)
def test_invalid_cors_origins_are_rejected(origins):
    with pytest.raises(ValidationError):
        Settings(cors_origins=origins)


def test_valid_cors_origins_are_normalized():
    settings = Settings(cors_origins=" https://Example.com/ , http://localhost:3000, http://localhost:0 ")
    assert settings.allowed_origins == {
        "https://example.com",
        "http://localhost:3000",
        "http://localhost:0",
    }


def test_cors_options_preflight_allows_configured_origin(client):
    response = client.options(
        "/api/health",
        headers={
            "Host": "127.0.0.1",
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_startup_fails_when_contract_validation_fails(project_env, monkeypatch):
    import importlib
    import shutil

    from backend.app.config import get_settings

    contracts = project_env / "invalid-contracts"
    shutil.copytree(Path(__file__).resolve().parents[2] / "contracts", contracts)
    (contracts / "api.schema.json").write_text("{ invalid json", encoding="utf-8")
    monkeypatch.setenv("AIRLOCK_CONTRACTS_DIR", str(contracts))
    get_settings.cache_clear()
    import backend.app.main as main_module

    main_module = importlib.reload(main_module)
    try:
        with pytest.raises(RuntimeError, match="Contract validation failed"):
            with TestClient(main_module.app):
                pass
    finally:
        get_settings.cache_clear()
