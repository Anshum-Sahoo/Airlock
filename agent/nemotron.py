"""Ask Nemotron to triage overdue invoices and stage its recommendation."""

import json

import httpx

from .client import AgentError, TOOLS, validate


def choose_invoice(candidates, client, model):
    instructions = (
        "You are an accounts-receivable agent. Choose one overdue invoice for follow-up. "
        "Consider its due date and balance. Compare amounts only within the same currency. "
        "Write a concise, factual follow-up note using the supplied values. "
        "Return only a JSON object with invoice_id and notes. Do not claim a payment was received."
    )
    try:
        response = client.post("chat/completions", json={
            "model": model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": json.dumps(candidates)},
            ],
            "max_tokens": 1024,
        })
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        proposal = json.loads(content.strip().removeprefix("```json").removesuffix("```").strip())
    except httpx.HTTPStatusError as exc:
        raise AgentError(f"NVIDIA returned HTTP {exc.response.status_code}. Check the key and model ID.") from None
    except (httpx.RequestError, ValueError, KeyError, IndexError, AttributeError, TypeError):
        raise AgentError("NVIDIA did not return a usable invoice recommendation.") from None
    if not isinstance(proposal, dict) or set(proposal) != {"invoice_id", "notes"}:
        raise AgentError("Nemotron returned fields outside the review task.")
    validate(proposal, TOOLS["update_invoice"]["parameters"], "Proposed note")
    if proposal["invoice_id"] not in [row["invoice_id"] for row in candidates] or not (
        isinstance(proposal["notes"], str) and proposal["notes"].strip()
    ):
        raise AgentError("Nemotron must choose a listed invoice and supply a follow-up note.")
    return proposal


def review(api, env):
    key = env.get("NVIDIA_API_KEY")
    if not key:
        raise AgentError("Set NVIDIA_API_KEY in the agent shell.")
    url = httpx.URL(env.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"))
    if url.scheme != "https" or not url.host or url.userinfo or url.query or url.fragment:
        raise AgentError("NVIDIA_BASE_URL must be an HTTPS base URL.")
    model = env.get("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")
    sid = api.create("Nemotron invoice reviewer", "Prioritize an overdue invoice and stage a follow-up note.")["session_id"]
    rows = api.execute(sid, "list_invoices", {"status": "OVERDUE", "limit": 5})["result"]["invoices"]
    if not rows:
        return api.complete(sid, "No overdue invoices were available for review.")
    candidates = [
        {"invoice_id": row["id"], "amount_cents": row["amount_cents"],
         "currency": row["currency"], "due_date": row["due_date"]}
        for row in rows
    ]
    try:
        with httpx.Client(base_url=url, headers={"Authorization": f"Bearer {key}"},
                          timeout=90, trust_env=False) as client:
            proposal = choose_invoice(candidates, client, model)
    except AgentError:
        api.complete(sid, "Model recommendation unavailable. No invoice update was submitted.")
        raise
    api.execute(sid, "update_invoice", proposal)
    return api.complete(sid, f"{model} selected {proposal['invoice_id']}. Proposed note: {proposal['notes']}"[:1000])
