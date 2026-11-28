"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { MutationTable } from "@/components/MutationTable";
import { NewSession } from "@/components/NewSession";
import { TokenInput } from "@/components/TokenInput";
import { SessionList } from "@/components/SessionList";
import { SessionDetail } from "@/components/SessionDetail";
import { fetchSessions, fetchSession, MOCK_MODE, POLL_INTERVAL_MS } from "@/lib/api-client";
import type { SessionSummary, SessionManifest } from "@/lib/types";

type SessionFilter = "all" | "pending" | "approval" | "blocked";

function MetricCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: number | string;
  detail: string;
  tone: "neutral" | "orange" | "red" | "green";
}) {
  const tones = {
    neutral: "bg-[#F8F9FA] text-[#52525B]",
    orange: "bg-[#FFF3E8] text-[#E56828]",
    red: "bg-[#FDECE9] text-[#EF492F]",
    green: "bg-[#EAF5EF] text-[#52525B]",
  };
  const dotTones = {
    neutral: "bg-[#52525B]",
    orange: "bg-[#E56828]",
    red: "bg-[#EF492F]",
    green: "bg-[#22C55E]",
  };

  return (
    <article className="rounded-xl border border-[#E5E6E8] bg-white p-4 shadow-[0_2px_8px_rgba(20,24,35,0.035)]">
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.11em] text-[#52525B]">{label}</p>
        <span className={`grid h-8 w-8 place-items-center rounded-lg ${tones[tone]}`} aria-hidden="true">
          <span className={`h-2 w-2 rounded-full ${dotTones[tone]}`} />
        </span>
      </div>
      <p className="mt-3 text-[27px] font-semibold leading-none tracking-[-0.04em] text-[#191A1C]">{value}</p>
      <p className="mt-2 text-[11px] text-[#85878C]">{detail}</p>
    </article>
  );
}

function SessionOverview({ sessions }: { sessions: SessionSummary[] }) {
  const counts = [
    { label: "Allow", color: "#22C55E", value: sessions.filter((s) => s.gate_decision === "ALLOW").length },
    { label: "Approval required", color: "#E56828", value: sessions.filter((s) => s.gate_decision === "REQUIRE_APPROVAL").length },
    { label: "Blocked", color: "#EF492F", value: sessions.filter((s) => s.gate_decision === "BLOCK").length },
    { label: "Pending decision", color: "#85878C", value: sessions.filter((s) => s.gate_decision === "PENDING").length },
  ];
  const total = Math.max(sessions.length, 1);
  let cursor = 0;
  const stops = counts.map((item) => {
    const start = cursor;
    cursor += (item.value / total) * 100;
    return `${item.color} ${start}% ${cursor}%`;
  }).join(", ");

  return (
    <section className="rounded-xl border border-[#E5E6E8] bg-white p-5 shadow-[0_2px_8px_rgba(20,24,35,0.035)]" aria-labelledby="session-overview-title">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#85878C]">Session overview</p>
          <h2 id="session-overview-title" className="mt-1 text-base font-semibold tracking-tight text-[#191A1C]">Gate decisions</h2>
        </div>
        <span className="rounded-md bg-[#F8F9FA] px-2 py-1 text-[10px] text-[#52525B]">{MOCK_MODE ? "Preview" : "Live"}</span>
      </div>
      <div className="mt-5 flex items-center gap-5">
        <div
          className="grid h-[132px] w-[132px] shrink-0 place-items-center rounded-full"
          style={{ background: sessions.length ? `conic-gradient(${stops})` : "#E5E6E8" }}
          role="img"
          aria-label={`${sessions.length} sessions grouped by gate decision`}
        >
          <div className="grid h-[88px] w-[88px] place-items-center rounded-full bg-white text-center shadow-inner">
            <div><strong className="block text-[25px] font-semibold leading-none text-[#191A1C]">{sessions.length}</strong><span className="mt-1 block text-[10px] text-[#85878C]">sessions</span></div>
          </div>
        </div>
        <ul className="min-w-0 flex-1 space-y-3">
          {counts.map((item) => (
            <li key={item.label} className="flex items-center justify-between gap-2 text-xs">
              <span className="flex min-w-0 items-center gap-2 text-[#52525B]"><i className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />{item.label}</span>
              <span className="font-semibold tabular-nums text-[#191A1C]">{item.value}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="mt-5 rounded-lg bg-[#F8F9FA] px-3 py-2.5 text-[11px] leading-relaxed text-[#52525B]">
        <span className="font-semibold text-[#191A1C]">Review required:</span> ALLOW still needs a human reviewer to commit.
      </div>
    </section>
  );
}

const pages = [
  ["/", "Overview"],
  ["/sessions", "Agent Sessions"],
  ["/session-details", "Session Details"],
  ["/mutations", "Mutations & Changes"],
  ["/settings", "Settings"],
] as const;

export default function Dashboard({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const title = pages.find(([url]) => url === path)?.[1];

  const [reviewerToken, setReviewerToken] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionTotal, setSessionTotal] = useState(0);
  const [sessionsLoading, setSessionsLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionManifest | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [filter, setFilter] = useState<SessionFilter>("all");
  const [query, setQuery] = useState("");

  const selected = useRef<string | null>(null);
  const detailRequest = useRef(0);
  const listRequest = useRef(0);

  const pollSessions = useCallback(async () => {
    const request = ++listRequest.current;
    try {
      const response = await fetchSessions();
      if (request !== listRequest.current) return;
      setSessions(response.sessions);
      setSessionTotal(response.total);
      setSessionsError(null);
    } catch (error) {
      if (request !== listRequest.current) return;
      setSessionsError(error instanceof Error ? error.message : String(error));
    } finally {
      if (request === listRequest.current) setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    pollSessions();
    const timer = setInterval(pollSessions, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [pollSessions]);

  const loadDetail = useCallback(async (id: string) => {
    if (selected.current !== id) return;
    const request = ++detailRequest.current;
    setDetailLoading(true);
    setDetailError(null);
    try {
      const manifest = await fetchSession(id);
      if (request === detailRequest.current) setDetail(manifest);
    } catch (error) {
      if (request !== detailRequest.current) return;
      setDetailError(error instanceof Error ? error.message : String(error));
      setDetail(null);
    } finally {
      if (request === detailRequest.current) setDetailLoading(false);
    }
  }, []);

  function selectSession(id: string) {
    if (path === "/sessions") router.push("/session-details");
    if (id === selectedId) return;
    selected.current = id;
    setSelectedId(id);
    setDetail(null);
    loadDetail(id);
  }

  useEffect(() => {
    if (!selectedId || (detail?.execution_status !== "ACTIVE" && detail?.execution_status !== "COMPLETED")) return;
    const timer = setInterval(() => loadDetail(selectedId), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [detail?.execution_status, loadDetail, selectedId]);

  const filteredSessions = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return sessions.filter((session) => {
      const matchesFilter = filter === "all" ||
        (filter === "pending" && session.human_review_status === "PENDING") ||
        (filter === "approval" && session.gate_decision === "REQUIRE_APPROVAL") ||
        (filter === "blocked" && session.gate_decision === "BLOCK");
      const matchesQuery = !normalizedQuery || [session.session_id, session.agent_name, session.task_description ?? ""]
        .some((value) => value.toLowerCase().includes(normalizedQuery));
      return matchesFilter && matchesQuery;
    });
  }, [filter, query, sessions]);

  const pendingCount = sessions.filter((session) => session.human_review_status === "PENDING").length;
  const approvalCount = sessions.filter((session) => session.gate_decision === "REQUIRE_APPROVAL").length;
  const blockedCount = sessions.filter((session) => session.gate_decision === "BLOCK").length;

  function handleActionComplete(updated: SessionManifest) {
    if (updated.session_id === selected.current) {
      ++detailRequest.current;
      setDetailLoading(false);
      setDetailError(null);
      setDetail(updated);
    }
    ++listRequest.current;
    void pollSessions();
    setSessions((current) => current.map((session) => session.session_id === updated.session_id
      ? { ...session, execution_status: updated.execution_status, gate_decision: updated.gate_decision, human_review_status: updated.human_review_status }
      : session));
  }

  const filters: { value: SessionFilter; label: string }[] = [
    { value: "all", label: "All sessions" },
    { value: "pending", label: "Pending review" },
    { value: "approval", label: "Approval required" },
    { value: "blocked", label: "Blocked" },
  ];

  return (
    <div className="min-h-screen bg-[#F4F5F7] text-[#191A1C]">
      <div className="flex min-h-screen flex-col sm:flex-row">
        <aside className="flex w-full sm:w-[190px] shrink-0 flex-col border-r border-[#E5E6E8] bg-white px-3.5 py-5 sm:flex xl:w-[220px] xl:px-4">
          <div className="flex items-center gap-2.5 px-1">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-[#191A1C] text-sm text-white">⬡</span>
            <div><p className="text-sm font-bold tracking-tight">Airlock</p><p className="text-[9px] font-medium uppercase tracking-[0.14em] text-[#85878C]">Security gateway</p></div>
          </div>
          <p className="mb-2 mt-9 px-2 text-[9px] font-semibold uppercase tracking-[0.16em] text-[#85878C]">Workspace</p>
          <nav className="flex flex-wrap gap-1 sm:flex-col" aria-label="Main navigation">
            {pages.map(([url, label]) => (
              <Link key={url} href={url} aria-current={path === url ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-sm font-medium ${path === url ? "bg-[#FFF3E8] text-[#B74615]" : "text-[#52525B] hover:bg-gray-100"}`}>
                {label}
              </Link>
            ))}
          </nav>
          <div className="mt-auto hidden sm:block rounded-xl bg-[#F8F9FA] p-3.5">
            <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#85878C]">Review policy</p>
            <p className="mt-2 text-[11px] leading-relaxed text-[#52525B]">Every proposed change waits for a human decision before production.</p>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header id="overview" className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E5E6E8] bg-white px-5 py-4 sm:px-7">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.13em] text-[#85878C]">Airlock / {title}</p>
              <h1 className="mt-1 text-[20px] font-semibold tracking-[-0.035em] text-[#191A1C]">{title}</h1>
              <p className="mt-0.5 text-[11px] text-[#85878C]">Review agent activity and proposed changes before they reach production.</p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              {MOCK_MODE && <span className="rounded-md border border-[#E56828] bg-[#FFF3E8] px-2 py-1 text-[9px] font-semibold uppercase tracking-[0.12em] text-[#E56828]">Mock preview</span>}
              {path !== "/settings" && <TokenInput onTokenSet={setReviewerToken} hasToken={!!reviewerToken} />}
            </div>
          </header>

          <main className="mx-auto max-w-[1600px] space-y-5 px-4 py-5 sm:px-7 sm:py-6">

            {path === "/" && <section className="grid grid-cols-2 gap-3 xl:grid-cols-4" aria-label="Session summary">
              <MetricCard label="Total sessions" value={sessionTotal} detail="Across all agent runs" tone="neutral" />
              <MetricCard label="Pending review" value={pendingCount} detail="Waiting for a reviewer" tone="orange" />
              <MetricCard label="Approval required" value={approvalCount} detail="Policy thresholds exceeded" tone="orange" />
              <MetricCard label="Blocked" value={blockedCount} detail="Commit is unavailable" tone="red" />
            </section>}
            {path === "/" && <SessionOverview sessions={sessions} />}

            {sessionsError && <div className="flex items-center justify-between rounded-lg border border-[#FDECE9] bg-[#FDECE9] px-4 py-3 text-xs text-[#EF492F]">{sessionsError}<button className="font-semibold underline" onClick={pollSessions}>Retry</button></div>}

            {(path === "/sessions" || path === "/session-details") && !MOCK_MODE && <NewSession onCreated={id => { void pollSessions(); selectSession(id); }} />}
            {path === "/sessions" && <div id="sessions" className="min-w-0 overflow-hidden rounded-xl border border-[#E5E6E8] bg-white shadow-[0_2px_8px_rgba(20,24,35,0.035)]">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E5E6E8] px-4 py-4 sm:px-5">
                  <div><p className="text-[9px] font-semibold uppercase tracking-[0.15em] text-[#85878C]">Monitoring</p><h2 className="mt-1 text-sm font-semibold text-[#191A1C]">Agent sessions</h2></div>
                  <label className="flex h-9 w-full items-center gap-2 rounded-lg border border-[#E5E6E8] bg-[#FFFFFF] px-3 text-xs text-[#85878C] sm:w-[210px]">
                    <span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search sessions" aria-label="Search sessions" className="min-w-0 flex-1 bg-transparent text-[#191A1C] outline-none placeholder:text-[#85878C]" />
                  </label>
                </div>
                <div className="flex overflow-x-auto border-b border-[#E5E6E8] px-4 py-2.5 sm:px-5">
                  <div className="inline-flex items-center gap-0.5 rounded-lg border border-[#E5E6E8] bg-[#F8F9FA] p-1">
                    {filters.map((item) => <button key={item.value} onClick={() => setFilter(item.value)} className={`whitespace-nowrap rounded-md px-2.5 py-1.5 text-[10px] font-medium transition-colors ${filter === item.value ? "bg-[#191A1C] text-white shadow-sm" : "text-[#52525B] hover:bg-white hover:text-[#191A1C]"}`}>{item.label}</button>)}
                  </div>
                </div>
                <SessionList sessions={filteredSessions} selectedId={selectedId} onSelect={selectSession} loading={sessionsLoading} hasError={sessionsError !== null} />
              </div>}
            {(path === "/session-details" || path === "/mutations") && <div className="min-w-0 space-y-4">
                <label className="block rounded-xl border bg-white p-4 text-sm font-medium">
                  Session
                  <select className="ml-3 max-w-full rounded border px-2 py-1" value={selectedId ?? ""} onChange={event => selectSession(event.target.value)}>
                    <option value="" disabled>{sessions.length ? "Choose a session" : "No sessions available"}</option>
                    {sessions.map(item => <option key={item.session_id} value={item.session_id}>{item.agent_name} ? {item.session_id}</option>)}
                  </select>
                </label>
                {detailError && <div className="flex items-center justify-between rounded-lg border border-[#FDECE9] bg-[#FDECE9] px-4 py-3 text-xs text-[#EF492F]">{detailError}{selectedId && <button className="font-semibold underline" onClick={() => loadDetail(selectedId)}>Retry</button>}</div>}
                {selectedId && detailLoading && !detail && <div className="rounded-xl border border-[#E5E6E8] bg-white p-8 text-center text-xs text-[#52525B]">Loading session…</div>}
                {detail && path === "/session-details" && <SessionDetail key={detail.session_id} session={detail} reviewerToken={reviewerToken} onClearToken={() => setReviewerToken("")} onRefresh={() => { pollSessions(); loadDetail(detail.session_id); }} onActionComplete={handleActionComplete} />}
                {detail && path === "/mutations" && <MutationTable key={detail.session_id} mutations={detail.mutations} />}
                {selectedId && !detail && !detailLoading && !detailError && <div className="rounded-xl border border-[#E5E6E8] bg-white p-8 text-center text-xs text-[#52525B]">Select a session to review its proposed mutations and policy decisions.</div>}
              </div>}
            {path === "/settings" && <section className="space-y-4 rounded-xl border bg-white p-6">
              <h2 className="font-semibold">Reviewer access</h2>
              <TokenInput onTokenSet={setReviewerToken} hasToken={Boolean(reviewerToken)} />
              <p className="text-sm">Connection mode: {MOCK_MODE ? "Preview" : "Live backend"}</p>
              <p className="text-sm">Session refresh interval: {POLL_INTERVAL_MS / 1000} seconds</p>
            </section>}
            {children}
            <footer className="flex flex-wrap items-center justify-between gap-2 px-1 text-[10px] text-[#85878C]"><span>Airlock reviewer workspace</span><span>Session data refreshes every {Math.round(POLL_INTERVAL_MS / 1000)} seconds</span></footer>
          </main>
        </div>
      </div>
    </div>
  );
}
