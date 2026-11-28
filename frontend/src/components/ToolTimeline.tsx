"use client";

import type { ToolExecution } from "@/lib/types";
import { Badge } from "./StatusBadge";

interface ToolTimelineProps {
  executions: ToolExecution[];
}

const statusVariant = {
  SUCCESS: "ok",
  BLOCKED: "danger",
  ERROR: "warn",
} as const;

const decisionVariant = {
  ALLOW: "blue",
  REQUIRE_APPROVAL: "warn",
  BLOCK: "danger",
} as const;

export function ToolTimeline({ executions }: ToolTimelineProps) {
  if (executions.length === 0) {
    return <p className="py-4 text-center text-sm text-[#94A3B8]">No tool calls recorded.</p>;
  }

  return (
    <ol className="space-y-3">
      {executions.map((execution) => (
        <li key={execution.operation_id} className="rounded border border-[#263247] bg-[#111827] p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm text-[#F8FAFC]">{execution.tool_name}</span>
              <Badge label={execution.status} variant={statusVariant[execution.status]} />
            </div>
            <span className="font-mono text-[11px] text-[#94A3B8]">{execution.executed_at}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
            <span className="text-[#94A3B8]">Tool decision: <Badge label={execution.tool_decision} variant={decisionVariant[execution.tool_decision]} /></span>
            <span className="text-[#94A3B8]">Read only: <span className="text-[#CBD5E1]">{execution.read_only === null ? "Unknown" : String(execution.read_only)}</span></span>
            <span className="text-[#94A3B8]">Mutations recorded: <span className="text-[#CBD5E1]">{execution.mutations_recorded}</span></span>
            {execution.error_code && <span className="text-[#EF4444]">Error: {execution.error_code}</span>}
          </div>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-[#0D1320] p-2 text-[11px] text-[#94A3B8]">{JSON.stringify(execution.arguments, null, 2)}</pre>
        </li>
      ))}
    </ol>
  );
}
