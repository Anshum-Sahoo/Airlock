/**
 * Session list table with status badges.
 * Renders agent-controlled text as plain text (no dangerouslySetInnerHTML).
 */

"use client";

import type { SessionSummary } from "@/lib/types";
import {
  ExecutionStatusBadge,
  GateDecisionBadge,

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
      <div className="flex items-center justify-center h-32 text-[#94A3B8] text-sm">
        Loading sessions…
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-[#94A3B8] text-sm">
        {hasError ? "Sessions unavailable." : "No sessions found."}
      </div>
    );
  }

  return (
    <ul className="session-feed" aria-label="Agent sessions">
      {sessions.map(s => (
        <li key={s.session_id}>
          <button type="button" className="session-row" aria-pressed={s.session_id === selectedId}
            onClick={() => onSelect(s.session_id)}>
            <span className="row-top"><strong>{s.agent_name}</strong><GateDecisionBadge decision={s.gate_decision} /></span>
            <span className="row-task">{s.task_description}</span>
            <span className="row-meta"><ExecutionStatusBadge status={s.execution_status} />
              <span>{s.mutation_counts.total} changes</span><time dateTime={s.created_at}>{fmt(s.created_at)}</time></span>
          </button>
        </li>
      ))}
    </ul>
  );
}
