// Airlock API contract types — exact shapes from contracts/api.schema.json
// and contracts/manifest.schema.json (v1.2.1). Do not add fields not in the contract.

export type ExecutionStatus = "ACTIVE" | "COMPLETED" | "COMMITTED" | "ROLLED_BACK";
export type GateDecision = "PENDING" | "ALLOW" | "REQUIRE_APPROVAL" | "BLOCK";
export type HumanReviewStatus = "PENDING" | "APPROVED" | "REJECTED";
export type MutationType = "INSERT" | "UPDATE" | "DELETE";
export type PolicyDecision = "PENDING" | "ALLOW" | "REQUIRE_APPROVAL" | "BLOCK";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type EffectScope = "SESSION" | "TOOL";
export type PolicyDecisionEnum = "ALLOW" | "REQUIRE_APPROVAL" | "BLOCK";
export type PolicyStage = "TOOL_EXECUTE" | "SESSION_COMPLETE";
export type ToolExecutionStatus = "SUCCESS" | "BLOCKED" | "ERROR";
export type ToolDecision = "ALLOW" | "REQUIRE_APPROVAL" | "BLOCK";
export type ChangedInvoiceField =
  | "customer_name"
  | "customer_email"
  | "amount_cents"
  | "currency"
  | "status"
  | "due_date"
  | "notes";

/** contracts/invoice.schema.json */
export interface Invoice {
  id: string;
  customer_name: string;
  customer_email: string;
  amount_cents: number;
  currency: string;
  status: "OVERDUE" | "PAID" | "PENDING" | "CANCELLED";
  due_date: string;
  notes: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

/** contracts/manifest.schema.json#/$defs/Mutation */
export interface Mutation {
  mutation_id: string;
  operation_id: string;
  tool_name: string;
  entity_type: "invoice";
  entity_id: string;
  mutation_type: MutationType;
  before: Invoice | null;
  after: Invoice | null;
  changed_fields: ChangedInvoiceField[];
  baseline_version: number | null;
  timestamp: string;
  policy_decision: PolicyDecision;
}

/** contracts/manifest.schema.json#/$defs/PolicyViolation */
export interface PolicyViolation {
  policy_id: string;
  policy_name: string;
  severity: RiskLevel;
  decision: PolicyDecisionEnum;
  effect_scope: EffectScope;
  stage: PolicyStage;
  operation_id: string | null;
  explanation: string;
  affected_record_count: number | null;
  timestamp: string;
}

/** contracts/manifest.schema.json#/$defs/StagedWebhook */
export interface StagedWebhook {
  webhook_id: string;
  operation_id: string;
  url: string;
  event_type: string;
  payload: Record<string, unknown>;
  staged_at: string;
  status: "STAGED" | "BLOCKED";
}

/** contracts/manifest.schema.json#/$defs/ToolExecution */
export interface ToolExecution {
  operation_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  read_only: boolean | null;
  status: ToolExecutionStatus;
  tool_decision: ToolDecision;
  mutations_recorded: number;
  error_code:
    | "INVALID_TOOL"
    | "INVALID_ARGUMENTS"
    | "INVOICE_NOT_FOUND"
    | "POLICY_BLOCK"
    | "DATABASE_FAILURE"
    | "INTERNAL_ERROR"
    | null;
  executed_at: string;
}

/** contracts/manifest.schema.json#/$defs/RiskSummary */
export interface RiskSummary {
  total_mutations: number;
  affected_percentage: number;
  overall_risk_level: RiskLevel;
  violation_count: number;
  block_count: number;
  require_approval_count: number;
  staged_webhook_count: number;
  summary_text: string;
}

/** contracts/manifest.schema.json#/$defs/MutationCounts */
export interface MutationCounts {
  inserted: number;
  updated: number;
  deleted: number;
  total: number;
}

/** contracts/api.schema.json#/$defs/HealthResponse */
export interface HealthResponse {
  status: "ok";
  prod_db_connected: true;
  meta_db_connected: true;
  prod_invoice_count: number;
  active_sessions: number;
  contracts_loaded: true;
  timestamp: string;
}

/** contracts/api.schema.json#/$defs/SessionSummary */
export interface SessionSummary {
  session_id: string;
  agent_name: string;
  task_description: string | null;
  created_at: string;
  updated_at: string;
  execution_status: ExecutionStatus;
  gate_decision: GateDecision;
  human_review_status: HumanReviewStatus;
  mutation_counts: MutationCounts;
  risk_summary: RiskSummary;
}

/** contracts/api.schema.json#/$defs/SessionListResponse */
export interface SessionListResponse {
  total: number;
  sessions: SessionSummary[];
}

export type ConflictType = "MISSING" | "MODIFIED" | "UNEXPECTED_EXISTING";

/** contracts/manifest.schema.json#/$defs/ConflictDetail */
export interface ConflictDetail {
  entity_type: "invoice";
  entity_id: string;
  conflict_type: ConflictType;
  expected_version: number | null;
  actual_version: number | null;
}

/** contracts/manifest.schema.json#/$defs/FinalizationResult */
export interface FinalizationResult {
  action: "COMMIT" | "ROLLBACK";
  status: "SUCCESS" | "FAILED";
  actor: string;
  reason: string | null;
  timestamp: string;
  applied_counts: {
    inserted: number;
    updated: number;
    deleted: number;
  };
  conflict_details: ConflictDetail[] | null;
  ledger_id: string | null;
  recovered: boolean;
}

/** contracts/manifest.schema.json — full session detail returned by GET /api/sessions/{id} */
export interface SessionManifest {
  session_id: string;
  agent_name: string;
  task_description: string | null;
  agent_summary: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  finalized_at: string | null;
  execution_status: ExecutionStatus;
  gate_decision: GateDecision;
  human_review_status: HumanReviewStatus;
  baseline_record_count: number;
  risk_summary: RiskSummary;
  mutation_counts: MutationCounts;
  mutations: {
    inserted: Mutation[];
    updated: Mutation[];
    deleted: Mutation[];
  };
  staged_webhooks: StagedWebhook[];
  policy_violations: PolicyViolation[];
  tool_execution_history: ToolExecution[];
  finalization_result: FinalizationResult | null;
}

/** contracts/api.schema.json#/$defs/ReviewerActionRequest */
export interface ReviewerActionRequest {
  reviewer: string;
  reason?: string | null;
}

/** Commit/rollback response — the full SessionManifest is returned on success */
export type CommitResponse = SessionManifest;
export type RollbackResponse = SessionManifest;

/** contracts/error.schema.json error envelope */
export interface ApiError {
  error: {
    code: string;
    message: string;
    http_status: number;
    details: Record<string, unknown>;
    request_id: string;
    timestamp: string;
  };
}
