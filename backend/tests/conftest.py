import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def project_env(tmp_path, monkeypatch):
    contracts = Path(__file__).resolve().parents[2] / "contracts"
    monkeypatch.setenv("AIRLOCK_HOST", "127.0.0.1")
    monkeypatch.setenv("AIRLOCK_PORT", "8000")
    monkeypatch.setenv("AIRLOCK_DEMO_MODE", "true")
    monkeypatch.setenv("AIRLOCK_PROD_DB_PATH", str(tmp_path / "prod.db"))
    monkeypatch.setenv("AIRLOCK_META_DB_PATH", str(tmp_path / "meta.db"))
    monkeypatch.setenv("AIRLOCK_SPECULATIVE_DIR", str(tmp_path / "speculative"))
    monkeypatch.setenv("AIRLOCK_CONTRACTS_DIR", str(contracts))
    monkeypatch.setenv("AIRLOCK_AGENT_TOKEN", "test-agent-token")
    monkeypatch.setenv("AIRLOCK_REVIEWER_TOKEN", "test-reviewer-token")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return tmp_path


@pytest.fixture()
def client(project_env):
    # Import after environment variables are set because settings are cached.
    import importlib
    from backend.app.config import get_settings
    get_settings.cache_clear()
    import backend.app.main as main_module
    main_module = importlib.reload(main_module)
    with TestClient(main_module.app) as test_client:
        yield test_client
    get_settings.cache_clear()
