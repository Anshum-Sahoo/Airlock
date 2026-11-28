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
  ok:     "bg-[#EAF5EF] text-[#347B55] border border-[#D5E9DC]",
  warn:   "bg-[#FFF3E8] text-[#B75E25] border border-[#F4E0CF]",
  danger: "bg-[#FDECE9] text-[#C94D3A] border border-[#F2D6D1]",
  blue:   "bg-[#FFF0EB] text-[#C94D3A] border border-[#F2D9D2]",
  cyan:   "bg-[#F4F5F6] text-[#62666D] border border-[#E6E7E9]",
  muted:  "bg-[#F5F5F6] text-[#686B70] border border-[#E7E8EA]",
};

export function Badge({ label, variant, pulse }: BadgeProps) {
  return (
    <span
      className={`inline-flex min-h-6 items-center gap-1.5 rounded-md border px-2 py-1 text-[10px] font-medium leading-none tracking-normal font-sans ${VARIANT_STYLES[variant]}`}
    >
      {pulse && (
        <span
          className={`inline-block w-1.5 h-1.5 rounded-full animate-pulse ${
            variant === "ok" ? "bg-[#4B9B6B]" :
            variant === "warn" ? "bg-[#E56828]" :
            variant === "danger" ? "bg-[#D85340]" :
            variant === "blue" ? "bg-[#EF492F]" :
            variant === "cyan" ? "bg-[#92959A]" : "bg-[#92959A]"
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
    PENDING:          { label: "Pending Review",    variant: "muted" },
    ALLOW:            { label: "ALLOW · Commit required", variant: "ok" },
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
