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
} from "./StatusBadge";

interface SessionListProps {
  sessions: SessionSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  hasError?: boolean;
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

export function SessionList({ sessions, selectedId, onSelect, loading, hasError = false }: SessionListProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-32 text-[#52525B] text-sm">
        Loading sessions…
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-[#52525B] text-sm">
        {hasError ? "Sessions unavailable." : "No sessions found."}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-b-xl">
      <table className="w-full min-w-[760px] border-collapse text-xs">
        <thead>
          <tr className="bg-[#F8F9FA] border-b border-[#E5E6E8]">
            {[
              { label: "Session", className: "hidden xl:table-cell" },
              { label: "Agent", className: "hidden lg:table-cell" },
              { label: "Task", className: "w-[28%]" },
              { label: "Created", className: "hidden xl:table-cell" },
              { label: "Exec status", className: "w-[120px]" },
              { label: "Gate decision", className: "w-[172px]" },
              { label: "Review", className: "w-[106px]" },
              { label: "Mutations", className: "hidden xl:table-cell" },
            ].map(({ label, className }) => (
              <th
                key={label}
                className={`px-3 py-2.5 text-left text-[9px] font-semibold uppercase tracking-[0.1em] text-[#85878C] whitespace-nowrap ${className}`}
              >
                {label}
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
                  border-b border-[#E5E6E8] cursor-pointer transition-colors
                  ${isSelected
                    ? "bg-[#FDECE9] border-l-2 border-l-[#EF492F]"
                    : "bg-[#FFFFFF] hover:bg-[#FFFFFF]"}
                `}
              >
                <td className="hidden xl:table-cell px-3 py-2.5 font-mono text-[#52525B] whitespace-nowrap">
                  {s.session_id}
                </td>
                {/* Agent name — plain text, agent-controlled */}
                <td className="hidden lg:table-cell px-3 py-2.5 font-mono text-[#191A1C] whitespace-nowrap max-w-[120px] truncate">
                  {s.agent_name}
                </td>
                {/* Task description — plain text, agent-controlled */}
                <td className="px-3 py-2.5 text-[#52525B] max-w-[220px] truncate" title={s.task_description ?? ""}>
                  {s.task_description ?? "—"}
                </td>
                <td className="hidden xl:table-cell px-3 py-2.5 text-[#52525B] whitespace-nowrap font-mono tnum">
                  {fmt(s.created_at)}
                </td>
                <td className="px-3 py-2.5 whitespace-nowrap">
                  <ExecutionStatusBadge status={s.execution_status} />
                </td>
                <td className="px-3 py-2.5 whitespace-nowrap">
                  <GateDecisionBadge decision={s.gate_decision} />
                </td>
                <td className="px-3 py-2.5 whitespace-nowrap">
                  <HumanReviewBadge status={s.human_review_status} />
                </td>
                <td className="hidden xl:table-cell px-3 py-2.5 font-mono tnum text-[#52525B] whitespace-nowrap">
                  <span className="text-[#191A1C]">{s.mutation_counts.total}</span>
                  {" "}
                  <span className="text-[#22C55E]">+{s.mutation_counts.inserted}</span>
                  {" / "}
                  <span className="text-[#EF492F]">~{s.mutation_counts.updated}</span>
                  {" / "}
                  <span className="text-[#EF492F]">-{s.mutation_counts.deleted}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
