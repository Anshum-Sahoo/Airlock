"""Local dashboard launcher for the isolated Nemotron agent."""
import json
import re
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from .__main__ import ISOLATED_VARS
from .client import AgentError, Airlock
from .model_demo import named_session, run_session

ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000"}
busy = threading.Lock()
state_lock = threading.Lock()
state = {"session_id": None, "status": "Ready", "results": []}


class Results(list):
    def append(self, item):
        super().append(item)
        with state_lock:
            state["results"] = list(self)


def gateway():
    return httpx.Client(base_url=os.environ["AIRLOCK_API_BASE_URL"], timeout=30, trust_env=False)


def execute(session, scenario, invoice_id, title):
    try:
        key = os.environ["NVIDIA_API_KEY"]
        token = os.environ["AIRLOCK_AGENT_TOKEN"]
        with gateway() as http, httpx.Client(
            base_url=os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            headers={"Authorization": f"Bearer {key}"}, timeout=90, trust_env=False,
        ) as model_http:
            if scenario in ("inspect", "single_delete"):
                manifest = named_session(Airlock(http, token), model_http, os.environ["NVIDIA_MODEL"],
                                         title, invoice_id, inspect_only=scenario == "inspect",
                                         session=session, receipts=Results())
            else:
                manifest = run_session(Airlock(http, token), model_http, os.environ["NVIDIA_MODEL"],
                                   scenario, [key, token], session, Results())
        status = "Completed · " + manifest["gate_decision"]
    except Exception:
        status = "Stopped. Inspect the session history and agent summary."
    finally:
        with state_lock:
            state["status"] = status
        busy.release()


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, data=None):
        self.send_response(code)
        origin = self.headers.get("Origin")
        if origin in ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if data is not None:
            self.wfile.write(json.dumps(data).encode())

    def allowed(self):
        return (self.path == "/session" and self.headers.get("Host") == "127.0.0.1:8765"
                and self.headers.get("Origin") in ORIGINS)

    def do_OPTIONS(self):
        self.reply(204 if self.allowed() else 403)

    def do_GET(self):
        if not self.allowed():
            return self.reply(403)
        with state_lock:
            snapshot = dict(state)
        self.reply(200, snapshot)

    def do_POST(self):
        if not self.allowed() or self.headers.get_content_type() != "application/json":
            return self.reply(403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 1 <= size <= 512:
                raise ValueError
            data = json.loads(self.rfile.read(size))
            scenario = data["scenario"]
            title = data["name"].strip()
            invoice_id = data.get("invoice_id")
            if scenario in ("inspect", "single_delete") and not re.fullmatch(r"INV-[0-9]{4}", invoice_id or ""):
                raise ValueError
            if (scenario not in ("deletion", "webhook", "inspect", "single_delete") or not 1 <= len(title) <= 70
                    or any(os.environ[k] in title for k in ("NVIDIA_API_KEY", "AIRLOCK_AGENT_TOKEN"))):
                raise ValueError
        except (ValueError, TypeError, AttributeError, KeyError):
            return self.reply(400)
        if not busy.acquire(blocking=False):
            return self.reply(409)
        try:
            with gateway() as http:
                api = Airlock(http, os.environ["AIRLOCK_AGENT_TOKEN"])
                task = "Inspect and stage overdue invoice deletions" if scenario == "deletion" else "Test the synthetic webhook policy"
                if scenario == "inspect":
                    task = f"Inspect the status and due date of {invoice_id}"
                elif scenario == "single_delete":
                    task = f"Stage deletion of {invoice_id} only if overdue"
                session = api.create("Nemotron: " + title, task)
            sid = session["session_id"]
            with state_lock:
                state.update(session_id=sid, status="Running", results=[])
            threading.Thread(target=execute, args=(session, scenario, invoice_id, title), daemon=True).start()
        except Exception:
            busy.release()
            return self.reply(502)
        self.reply(201, {"session_id": sid})


if __name__ == "__main__":
    if any(name in os.environ for name in ISOLATED_VARS):
        raise SystemExit("Start the worker in the isolated agent environment.")
    if not all(os.environ.get(k) for k in ("AIRLOCK_AGENT_TOKEN", "AIRLOCK_API_BASE_URL", "NVIDIA_API_KEY", "NVIDIA_MODEL")):
        raise SystemExit("Set the agent and NVIDIA configuration first.")
    url = httpx.URL(os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"))
    if url.scheme != "https" or not url.host or url.userinfo or url.query or url.fragment:
        raise SystemExit("Invalid NVIDIA base URL.")
    print("Agent ready. Open the Airlock dashboard and choose New session.", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
