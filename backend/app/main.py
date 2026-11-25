from __future__ import annotations

from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import get_settings
from .database import database_health, initialize_databases, load_contracts


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    validator = Path(__file__).resolve().parents[2] / "scripts" / "validate_contracts.py"
    result = subprocess.run(
        [sys.executable, str(validator), "--contracts-dir", str(settings.airlock_contracts_dir.resolve())],
        cwd=validator.parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            "Contract validation failed; application startup aborted.\n"
            f"{result.stdout}{result.stderr}"
        )
    initialize_databases(settings)
    yield


app = FastAPI(
    title="Airlock API",
    description="Security gateway for autonomous AI agents — backend foundation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "[::1]"],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Origin"],
)


@app.get("/api/health", name="health")
def health() -> dict:
    prod_connected, meta_connected, invoice_count, active_sessions = database_health(settings)
    contracts_loaded = load_contracts(settings.airlock_contracts_dir)
    return {
        "status": "ok",
        "prod_db_connected": prod_connected,
        "meta_db_connected": meta_connected,
        "prod_invoice_count": invoice_count,
        "active_sessions": active_sessions,
        "contracts_loaded": contracts_loaded,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
