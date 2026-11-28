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
      <div><h2>Agent control</h2><span role="status" className="worker-status">{connected === null ? "Connecting to worker..." : connected ? (run?.mode === "deterministic" ? "Local demo worker online" : "Nemotron worker online") : "Worker offline · start Run-NemotronDemo.ps1 -Worker"}</span></div>
      <button ref={trigger} disabled={pending} aria-expanded={open} className={open ? "cancel-session" : "rounded bg-blue-600 px-3 py-2 text-white"} onClick={() => { setError(""); setOpen(!open); }}>
        {open ? "Cancel" : "New session"}</button>
    </div>
    {open && <form className="mt-3 grid gap-3" onSubmit={start}>
      <label>Session name <input ref={nameField} className="rounded bg-slate-800 p-2" required maxLength={70}
        value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Task <select className="rounded bg-slate-800 p-2" value={scenario} onChange={e => setScenario(e.target.value)}>
        <option value="deletion">Inspect and stage overdue invoice deletions</option>
        <option value="webhook">Attempt a synthetic secret webhook</option>
        <option value="inspect">Inspect invoice status and due date</option>
        <option value="single_delete">Stage one deletion if overdue</option>
      </select></label>
      {single && <label>Invoice ID<input required pattern="INV-[0-9]{4}" title="Use an ID such as INV-0042" value={invoice} onChange={e => setInvoice(e.target.value.toUpperCase())} /></label>}
      <button className="justify-self-start rounded bg-blue-600 px-3 py-2 text-white disabled:opacity-50"
        disabled={!connected || pending || run?.status === "Running" || !name.trim()}>{pending ? "Starting session..." : "Run agent"}</button>
      {error && <p role="alert">{error}</p>}
    </form>}
    {run?.session_id && <div className="live-trace">
      <button className="underline" onClick={() => onCreated(run.session_id!)}>View latest run</button>
      <span> · {run.status}</span>
      <ol aria-label="Live tool results" aria-live="polite" aria-relevant="additions" className="trace-steps">{run.results.map((line, i) => <li key={i}>{line}</li>)}</ol>
    </div>}
  </section>;
}
