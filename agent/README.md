# Airlock Python agent

Install the agent dependencies from the repository root with `python -m pip install -r agent/requirements.txt`. Start Airlock separately with the documented 500-invoice demo seed. In a separate shell, set `AIRLOCK_API_BASE_URL` (typically `http://127.0.0.1:8000`) and `AIRLOCK_AGENT_TOKEN` to the gateway's agent token. Supply only agent configuration to this process.

- `python -m agent delete-demo` stages deletions for invoices with status `OVERDUE`, then completes the session. With the demo seed, the output reports 420 deletions, 84% affected, and `REQUIRE_APPROVAL`.
- `python -m agent webhook-demo` creates a fresh session, submits a synthetic secret marker through `stage_webhook` using the allowlisted demo hostname, then completes the blocked session. The output reports `POLICY_BLOCK`, `POL-003`, and the final `BLOCK` gate.
- `python -m agent demo` runs both scenarios in separate sessions. It uses Nemotron when `NVIDIA_API_KEY` is present and the deterministic runner otherwise. Use `--mode nemotron` for a presentation that requires the model, or `--mode deterministic` for an offline model fallback. Both modes need a running Airlock backend.
- `python -m agent nemotron-lookup "Find up to five overdue invoices"` optionally uses `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, and `NVIDIA_MODEL` from the agent environment. Nemotron selects one read-only Airlock tool using the supplied prompt and tool definitions. The agent executes the tool and prints the result locally. Keep secrets and sensitive invoice data out of the prompt.

The agent sends one request per operation and stops on API or transport failures. If a request times out after submission, use the dashboard to inspect the session before rerunning the demo. Webhook staging requests go only to Airlock.

Run the mocked HTTP tests with `python -m unittest discover -s agent/tests -v`.

## Present the two Nemotron sessions

1. Start the backend with disposable databases and the synthetic 500-invoice seed. Open the dashboard connected to this backend. In a separate PowerShell at the repository root, activate the Python environment with the agent dependencies.
2. Set the agent's gateway URL and enter the gateway's agent token and NVIDIA key at masked prompts. Use the model ID and HTTPS base URL from your NVIDIA deployment. The runner supports native function calls and a JSON tool-call protocol for chat endpoints that reject the native tool request.

   ```powershell
   $env:AIRLOCK_API_BASE_URL = 'http://127.0.0.1:8000'
   $env:AIRLOCK_AGENT_TOKEN = [Net.NetworkCredential]::new('', (Read-Host 'Airlock agent token' -AsSecureString)).Password
   $env:NVIDIA_API_KEY = [Net.NetworkCredential]::new('', (Read-Host 'NVIDIA API key' -AsSecureString)).Password
   $env:NVIDIA_BASE_URL = 'https://integrate.api.nvidia.com/v1'
   $env:NVIDIA_MODEL = Read-Host 'NVIDIA model ID'
   python -m agent demo --mode nemotron
   ```

3. Open **Nemotron: Overdue invoice deletion** in the dashboard. Follow **Tool activity** as the agent samples overdue invoices, optionally inspects one sampled ID, and stages a bulk deletion. Nemotron receives the matching count, sampled IDs and, for an optional lookup, the status and due date. **Mutations** shows the 420 proposed deletions. **Violations** shows POL-001 and the final gate is `REQUIRE_APPROVAL`. A reviewer can commit or roll back this session.
4. Open **Nemotron: Secret webhook check**. Its single staging attempt uses a synthetic marker and an allowlisted hostname. Airlock records a redacted call with `POLICY_BLOCK`, zero invoice mutations and a `BLOCK` gate under POL-003. The blocked session can only be rolled back. The agent never dispatches a webhook.

Each session's **Agent Summary** contains a short model explanation and the observed results for each call. Airlock supplies the authoritative gate, row-level changes and review status. A model failure during planning ends the session with its work so far. If only the final explanation fails, the summary displays the Airlock results. A gateway failure with an uncertain outcome stops the run and leaves the session available for inspection. The runner never replays a mutation or starts the deterministic demo on a model error.

Keep the NVIDIA key and agent token in the agent shell. Close that shell after the demo. Only the reviewer enters the separate reviewer token in the dashboard.

For a model-generated review, run `python -m agent nemotron-review` with
`NVIDIA_API_KEY` and the exact `NVIDIA_MODEL` ID from your NVIDIA endpoint.
The agent reads up to five overdue invoices and sends NVIDIA their IDs,
amounts, currencies, and due dates. It stages the selected note through Airlock.
Open **Nemotron invoice reviewer** in the dashboard to inspect the tool activity,
invoice diff, policy decision, and model recommendation.

## Start sessions from the dashboard

Start the backend with its synthetic seed and the frontend at http://127.0.0.1:3000.
In the agent-only shell configured above, run `python -m agent.worker` and leave it running.
Select **New session**, enter a name, choose a task and select **Run agent**.
The dashboard shows tool results during execution. Single-invoice tasks accept an ID such as
INV-0042. The worker listens on 127.0.0.1:8765. Keep the reviewer token in the reviewer dashboard.
