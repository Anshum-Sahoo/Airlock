# Airlock team workflow

## Team ownership

| Person | Responsibility | Intended paths |
|---|---|---|
| You / integration lead | FastAPI backend, auth, security, database, policies, session lifecycle, commit/rollback, contracts, final integration | `backend/`, `contracts/`, `scripts/`, shared architecture docs |
| Member 2 | Next.js frontend, dashboard, approval/rejection UI, API client | `frontend/` |
| Member 3 | Nemotron agent runner, tool adapter, agent API client | `agent/` |
| Member 4 | QA, security scenarios, synthetic-data checks, test documentation | `security-tests/`, assigned test/docs files |

The `frontend/`, `agent/`, and `security-tests/` folders are planned and may not exist in the current starter. Create them when the corresponding work is assigned.

## Non-negotiable rules

1. Treat `contracts/` v1.2.1 as the source of truth.
2. Do not change contracts, schemas, policies, or `tools.json` without explicit integration-lead approval.
3. The agent must never connect to or mutate the production database directly.
4. Never replace the production DB with a speculative DB file.
5. Keep reviewer credentials separate from agent credentials. Agent credentials cannot approve or commit.
6. Webhooks are staged only; do not dispatch them.
7. Never commit `.env`, API keys, tokens, credentials, local DBs, `.venv`, or `node_modules`.
8. Never merge directly to `main`; use a pull request.
9. Keep each PR focused on one assigned task and its allowed paths.
10. Ask when the API contract is unclear; do not invent request/response fields.

## Clone the repository

```powershell
git clone https://github.com/YOUR_ORG_OR_USERNAME/Airlock.git
cd Airlock
git switch main
git pull origin main
```

## Backend setup (Python 3.12)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q backend/tests
python scripts/validate_contracts.py
```

Each developer keeps their own local `.env`. Never send secrets through GitHub.

## Daily branch workflow

```powershell
git switch main
git pull origin main
git switch -c feature/short-task-name
```

After editing only assigned files:

```powershell
git status
git diff --check
git diff
git add path/to/changed-files
git commit -m "feat: describe the change"
git push -u origin feature/short-task-name
```

Open a PR to `main`, link the task issue, and complete the PR template. Inspect `git status` before staging; avoid blindly using `git add .`.

## Workstream boundaries

### Frontend member
- Work in `frontend/` only unless the integration lead approves another path.
- Use `contracts/API_CONTRACT.md` as the API reference.
- Do not implement backend endpoints, database access, policy logic, or authentication rules.
- Do not invent API fields. Ask the integration lead if a UI requirement is not represented in the contract.
- Mock data is acceptable for isolated UI development only; label it and remove/isolate it before final integration.

### Agent member
- Work in `agent/` only unless explicitly approved.
- Use `contracts/tools.json` and the API contract.
- Call Airlock APIs; never connect directly to the production SQLite database.
- Do not implement reviewer approval or production commit authority.

### QA member
- Work in `security-tests/` and specifically assigned test/documentation paths.
- Test allowed and denied cases: unauthorized reviewer actions, unknown tools, policy thresholds, secret redaction, rollback, and production-data integrity.
- Use synthetic data only.

### Integration lead
- Own backend, security, contracts, database lifecycle, and final integration.
- Review cross-workstream changes and resolve API/contract questions.
- Verify the demo is reproducible and production data remains safe.

## Pull request review

1. Contributor opens a PR and links the assigned issue.
2. Contributor lists changed paths and exact test commands/results.
3. GitHub Actions runs relevant checks.
4. CODEOWNERS identifies reviewers, subject to repository ruleset settings.
5. You review scope, contract compatibility, security impact, and test evidence. Codex can assist, but does not replace human approval.
6. Merge only when required reviews and checks pass.

## Configure GitHub protection manually

These files do not activate branch protection. In GitHub, open **Settings → Rules → Rulesets** (or branch protection settings) and create a ruleset for `main`:
- Require a pull request before merging.
- Require at least one approval.
- Require Code Owner review.
- Require the `backend-tests` and `contract-validation` checks when applicable.
- Dismiss stale approvals after new commits (recommended).
- Block force pushes and branch deletion.

## Important permission limitation

CODEOWNERS routes reviews; it is not folder-level write permission. A collaborator with repository write access can edit any path on their branch. Required PRs and Code Owner approval let you prevent those changes from entering `main`. For hard separation, use separate repositories.

## Suggested GitHub Projects columns

Backlog → Ready → In Progress → In Review → Done.

Every task should have one owner, allowed paths, acceptance criteria, and a linked PR.
