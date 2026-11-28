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
  MEDIUM:   "text-[#E56828] border-[rgba(245,158,11,0.3)]",
  HIGH:     "text-[#E56828] border-[rgba(245,158,11,0.3)]",
  CRITICAL: "text-[#EF492F] border-[rgba(239,73,47,0.3)]",
};

const DECISION_STYLES = {
  ALLOW:            "text-[#EF492F]",
  REQUIRE_APPROVAL: "text-[#E56828]",
  BLOCK:            "text-[#EF492F]",
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
        {violations.map((v, index) => (
        <div
          key={`${v.policy_id}-${v.stage}-${v.operation_id ?? "session"}-${index}`}
          className="bg-[#FFFFFF] border border-[#E5E6E8] rounded-lg p-3 space-y-1"
        >
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <span className={`text-[11px] font-bold font-mono px-1.5 py-0.5 rounded border ${SEVERITY_STYLES[v.severity]}`}>
                {v.severity}
              </span>
              <span className="text-sm font-semibold text-[#191A1C]">{v.policy_id}</span>
              <span className="text-xs text-[#52525B]">{v.policy_name}</span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <span>
                Decision:{" "}
                <span className={`font-bold ${DECISION_STYLES[v.decision]}`}>{v.decision}</span>
              </span>
              <span className="text-[#52525B]">
                Scope: <span className="text-[#52525B]">{v.effect_scope}</span>
              </span>
              <span className="text-[#52525B]">
                Stage: <span className="text-[#52525B]">{v.stage}</span>
              </span>
            </div>
          </div>
          {/* explanation is backend-generated and redacted — plain text */}
          <p className="text-xs text-[#52525B]">{v.explanation}</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[#52525B] font-mono">
            <span>Affected records: {v.affected_record_count ?? "—"}</span>
            <span>Operation: {v.operation_id ?? "session completion"}</span>
            <span>{v.timestamp}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
