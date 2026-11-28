from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

from .config import Settings


INVOICE_SCHEMA_FILE = "invoice.schema.json"
REQUIRED_CONTRACT_FILES = (
    "api.schema.json",
    "error.schema.json",
    "invoice.schema.json",
    "manifest.schema.json",
    "policies.json",
    "tools.json",
)


@contextmanager
def _connect(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _connect_readonly(path: Path):
    uri = path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def load_contracts(contracts_dir: Path) -> bool:
    """Fail closed if required JSON contract files are missing or malformed."""
    for filename in REQUIRED_CONTRACT_FILES:
        path = contracts_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Required contract file missing: {path}")
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
    return True


def initialize_production_db(settings: Settings) -> None:
    invoice_schema = json.loads((settings.airlock_contracts_dir / INVOICE_SCHEMA_FILE).read_text(encoding="utf-8"))
    ddl = invoice_schema.get("x-sqlite", {}).get("ddl")
    if not isinstance(ddl, list) or not ddl:
        raise ValueError("invoice.schema.json is missing x-sqlite.ddl")
    with _connect(settings.airlock_prod_db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        invoice_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'invoices'"
        ).fetchone()
        if invoice_table is None:
            conn.executescript("\n".join(ddl))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS airlock_commit_ledger (
              ledger_id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL UNIQUE,
              committed_at TEXT NOT NULL,
              reviewer TEXT NOT NULL,
              reason TEXT,
              gate_decision TEXT NOT NULL CHECK (gate_decision IN ('ALLOW','REQUIRE_APPROVAL')),
              baseline_record_count INTEGER NOT NULL,
              inserted_count INTEGER NOT NULL,
              updated_count INTEGER NOT NULL,
              deleted_count INTEGER NOT NULL,
              mutation_digest TEXT NOT NULL CHECK (length(mutation_digest) = 64)
            );
        """)


def initialize_metadata_db(settings: Settings) -> None:
    with _connect(settings.airlock_meta_db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
              session_id TEXT PRIMARY KEY,
              agent_name TEXT NOT NULL,
              execution_status TEXT NOT NULL CHECK (execution_status IN ('ACTIVE','COMPLETED','COMMITTED','ROLLED_BACK')),
              gate_decision TEXT NOT NULL CHECK (gate_decision IN ('PENDING','ALLOW','REQUIRE_APPROVAL','BLOCK')),
              human_review_status TEXT NOT NULL CHECK (human_review_status IN ('PENDING','APPROVED','REJECTED')),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              manifest_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions (created_at DESC);
        """)


def initialize_databases(settings: Settings) -> None:
    settings.airlock_speculative_dir.mkdir(parents=True, exist_ok=True)
    load_contracts(settings.airlock_contracts_dir)
    initialize_production_db(settings)
    initialize_metadata_db(settings)
    seed_production(settings)


def seed_rows(settings: Settings) -> list[dict]:
    seed = json.loads((settings.airlock_contracts_dir / INVOICE_SCHEMA_FILE).read_text(encoding="utf-8"))["x-seed"]
    fixed = {row["id"]: row for row in seed["fixed_records"]}
    statuses = {i: "OVERDUE" if i <= 420 else "PAID" if i <= 460 else "PENDING" if i <= 485 else "CANCELLED" for i in range(1, 501)}
    rows = []
    for n in range(1, seed["total"] + 1):
        invoice_id = f"INV-{n:04d}"
        day = (n % 28) + 1
        created = f"2026-09-{day:02d}T10:00:00Z"
        rows.append(fixed.get(invoice_id, {
            "id": invoice_id, "customer_name": f"Customer {n:04d}",
            "customer_email": f"ap{n:04d}@customer{n:04d}.example.com",
            "amount_cents": 10000 + n * 137, "currency": "USD", "status": statuses[n],
            "due_date": f"2026-{10 if statuses[n] == 'OVERDUE' else 12}-{day:02d}",
            "notes": None, "version": 1, "created_at": created, "updated_at": created,
        }))
    return rows


def seed_production(settings: Settings) -> None:
    columns = json.loads((settings.airlock_contracts_dir / INVOICE_SCHEMA_FILE).read_text(encoding="utf-8"))["x-sqlite"]["column_order"]
    with _connect(settings.airlock_prod_db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        if count:
            return
        conn.executemany(
            f"INSERT INTO invoices ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            [[row[key] for key in columns] for row in seed_rows(settings)],
        )


def database_health(settings: Settings) -> tuple[bool, bool, int, int]:
    """Return production/meta connectivity and invoice/active-session counts."""
    with _connect_readonly(settings.airlock_prod_db_path) as conn:
        invoice_count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    with _connect(settings.airlock_meta_db_path) as conn:
        active_sessions = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE execution_status = 'ACTIVE'"
        ).fetchone()[0]
    return True, True, int(invoice_count), int(active_sessions)
