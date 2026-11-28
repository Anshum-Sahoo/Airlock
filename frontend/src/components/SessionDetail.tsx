/**
 * Session detail panel: full manifest view with commit/rollback actions.
 *
 * Security model (API_CONTRACT.md §3.3):
 * - reviewerToken lives in page-memory only (passed as prop).
 * - The reviewer field is a self-asserted audit label (not an identity proof).
 * - ALLOW gate does NOT mean automatic approval; reviewer must explicitly commit.
 * - BLOCK gate means commit is impossible; only rollback is available.
 */

"use client";

import { useState } from "react";
import type { ConflictDetail, SessionManifest } from "@/lib/types";
import {
  Badge,
  ExecutionStatusBadge,
  GateDecisionBadge,
  HumanReviewBadge,
  RiskBadge,
} from "./StatusBadge";
import { MutationTable } from "./MutationTable";
import { ViolationList } from "./ViolationList";
import { ToolTimeline } from "./ToolTimeline";
import { WebhookList } from "./WebhookList";
import { commitSession, rollbackSession, AirlockApiError } from "@/lib/api-client";

interface SessionDetailProps {
  session: SessionManifest;
  reviewerToken: string;
  onClearToken: () => void;
  onRefresh: () => void;
  onActionComplete: (updated: SessionManifest) => void;
}

type Tab = "overview" | "activity" | "mutations" | "violations" | "webhooks" | "summary";

function fmt(ts: string | null): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });
  } catch {
    return ts;
  }
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 py-1.5 border-b border-[#E5E6E8] last:border-b-0">
      <span className="text-[11px] uppercase tracking-widest text-[#52525B] w-36 flex-shrink-0 pt-0.5 font-semibold">
        {label}
      </span>
      <span className="text-sm text-[#191A1C] break-all">{value}</span>
    </div>
  );
}

export function SessionDetail({ session, reviewerToken, onClearToken, onRefresh, onActionComplete }: SessionDetailProps) {
  const [tab, setTab] = useState<Tab>("overview");
  const [reviewer, setReviewer] = useState("");
  const [reason, setReason] = useState("");
  const [working, setWorking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [liveConflicts, setLiveConflicts] = useState<ConflictDetail[] | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const isFinalized =
    session.execution_status === "COMMITTED" ||
    session.execution_status === "ROLLED_BACK";
  const fin = session.finalization_result;
  const hasConflict =
    (fin?.status === "FAILED" && (fin.conflict_details?.length ?? 0) > 0) ||
    (liveConflicts !== null && liveConflicts.length > 0);
  const hasFailed = fin?.status === "FAILED" && !hasConflict;
  const displayedConflicts = liveConflicts ?? fin?.conflict_details ?? [];

  const canCommit =
    !isFinalized &&
    session.execution_status === "COMPLETED" &&
    session.gate_decision !== "BLOCK" &&
    session.human_review_status === "PENDING";
  const canRollback =
    (session.execution_status === "ACTIVE" || session.execution_status === "COMPLETED") &&
    session.human_review_status === "PENDING";
  const noToken = !reviewerToken;

  async function handleAction(action: "commit" | "rollback") {
    if (
      action === "commit" &&
      session.gate_decision === "REQUIRE_APPROVAL" &&
      !window.confirm("Policy requires explicit approval. Commit these reviewed mutations to production?")
    ) return;
    if (!reviewer.trim()) {
      setActionError("Reviewer name is required (audit label).");
      return;
    }
    if (!reviewerToken) {
      setActionError("Set the reviewer token first.");
      return;
    }
    setWorking(true);
    setActionError(null);
    setLiveConflicts(null);
    setActionSuccess(null);
    try {
      const body = { reviewer: reviewer.trim(), reason: reason.trim() || null };
      let updated: SessionManifest;
      if (action === "commit") {
        updated = await commitSession(session.session_id, body, reviewerToken);
        setActionSuccess("Session committed successfully. Production updated.");
      } else {
        updated = await rollbackSession(session.session_id, body, reviewerToken);
        setActionSuccess("Session rolled back. Production unchanged.");
      }
      onActionComplete(updated);
    } catch (e) {
      if (e instanceof AirlockApiError) {
        if (e.errorCode === "UNAUTHORIZED_REVIEWER") {
          onClearToken();
        }
        if (action === "commit" && e.errorCode === "DATABASE_FAILURE" && e.details.commit_durable === true) {
          setActionSuccess("Commit is durable; refreshing the session record.");
          onRefresh();
        } else {
          setActionError(`${e.errorCode}: ${e.message}`);
        }
        if (
          e.errorCode === "COMMIT_CONFLICT" &&
          Array.isArray(e.details?.conflicts)
        ) {
          setLiveConflicts(e.details.conflicts as ConflictDetail[]);
        }
      } else {
        setActionError(String(e));
      }
    } finally {
      setWorking(false);
    }
  }

  const TABS: { key: Tab; label: string; count?: number }[] = [
    { key: "overview", label: "Overview" },
    { key: "activity", label: "Tool activity", count: session.tool_execution_history.length },
    {
      key: "mutations",
      label: "Mutations",
      count: session.mutation_counts.total,
    },
    {
      key: "violations",
      label: "Violations",
      count: session.policy_violations.length,
    },
    { key: "webhooks", label: "Webhooks", count: session.staged_webhooks.length },
    { key: "summary", label: "Agent Summary" },
  ];

  return (
    <div className="bg-[#FFFFFF] border border-[#E5E6E8] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-[#F8F9FA] border-b border-[#E5E6E8] flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          {/* session_id is a UUID — not agent-controlled free text */}
          <div className="font-mono text-xs text-[#52525B]">{session.session_id}</div>
          {/* agent_name rendered as plain text */}
          <div className="text-sm font-semibold text-[#191A1C]">{session.agent_name}</div>
          {/* task_description rendered as plain text */}
          {session.task_description && (
            <div className="text-xs text-[#52525B] max-w-lg">{session.task_description}</div>
          )}
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <ExecutionStatusBadge status={session.execution_status} />
          <GateDecisionBadge decision={session.gate_decision} />
          <HumanReviewBadge status={session.human_review_status} />
          {hasConflict && <Badge label="Conflict" variant="warn" />}
          {hasFailed && <Badge label="Failed" variant="danger" />}
          {isFinalized && <Badge label="Finalized" variant="muted" />}
          <RiskBadge level={session.risk_summary.overall_risk_level} />
        </div>
      </div>

      {/* State & outcome banners */}
      {session.gate_decision === "ALLOW" && !isFinalized && (
        <div className="px-4 py-2 bg-[rgba(239,73,47,0.07)] border-b border-[rgba(239,73,47,0.12)] text-xs text-[#EF492F]">
          Gate decision <strong>ALLOW</strong> means no policy objected — it does <strong>NOT</strong> commit automatically.
          A reviewer must explicitly commit this session.
        </div>
      )}
      {session.gate_decision === "REQUIRE_APPROVAL" && !isFinalized && (
        <div className="px-4 py-2 bg-[rgba(245,158,11,0.08)] border-b border-[rgba(245,158,11,0.2)] text-xs text-[#E56828]">
          <strong>APPROVAL REQUIRED</strong> — policy thresholds were exceeded. Review mutations before committing or rolling back.
        </div>
      )}
      {session.gate_decision === "BLOCK" && !isFinalized && (
        <div className="px-4 py-2 bg-[rgba(239,73,47,0.08)] border-b border-[rgba(239,73,47,0.2)] text-xs text-[#EF492F]">
          Gate decision <strong>BLOCK</strong> — commit is permanently denied. Only rollback is available.
        </div>
      )}
      {hasConflict && (
        <div className="px-4 py-3 bg-[rgba(245,158,11,0.08)] border-b border-[rgba(245,158,11,0.3)] text-xs space-y-2">
          <div className="text-[#E56828] font-semibold">
            COMMIT CONFLICT — Production rows changed since baseline. Nothing was applied; rollback or resolve.
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-[11px] border-collapse">
              <thead>
                <tr className="text-[#52525B] border-b border-[rgba(245,158,11,0.2)]">
                  <th className="py-1 pr-3">Entity</th>
                  <th className="py-1 pr-3">Conflict</th>
                  <th className="py-1 pr-3">Expected Ver</th>
                  <th className="py-1">Actual Ver</th>
                </tr>
              </thead>
              <tbody>
                {displayedConflicts.map((c) => (
                  <tr key={c.entity_id} className="text-[#191A1C] border-b border-[rgba(245,158,11,0.1)]">
                    <td className="py-1 pr-3">{c.entity_id}</td>
                    <td className="py-1 pr-3 text-[#E56828]">{c.conflict_type}</td>
                    <td className="py-1 pr-3">{c.expected_version ?? "null"}</td>
                    <td className="py-1">{c.actual_version ?? "null"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {hasFailed && fin && (
        <div className="px-4 py-2 bg-[rgba(239,73,47,0.08)] border-b border-[rgba(239,73,47,0.2)] text-xs text-[#EF492F]">
          <strong>FAILED</strong> — last {fin.action} attempt at {fmt(fin.timestamp)} failed. Production is unchanged.
        </div>
      )}
      {isFinalized && fin && (
        <div className="px-4 py-2 bg-[#F8F9FA] border-b border-[#E5E6E8] text-xs text-[#52525B] flex flex-wrap items-center gap-3">
          <span>
            <strong>FINALIZED</strong> ({fin.action} · {fin.status}) by{" "}
            <span className="font-mono text-[#191A1C]">{fin.actor}</span> at {fmt(fin.timestamp)}
          </span>
          {fin.ledger_id && (
            <span className="font-mono text-[#52525B]">
              Ledger: <span className="text-[#22C55E]">{fin.ledger_id}</span>
            </span>
          )}
          {fin.recovered && (
            <Badge label="Recovered" variant="cyan" />
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-[#E5E6E8] bg-[#F8F9FA]">
        {TABS.map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-xs font-semibold transition-colors whitespace-nowrap ${
              tab === key
                ? "text-[#EF492F] border-b-2 border-[#EF492F]"
                : "text-[#52525B] hover:text-[#191A1C]"
            }`}
          >
            {label}
            {count !== undefined && (
              <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] ${
                count > 0 ? "bg-[rgba(239,73,47,0.12)] text-[#EF492F]" : "bg-[#E5E6E8] text-[#52525B]"
              }`}>
                {count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4">
        {tab === "overview" && (
          <div className="space-y-1">
            <InfoRow label="Session ID" value={<span className="font-mono">{session.session_id}</span>} />
            <InfoRow label="Created" value={fmt(session.created_at)} />
            <InfoRow label="Completed" value={fmt(session.completed_at)} />
            <InfoRow label="Finalized" value={fmt(session.finalized_at)} />
            <InfoRow label="Baseline Count" value={
              <span className="font-mono tnum">{session.baseline_record_count}</span>
            } />
            <InfoRow label="Mutations" value={
              <span className="font-mono tnum">
                <span className="text-[#22C55E]">+{session.mutation_counts.inserted} ins</span>
                {" · "}
                <span className="text-[#EF492F]">~{session.mutation_counts.updated} upd</span>
                {" · "}
                <span className="text-[#EF492F]">-{session.mutation_counts.deleted} del</span>
                {" · "}
                total {session.mutation_counts.total}
              </span>
            } />
            <InfoRow label="Affected %" value={
              <span className="font-mono tnum">{session.risk_summary.affected_percentage.toFixed(2)}%</span>
            } />
            <InfoRow label="Violations" value={
              <span className="font-mono tnum">
                {session.risk_summary.violation_count} total,{" "}
                <span className="text-[#EF492F]">{session.risk_summary.block_count} block</span>,{" "}
                <span className="text-[#E56828]">{session.risk_summary.require_approval_count} req_approval</span>
              </span>
            } />
            <InfoRow label="Summary" value={
              /* summary_text is backend-generated display text */
              <span className="text-[#52525B]">{session.risk_summary.summary_text}</span>
            } />
          </div>
        )}

        {tab === "activity" && (
          <ToolTimeline executions={session.tool_execution_history} />
        )}

        {tab === "mutations" && (
          <div className="space-y-3">
            {session.mutation_counts.total > 0 && (
              <div className="rounded border border-[#E5E6E8] bg-[#F8F9FA] px-3 py-2 text-sm text-[#52525B]">
                {session.risk_summary.summary_text} <span className="text-[#52525B]">({session.risk_summary.affected_percentage.toFixed(1)}% of baseline)</span>
              </div>
            )}
            <MutationTable mutations={session.mutations} />
          </div>
        )}

        {tab === "violations" && (
          <ViolationList violations={session.policy_violations} />
        )}

        {tab === "webhooks" && (
          <WebhookList webhooks={session.staged_webhooks} />
        )}

        {tab === "summary" && (
          <div className="space-y-2">
            {session.agent_summary ? (
              /* agent_summary rendered as plain text (§3.8) */
              <p className="text-sm text-[#52525B] whitespace-pre-wrap">{session.agent_summary}</p>
            ) : (
              <p className="text-[#52525B] text-sm">No agent summary provided.</p>
            )}
          </div>
        )}
      </div>

      {/* Reviewer action panel */}
      {!isFinalized && (
        <div className="border-t border-[#E5E6E8] p-4 bg-[#F8F9FA] space-y-3">
          <div className="text-xs font-semibold uppercase tracking-widest text-[#52525B] mb-1">
            Reviewer Action
          </div>

          {noToken && (
            <div className="text-xs text-[#E56828] bg-[rgba(245,158,11,0.08)] border border-[rgba(245,158,11,0.3)] rounded px-3 py-2">
              ⚠️ Set the reviewer token (top bar) before committing or rolling back.
            </div>
          )}

          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="text"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              placeholder="Your name or email (audit label)"
              maxLength={120}
              className="
                flex-1 px-3 py-2 bg-[#F8F9FA] border border-[#E5E6E8] rounded
                text-xs text-[#191A1C] placeholder-[#52525B]
                focus:outline-none focus:border-[#EF492F]
              "
              aria-label="Reviewer name (audit label)"
            />
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason (optional)"
              maxLength={500}
              className="
                flex-1 px-3 py-2 bg-[#F8F9FA] border border-[#E5E6E8] rounded
                text-xs text-[#191A1C] placeholder-[#52525B]
                focus:outline-none focus:border-[#EF492F]
              "
              aria-label="Reason (optional)"
            />
          </div>

          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => handleAction("commit")}
              disabled={!canCommit || working || noToken}
              title={
                session.gate_decision === "BLOCK"
                  ? "Cannot commit: session is blocked"
                  : session.execution_status !== "COMPLETED"
                  ? "Session must be COMPLETED"
                  : noToken
                  ? "Set reviewer token first"
                  : "Commit mutations to production"
              }
              className="
                px-4 py-2 text-xs font-semibold rounded transition-all
                bg-[#EF492F] text-white
                hover:bg-[#EF492F] hover:shadow-[0_0_12px_rgba(239,73,47,0.22)]
                disabled:opacity-40 disabled:cursor-not-allowed
              "
            >
              {working ? "Working…" : "✓ Commit"}
            </button>
            <button
              onClick={() => handleAction("rollback")}
              disabled={!canRollback || working || noToken}
              title={noToken ? "Set reviewer token first" : "Rollback — discard speculative state"}
              className="
                px-4 py-2 text-xs font-semibold rounded transition-all
                bg-[rgba(239,73,47,0.15)] text-[#EF492F] border border-[#EF492F]
                hover:bg-[#EF492F] hover:text-white
                disabled:opacity-40 disabled:cursor-not-allowed
              "
            >
              {working ? "Working…" : "✕ Rollback"}
            </button>
          </div>

          {actionError && (
            <div className="text-xs text-[#EF492F] bg-[rgba(239,73,47,0.08)] border border-[rgba(239,73,47,0.3)] rounded px-3 py-2">
              {/* actionError is from API or local validation — no secrets */}
              {actionError}
            </div>
          )}
          {actionSuccess && (
            <div className="text-xs text-[#22C55E] bg-[rgba(34,197,94,0.08)] border border-[rgba(34,197,94,0.3)] rounded px-3 py-2">
              {actionSuccess}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
