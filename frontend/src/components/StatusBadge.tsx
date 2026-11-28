/**
 * State badges for execution_status, gate_decision, and human_review_status.
 * Uses design tokens from DESIGN.md / Stitch color system.
 * Renders as plain text in a styled pill — no dangerouslySetInnerHTML.
 */

import type {
  ExecutionStatus,
  GateDecision,
  HumanReviewStatus,
  RiskLevel,
} from "@/lib/types";

type BadgeVariant = "ok" | "warn" | "danger" | "blue" | "cyan" | "muted";

interface BadgeProps {
  label: string;
  variant: BadgeVariant;
  pulse?: boolean;
}

const VARIANT_STYLES: Record<BadgeVariant, string> = {
  ok:     "bg-[rgba(34,197,94,0.1)]  text-[#22C55E] border border-[rgba(34,197,94,0.3)]",
  warn:   "bg-[rgba(245,158,11,0.1)] text-[#F59E0B] border border-[rgba(245,158,11,0.3)]",
  danger: "bg-[rgba(239,68,68,0.1)]  text-[#EF4444] border border-[rgba(239,68,68,0.3)]",
  blue:   "bg-[rgba(59,130,246,0.1)] text-[#3B82F6] border border-[rgba(59,130,246,0.3)]",
  cyan:   "bg-[rgba(6,182,212,0.1)]  text-[#06B6D4] border border-[rgba(6,182,212,0.3)]",
  muted:  "bg-[rgba(148,163,184,0.1)] text-[#94A3B8] border border-[rgba(148,163,184,0.3)]",
};

export function Badge({ label, variant, pulse }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold uppercase tracking-widest font-sans ${VARIANT_STYLES[variant]}`}
    >
      {pulse && (
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full animate-pulse ${
            variant === "ok" ? "bg-[#22C55E]" :
            variant === "warn" ? "bg-[#F59E0B]" :
            variant === "danger" ? "bg-[#EF4444]" :
            variant === "blue" ? "bg-[#3B82F6]" :
            variant === "cyan" ? "bg-[#06B6D4]" : "bg-[#94A3B8]"
          }`}
        />
      )}
      {label}
    </span>
  );
}

export function ExecutionStatusBadge({ status }: { status: ExecutionStatus }) {
  const map: Record<ExecutionStatus, { label: string; variant: BadgeVariant; pulse?: boolean }> = {
    ACTIVE:      { label: "Active",      variant: "blue",  pulse: true },
    COMPLETED:   { label: "Completed",   variant: "cyan" },
    COMMITTED:   { label: "Committed",   variant: "ok" },
    ROLLED_BACK: { label: "Rolled Back", variant: "muted" },
  };
  const cfg = map[status];
  return <Badge {...cfg} />;
}

export function GateDecisionBadge({ decision }: { decision: GateDecision }) {
  // Important: ALLOW does NOT mean auto-approved. Reviewer must still commit.
  const map: Record<GateDecision, { label: string; variant: BadgeVariant }> = {
    PENDING:          { label: "Pending Review",    variant: "cyan" },
    ALLOW:            { label: "Allow (needs commit)", variant: "blue" },
    REQUIRE_APPROVAL: { label: "Approval Required", variant: "warn" },
    BLOCK:            { label: "Blocked",            variant: "danger" },
  };
  const cfg = map[decision];
  return <Badge label={cfg.label} variant={cfg.variant} />;
}

export function HumanReviewBadge({ status }: { status: HumanReviewStatus }) {
  const map: Record<HumanReviewStatus, { label: string; variant: BadgeVariant }> = {
    PENDING:  { label: "Pending",  variant: "muted" },
    APPROVED: { label: "Approved", variant: "ok" },
    REJECTED: { label: "Rejected", variant: "danger" },
  };
  const cfg = map[status];
  return <Badge label={cfg.label} variant={cfg.variant} />;
}

export function RiskBadge({ level }: { level: RiskLevel }) {
  const map: Record<RiskLevel, { label: string; variant: BadgeVariant }> = {
    LOW:      { label: "Low Risk",      variant: "ok" },
    MEDIUM:   { label: "Medium Risk",   variant: "warn" },
    HIGH:     { label: "High Risk",     variant: "warn" },
    CRITICAL: { label: "Critical Risk", variant: "danger" },
  };
  const cfg = map[level];
  return <Badge label={cfg.label} variant={cfg.variant} />;
}
