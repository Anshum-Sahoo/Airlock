/**
 * Airlock API client.
 *
 * Security notes (from contracts/API_CONTRACT.md section 3.3):
 * - The reviewer token is passed in at call time from page-memory state only.
 * - It is NEVER stored in localStorage, sessionStorage, cookies, URLs, or env.
 * - NEXT_PUBLIC_AIRLOCK_API_URL exposes only the backend base URL — no secrets.
 * - NEXT_PUBLIC_POLL_INTERVAL_MS is the contract's public refresh interval.
 * - NEXT_PUBLIC_MOCK_MODE=true enables isolated mock mode for UI preview.
 * - No NVIDIA credentials or other backend secrets appear here.
 */

import type {
  HealthResponse,
  SessionListResponse,
  SessionManifest,
  ReviewerActionRequest,
  CommitResponse,
  RollbackResponse,
  ApiError,
} from "./types";
import {
  getMockHealth,
  getMockSessionList,
  getMockSessionDetail,
  finalizeMockSession,
} from "./mock-data";

// ---------------------------------------------------------------------------
// Config — public, non-secret values only
// ---------------------------------------------------------------------------

/** Backend base URL. Must be a loopback or known host — no secrets. */
const API_BASE =
  process.env.NEXT_PUBLIC_AIRLOCK_API_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

const configuredPollInterval = Number(process.env.NEXT_PUBLIC_POLL_INTERVAL_MS);
export const POLL_INTERVAL_MS =
  Number.isFinite(configuredPollInterval) && configuredPollInterval > 0
    ? configuredPollInterval
    : 2000;

/** When true, all reads return mock data and mutating calls are simulated. */
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === "true";

// ---------------------------------------------------------------------------
// Low-level fetch helper
// ---------------------------------------------------------------------------

class AirlockApiError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly errorCode: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
    public readonly requestId?: string
  ) {
    super(message);
    this.name = "AirlockApiError";
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      headers: {
        ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...(options.headers ?? {}),
      },
    });
  } catch (err) {
    throw new AirlockApiError(0, "NETWORK_ERROR", String(err));
  }

  if (!res.ok) {
    let body: Partial<ApiError> = {};
    try {
      body = await res.json();
    } catch {
      /* non-JSON error body */
    }
    const e = body?.error;
    throw new AirlockApiError(
      res.status,
      e?.code ?? "UNKNOWN_ERROR",
      e?.message ?? `HTTP ${res.status}`,
      e?.details ?? {},
      e?.request_id
    );
  }

  return res.json() as Promise<T>;
}

function reviewerHeaders(token: string): HeadersInit {
  // token comes from page-memory only; never logged or stored
  return { Authorization: `Bearer ${token}` };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export { MOCK_MODE, AirlockApiError };

/** GET /api/health */
export async function fetchHealth(): Promise<HealthResponse> {
  if (MOCK_MODE) return getMockHealth();
  return apiFetch<HealthResponse>("/api/health");
}

/** GET /api/sessions */
export async function fetchSessions(): Promise<SessionListResponse> {
  if (MOCK_MODE) return getMockSessionList();
  return apiFetch<SessionListResponse>("/api/sessions");
}

/** GET /api/sessions/{session_id} */
export async function fetchSession(sessionId: string): Promise<SessionManifest> {
  if (MOCK_MODE) {
    const m = getMockSessionDetail(sessionId);
    if (!m) {
      throw new AirlockApiError(404, "SESSION_NOT_FOUND", `Session ${sessionId} not found`);
    }
    return m;
  }
  return apiFetch<SessionManifest>(`/api/sessions/${encodeURIComponent(sessionId)}`);
}

/** POST /api/sessions/{session_id}/commit — reviewer-only */
export async function commitSession(
  sessionId: string,
  body: ReviewerActionRequest,
  reviewerToken: string
): Promise<CommitResponse> {
  if (MOCK_MODE) {
    // Simulate success response in mock mode
    const manifest = getMockSessionDetail(sessionId);
    if (!manifest) {
      throw new AirlockApiError(404, "SESSION_NOT_FOUND", `Session ${sessionId} not found`);
    }
    if (manifest.gate_decision === "BLOCK") {
      throw new AirlockApiError(403, "POLICY_BLOCK", "Session cannot be committed: gate_decision is BLOCK", { gate_decision: "BLOCK" });
    }
    if (manifest.execution_status !== "COMPLETED") {
      throw new AirlockApiError(409, "INVALID_SESSION_STATE", "Session must be COMPLETED to commit");
    }
    const updated = finalizeMockSession(sessionId, "COMMIT", body.reviewer, body.reason ?? null);
    if (!updated) {
      throw new AirlockApiError(404, "SESSION_NOT_FOUND", `Session ${sessionId} not found`);
    }
    return updated;
  }
  return apiFetch<CommitResponse>(
    `/api/sessions/${encodeURIComponent(sessionId)}/commit`,
    {
      method: "POST",
      // The browser supplies the page Origin automatically; the backend checks it.
      headers: reviewerHeaders(reviewerToken),
      body: JSON.stringify(body),
    }
  );
}

/** POST /api/sessions/{session_id}/rollback — reviewer-only */
export async function rollbackSession(
  sessionId: string,
  body: ReviewerActionRequest,
  reviewerToken: string
): Promise<RollbackResponse> {
  if (MOCK_MODE) {
    const manifest = getMockSessionDetail(sessionId);
    if (!manifest) {
      throw new AirlockApiError(404, "SESSION_NOT_FOUND", `Session ${sessionId} not found`);
    }
    if (manifest.execution_status === "COMMITTED" || manifest.execution_status === "ROLLED_BACK") {
      throw new AirlockApiError(409, "SESSION_ALREADY_FINALIZED", "Session is already finalized");
    }
    const updated = finalizeMockSession(sessionId, "ROLLBACK", body.reviewer, body.reason ?? null);
    if (!updated) {
      throw new AirlockApiError(404, "SESSION_NOT_FOUND", `Session ${sessionId} not found`);
    }
    return updated;
  }
  return apiFetch<RollbackResponse>(
    `/api/sessions/${encodeURIComponent(sessionId)}/rollback`,
    {
      method: "POST",
      // The browser supplies the page Origin automatically; the backend checks it.
      headers: reviewerHeaders(reviewerToken),
      body: JSON.stringify(body),
    }
  );
}
