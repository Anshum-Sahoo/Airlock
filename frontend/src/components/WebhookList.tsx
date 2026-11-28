"use client";

import type { StagedWebhook } from "@/lib/types";
import { Badge } from "./StatusBadge";

interface WebhookListProps {
  webhooks: StagedWebhook[];
}

export function WebhookList({ webhooks }: WebhookListProps) {
  if (webhooks.length === 0) {
    return <p className="py-4 text-center text-sm text-[#52525B]">No staged webhooks.</p>;
  }

  return (
    <div className="space-y-3">
      <p className="border border-[rgba(245,158,11,0.3)] bg-[rgba(245,158,11,0.08)] px-3 py-2 text-xs text-[#E56828]">
        Webhooks are recorded intent only. Airlock never dispatches them.
      </p>
      {webhooks.map((webhook) => (
        <article key={webhook.webhook_id} className="rounded border border-[#E5E6E8] bg-[#FFFFFF] p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-[#191A1C]">{webhook.event_type}</span>
              <Badge label={webhook.status} variant={webhook.status === "STAGED" ? "cyan" : "danger"} />
            </div>
            <time className="font-mono text-[11px] text-[#52525B]">{webhook.staged_at}</time>
          </div>
          <p className="mt-2 break-all font-mono text-xs text-[#52525B]">{webhook.url}</p>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-[#F8F9FA] p-2 text-[11px] text-[#52525B]">{JSON.stringify(webhook.payload, null, 2)}</pre>
        </article>
      ))}
    </div>
  );
}
