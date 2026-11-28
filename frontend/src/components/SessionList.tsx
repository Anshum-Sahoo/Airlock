/**
 * Session list table with status badges.
 * Renders agent-controlled text as plain text (no dangerouslySetInnerHTML).
 */

"use client";

import type { SessionSummary } from "@/lib/types";
import {
  ExecutionStatusBadge,
  GateDecisionBadge,
  HumanReviewBadge,
  RiskBadge,
} from "./StatusBadge";

interface SessionListProps {
  sessions: SessionSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
}

function fmt(ts: string): string {
  try {
    return new Date(ts).toLocaleString(undefined, {
      month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: false,
    });
  } catch {
    return ts;
  }
}

export function SessionList({ sessions, selectedId, onSelect, loading }: SessionListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-32 text-[#94A3B8] text-sm">
        Loading sessions…
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-[#94A3B8] text-sm">
        No sessions found.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="bg-[#0D1320] border-b border-[#263247]">
            {["Agent", "Task", "Created", "Exec Status", "Gate Decision", "Review", "Risk", "Mutations"].map((h) => (
              <th
                key={h}
                className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-widest text-[#94A3B8] whitespace-nowrap"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => {
            const isSelected = s.session_id === selectedId;
            return (
              <tr
                key={s.session_id}
                onClick={() => onSelect(s.session_id)}
                className={`
                  border-b border-[#263247] cursor-pointer transition-colors
                  ${isSelected
                    ? "bg-[#172033] border-l-2 border-l-[#3B82F6]"
                    : "bg-[#111827] hover:bg-[#172033]"}
                `}
              >
                {/* Agent name — plain text, agent-controlled */}
                <td className="px-3 py-2 font-mono text-[#F8FAFC] whitespace-nowrap max-w-[120px] truncate">
                  {s.agent_name}
                </td>
                {/* Task description — plain text, agent-controlled */}
                <td className="px-3 py-2 text-[#CBD5E1] max-w-[200px] truncate" title={s.task_description ?? ""}>
                  {s.task_description ?? "—"}
                </td>
                <td className="px-3 py-2 text-[#94A3B8] whitespace-nowrap font-mono tnum">
                  {fmt(s.created_at)}
                </td>
                <td className="px-3 py-2 whitespace-nowrap">
                  <ExecutionStatusBadge status={s.execution_status} />
                </td>
                <td className="px-3 py-2 whitespace-nowrap">
                  <GateDecisionBadge decision={s.gate_decision} />
                </td>
                <td className="px-3 py-2 whitespace-nowrap">
                  <HumanReviewBadge status={s.human_review_status} />
                </td>
                <td className="px-3 py-2 whitespace-nowrap">
                  <RiskBadge level={s.risk_summary.overall_risk_level} />
                </td>
                <td className="px-3 py-2 font-mono tnum text-[#94A3B8] whitespace-nowrap">
                  <span className="text-[#22C55E]">+{s.mutation_counts.inserted}</span>
                  {" / "}
                  <span className="text-[#3B82F6]">~{s.mutation_counts.updated}</span>
                  {" / "}
                  <span className="text-[#EF4444]">-{s.mutation_counts.deleted}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
