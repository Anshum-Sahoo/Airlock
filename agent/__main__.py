"""Run the Airlock demo with Nemotron or the deterministic runner."""

import argparse
import json
import os
import sys

import httpx

from .client import API, TOOLS, AgentError, Airlock, ApiError, validate
from .model_demo import WEBHOOK, model_sessions
from .nemotron import review

AGENT_NAME = "airlock-python-agent"
ISOLATED_VARS = ("AIRLOCK_PROD_DB_PATH", "AIRLOCK_META_DB_PATH",
                 "AIRLOCK_SPECULATIVE_DIR", "AIRLOCK_REVIEWER_TOKEN")


def report(manifest):
    return {
        field: manifest[field]
        for field in ("session_id", "execution_status", "gate_decision",
                      "human_review_status", "mutation_counts", "risk_summary")
    }


def delete_demo(api):
    session = api.create(AGENT_NAME, "Stage deletion of overdue demo invoices")
    session_id = session["session_id"]
    if session["baseline_record_count"] != 500:
        raise AgentError("The deletion demo requires the 500-invoice seed dataset.")
    result = api.execute(session_id, "bulk_delete_invoices", {"status": "OVERDUE"})
    manifest = api.complete(session_id, "Staged deletion of overdue invoices.")
    if (result["result"]["deleted_count"], manifest["mutation_counts"]["deleted"],
        manifest["gate_decision"]) != (420, 420, "REQUIRE_APPROVAL"):
        raise AgentError(f"Unexpected deletion demo outcome for session {session_id}.")
    return report(manifest)


def webhook_demo(api):
    session_id = api.create(AGENT_NAME, "Demonstrate webhook secret policy")["session_id"]
    try:
        api.execute(session_id, "stage_webhook", WEBHOOK)
    except ApiError as exc:
        if exc.code != "POLICY_BLOCK":
            raise
        validate(exc.details, {"$ref": API + "ToolPolicyBlockDetails"}, "Webhook policy decision")
        policy_ids = [item["policy_id"] for item in exc.details["policy_violations"]]
        if ("POL-003" not in policy_ids or exc.details["tool_name"] != "stage_webhook"
                or exc.details["session_gate_decision"] != "BLOCK"):
            raise AgentError("The webhook demo did not receive the expected secret-policy block.") from None
    else:
        raise AgentError(f"Airlock unexpectedly allowed the demo webhook in session {session_id}.")
    manifest = api.complete(session_id, "The webhook secret policy blocked the request.")
    if manifest["gate_decision"] != "BLOCK":
        raise AgentError(f"Airlock returned an unexpected gate for session {session_id}.")
    return {**report(manifest), "tool_error": "POLICY_BLOCK", "policy_ids": policy_ids}


def nemotron_lookup(api, prompt, env):
    key = env.get("NVIDIA_API_KEY")
    if not key:
        raise AgentError("Set NVIDIA_API_KEY to use the Nemotron lookup.")
    base_url = env.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    url = httpx.URL(base_url)
    if url.scheme != "https" or not url.host or url.userinfo or url.query or url.fragment:
        raise AgentError("NVIDIA_BASE_URL must be an HTTPS base URL.")
    model = env.get("NVIDIA_MODEL", "nvidia/llama-3.1-nemotron-70b-instruct")
    functions = [
        {"type": "function", "function": {key: tool[key] for key in ("name", "description", "parameters")}}
        for tool in TOOLS.values() if tool["read_only"]
    ]
    try:
        with httpx.Client(base_url=url, timeout=30, trust_env=False) as model_client:
            response = model_client.post("/chat/completions", headers={"Authorization": f"Bearer {key}"}, json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Choose exactly one read-only invoice tool."},
                    {"role": "user", "content": prompt},
                ],
                "tools": functions,
                "tool_choice": "required",
            })
            response.raise_for_status()
            calls = response.json()["choices"][0]["message"]["tool_calls"]
            if len(calls) != 1 or calls[0]["type"] != "function":
                raise ValueError
            call = calls[0]["function"]
            name, arguments = call["name"], json.loads(call["arguments"])
            if name not in TOOLS or not TOOLS[name]["read_only"]:
                raise ValueError
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        raise AgentError("Nemotron did not return a usable read-only tool call.") from None

    validate(arguments, TOOLS[name]["parameters"], "Nemotron tool arguments")
    session_id = api.create(AGENT_NAME, "Read-only invoice lookup")["session_id"]
    result = api.execute(session_id, name, arguments)
    manifest = api.complete(session_id, "Completed read-only invoice lookup.")
    return {**report(manifest), "tool_name": name, "result": result["result"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("delete-demo")
    commands.add_parser("webhook-demo")
    custom = commands.add_parser("new-session", help="Inspect an invoice and stage deletion if overdue.")
    custom.add_argument("name")
    custom.add_argument("invoice_id")
    commands.add_parser("nemotron-review", help="Ask Nemotron to select an overdue invoice and stage a follow-up note.")
    demo = commands.add_parser("demo", help="Run both scenarios in separate sessions.")
    demo.add_argument("--mode", choices=("auto", "nemotron", "deterministic"), default="auto",
                      help="Auto uses Nemotron when NVIDIA_API_KEY is set.")
    lookup = commands.add_parser("nemotron-lookup")
    lookup.add_argument("prompt")
    args = parser.parse_args(argv)
    try:
        if any(name in os.environ for name in ISOLATED_VARS):
            raise AgentError("Start the agent with only its own Airlock configuration.")
        token = os.environ.get("AIRLOCK_AGENT_TOKEN")
        base_url = os.environ.get("AIRLOCK_API_BASE_URL")
        if not token or not base_url:
            raise AgentError("Set AIRLOCK_AGENT_TOKEN and AIRLOCK_API_BASE_URL.")
        url = httpx.URL(base_url)
        if (url.scheme not in ("http", "https") or not url.host or url.userinfo
                or url.query or url.fragment or url.path not in ("", "/")):
            raise AgentError("AIRLOCK_API_BASE_URL must be an HTTP(S) origin.")
        with httpx.Client(base_url=url, timeout=30, trust_env=False) as client:
            api = Airlock(client, token)
            if args.command == "new-session":
                for manifest in model_sessions(api, os.environ, (args.name, args.invoice_id)):
                    print(json.dumps({**report(manifest), "agent_summary": manifest["agent_summary"]}, indent=2))
                return 0
            if args.command == "demo" and (args.mode == "nemotron" or (
                    args.mode == "auto" and os.environ.get("NVIDIA_API_KEY"))):
                for manifest in model_sessions(api, os.environ):
                    result = {**report(manifest), "agent_summary": manifest["agent_summary"],
                              "policy_ids": [v["policy_id"] for v in manifest["policy_violations"]]}
                    if manifest["gate_decision"] == "BLOCK":
                        result["tool_error"] = "POLICY_BLOCK"
                    print(json.dumps(result, indent=2), flush=True)
                return 0
            if args.command == "nemotron-review":
                print(json.dumps(report(review(api, os.environ)), indent=2))
            if args.command in ("demo", "delete-demo"):
                print(json.dumps(delete_demo(api), indent=2))
            if args.command in ("demo", "webhook-demo"):
                print(json.dumps(webhook_demo(api), indent=2))
            if args.command == "nemotron-lookup":
                print(json.dumps(nemotron_lookup(api, args.prompt, os.environ), indent=2))
    except (AgentError, httpx.InvalidURL) as exc:
        print(str(exc) if isinstance(exc, AgentError) else "Invalid service URL.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
