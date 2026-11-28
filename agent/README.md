# Airlock Python agent

Install the agent dependencies from the repository root with `python -m pip install -r agent/requirements.txt`. Start Airlock separately with the documented 500-invoice demo seed. In a separate shell, set `AIRLOCK_API_BASE_URL` (typically `http://127.0.0.1:8000`) and `AIRLOCK_AGENT_TOKEN` to the gateway's agent token. Supply only agent configuration to this process.

- `python -m agent delete-demo` stages deletions for invoices with status `OVERDUE`, then completes the session. With the demo seed, the output reports 420 deletions, 84% affected, and `REQUIRE_APPROVAL`.
- `python -m agent webhook-demo` creates a fresh session, submits a synthetic secret marker through `stage_webhook` using the allowlisted demo hostname, then completes the blocked session. The output reports `POLICY_BLOCK`, `POL-003`, and the final `BLOCK` gate.
- `python -m agent demo` runs both scenarios in separate sessions. The demos work without NVIDIA credentials.
- `python -m agent nemotron-lookup "Find up to five overdue invoices"` optionally uses `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, and `NVIDIA_MODEL` from the agent environment. Nemotron selects one read-only Airlock tool using the supplied prompt and tool definitions. The agent executes the tool and prints the result locally. Keep secrets and sensitive invoice data out of the prompt.

The agent sends one request per operation and stops on API or transport failures. If a request times out after submission, use the dashboard to inspect the session before rerunning the demo. Webhook staging requests go only to Airlock.

Run the mocked HTTP tests with `python -m unittest discover -s agent/tests -v`.
