# Reviewer dashboard

Install Node.js 20 or later and pnpm 9.15.9, then run from this directory:

```sh
pnpm install --frozen-lockfile
cp .env.local.example .env.local
pnpm dev --hostname 127.0.0.1 --port 3000
```

Set the backend CORS origin to `http://127.0.0.1:3000`. Use synthetic data and a loopback-only backend for local API testing. Set `NEXT_PUBLIC_MOCK_MODE=true` only for visual preview. Enter the reviewer token in the page after loading it.

Run checks with `pnpm run typecheck`, `pnpm run lint`, `pnpm test`, and `pnpm run build`.
