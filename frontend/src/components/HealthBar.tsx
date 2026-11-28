/**
 * Health bar: shows backend status and invoice count.
 * Polls GET /api/health every 2000ms as specified in API_CONTRACT.md section 1.
 */

"use client";

import { useEffect, useState } from "react";
import { fetchHealth, MOCK_MODE, POLL_INTERVAL_MS } from "@/lib/api-client";
import type { HealthResponse } from "@/lib/types";

interface HealthBarProps {
  onError?: (msg: string) => void;
}

export function HealthBar({ onError }: HealthBarProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    async function poll() {
      try {
        const h = await fetchHealth();
        if (alive) { setHealth(h); setError(null); }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        if (alive) { setError(msg); onError?.(msg); }
      }
    }

    poll();
    const id = setInterval(poll, POLL_INTERVAL_MS);
    return () => { alive = false; clearInterval(id); };
  }, [onError]);

  const online = health !== null && error === null;

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-[#0D1320] border-b border-[#263247] text-xs font-mono">
      {/* Backend status indicator */}
      <span className="flex items-center gap-1.5">
        <span
          className={`w-2 h-2 rounded-full ${online ? "bg-[#22C55E] shadow-[0_0_6px_rgba(34,197,94,0.6)]" : "bg-[#EF4444] shadow-[0_0_6px_rgba(239,68,68,0.6)]"}`}
        />
        <span className={online ? "text-[#22C55E]" : error ? "text-[#EF4444]" : "text-[#F59E0B]"}>
          {online ? "Backend Online" : error ? "Backend Offline" : "Checking backend…"}
        </span>
      </span>

      {health && (
        <>
          <span className="text-[#263247]">|</span>
          <span className="text-[#94A3B8]">
            Invoices: <span className="text-[#F8FAFC] tnum">{health.prod_invoice_count}</span>
          </span>
          <span className="text-[#263247]">|</span>
          <span className="text-[#94A3B8]">
            Active Sessions: <span className="text-[#F8FAFC] tnum">{health.active_sessions}</span>
          </span>
          <span className="text-[#263247]">|</span>
          <span className="text-[#94A3B8]">
            DB: {health.prod_db_connected && health.meta_db_connected ? (
              <span className="text-[#22C55E]">Connected</span>
            ) : (
              <span className="text-[#EF4444]">Degraded</span>
            )}
          </span>
        </>
      )}

      {error && (
        <>
          <span className="text-[#263247]">|</span>
          <span className="text-[#EF4444] truncate max-w-xs" title={error}>{error}</span>
        </>
      )}

      <span className="ml-auto text-[#263247]">
        {MOCK_MODE && (
          <span className="text-[#F59E0B] border border-[rgba(245,158,11,0.3)] px-2 py-0.5 rounded text-[10px] uppercase tracking-widest">
            Mock Mode
          </span>
        )}
      </span>
    </div>
  );
}
