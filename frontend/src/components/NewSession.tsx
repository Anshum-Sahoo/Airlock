"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

const worker = "http://127.0.0.1:8765/session";
type Run = { mode?: string; session_id: string | null; status: string; results: string[] };

export function NewSession({ onCreated }: { onCreated: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [scenario, setScenario] = useState("deletion");
  const [invoice, setInvoice] = useState("INV-0042");
  const single = scenario === "inspect" || scenario === "single_delete";
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const nameField = useRef<HTMLInputElement>(null);
  useEffect(() => { if (open) nameField.current?.focus(); }, [open]);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const response = await fetch(worker, { cache: "no-store" });
        if (!response.ok) throw new Error();
        const data = await response.json();
        if (active) { setRun(data); setConnected(true); }
      } catch {
        if (active) setConnected(false);
      } finally {
        if (active) timer = setTimeout(refresh, 1000);
      }
    }
    refresh();
    return () => { active = false; clearTimeout(timer); };
  }, []);

  async function start(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const response = await fetch(worker, { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, scenario, invoice_id: single ? invoice : undefined }) });
      if (!response.ok) throw new Error(response.status === 409 ? "A session is already running." : "Check that the Airlock backend is running, then try again.");
      const { session_id } = await response.json();
      setRun({ mode: run?.mode, session_id, status: "Running", results: [] });
      onCreated(session_id);
      setOpen(false);
      trigger.current?.focus();
    } catch (err) {
      setError(err instanceof TypeError ? "Connection lost. Check session history before starting another run." : err instanceof Error ? err.message : "Worker unavailable.");
    } finally { setPending(false); }
  }
  return <section className="run-panel">
    <div className="flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-3">
        <span aria-hidden="true" className="agent-mark"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="6" width="18" height="13" rx="3"/><path d="m7 10 3 2-3 2m6 0h4"/></svg></span>
        <div><h2>Agent control</h2><span role="status" className="worker-status" data-online={connected === true}>{connected === null ? "Connecting to worker..." : connected ? (run?.mode === "deterministic" ? "Local demo worker online" : "Nemotron worker online") : "Worker offline · start Run-NemotronDemo.ps1 -Worker"}</span></div></div>
      <button ref={trigger} disabled={pending} aria-expanded={open} className={open ? "cancel-session" : "agent-primary"} onClick={() => { setError(""); setOpen(!open); }}>
        {open ? "Cancel" : "New session"}</button>
    </div>
    {open && <form className="agent-form" onSubmit={start}>
      <label>Session name <input ref={nameField}  required maxLength={70}
        value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Task <select  value={scenario} onChange={e => setScenario(e.target.value)}>
        <option value="deletion">Inspect and stage overdue invoice deletions</option>
        <option value="webhook">Attempt a synthetic secret webhook</option>
        <option value="inspect">Inspect invoice status and due date</option>
        <option value="single_delete">Stage one deletion if overdue</option>
      </select></label>
      {single && <label>Invoice ID<input required pattern="INV-[0-9]{4}" title="Use an ID such as INV-0042" value={invoice} onChange={e => setInvoice(e.target.value.toUpperCase())} /></label>}
      <button className="agent-primary justify-self-start"
        disabled={!connected || pending || run?.status === "Running" || !name.trim()}>{pending ? "Starting session..." : "Run agent"}</button>
      {error && <p role="alert">{error}</p>}
    </form>}
    {run?.session_id && <div className="live-trace">
      <div className="run-summary">
        <h3>Latest run</h3>
        <p className="run-state">{run.status.split(" · ")[0]}</p>
        {run.status.includes(" · ") && <span className="run-status" data-gate={run.status.split(" · ")[1]}>{run.status.split(" · ")[1].replace(/_/g, " ")}</span>}
        <button className="run-link" onClick={() => onCreated(run.session_id!)}>View run</button>
      </div>
      <div className="run-activity">
        <h3>Tool activity</h3>
        <ol aria-label="Live tool results" aria-live="polite" aria-relevant="additions" className="trace-steps">
          {run.results.map((line, i) => {
            const tool = /^([a-z]+_[a-z_]+)[: ]+(.+)$/.exec(line);
            return <li key={i}>{tool ? <><code>{tool[1]}</code><span>{tool[2]}</span></> : line}</li>;
          })}
        </ol>
        {!run.results.length && <p className="text-sm text-zinc-600">No tool results yet.</p>}
      </div>
    </div>}
  </section>;
}
