from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
import subprocess
import sys
import threading
import uuid
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import get_settings
from .database import _connect, _connect_readonly, database_health, initialize_databases, load_contracts, seed_rows

settings = get_settings()
LOCK = threading.Lock()
POLICIES: dict = {}
TOOLS: dict = {}
SCHEMAS: dict = {}
REGISTRY = Registry()
COLS = ("id", "customer_name", "customer_email", "amount_cents", "currency", "status", "due_date", "notes", "version", "created_at", "updated_at")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def uid() -> str:
    return str(uuid.uuid4())


def clean(value):
    markers = POLICIES.get("secret_markers", [])
    if isinstance(value, str):
        return "[REDACTED]" if any(marker in value for marker in markers) else value
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {("[REDACTED_KEY]" if any(m in str(k) for m in markers) else k): clean(v) for k, v in value.items()}
    return value


def stamp():
    return now()


def api_error(request: Request, status: int, code: str, message: str, details=None):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": clean(message), "http_status": status, "details": clean(details or {}), "request_id": uid(), "timestamp": stamp()}})


def err(status, code, message, details=None):
    raise AirlockError(status, code, message, details or {})


class AirlockError(Exception):
    def __init__(self, status, code, message, details):
        self.status, self.code, self.message, self.details = status, code, message, details


def bearer(request: Request, role: str):
    token = settings.airlock_agent_token if role == "agent" else settings.airlock_reviewer_token
    header = request.headers.get("authorization", "")
    parts = header.split()
    valid = len(parts) == 2 and parts[0].lower() == "bearer" and hmac.compare_digest(parts[1], token)
    if not valid:
        code = "UNAUTHORIZED_AGENT" if role == "agent" else "UNAUTHORIZED_REVIEWER"
        err(401, code, f"Missing or invalid {role} bearer token.")


def origin_guard(request: Request):
    if request.headers.get("origin") not in settings.allowed_origins:
        err(403, "FORBIDDEN", "Origin header is missing or not in the configured CORS_ORIGINS allowlist.")


async def json_body(request: Request, optional: bool = False):
    raw = await request.body()
    if len(raw) > 1024 * 1024:
        err(422, "INVALID_ARGUMENTS", "Request body exceeds 1 MiB.")
    if not raw and optional:
        return {}
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        err(422, "INVALID_ARGUMENTS", "Content-Type must be application/json.")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        err(422, "INVALID_ARGUMENTS", "Request body must be valid JSON.")


def validate(schema_name: str, obj):
    schema = SCHEMAS[schema_name]
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker(), registry=REGISTRY).iter_errors(obj), key=lambda e: list(e.path))
    if errors:
        err(422, "INVALID_ARGUMENTS", "Argument validation failed; the call was not executed.", {"errors": [{"path": "$" + "".join(f".{p}" for p in e.absolute_path), "message": e.message[:200]} for e in errors[:10]]})


def api_errors(name: str, obj):
    return list(Draft202012Validator(SCHEMAS["api"], registry=REGISTRY).evolve(schema=SCHEMAS["api"]["$defs"][name]).iter_errors(obj))


def read_manifest(session_id: str):
    with _connect(settings.airlock_meta_db_path) as conn:
        row = conn.execute("SELECT manifest_json FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    if not row:
        err(404, "INVALID_SESSION", "Session was not found.")
    return json.loads(row[0])


def save_manifest(m):
    m["updated_at"] = now()
    with _connect(settings.airlock_meta_db_path) as conn:
        conn.execute("UPDATE sessions SET execution_status=?,gate_decision=?,updated_at=?,manifest_json=? WHERE session_id=?", (m["execution_status"], m["gate_decision"], m["updated_at"], json.dumps(clean(m), separators=(",", ":")), m["session_id"]))


def gate(m):
    violations = m["policy_violations"]
    if any(v["decision"] == "BLOCK" and v["effect_scope"] == "SESSION" for v in violations): return "BLOCK"
    if m["execution_status"] == "ACTIVE": return "PENDING"
    if any(v["decision"] == "REQUIRE_APPROVAL" and v["effect_scope"] == "SESSION" for v in violations): return "REQUIRE_APPROVAL"
    return "ALLOW"


def risk(m):
    total = m["mutation_counts"]["total"]
    baseline = m["baseline_record_count"]
    pct = round(min(100, total * 100 / baseline), 2) if baseline else 0.0
    violations = m["policy_violations"]
    level = "CRITICAL" if any(v["severity"] == "CRITICAL" for v in violations) else "HIGH" if violations else "LOW" if total else "LOW"
    m["risk_summary"] = {"overall_risk_level": level, "total_mutations": total, "affected_percentage": pct, "violation_count": len(violations), "block_count": sum(v["decision"] == "BLOCK" for v in violations), "require_approval_count": sum(v["decision"] == "REQUIRE_APPROVAL" for v in violations), "staged_webhook_count": sum(w["status"] == "STAGED" for w in m["staged_webhooks"]), "summary_text": f"{total} mutations ({pct:.1f}% of baseline), {sum(w['status']=='STAGED' for w in m['staged_webhooks'])} webhooks staged, {len(violations)} policy violations."}


def violation(policy, stage, operation, explanation, count=None):
    return {"policy_id": policy["policy_id"], "policy_name": policy["policy_name"], "severity": policy["severity"], "decision": policy["decision"], "effect_scope": policy["effect_scope"], "stage": stage, "operation_id": operation, "explanation": explanation, "affected_record_count": count, "timestamp": now()}


def invoice(conn, invoice_id):
    row = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    return dict(row) if row else None


def mutation(m, op, tool, before, after):
    kind = "INSERT" if before is None else "DELETE" if after is None else "UPDATE"
    key = {"INSERT":"inserted", "UPDATE":"updated", "DELETE":"deleted"}[kind]
    existing = next((x for group in m["mutations"].values() for x in group if x["entity_id"] == (after or before)["id"]), None)
    if existing:
        m["mutations"][key].remove(existing)
        if existing["before"] is None and after is None:
            m["mutation_counts"] = {"inserted":len(m["mutations"]["inserted"]), "updated":len(m["mutations"]["updated"]), "deleted":len(m["mutations"]["deleted"])}
            m["mutation_counts"]["total"] = sum(m["mutation_counts"].values())
            return
        before = existing["before"]
        kind = "DELETE" if after is None else "UPDATE"
        key = {"INSERT":"inserted", "UPDATE":"updated", "DELETE":"deleted"}[kind]
    rec = {"mutation_id":uid(), "operation_id":op, "tool_name":tool, "entity_type":"invoice", "entity_id":(after or before)["id"], "mutation_type":kind, "before":before, "after":after, "changed_fields":sorted(k for k in COLS if before and after and before[k] != after[k] and k not in ("version","updated_at")), "baseline_version":before["version"] if before else None, "timestamp":now(), "policy_decision":"PENDING"}
    m["mutations"][key].append(rec)
    m["mutation_counts"] = {"inserted":len(m["mutations"]["inserted"]), "updated":len(m["mutations"]["updated"]), "deleted":len(m["mutations"]["deleted"])}
    m["mutation_counts"]["total"] = sum(m["mutation_counts"].values())


def persist_new(m):
    with _connect(settings.airlock_meta_db_path) as conn:
        conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)", (m["session_id"],m["agent_name"],m["execution_status"],m["gate_decision"],m["human_review_status"],m["created_at"],m["updated_at"],json.dumps(m,separators=(",",":"))))


@asynccontextmanager
async def lifespan(app: FastAPI):
    validator = Path(__file__).resolve().parents[2] / "scripts" / "validate_contracts.py"
    check = subprocess.run([sys.executable, str(validator), "--contracts-dir", str(settings.airlock_contracts_dir.resolve())], cwd=validator.parents[1], capture_output=True, text=True)
    if check.returncode:
        raise RuntimeError("Contract validation failed; application startup aborted.\n" + check.stdout + check.stderr)
    load_contracts(settings.airlock_contracts_dir)
    global POLICIES, TOOLS, SCHEMAS, REGISTRY
    base = settings.airlock_contracts_dir
    POLICIES = json.loads((base / "policies.json").read_text())
    TOOLS = {x["name"]: x for x in json.loads((base / "tools.json").read_text())["tools"]}
    SCHEMAS = {"manifest": json.loads((base / "manifest.schema.json").read_text()), "api": json.loads((base / "api.schema.json").read_text()), "invoice": json.loads((base / "invoice.schema.json").read_text())}
    REGISTRY = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in SCHEMAS.values())
    initialize_databases(settings)
    reconcile_sessions()
    yield


app = FastAPI(title="Airlock API", version="0.2.0", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])
app.add_middleware(CORSMiddleware, allow_origins=sorted(settings.allowed_origins), allow_credentials=False, allow_methods=["GET","POST","OPTIONS"], allow_headers=["Authorization","Content-Type"])


@app.exception_handler(AirlockError)
async def handle_airlock(request, exc): return api_error(request, exc.status, exc.code, exc.message, exc.details)

@app.exception_handler(RequestValidationError)
async def handle_validation(request, exc): return api_error(request, 422, "INVALID_ARGUMENTS", "Request validation failed.")

@app.exception_handler(HTTPException)
async def handle_http(request, exc):
    status = exc.status_code
    code = "INVALID_SESSION" if status == 404 else "FORBIDDEN" if status == 403 else "INVALID_ARGUMENTS" if status == 422 else "INTERNAL_ERROR"
    return api_error(request, status, code, "The requested resource or operation is unavailable.")

@app.exception_handler(sqlite3.Error)
async def handle_sqlite(request, exc): return api_error(request, 500, "DATABASE_FAILURE", "A database operation failed.")

@app.exception_handler(Exception)
async def handle_internal(request, exc): return api_error(request, 500, "INTERNAL_ERROR", "An internal error occurred.")


@app.get("/api/health")
def health():
    prod, meta, count, active = database_health(settings)
    return {"status":"ok","prod_db_connected":prod,"meta_db_connected":meta,"prod_invoice_count":count,"active_sessions":active,"contracts_loaded":True,"timestamp":now()}


@app.post("/api/sessions", status_code=201)
async def create_session(request: Request):
    bearer(request, "agent")
    body = await json_body(request)
    errors = api_errors("CreateSessionRequest", body)
    if errors: err(422,"INVALID_ARGUMENTS","Invalid session request.")
    with LOCK:
        created = now(); session_id = uid()
        spec = settings.airlock_speculative_dir / f"{session_id}.db"
        # Backup API produces an independent snapshot without exposing production paths to the agent.
        with _connect_readonly(settings.airlock_prod_db_path) as source, closing(sqlite3.connect(spec)) as target:
            source.backup(target)
        with closing(sqlite3.connect(spec)) as conn, conn:
            conn.execute("DROP TABLE IF EXISTS airlock_commit_ledger")
        with _connect_readonly(settings.airlock_prod_db_path) as conn: baseline = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        m = {"session_id":session_id,"agent_name":clean(body["agent_name"]),"task_description":clean(body.get("task_description")),"agent_summary":None,"created_at":created,"updated_at":created,"completed_at":None,"finalized_at":None,"execution_status":"ACTIVE","gate_decision":"PENDING","human_review_status":"PENDING","baseline_record_count":baseline,"risk_summary":{},"mutation_counts":{"inserted":0,"updated":0,"deleted":0,"total":0},"mutations":{"inserted":[],"updated":[],"deleted":[]},"staged_webhooks":[],"policy_violations":[],"tool_execution_history":[],"finalization_result":None}
        risk(m); persist_new(m)
        return {k:m[k] for k in ("session_id","agent_name","task_description","execution_status","gate_decision","human_review_status","baseline_record_count","created_at")}


@app.get("/api/sessions")
def list_sessions():
    with _connect(settings.airlock_meta_db_path) as conn: rows=conn.execute("SELECT manifest_json FROM sessions ORDER BY created_at DESC").fetchall()
    result=[]
    for row in rows:
        m=json.loads(row[0]); result.append({k:m[k] for k in ("session_id","agent_name","task_description","created_at","updated_at","execution_status","gate_decision","human_review_status","mutation_counts","risk_summary")})
    return {"sessions":result,"total":len(result)}


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str): return read_manifest(session_id)


@app.post("/api/tools/execute")
async def execute(request: Request):
    bearer(request,"agent"); body=await json_body(request)
    if api_errors("ExecuteRequest", body): err(422,"INVALID_ARGUMENTS","Invalid tool request.")
    with LOCK:
        return execute_locked(body)


def execute_locked(body):
    name=body["tool_name"]; op=uid(); m=read_manifest(body["session_id"])
    if m["execution_status"] in ("COMMITTED","ROLLED_BACK"): err(409,"SESSION_ALREADY_FINALIZED","Session is already finalized.")
    if m["execution_status"] != "ACTIVE": err(409,"INVALID_SESSION_STATE","Tools are only available for ACTIVE sessions.")
    tool=TOOLS.get(name)
    if not tool:
        p=next(x for x in POLICIES["policies"] if x["policy_id"]=="POL-005"); m["policy_violations"].append(violation(p,"TOOL_EXECUTE",op,f"Tool '{name}' is not in the tools.json allowlist.")); m["tool_execution_history"].append({"operation_id":op,"tool_name":clean(name),"arguments":clean(body["arguments"]),"read_only":False,"status":"BLOCKED","tool_decision":"BLOCK","mutations_recorded":0,"error_code":"INVALID_TOOL","executed_at":now()}); risk(m); save_manifest(m)
        err(400,"INVALID_TOOL",f"Tool '{name}' is not in the tools.json allowlist; the call was blocked and not executed.",{"operation_id":op,"tool_name":name,"tool_decision":"BLOCK","session_gate_decision":m["gate_decision"]})
    args=body["arguments"]
    if list(Draft202012Validator(tool["parameters"],format_checker=FormatChecker(),registry=REGISTRY).iter_errors(args)): err(422,"INVALID_ARGUMENTS","Tool arguments failed validation.")
    read_only=tool["read_only"]
    if m["gate_decision"]=="BLOCK" and not read_only:
        m["tool_execution_history"].append({"operation_id":op,"tool_name":name,"arguments":clean(body["arguments"]),"read_only":False,"status":"BLOCKED","tool_decision":"BLOCK","mutations_recorded":0,"error_code":"POLICY_BLOCK","executed_at":now()}); save_manifest(m)
        err(403,"POLICY_BLOCK","Session gate_decision is BLOCK; mutating tools are rejected.",{"reason":"SESSION_BLOCKED","operation_id":op,"tool_name":name,"tool_decision":"BLOCK","session_gate_decision":"BLOCK","blocking_policy_ids":[v["policy_id"] for v in m["policy_violations"] if v["decision"]=="BLOCK"]})
    # Never evaluate or persist unredacted arguments.
    saved_args=clean(args); mutations=0; result={}; violations=[]
    spec=settings.airlock_speculative_dir/f"{m['session_id']}.db"
    with closing(sqlite3.connect(spec)) as raw, raw:
        raw.row_factory=sqlite3.Row
        if name=="list_invoices":
            where=[]; params=[]
            if args.get("status"): where.append("status=?"); params.append(args["status"])
            if args.get("customer_name"): where.append("customer_name LIKE ? COLLATE NOCASE"); params.append(f"%{args['customer_name']}%")
            clause=" WHERE "+" AND ".join(where) if where else ""
            total=raw.execute("SELECT COUNT(*) FROM invoices"+clause,params).fetchone()[0]; rows=raw.execute("SELECT * FROM invoices"+clause+" ORDER BY id LIMIT ? OFFSET ?",params+[args.get("limit",50),args.get("offset",0)]).fetchall()
            result={"total_matching":total,"returned":len(rows),"invoices":[dict(r) for r in rows]}
        elif name=="get_invoice":
            row=invoice(raw,args["invoice_id"])
            if not row: err(404,"INVOICE_NOT_FOUND","Invoice was not found.")
            result={"invoice":row}
        elif name=="update_invoice":
            if args.get("notes") and any(mark in args["notes"] for mark in POLICIES["secret_markers"]): err(422,"INVALID_ARGUMENTS","Argument validation failed; the call was not executed.",{"reason":"SECRET_IN_ARGUMENT","errors":[{"path":"$.notes","message":"value contains a configured secret marker (redacted)"}]})
            old=invoice(raw,args["invoice_id"])
            if not old: err(404,"INVOICE_NOT_FOUND","Invoice was not found.")
            new=dict(old); new.update({k:v for k,v in args.items() if k in ("status","amount_cents","due_date","notes")})
            if any(new[k]!=old[k] for k in ("status","amount_cents","due_date","notes")):
                new["version"]+=1; new["updated_at"]=now(); raw.execute("UPDATE invoices SET status=?,amount_cents=?,due_date=?,notes=?,version=?,updated_at=? WHERE id=?",(new["status"],new["amount_cents"],new["due_date"],new["notes"],new["version"],new["updated_at"],new["id"])); mutation(m,op,name,old,new); mutations=1
            result={"updated_invoice":new}
        elif name in ("delete_invoice","bulk_delete_invoices"):
            ids=[args["invoice_id"]] if name=="delete_invoice" else args.get("invoice_ids")
            if ids:
                missing=[i for i in ids if not invoice(raw,i)]
                if missing: err(404,"INVOICE_NOT_FOUND","One or more requested invoice IDs do not exist; no invoices were deleted.",{"operation_id":op,"missing_count":len(missing),"missing_invoice_ids":missing[:50],"truncated":len(missing)>50})
            if name=="delete_invoice": rows=[invoice(raw,args["invoice_id"])]
            elif ids:
                requested_rows=[invoice(raw,i) for i in ids]; rows=[r for r in requested_rows if not args.get("status") or r["status"]==args["status"]]
            else: rows=[dict(r) for r in raw.execute("SELECT * FROM invoices WHERE status=?",(args["status"],)).fetchall()]
            for row in rows:
                raw.execute("DELETE FROM invoices WHERE id=?",(row["id"],)); mutation(m,op,name,row,None)
            mutations=len(rows)
            result={"deleted_invoice_id":args["invoice_id"]} if name=="delete_invoice" else {"deleted_count":len(rows),"deleted_invoice_ids":[r["id"] for r in rows],"unmatched_invoice_ids":[r["id"] for r in requested_rows if args.get("status") and r["status"]!=args["status"]] if ids else []}
        elif name=="stage_webhook":
            markers=POLICIES["secret_markers"]
            def scan(v):
                if isinstance(v,str): return any(x in v for x in markers)
                if isinstance(v,dict): return any(any(x in str(k) for x in markers) or scan(val) for k,val in v.items())
                if isinstance(v,list): return any(scan(x) for x in v)
                return False
            secret=scan(args) or any(x in unquote(args["url"]) for x in markers)
            host=(urlsplit(args["url"]).hostname or "").lower()
            badhost=host not in POLICIES["allowed_webhook_domains"]
            if secret:
                p=next(x for x in POLICIES["policies"] if x["policy_id"]=="POL-003"); violations.append(violation(p,"TOOL_EXECUTE",op,"Webhook contains a configured secret marker; value redacted."))
            if badhost:
                p=next(x for x in POLICIES["policies"] if x["policy_id"]=="POL-004"); violations.append(violation(p,"TOOL_EXECUTE",op,f"Webhook destination host {host} is not in allowed_webhook_domains."))
            if violations:
                m["policy_violations"].extend(violations); m["staged_webhooks"].append({"webhook_id":uid(),"operation_id":op,"url":clean(args["url"]),"event_type":clean(args["event_type"]),"payload":clean(args["payload"]),"staged_at":now(),"status":"BLOCKED"}); m["tool_execution_history"].append({"operation_id":op,"tool_name":name,"arguments":saved_args,"read_only":False,"status":"BLOCKED","tool_decision":"BLOCK","mutations_recorded":0,"error_code":"POLICY_BLOCK","executed_at":now()}); m["gate_decision"]="BLOCK"; risk(m); save_manifest(m)
                err(403,"POLICY_BLOCK","Webhook blocked by policy and was not dispatched.",{"operation_id":op,"tool_name":name,"tool_decision":"BLOCK","session_gate_decision":"BLOCK","policy_violations":violations})
            webhook={"webhook_id":uid(),"operation_id":op,"url":args["url"],"event_type":args["event_type"],"payload":clean(args["payload"]),"staged_at":now(),"status":"STAGED"}; m["staged_webhooks"].append(webhook); result={"webhook_id":webhook["webhook_id"],"staged_status":"STAGED"}
    m["tool_execution_history"].append({"operation_id":op,"tool_name":name,"arguments":saved_args,"read_only":read_only,"status":"SUCCESS","tool_decision":"ALLOW","mutations_recorded":mutations,"error_code":None,"executed_at":now()}); m["gate_decision"]=gate(m); risk(m); save_manifest(m)
    return {"operation_id":op,"session_id":m["session_id"],"tool_name":name,"status":"SUCCESS","read_only":read_only,"tool_decision":"ALLOW","session_gate_decision":m["gate_decision"],"mutations_recorded":mutations,"policy_violations":[],"result":result,"executed_at":now()}


@app.post("/api/sessions/{session_id}/complete")
async def complete(session_id: str, request: Request):
    bearer(request,"agent"); body=await json_body(request, optional=True)
    if api_errors("CompleteRequest", body): err(422,"INVALID_ARGUMENTS","Invalid completion request.")
    with LOCK:
        m=read_manifest(session_id)
        if m["execution_status"] in ("COMMITTED","ROLLED_BACK"): err(409,"SESSION_ALREADY_FINALIZED","Session is already finalized.")
        if m["execution_status"]!="ACTIVE": err(409,"INVALID_SESSION_STATE","Session is not ACTIVE.")
        m["agent_summary"]=clean(body.get("agent_summary")); m["execution_status"]="COMPLETED"; m["completed_at"]=now()
        for policy_id,key in (("POL-001","deleted"),("POL-002","updated")):
            p=next(x for x in POLICIES["policies"] if x["policy_id"]==policy_id); count=m["mutation_counts"][key]
            if p["enabled"] and m["baseline_record_count"] and count*100>p["threshold_percent"]*m["baseline_record_count"]:
                m["policy_violations"].append(violation(p,"SESSION_COMPLETE",None,f"{count} of {m['baseline_record_count']} baseline records {key}.",count))
                for item in m["mutations"][key]: item["policy_decision"]="REQUIRE_APPROVAL"
        for key in m["mutations"]:
            for item in m["mutations"][key]:
                if item["policy_decision"]=="PENDING": item["policy_decision"]="ALLOW"
        m["gate_decision"]=gate(m); risk(m); save_manifest(m); return m


async def reviewer_body(request):
    body=await json_body(request, optional=True)
    if api_errors("ReviewerActionRequest", body): err(422,"INVALID_ARGUMENTS","Invalid reviewer action request.")
    return clean(body)


def finalize(m, action, body, ledger_id=None, counts=None, conflicts=None, recovered=False):
    t=now(); m["execution_status"]="COMMITTED" if action=="COMMIT" else "ROLLED_BACK"; m["human_review_status"]="APPROVED" if action=="COMMIT" else "REJECTED"; m["finalized_at"]=t; m["finalization_result"]={"action":action,"status":"SUCCESS" if not conflicts else "FAILED","actor":body["reviewer"],"reason":body.get("reason"),"timestamp":t,"applied_counts":counts or {"inserted":0,"updated":0,"deleted":0},"conflict_details":conflicts,"ledger_id":ledger_id,"recovered":recovered}; save_manifest(m)


@app.post("/api/sessions/{session_id}/rollback")
async def rollback(session_id: str, request: Request):
    origin_guard(request); bearer(request,"reviewer"); body=await reviewer_body(request)
    with LOCK:
        m=read_manifest(session_id)
        if m["execution_status"] in ("COMMITTED","ROLLED_BACK"): err(409,"SESSION_ALREADY_FINALIZED","Session is already finalized.")
        if m["execution_status"] not in ("ACTIVE","COMPLETED"): err(409,"INVALID_SESSION_STATE","Session cannot be rolled back.")
        if read_receipt(session_id): err(409,"SESSION_ALREADY_FINALIZED","Session already has a durable commit receipt.")
        finalize(m,"ROLLBACK",body); (settings.airlock_speculative_dir/f"{session_id}.db").unlink(missing_ok=True); return m


def read_receipt(session_id):
    with _connect(settings.airlock_prod_db_path) as conn: return conn.execute("SELECT * FROM airlock_commit_ledger WHERE session_id=?",(session_id,)).fetchone()


def reconcile_sessions():
    with _connect(settings.airlock_meta_db_path) as conn:
        rows = conn.execute("SELECT session_id,manifest_json FROM sessions").fetchall()
    for row in rows:
        receipt = read_receipt(row["session_id"])
        m = json.loads(row["manifest_json"])
        if receipt and m["execution_status"] not in ("COMMITTED", "ROLLED_BACK"):
            m["execution_status"] = "COMMITTED"; m["gate_decision"] = receipt["gate_decision"]
            m["human_review_status"] = "APPROVED"; m["finalized_at"] = receipt["committed_at"]
            m["finalization_result"] = {"action":"COMMIT","status":"SUCCESS","actor":receipt["reviewer"],"reason":receipt["reason"],"timestamp":receipt["committed_at"],"applied_counts":{"inserted":receipt["inserted_count"],"updated":receipt["updated_count"],"deleted":receipt["deleted_count"]},"conflict_details":None,"ledger_id":receipt["ledger_id"],"recovered":True}
            save_manifest(m)
            (settings.airlock_speculative_dir/f"{row['session_id']}.db").unlink(missing_ok=True)


@app.post("/api/sessions/{session_id}/commit")
async def commit(session_id: str, request: Request):
    origin_guard(request); bearer(request,"reviewer"); body=await reviewer_body(request)
    with LOCK:
        m=read_manifest(session_id)
        if m["execution_status"] in ("COMMITTED","ROLLED_BACK") or read_receipt(session_id): err(409,"SESSION_ALREADY_FINALIZED","Session is already finalized.")
        if m["execution_status"]!="COMPLETED": err(409,"INVALID_SESSION_STATE","Only COMPLETED sessions can be committed.")
        if m["gate_decision"]=="BLOCK": err(403,"POLICY_BLOCK","Session cannot be committed because gate_decision is BLOCK.",{"gate_decision":"BLOCK","blocking_policy_ids":[v["policy_id"] for v in m["policy_violations"] if v["decision"]=="BLOCK"]})
        records=sorted([x for group in m["mutations"].values() for x in group],key=lambda x:x["entity_id"]); conflicts=[]
        conn=sqlite3.connect(settings.airlock_prod_db_path, timeout=10); conn.row_factory=sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            for r in records:
                current=invoice(conn,r["entity_id"]); expected=r["baseline_version"]
                if r["mutation_type"]=="INSERT":
                    if current: conflicts.append({"entity_type":"invoice","entity_id":r["entity_id"],"conflict_type":"UNEXPECTED_EXISTING","expected_version":None,"actual_version":current["version"]})
                elif current is None: conflicts.append({"entity_type":"invoice","entity_id":r["entity_id"],"conflict_type":"MISSING","expected_version":expected,"actual_version":None})
                elif current["version"]!=expected or current!=r["before"]: conflicts.append({"entity_type":"invoice","entity_id":r["entity_id"],"conflict_type":"MODIFIED","expected_version":expected,"actual_version":current["version"]})
            if conflicts:
                conn.rollback(); m["finalization_result"]={"action":"COMMIT","status":"FAILED","actor":body["reviewer"],"reason":body.get("reason"),"timestamp":now(),"applied_counts":{"inserted":0,"updated":0,"deleted":0},"conflict_details":conflicts,"ledger_id":None,"recovered":False}; save_manifest(m)
                err(409,"COMMIT_CONFLICT","Production data changed since the session baseline; no changes were applied.",{"conflict_count":len(conflicts),"truncated":len(conflicts)>50,"conflicts":conflicts[:50]})
            counts={"inserted":0,"updated":0,"deleted":0}
            for r in records:
                if r["mutation_type"]=="DELETE": conn.execute("DELETE FROM invoices WHERE id=?",(r["entity_id"],)); counts["deleted"]+=1
                else:
                    vals=[r["after"][k] for k in COLS]
                    if r["mutation_type"]=="INSERT": conn.execute(f"INSERT INTO invoices ({','.join(COLS)}) VALUES ({','.join('?' for _ in COLS)})",vals); counts["inserted"]+=1
                    else: conn.execute(f"UPDATE invoices SET {','.join(k+'=?' for k in COLS[1:])} WHERE id=?",vals[1:]+[r["entity_id"]]); counts["updated"]+=1
            ledger=uid(); digest_rows=[{k:r[k] for k in ("entity_id","mutation_type","baseline_version","before","after")} for r in records]
            digest=hashlib.sha256(json.dumps(digest_rows,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest(); committed=now()
            conn.execute("INSERT INTO airlock_commit_ledger VALUES (?,?,?,?,?,?,?,?,?,?,?)",(ledger,session_id,committed,body["reviewer"],body.get("reason"),m["gate_decision"],m["baseline_record_count"],counts["inserted"],counts["updated"],counts["deleted"],digest)); conn.commit()
        except AirlockError: raise
        except Exception:
            conn.rollback(); raise
        finally: conn.close()
        finalize(m,"COMMIT",body,ledger_id=ledger,counts=counts); (settings.airlock_speculative_dir/f"{session_id}.db").unlink(missing_ok=True); return m


@app.post("/api/demo/reset")
async def reset(request: Request):
    origin_guard(request)
    client=request.client.host if request.client else ""
    if not settings.airlock_demo_mode or client not in ("127.0.0.1","::1"): err(403,"FORBIDDEN","Demo reset is restricted to demo mode and loopback clients.")
    bearer(request,"reviewer"); body=await json_body(request, optional=True)
    if api_errors("EmptyObject", body): err(422,"INVALID_ARGUMENTS","Reset accepts only an empty object.")
    with LOCK:
        for p in settings.airlock_speculative_dir.glob("*.db"): p.unlink(missing_ok=True)
        with _connect(settings.airlock_meta_db_path) as conn: cleared=conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]; conn.execute("DELETE FROM sessions")
        cols=COLS
        with _connect(settings.airlock_prod_db_path) as conn:
            conn.execute("BEGIN IMMEDIATE"); conn.execute("DELETE FROM invoices"); conn.execute("DELETE FROM airlock_commit_ledger"); conn.executemany(f"INSERT INTO invoices ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",[[row[c] for c in cols] for row in seed_rows(settings)]); conn.commit()
        return {"status":"reset_complete","prod_invoice_count":500,"overdue_count":420,"non_overdue_count":80,"cleared_sessions":cleared,"timestamp":now()}
