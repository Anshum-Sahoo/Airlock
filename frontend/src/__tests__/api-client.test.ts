import { getMockSessionDetail } from "../lib/mock-data";

const SESSION_ID = "b7d4e2c9-1a3f-4b68-8e52-6f9c0d7a3b21";

function jsonResponse(value: unknown): Response {
  return { ok: true, json: async () => value } as Response;
}

describe("real Airlock API client", () => {
  beforeEach(() => {
    jest.resetModules();
    process.env.NEXT_PUBLIC_MOCK_MODE = "false";
    process.env.NEXT_PUBLIC_AIRLOCK_API_URL = "http://127.0.0.1:8000";
  });

  afterEach(() => {
    jest.restoreAllMocks();
    delete process.env.NEXT_PUBLIC_AIRLOCK_API_URL;
    delete process.env.NEXT_PUBLIC_MOCK_MODE;
  });

  it("loads health, session summaries, and a contract manifest from existing GET routes", async () => {
    const manifest = getMockSessionDetail(SESSION_ID);
    if (!manifest) throw new Error("test fixture is missing");
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(jsonResponse({ status: "ok", prod_db_connected: true, meta_db_connected: true, prod_invoice_count: 500, active_sessions: 1, contracts_loaded: true, timestamp: "2026-11-28T00:00:00Z" }))
      .mockResolvedValueOnce(jsonResponse({ total: 1, sessions: [] }))
      .mockResolvedValueOnce(jsonResponse(manifest));
    global.fetch = fetchMock as unknown as typeof fetch;
    const api = require("../lib/api-client") as typeof import("../lib/api-client");

    await api.fetchHealth();
    await api.fetchSessions();
    await api.fetchSession(SESSION_ID);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      "http://127.0.0.1:8000/api/health",
      "http://127.0.0.1:8000/api/sessions",
      `http://127.0.0.1:8000/api/sessions/${SESSION_ID}`,
    ]);
    expect(fetchMock.mock.calls[0][1]?.headers).toEqual({});
    expect(fetchMock.mock.calls[1][1]?.headers).toEqual({});
  });

  it("posts exact reviewer action fields to the existing commit and rollback routes", async () => {
    const manifest = getMockSessionDetail(SESSION_ID);
    if (!manifest) throw new Error("test fixture is missing");
    const fetchMock = jest.fn()
      .mockResolvedValueOnce(jsonResponse(manifest))
      .mockResolvedValueOnce(jsonResponse(manifest));
    global.fetch = fetchMock as unknown as typeof fetch;
    const api = require("../lib/api-client") as typeof import("../lib/api-client");
    const action = { reviewer: "Synthetic Reviewer", reason: "Local API client test" };

    await api.commitSession(SESSION_ID, action, "synthetic-reviewer-token");
    await api.rollbackSession(SESSION_ID, action, "synthetic-reviewer-token");

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      `http://127.0.0.1:8000/api/sessions/${SESSION_ID}/commit`,
      `http://127.0.0.1:8000/api/sessions/${SESSION_ID}/rollback`,
    ]);
    for (const [, request] of fetchMock.mock.calls) {
      expect(request?.method).toBe("POST");
      expect(request?.headers).toEqual({
        Authorization: "Bearer synthetic-reviewer-token",
        "Content-Type": "application/json",
      });
      expect(JSON.parse(String(request?.body))).toEqual(action);
    }
  });
});
