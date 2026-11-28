/**
 * Mutation diff table: shows before/after invoice values and policy decisions.
 * Plain text rendering for all agent-controlled fields (API_CONTRACT.md §3.8).
 */

"use client";

import { useState } from "react";
import type { Mutation, Invoice } from "@/lib/types";

interface MutationTableProps {
  mutations: {
    inserted: Mutation[];
    updated: Mutation[];
    deleted: Mutation[];
  };
}

function formatValue(key: string, val: unknown, currency: string): string {
  if (val === null || val === undefined) return "—";
  if (key === "amount_cents" && typeof val === "number") {
    return `${currency} ${(val / 100).toFixed(2)}`;
  }
  return String(val);
}

function InvoiceRow({ invoice, changed }: { invoice: Invoice; changed?: string[] }) {
  const fields: (keyof Invoice)[] = [
    "id", "customer_name", "customer_email", "amount_cents",
    "currency", "status", "due_date", "notes", "version",
  ];

  return (
    <table className="w-full border-collapse text-xs">
      <tbody>
        {fields.map((f) => {
          const isChanged = changed?.includes(f);
          return (
            <tr key={f} className={isChanged ? "bg-[rgba(245,158,11,0.08)]" : ""}>
              <td className="px-2 py-1 text-[#52525B] font-mono w-36 whitespace-nowrap border-b border-[#E5E6E8]">
                {f}
              </td>
              <td className={`px-2 py-1 font-mono border-b border-[#E5E6E8] ${isChanged ? "text-[#E56828]" : "text-[#191A1C]"}`}>
                {/* Plain text — invoice fields are never redacted (§3.7) */}
                {formatValue(f, invoice[f], invoice.currency)}
                {isChanged && (
                  <span className="ml-2 text-[10px] text-[#E56828] uppercase tracking-widest">changed</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function MutationCard({ mutation }: { mutation: Mutation }) {
  const typeColors = {
    INSERT: "text-[#22C55E] border-[rgba(34,197,94,0.3)]",
    UPDATE: "text-[#EF492F] border-[rgba(239,73,47,0.2)]",
    DELETE: "text-[#EF492F] border-[rgba(239,73,47,0.3)]",
  };
  const policyColors = {
    PENDING:          "text-[#52525B]",
    ALLOW:            "text-[#EF492F]",
    REQUIRE_APPROVAL: "text-[#E56828]",
    BLOCK:             "text-[#EF492F]",
  };

  return (
    <div className="bg-[#FFFFFF] border border-[#E5E6E8] rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold uppercase font-mono px-2 py-0.5 rounded border ${typeColors[mutation.mutation_type]}`}>
            {mutation.mutation_type}
          </span>
          {/* entity_id is a business key like INV-0042, not agent-generated text */}
          <span className="text-sm font-mono text-[#191A1C]">{mutation.entity_id}</span>
          <span className="text-xs text-[#52525B] font-mono">via {mutation.tool_name}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-[#52525B]">Policy:</span>
          <span className={`font-semibold ${policyColors[mutation.policy_decision]}`}>
            {mutation.policy_decision}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {mutation.before && (
          <div>
            <div className="text-[11px] uppercase tracking-widest text-[#52525B] mb-1">Before</div>
            <div className="border border-[#E5E6E8] rounded overflow-hidden">
              <InvoiceRow
                invoice={mutation.before}
                changed={mutation.mutation_type === "UPDATE" ? mutation.changed_fields : undefined}
              />
            </div>
          </div>
        )}
        {mutation.after && (
          <div>
            <div className="text-[11px] uppercase tracking-widest text-[#52525B] mb-1">After</div>
            <div className="border border-[rgba(239,73,47,0.2)] rounded overflow-hidden">
              <InvoiceRow
                invoice={mutation.after}
                changed={mutation.mutation_type === "UPDATE" ? mutation.changed_fields : undefined}
              />
            </div>
          </div>
        )}
        {mutation.mutation_type === "DELETE" && !mutation.after && (
          <div className="flex items-center justify-center border border-[rgba(239,73,47,0.3)] rounded h-20">
            <span className="text-[#EF492F] text-xs uppercase tracking-widest">Row will be deleted</span>
          </div>
        )}
        {mutation.mutation_type === "INSERT" && !mutation.before && (
          <div className="flex items-center justify-center border border-[rgba(34,197,94,0.3)] rounded h-20">
            <span className="text-[#22C55E] text-xs uppercase tracking-widest">New row (no baseline)</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function MutationTable({ mutations }: MutationTableProps) {
  const [showAll, setShowAll] = useState(false);
  const all = [
    ...mutations.updated,
    ...mutations.deleted,
    ...mutations.inserted,
  ];

  if (all.length === 0) {
    return (
      <div className="text-[#52525B] text-sm py-4 text-center">
        No invoice mutations in this session.
      </div>
    );
  }

  // Show first 50 — bulk sessions can have 420+ mutations; pagination out of MVP scope
  const shown = showAll ? all : all.slice(0, 50);
  const truncated = all.length > 50;

  return (
    <div className="space-y-3">
      {shown.map((m) => (
        <MutationCard key={m.mutation_id} mutation={m} />
      ))}
      {truncated && (
        <div className="text-center text-xs text-[#52525B] py-2">
          Showing {shown.length} of {all.length} mutations. {" "}
          <button
            type="button"
            className="text-[#EF492F] underline"
            onClick={() => setShowAll((value) => !value)}
          >
            {showAll ? "Show first 50" : `Show all ${all.length}`}
          </button>
        </div>
      )}
    </div>
  );
}
