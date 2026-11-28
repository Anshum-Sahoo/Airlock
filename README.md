# Airlock — Starter Workspace

**The Security Gateway for Autonomous AI Agents**  
Backend foundation: FastAPI + SQLite. Frozen contract package: **v1.2.1**.

The backend MVP provides the contract-driven SQLite store, isolated agent sessions, allowlisted invoice tools, deterministic policy checks, and reviewer commit/rollback workflows. The Next.js dashboard and Nemotron agent runner are separate workstreams and are not included here.

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

Startup initializes the production and metadata databases, validates the contract package, and seeds the production invoice table from `invoice.schema.json` when it is empty. The demo baseline contains 500 rows: 420 overdue and 80 non-overdue. `/api/demo/reset` restores that baseline and clears sessions.

## Security notes

- `.env` contains local secrets and must never be committed.
- Agent and reviewer tokens must be different.
- NVIDIA credentials belong only in the agent process environment, never in `NEXT_PUBLIC_*` variables.
- The agent process must not receive database paths or reviewer credentials.
- CORS is not authentication. Commit, rollback, and reset enforce the configured Origin server-side and require the reviewer bearer token. Agent tools require the separate agent token.
- This is a single-host local demo MVP; follow the limitations in `contracts/API_CONTRACT.md` before using it on shared or production infrastructure.

## Contract change policy

`contracts/` is the frozen Airlock Contracts v1.2.1 package. Do not edit contract files ad hoc during implementation. Propose changes as a versioned contract update and review them with the team first.
