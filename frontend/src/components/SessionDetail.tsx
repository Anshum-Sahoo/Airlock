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
import { commitSession, rollbackSession, AirlockApiError } from "@/lib/api-client";

interface SessionDetailProps {
  session: SessionManifest;
  reviewerToken: string;
  onActionComplete: (updated: SessionManifest) => void;
}

type Tab = "overview" | "mutations" | "violations" | "summary";

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
    <div className="flex items-start gap-3 py-1.5 border-b border-[#263247] last:border-b-0">
      <span className="text-[11px] uppercase tracking-widest text-[#94A3B8] w-36 flex-shrink-0 pt-0.5 font-semibold">
        {label}
      </span>
      <span className="text-sm text-[#F8FAFC] break-all">{value}</span>
    </div>
  );
}

export function SessionDetail({ session, reviewerToken, onActionComplete }: SessionDetailProps) {
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
    !isFinalized && session.human_review_status === "PENDING";
  const noToken = !reviewerToken;

  async function handleAction(action: "commit" | "rollback") {
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
        setActionError(`${e.errorCode}: ${e.message}`);
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
    { key: "summary", label: "Agent Summary" },
  ];

  return (
    <div className="bg-[#111827] border border-[#263247] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-[#0D1320] border-b border-[#263247] flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          {/* session_id is a UUID — not agent-controlled free text */}
          <div className="font-mono text-xs text-[#94A3B8]">{session.session_id}</div>
          {/* agent_name rendered as plain text */}
          <div className="text-sm font-semibold text-[#F8FAFC]">{session.agent_name}</div>
          {/* task_description rendered as plain text */}
          {session.task_description && (
            <div className="text-xs text-[#CBD5E1] max-w-lg">{session.task_description}</div>
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
        <div className="px-4 py-2 bg-[rgba(59,130,246,0.08)] border-b border-[rgba(59,130,246,0.2)] text-xs text-[#3B82F6]">
          Gate decision <strong>ALLOW</strong> means no policy objected — it does <strong>NOT</strong> commit automatically.
          A reviewer must explicitly commit this session.
        </div>
      )}
      {session.gate_decision === "REQUIRE_APPROVAL" && !isFinalized && (
        <div className="px-4 py-2 bg-[rgba(245,158,11,0.08)] border-b border-[rgba(245,158,11,0.2)] text-xs text-[#F59E0B]">
          <strong>APPROVAL REQUIRED</strong> — policy thresholds were exceeded. Review mutations before committing or rolling back.
        </div>
      )}
      {session.gate_decision === "BLOCK" && !isFinalized && (
        <div className="px-4 py-2 bg-[rgba(239,68,68,0.08)] border-b border-[rgba(239,68,68,0.2)] text-xs text-[#EF4444]">
          Gate decision <strong>BLOCK</strong> — commit is permanently denied. Only rollback is available.
        </div>
      )}
      {hasConflict && (
        <div className="px-4 py-3 bg-[rgba(245,158,11,0.08)] border-b border-[rgba(245,158,11,0.3)] text-xs space-y-2">
          <div className="text-[#F59E0B] font-semibold">
            COMMIT CONFLICT — Production rows changed since baseline. Nothing was applied; rollback or resolve.
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-[11px] border-collapse">
              <thead>
                <tr className="text-[#94A3B8] border-b border-[rgba(245,158,11,0.2)]">
                  <th className="py-1 pr-3">Entity</th>
                  <th className="py-1 pr-3">Conflict</th>
                  <th className="py-1 pr-3">Expected Ver</th>
                  <th className="py-1">Actual Ver</th>
                </tr>
              </thead>
              <tbody>
                {displayedConflicts.map((c) => (
                  <tr key={c.entity_id} className="text-[#F8FAFC] border-b border-[rgba(245,158,11,0.1)]">
                    <td className="py-1 pr-3">{c.entity_id}</td>
                    <td className="py-1 pr-3 text-[#F59E0B]">{c.conflict_type}</td>
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
        <div className="px-4 py-2 bg-[rgba(239,68,68,0.08)] border-b border-[rgba(239,68,68,0.2)] text-xs text-[#EF4444]">
          <strong>FAILED</strong> — last {fin.action} attempt at {fmt(fin.timestamp)} failed. Production is unchanged.
        </div>
      )}
      {isFinalized && fin && (
        <div className="px-4 py-2 bg-[#0D1320] border-b border-[#263247] text-xs text-[#CBD5E1] flex flex-wrap items-center gap-3">
          <span>
            <strong>FINALIZED</strong> ({fin.action} · {fin.status}) by{" "}
            <span className="font-mono text-[#F8FAFC]">{fin.actor}</span> at {fmt(fin.timestamp)}
          </span>
          {fin.ledger_id && (
            <span className="font-mono text-[#94A3B8]">
              Ledger: <span className="text-[#22C55E]">{fin.ledger_id}</span>
            </span>
          )}
          {fin.recovered && (
            <Badge label="Recovered" variant="cyan" />
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-[#263247] bg-[#0D1320]">
        {TABS.map(({ key, label, count }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-4 py-2 text-xs font-semibold transition-colors whitespace-nowrap ${
              tab === key
                ? "text-[#3B82F6] border-b-2 border-[#3B82F6]"
                : "text-[#94A3B8] hover:text-[#F8FAFC]"
            }`}
          >
            {label}
            {count !== undefined && (
              <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[10px] ${
                count > 0 ? "bg-[rgba(59,130,246,0.2)] text-[#3B82F6]" : "bg-[#263247] text-[#94A3B8]"
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
                <span className="text-[#3B82F6]">~{session.mutation_counts.updated} upd</span>
                {" · "}
                <span className="text-[#EF4444]">-{session.mutation_counts.deleted} del</span>
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
                <span className="text-[#EF4444]">{session.risk_summary.block_count} block</span>,{" "}
                <span className="text-[#F59E0B]">{session.risk_summary.require_approval_count} req_approval</span>
              </span>
            } />
            <InfoRow label="Summary" value={
              /* summary_text is backend-generated display text */
              <span className="text-[#CBD5E1]">{session.risk_summary.summary_text}</span>
            } />
          </div>
        )}

        {tab === "mutations" && (
          <MutationTable mutations={session.mutations} />
        )}

        {tab === "violations" && (
          <ViolationList violations={session.policy_violations} />
        )}

        {tab === "summary" && (
          <div className="space-y-2">
            {session.agent_summary ? (
              /* agent_summary rendered as plain text (§3.8) */
              <p className="text-sm text-[#CBD5E1] whitespace-pre-wrap">{session.agent_summary}</p>
            ) : (
              <p className="text-[#94A3B8] text-sm">No agent summary provided.</p>
            )}
          </div>
        )}
      </div>

      {/* Reviewer action panel */}
      {!isFinalized && (
        <div className="border-t border-[#263247] p-4 bg-[#0D1320] space-y-3">
          <div className="text-xs font-semibold uppercase tracking-widest text-[#94A3B8] mb-1">
            Reviewer Action
          </div>

          {noToken && (
            <div className="text-xs text-[#F59E0B] bg-[rgba(245,158,11,0.08)] border border-[rgba(245,158,11,0.3)] rounded px-3 py-2">
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
                flex-1 px-3 py-2 bg-[#0D1320] border border-[#263247] rounded
                text-xs text-[#F8FAFC] placeholder-[#94A3B8]
                focus:outline-none focus:border-[#3B82F6]
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
                flex-1 px-3 py-2 bg-[#0D1320] border border-[#263247] rounded
                text-xs text-[#F8FAFC] placeholder-[#94A3B8]
                focus:outline-none focus:border-[#3B82F6]
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
                bg-[#3B82F6] text-white
                hover:bg-[#2563EB] hover:shadow-[0_0_12px_rgba(59,130,246,0.35)]
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
                bg-[rgba(239,68,68,0.15)] text-[#EF4444] border border-[#EF4444]
                hover:bg-[#EF4444] hover:text-white
                disabled:opacity-40 disabled:cursor-not-allowed
              "
            >
              {working ? "Working…" : "✕ Rollback"}
            </button>
          </div>

          {actionError && (
            <div className="text-xs text-[#EF4444] bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.3)] rounded px-3 py-2">
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
