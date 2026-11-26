AIRLOCK TEAM GOVERNANCE FILES

1. Extract this ZIP into the root of your existing Airlock repository (example: E:\Airlock).
   Merge the .github folder and add TEAM_WORKFLOW.md. Do not replace existing backend,
   contracts, README, or project files.

2. Edit .github/CODEOWNERS. Replace YOUR_GITHUB_USERNAME with your username.
   When teammate usernames are known, uncomment the frontend, agent, and security-tests
   ownership lines and replace their placeholders. These three folders are planned and
   may not exist yet.

3. The workflows assume requirements.txt and scripts/validate_contracts.py are at the
   repository root, and tests are under backend/tests, matching the current starter layout.

4. Push these files through a branch and PR. Do not push directly to main if protection
   is already active.

5. Configure a GitHub ruleset for main manually, following TEAM_WORKFLOW.md.
   Adding these files does not automatically enable branch protection.

6. Current automation runs backend tests and contract validation only. Frontend and agent
   test workflows can be added once those projects exist.

IMPORTANT:
- CODEOWNERS does not prevent edits on another contributor's branch.
- These files do not grant ChatGPT access to your GitHub repository.
- Share PR links/diffs here for review, or connect an available GitHub integration.
- Never commit .env, secrets, local DB files, .venv, or node_modules.
