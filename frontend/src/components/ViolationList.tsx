/**
 * Policy violations panel.
 * Renders violation explanations as plain text (§3.8 of API_CONTRACT.md).
 */

"use client";

import type { PolicyViolation } from "@/lib/types";

interface ViolationListProps {
  violations: PolicyViolation[];
}

const SEVERITY_STYLES = {
  LOW:      "text-[#22C55E] border-[rgba(34,197,94,0.3)]",
  MEDIUM:   "text-[#F59E0B] border-[rgba(245,158,11,0.3)]",
  HIGH:     "text-[#F59E0B] border-[rgba(245,158,11,0.3)]",
  CRITICAL: "text-[#EF4444] border-[rgba(239,68,68,0.3)]",
};

const DECISION_STYLES = {
  ALLOW:            "text-[#3B82F6]",
  REQUIRE_APPROVAL: "text-[#F59E0B]",
  BLOCK:            "text-[#EF4444]",
};

export function ViolationList({ violations }: ViolationListProps) {
  if (violations.length === 0) {
    return (
      <div className="text-[#22C55E] text-sm py-3 text-center">
        ✓ No policy violations recorded.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {violations.map((v) => (
        <div
          key={v.violation_id}
          className="bg-[#111827] border border-[#263247] rounded-lg p-3 space-y-1"
        >
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className={`text-[11px] font-bold font-mono px-1.5 py-0.5 rounded border ${SEVERITY_STYLES[v.severity]}`}>
                {v.severity}
              </span>
              <span className="text-sm font-semibold text-[#F8FAFC]">{v.policy_id}</span>
              <span className="text-xs text-[#94A3B8]">{v.policy_name}</span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span>
                Decision:{" "}
                <span className={`font-bold ${DECISION_STYLES[v.decision]}`}>{v.decision}</span>
              </span>
              <span className="text-[#94A3B8]">
                Scope: <span className="text-[#CBD5E1]">{v.effect_scope}</span>
              </span>
            </div>
          </div>
          {/* explanation is backend-generated and redacted — plain text */}
          <p className="text-xs text-[#CBD5E1]">{v.explanation}</p>
          {v.entity_id && (
            <p className="text-xs text-[#94A3B8] font-mono">Entity: {v.entity_id}</p>
          )}
        </div>
      ))}
    </div>
  );
}
