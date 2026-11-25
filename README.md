# Airlock — Starter Workspace

**The Security Gateway for Autonomous AI Agents**  
Backend foundation: FastAPI + SQLite. Frozen contract package: **v1.2.1**.

This is a starter workspace, not a completed Airlock implementation. It currently provides configuration, contract loading, production/metadata SQLite initialization, `GET /api/health`, and initial tests. Agent execution, reviewer workflows, policy evaluation, speculative session creation, commit/recovery orchestration, frontend, and Nemotron integration are intentionally not implemented yet.

## Project structure

```text
Airlock/
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   └── tests/
├── contracts/                 # Frozen v1.2.1 source of truth
│   ├── API_CONTRACT.md
│   ├── *.schema.json
│   ├── policies.json
│   ├── tools.json
│   └── examples/
├── data/
│   └── speculative_dbs/
├── scripts/validate_contracts.py
├── .env.example
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.11 or newer
- Windows PowerShell, macOS Terminal, or Linux shell

## Run locally (Windows PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --reload
```

If PowerShell blocks activation, run this once in the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run locally (macOS / Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1 --reload
```

The backend intentionally uses one worker. The contract specifies a single-host local demo and in-process coordination. Do not bind to `0.0.0.0`.

## Verify

Open `http://127.0.0.1:8000/api/health` or run:

```bash
pytest -q
python scripts/validate_contracts.py
```

The API also runs the contract validator against `AIRLOCK_CONTRACTS_DIR` before database initialization on every startup. A failing or inconsistent contract package prevents the application from starting.

The health endpoint initializes the production and metadata database files on first startup. The invoice table and durable commit-ledger table are created from the v1.2.1 contract definitions. No demo invoices are seeded yet, so the initial invoice count is `0`.

## Security notes

- `.env` contains local secrets and must never be committed.
- Agent and reviewer tokens must be different.
- NVIDIA credentials belong only in the agent process environment, never in `NEXT_PUBLIC_*` variables.
- The agent process must not receive database paths or reviewer credentials.
- CORS is not authentication. The full server-side Origin validation and role authorization rules in `contracts/API_CONTRACT.md` must be implemented before reviewer endpoints are exposed.
- The current starter exposes only the health endpoint. Do not treat the project as production-ready.

## Contract change policy

`contracts/` is the frozen Airlock Contracts v1.2.1 package. Do not edit contract files ad hoc during implementation. Propose changes as a versioned contract update and review them with the team first.
