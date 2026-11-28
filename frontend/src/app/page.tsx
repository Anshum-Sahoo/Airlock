/**
 * Airlock Reviewer Dashboard — main page.
 *
 * Security model summary (API_CONTRACT.md §3.3):
 * - reviewerToken is React state (page-memory) only.
 * - Never in localStorage, sessionStorage, cookies, URLs, NEXT_PUBLIC_*, or logs.
 * - Requires re-entry on page reload.
 * - No backend secrets or NVIDIA credentials in this file or any import.
 *
 * Polling: GET /api/sessions every 2000ms (contract §1 specifies 2s interval).
 */

"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { HealthBar } from "@/components/HealthBar";
import { TokenInput } from "@/components/TokenInput";
import { SessionList } from "@/components/SessionList";
import { SessionDetail } from "@/components/SessionDetail";
import { fetchSessions, fetchSession, MOCK_MODE } from "@/lib/api-client";
import type { SessionSummary, SessionManifest } from "@/lib/types";

export default function DashboardPage() {
  // ---- Reviewer token: page-memory ONLY ----
  const [reviewerToken, setReviewerToken] = useState<string>("");
  const handleTokenSet = useCallback((t: string) => {
    // Not logged, not stored anywhere except this state variable
    setReviewerToken(t);
  }, []);

  // ---- Session list ----
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);

  const pollSessions = useCallback(async () => {
    try {
      const res = await fetchSessions();
      setSessions(res.sessions);
      setSessionsError(null);
    } catch (e) {
      setSessionsError(e instanceof Error ? e.message : String(e));
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    pollSessions();
    const id = setInterval(pollSessions, 2000);
    return () => clearInterval(id);
  }, [pollSessions]);

  // ---- Selected session detail ----
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionManifest | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    setDetailError(null);
    try {
      const m = await fetchSession(id);
      setDetail(m);
    } catch (e) {
      setDetailError(e instanceof Error ? e.message : String(e));
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  function handleSelectSession(id: string) {
    if (id === selectedId) return;
    setSelectedId(id);
    setDetail(null);
    loadDetail(id);
  }

  // Auto-refresh selected detail every 5s
  const selectedIdRef = useRef<string | null>(null);
  selectedIdRef.current = selectedId;

  useEffect(() => {
    const id = setInterval(() => {
      if (selectedIdRef.current) {
        loadDetail(selectedIdRef.current);
      }
    }, 5000);
    return () => clearInterval(id);
  }, [loadDetail]);

  function handleActionComplete(updated: SessionManifest) {
    setDetail(updated);
    // Also update the summary in the list
    setSessions((prev) =>
      prev.map((s) =>
        s.session_id === updated.session_id
          ? {
              ...s,
              execution_status: updated.execution_status,
              gate_decision: updated.gate_decision,
              human_review_status: updated.human_review_status,
            }
          : s
      )
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#090D16]">
      {/* Top health bar + meta */}
      <HealthBar />

      {/* Top nav bar */}
      <header className="px-6 py-3 bg-[#0D1320] border-b border-[#263247] flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-[#F8FAFC] tracking-tight">
            ⬡ Airlock
          </span>
          <span className="text-xs text-[#94A3B8] border-l border-[#263247] pl-3">
            Reviewer Dashboard
          </span>
          {MOCK_MODE && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-[rgba(245,158,11,0.15)] border border-[rgba(245,158,11,0.3)] text-[#F59E0B] uppercase tracking-widest">
              Mock Data
            </span>
          )}
        </div>
        <TokenInput
          onTokenSet={handleTokenSet}
          hasToken={!!reviewerToken}
        />
      </header>

      {/* Main layout: session list + detail */}
      <main className="flex flex-col lg:flex-row flex-1 overflow-hidden">
        {/* Left: session list */}
        <div className="lg:w-[55%] border-r border-[#263247] overflow-auto">
          <div className="px-4 py-3 border-b border-[#263247] bg-[#0D1320] flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-widest text-[#94A3B8]">
              Agent Sessions
            </span>
            <span className="text-xs font-mono tnum text-[#94A3B8]">
              {sessions.length} session{sessions.length !== 1 ? "s" : ""}
            </span>
          </div>

          {sessionsError && (
            <div className="px-4 py-2 text-xs text-[#EF4444] bg-[rgba(239,68,68,0.08)] border-b border-[rgba(239,68,68,0.3)]">
              {sessionsError}
            </div>
          )}

          <SessionList
            sessions={sessions}
            selectedId={selectedId}
            onSelect={handleSelectSession}
            loading={sessionsLoading}
          />
        </div>

        {/* Right: session detail */}
        <div className="flex-1 overflow-auto p-4">
          {!selectedId && (
            <div className="flex flex-col items-center justify-center h-64 text-center space-y-2">
              <span className="text-3xl">⬡</span>
              <p className="text-[#94A3B8] text-sm">
                Select a session to review its mutations, violations, and take action.
              </p>
            </div>
          )}

          {selectedId && detailLoading && !detail && (
            <div className="flex items-center justify-center h-32 text-[#94A3B8] text-sm">
              Loading session…
            </div>
          )}

          {detailError && (
            <div className="px-4 py-3 text-xs text-[#EF4444] bg-[rgba(239,68,68,0.08)] border border-[rgba(239,68,68,0.3)] rounded">
              {detailError}
            </div>
          )}

          {detail && (
            <SessionDetail
              session={detail}
              reviewerToken={reviewerToken}
              onClearToken={() => setReviewerToken("")}
              onRefresh={() => {
                pollSessions();
                loadDetail(detail.session_id);
              }}
              onActionComplete={handleActionComplete}
            />
          )}
        </div>
      </main>
    </div>
  );
}
