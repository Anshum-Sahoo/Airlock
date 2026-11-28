"""Run a 15-minute synthetic payment-reconciliation demo on local Airlock."""

import os
import random
import sys
import time
from uuid import uuid4

import httpx

from .__main__ import ISOLATED_VARS
from .client import AgentError, Airlock


def reconcile(api):
    receipt = uuid4().hex[:8].upper()
    requested = random.randint(1, 3)
    session = api.create("Demo payment reconciliation", f"Reconcile synthetic payment batch {receipt}")
    sid = session["session_id"]
    print(f"Started session {sid}", flush=True)
    result = api.execute(sid, "list_invoices", {"status": "OVERDUE", "limit": 500})
    invoices = result["result"]["invoices"]
    selected = random.sample(invoices, min(requested, len(invoices)))
    for invoice in selected:
        api.execute(sid, "update_invoice", {
            "invoice_id": invoice["id"],
            "status": "PAID",
            "notes": f"Synthetic payment matched in demo batch {receipt}.",
        })
    manifest = api.complete(sid, f"Matched {len(selected)} demo invoices in batch {receipt}.")
    print(f"{sid}  {manifest['gate_decision']}  updated={manifest['mutation_counts']['updated']}", flush=True)


def main():
    if any(name in os.environ for name in ISOLATED_VARS):
        raise AgentError("Use the isolated agent environment.")
    token = os.environ.get("AIRLOCK_AGENT_TOKEN")
    if not token:
        raise AgentError("Set AIRLOCK_AGENT_TOKEN for the local synthetic gateway.")
    url = os.environ.get("AIRLOCK_API_BASE_URL", "http://127.0.0.1:8000")
    if httpx.URL(url).host not in {"localhost", "127.0.0.1", "::1"}:
        raise AgentError("The judges' demo requires a loopback gateway.")
    with httpx.Client(base_url=url, timeout=30, trust_env=False) as client:
        api = Airlock(client, token)
        for index in range(15):
            if index:
                time.sleep(60)
            reconcile(api)


if __name__ == "__main__":
    try:
        main()
    except AgentError as exc:
        sys.exit(str(exc))
