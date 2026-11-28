/**
 * Frontend tests — contract shape, security rules, and state logic.
 * Uses jest + @testing-library/react (jsdom).
 *
 * These tests verify:
 * 1. No NEXT_PUBLIC_* env leaks the reviewer token.
 * 2. Status badge mapping matches the contract states.
 * 3. Mock data shapes conform to the type definitions.
 */

import { getMockHealth, getMockSessionList, getMockSessionDetail } from "../lib/mock-data";
import type { HealthResponse, SessionListResponse, SessionManifest } from "../lib/types";

// ---------------------------------------------------------------------------
// 1. Token security: reviewer token must NOT appear in any NEXT_PUBLIC_ env
// ---------------------------------------------------------------------------
describe("Security: reviewer token isolation", () => {
  it("no NEXT_PUBLIC_ env contains 'token' or 'secret' key substring", () => {
    const forbidden = Object.keys(process.env).filter(
      (k) =>
        k.startsWith("NEXT_PUBLIC_") &&
        (k.toLowerCase().includes("token") ||
          k.toLowerCase().includes("secret") ||
          k.toLowerCase().includes("key") ||
          k.toLowerCase().includes("credential"))
    );
    expect(forbidden).toEqual([]);
  });

  it("NEXT_PUBLIC_MOCK_MODE is not a secret", () => {
    // NEXT_PUBLIC_MOCK_MODE is a feature flag, not a credential — allowed
    const val = process.env.NEXT_PUBLIC_MOCK_MODE;
    if (val !== undefined) {
      expect(["true", "false", "1", "0", ""]).toContain(val);
    }
  });
});

// ---------------------------------------------------------------------------
// 2. HealthResponse shape
// ---------------------------------------------------------------------------
describe("HealthResponse contract shape", () => {
  it("getMockHealth returns all required fields", () => {
    const h: HealthResponse = getMockHealth();
    expect(h.status).toBe("ok");
    expect(h.prod_db_connected).toBe(true);
    expect(h.meta_db_connected).toBe(true);
    expect(typeof h.prod_invoice_count).toBe("number");
    expect(h.prod_invoice_count).toBeGreaterThanOrEqual(0);
    expect(typeof h.active_sessions).toBe("number");
    expect(h.contracts_loaded).toBe(true);
    expect(typeof h.timestamp).toBe("string");
    // UTC ISO 8601 ending in Z
    expect(h.timestamp).toMatch(/Z$/);
  });
});

// ---------------------------------------------------------------------------
// 3. SessionListResponse shape
// ---------------------------------------------------------------------------
describe("SessionListResponse contract shape", () => {
  const list: SessionListResponse = getMockSessionList();

  it("has total and sessions array", () => {
    expect(typeof list.total).toBe("number");
    expect(Array.isArray(list.sessions)).toBe(true);
    expect(list.sessions.length).toBeGreaterThan(0);
  });

  it("each session has required fields", () => {
    for (const s of list.sessions) {
      expect(typeof s.session_id).toBe("string");
      expect(typeof s.agent_name).toBe("string");
      expect(["ACTIVE", "COMPLETED", "COMMITTED", "ROLLED_BACK"]).toContain(s.execution_status);
      expect(["PENDING", "ALLOW", "REQUIRE_APPROVAL", "BLOCK"]).toContain(s.gate_decision);
      expect(["PENDING", "APPROVED", "REJECTED"]).toContain(s.human_review_status);
      expect(typeof s.mutation_counts.total).toBe("number");
      expect(["LOW", "MEDIUM", "HIGH", "CRITICAL"]).toContain(s.risk_summary.overall_risk_level);
    }
  });

  it("ALLOW sessions have human_review_status PENDING when not finalized", () => {
    // ALLOW gate does NOT auto-approve — must still have reviewer commit
    const allowSessions = list.sessions.filter(
      (s) => s.gate_decision === "ALLOW" && s.execution_status === "COMPLETED"
    );
    for (const s of allowSessions) {
      // human_review_status must be PENDING (not auto-approved)
      expect(s.human_review_status).toBe("PENDING");
    }
  });
});

// ---------------------------------------------------------------------------
// 4. SessionManifest shape
// ---------------------------------------------------------------------------
describe("SessionManifest contract shape", () => {
  const id = "b7d4e2c9-1a3f-4b68-8e52-6f9c0d7a3b21";
  const manifest: SessionManifest | null = getMockSessionDetail(id);

  it("returns a manifest for a known session", () => {
    expect(manifest).not.toBeNull();
  });

  it("has mutations with correct structure", () => {
    if (!manifest) return;
    expect(Array.isArray(manifest.mutations.inserted)).toBe(true);
    expect(Array.isArray(manifest.mutations.updated)).toBe(true);
    expect(Array.isArray(manifest.mutations.deleted)).toBe(true);
  });

  it("mutation records have before/after and policy_decision", () => {
    if (!manifest) return;
    for (const m of manifest.mutations.updated) {
      expect(["INSERT", "UPDATE", "DELETE"]).toContain(m.mutation_type);
      expect(["PENDING", "ALLOW", "REQUIRE_APPROVAL"]).toContain(m.policy_decision);
      // UPDATE must have both before and after
      if (m.mutation_type === "UPDATE") {
        expect(m.before).not.toBeNull();
        expect(m.after).not.toBeNull();
      }
    }
  });

  it("BLOCK sessions cannot have human_review_status APPROVED", () => {
    const blockId = "deadbeef-dead-4bef-beef-deadbeefcafe";
    const blocked = getMockSessionDetail(blockId);
    expect(blocked).not.toBeNull();
    if (!blocked) return;
    expect(blocked.gate_decision).toBe("BLOCK");
    // A blocked session must never reach APPROVED
    expect(blocked.human_review_status).not.toBe("APPROVED");
  });

  it("policy violations have required fields", () => {
    const bulkId = "a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
    const bulk = getMockSessionDetail(bulkId);
    expect(bulk).not.toBeNull();
    if (!bulk) return;
    expect(bulk.policy_violations.length).toBeGreaterThan(0);
    for (const v of bulk.policy_violations) {
      expect(typeof v.policy_id).toBe("string");
      expect(["ALLOW", "REQUIRE_APPROVAL", "BLOCK"]).toContain(v.decision);
      expect(["SESSION", "TOOL"]).toContain(v.effect_scope);
      expect(["LOW", "MEDIUM", "HIGH", "CRITICAL"]).toContain(v.severity);
      expect(["TOOL_EXECUTE", "SESSION_COMPLETE"]).toContain(v.stage);
      expect(["string", "object"]).toContain(typeof v.operation_id);
      expect(Object.keys(v).sort()).toEqual([
        "affected_record_count", "decision", "effect_scope", "explanation",
        "operation_id", "policy_id", "policy_name", "severity", "stage", "timestamp",
      ].sort());
    }
  });

  it("mock manifest detail collections use the frozen contract shapes", () => {
    const bulk = getMockSessionDetail("a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d");
    expect(bulk).not.toBeNull();
    if (!bulk) return;

    expect(bulk.mutations.deleted).toHaveLength(bulk.mutation_counts.deleted);
    expect(bulk.tool_execution_history[0]).toMatchObject({ status: "SUCCESS", tool_decision: "ALLOW" });
    expect(Object.keys(bulk.tool_execution_history[0]).sort()).toEqual([
      "arguments", "error_code", "executed_at", "mutations_recorded", "operation_id",
      "read_only", "status", "tool_decision", "tool_name",
    ].sort());
  });
});

// ---------------------------------------------------------------------------
// 5. Unknown session ID returns null
// ---------------------------------------------------------------------------
describe("getMockSessionDetail edge cases", () => {
  it("returns null for unknown session ID", () => {
    expect(getMockSessionDetail("00000000-0000-4000-8000-000000000000")).toBeNull();
  });
});
