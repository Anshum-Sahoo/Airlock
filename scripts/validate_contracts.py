#!/usr/bin/env python3
"""Airlock Contracts v1.2.1 validator (Python 3.9+, standard library only).

Usage:  python3 scripts/validate_contracts.py [--dump-instances out.json]

What it does
  1. Parses every JSON file.
  2. Lints every schema: only draft-07 / 2020-12 common keywords (plus x-* annotations) are allowed.
  3. Validates every example (fixtures, tools.json examples, error examples, JSON blocks in
     API_CONTRACT.md) against its schema using the built-in validator below.
  4. Runs cross-file consistency checks (UUID v4, tools, policies, endpoints, status codes,
     state machine, invoice fields, thresholds, commit ledger, env file).

IMPORTANT: the built-in validator implements only the keyword subset used by these schemas. It is
not a general JSON Schema implementation. For an independent second opinion run the same schemas
and instances through a standard validator (see README.md); --dump-instances writes every
(schema, instance) pair so another tool can replay them.
"""
import datetime, json, os, re, sys, urllib.parse, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
CONTRACTS = os.path.join(PKG, "contracts")
DEFAULT_CONTRACTS = CONTRACTS
BASE = "https://airlock.local/contracts/"
UUID4_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
UUID_ANY_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
FAILS, PASSES = [], []

def check(name, ok, detail=""):
    (PASSES if ok else FAILS).append(name)
    print(("PASS  " if ok else "FAIL  ") + name + ((" :: " + detail) if (detail and not ok) else ""))

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()

# ----------------------------------------------------------------------------- JSON Schema subset
ALLOWED = {"$schema","$id","$comment","$ref","$defs","title","description","type","enum","const","required",
           "properties","additionalProperties","items","minItems","maxItems","uniqueItems","minLength",
           "maxLength","pattern","format","minimum","maximum","allOf","anyOf","oneOf","if","then","else",
           "default","examples"}
SUBSCHEMA_MAP = {"properties","$defs"}
SUBSCHEMA_LIST = {"allOf","anyOf","oneOf"}
SUBSCHEMA_ONE = {"items","additionalProperties","if","then","else"}

def lint_schema(s, where, errs):
    if isinstance(s, bool): return
    if not isinstance(s, dict):
        errs.append("%s: schema is not an object" % where); return
    for k, v in s.items():
        if k not in ALLOWED and not k.startswith("x-"):
            errs.append("%s: unsupported keyword %r" % (where, k))
        if k in SUBSCHEMA_MAP and isinstance(v, dict):
            for n, sub in v.items(): lint_schema(sub, where + "/" + k + "/" + n, errs)
        elif k in SUBSCHEMA_LIST and isinstance(v, list):
            for i, sub in enumerate(v): lint_schema(sub, "%s/%s/%d" % (where, k, i), errs)
        elif k in SUBSCHEMA_ONE: lint_schema(v, where + "/" + k, errs)
    if "$ref" in s and len([k for k in s if k not in ("$ref", "$comment", "description")]):
        errs.append("%s: $ref must not have sibling keywords (draft-07 ignores them)" % where)

class Registry:
    def __init__(self): self.docs = {}
    def add(self, doc):
        self.docs[doc["$id"]] = doc
    def resolve(self, ref, base):
        url = urllib.parse.urljoin(base, ref)
        doc_url, _, frag = url.partition("#")
        doc = self.docs.get(doc_url)
        if doc is None: raise KeyError("unresolvable $ref %s (base %s)" % (ref, base))
        node = doc
        if frag:
            for part in frag.lstrip("/").split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                node = node[part]
        return node, doc_url

def jtype(x):
    if x is None: return "null"
    if isinstance(x, bool): return "boolean"
    if isinstance(x, int): return "integer"
    if isinstance(x, float): return "integer" if x.is_integer() else "number"
    if isinstance(x, str): return "string"
    if isinstance(x, list): return "array"
    if isinstance(x, dict): return "object"
    return "unknown"

def type_ok(x, t):
    jt = jtype(x)
    if t == "number": return jt in ("integer", "number")
    if t == "integer": return jt == "integer"
    return jt == t

def jeq(a, b):
    if isinstance(a, bool) != isinstance(b, bool): return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(jeq(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(jeq(a[k], b[k]) for k in a)
    return a == b

def fmt_ok(v, f):
    try:
        if f == "date-time":
            if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$", v): return False
            datetime.datetime.fromisoformat(v.replace("Z", "+00:00")); return True
        if f == "date":
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", v): return False
            datetime.date.fromisoformat(v); return True
        if f == "email": return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v) is not None
        if f == "uri":
            p = urllib.parse.urlparse(v); return bool(p.scheme) and (bool(p.netloc) or p.scheme in ("urn", "mailto"))
        if f == "uuid": uuid.UUID(v); return True
    except Exception:
        return False
    return True

def validate(inst, schema, reg, base, path="$"):
    """Return list of error strings (empty = valid)."""
    if schema is True: return []
    if schema is False: return ["%s: schema is false" % path]
    errs = []
    if "$ref" in schema:
        node, nb = reg.resolve(schema["$ref"], base)
        return validate(inst, node, reg, nb, path)
    if "type" in schema:
        ts = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(type_ok(inst, t) for t in ts):
            return ["%s: expected type %s, got %s" % (path, ts, jtype(inst))]
    if "const" in schema and not jeq(inst, schema["const"]):
        errs.append("%s: expected const %r" % (path, schema["const"]))
    if "enum" in schema and not any(jeq(inst, e) for e in schema["enum"]):
        errs.append("%s: %r not in enum %r" % (path, inst, schema["enum"]))
    if isinstance(inst, str):
        if "minLength" in schema and len(inst) < schema["minLength"]: errs.append("%s: shorter than minLength" % path)
        if "maxLength" in schema and len(inst) > schema["maxLength"]: errs.append("%s: longer than maxLength" % path)
        if "pattern" in schema and re.search(schema["pattern"], inst) is None:
            errs.append("%s: %r does not match pattern %s" % (path, inst[:60], schema["pattern"]))
        if "format" in schema and not fmt_ok(inst, schema["format"]):
            errs.append("%s: %r is not a valid %s" % (path, inst[:60], schema["format"]))
    if jtype(inst) in ("integer", "number"):
        if "minimum" in schema and inst < schema["minimum"]: errs.append("%s: below minimum" % path)
        if "maximum" in schema and inst > schema["maximum"]: errs.append("%s: above maximum" % path)
    if isinstance(inst, list):
        if "minItems" in schema and len(inst) < schema["minItems"]: errs.append("%s: fewer than minItems" % path)
        if "maxItems" in schema and len(inst) > schema["maxItems"]: errs.append("%s: more than maxItems" % path)
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in inst}) != len(inst):
            errs.append("%s: items not unique" % path)
        if "items" in schema:
            for i, x in enumerate(inst): errs += validate(x, schema["items"], reg, base, "%s[%d]" % (path, i))
    if isinstance(inst, dict):
        for r in schema.get("required", []):
            if r not in inst: errs.append("%s: missing required property %r" % (path, r))
        props = schema.get("properties", {})
        for k, v in inst.items():
            if k in props: errs += validate(v, props[k], reg, base, path + "." + k)
            elif "additionalProperties" in schema:
                ap = schema["additionalProperties"]
                if ap is False: errs.append("%s: additional property %r not allowed" % (path, k))
                elif ap is not True: errs += validate(v, ap, reg, base, path + "." + k)
    for sub in schema.get("allOf", []): errs += validate(inst, sub, reg, base, path)
    if "anyOf" in schema and not any(not validate(inst, s, reg, base, path) for s in schema["anyOf"]):
        errs.append("%s: does not match anyOf" % path)
    if "oneOf" in schema:
        n = sum(1 for s in schema["oneOf"] if not validate(inst, s, reg, base, path))
        if n != 1: errs.append("%s: matches %d oneOf branches (expected 1)" % (path, n))
    if "if" in schema:
        if not validate(inst, schema["if"], reg, base, path):
            if "then" in schema: errs += validate(inst, schema["then"], reg, base, path)
        elif "else" in schema: errs += validate(inst, schema["else"], reg, base, path)
    return errs

# ----------------------------------------------------------------------------- load
def load_all():
    data = {}
    for root, dirs, files in os.walk(PKG):
        if os.path.abspath(root) == os.path.abspath(DEFAULT_CONTRACTS):
            dirs.clear()
            continue
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, PKG).replace(os.sep, "/")
                try:
                    data[rel] = json.loads(read(p))
                except Exception as e:
                    data[rel] = e
    for root, _, files in os.walk(CONTRACTS):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, CONTRACTS).replace(os.sep, "/")
                try:
                    data["contracts/" + rel] = json.loads(read(p))
                except Exception as e:
                    data["contracts/" + rel] = e
    return data

INSTANCES = []   # (label, schema_ref, instance, details_ref)

def run():
    data = load_all()
    bad = [k for k, v in data.items() if isinstance(v, Exception)]
    check("V1 every JSON file parses (%d files)" % len(data), not bad, ", ".join("%s: %s" % (k, data[k]) for k in bad))
    if bad: return
    C = lambda n: data["contracts/" + n]
    invoice, error, manifest, api, tools, policies = C("invoice.schema.json"), C("error.schema.json"), C("manifest.schema.json"), C("api.schema.json"), C("tools.json"), C("policies.json")
    reg = Registry()
    for d in (invoice, error, manifest, api): reg.add(d)

    # ---- schema lint
    lint = []
    for n, d in (("invoice", invoice), ("error", error), ("manifest", manifest), ("api", api)): lint_schema(d, n, lint)
    for t in tools["tools"]:
        lint_schema(t["parameters"], "tools/" + t["name"] + "/parameters", lint)
        lint_schema(t["result_schema"], "tools/" + t["name"] + "/result_schema", lint)
    check("V2a schemas use only draft-07/2020-12 common keywords and resolvable $refs", not lint, "; ".join(lint[:5]))
    unresolved = []
    def walk_refs(o, base):
        if isinstance(o, dict):
            if "$ref" in o:
                try: reg.resolve(o["$ref"], base)
                except Exception as e: unresolved.append(str(e))
            for v in o.values(): walk_refs(v, base)
        elif isinstance(o, list):
            for v in o: walk_refs(v, base)
    for d in (invoice, error, manifest, api): walk_refs(d, d["$id"])
    for t in tools["tools"]:
        walk_refs(t["result_schema"], BASE + "tools.json"); walk_refs(t["parameters"], BASE + "tools.json")
    check("V2b all $ref targets resolve", not unresolved, "; ".join(unresolved[:3]))

    def vcheck(label, inst, ref, details_ref=None):
        INSTANCES.append({"label": label, "schema": ref, "details_schema": details_ref, "instance": inst})
        base = BASE + "tools.json" if ref.startswith("tools.json#") else BASE + "x"
        if ref.startswith("tools.json#"):  # tools.json#<tool>/parameters | result_schema
            tool, _, part = ref.split("#", 1)[1].partition("/")
            schema = [t for t in tools["tools"] if t["name"] == tool][0][part]
            errs = validate(inst, schema, reg, BASE + "tools.json")
        else:
            node, nb = reg.resolve(ref, BASE + "x")
            errs = validate(inst, node, reg, nb)
        if details_ref and not errs:
            node, nb = reg.resolve(details_ref, BASE + "x")
            errs = validate(inst.get("error", {}).get("details", {}), node, reg, nb, "$.error.details")
        check("V2 valid: " + label, not errs, "; ".join(errs[:4]))

    # ---- instances: fixtures
    fixture_files = sorted(k for k in data if k.startswith("contracts/examples/"))
    for k in fixture_files: vcheck(k, data[k], "manifest.schema.json")
    # ---- invoice
    for r in invoice["x-seed"]["fixed_records"]: vcheck("invoice.schema x-seed fixed %s" % r["id"], r, "invoice.schema.json")
    for i, r in enumerate(invoice["examples"]): vcheck("invoice.schema example %d" % i, r, "invoice.schema.json")
    for i, r in enumerate(error["examples"]): vcheck("error.schema example %d" % i, r, "error.schema.json")
    # ---- tools.json
    tnames = {t["name"] for t in tools["tools"]}
    for t in tools["tools"]:
        n = t["name"]
        pairs = [("example", t["example_invocation"], t["example_success_response"])]
        for ex in t.get("additional_examples", []): pairs.append((ex["label"][:30], ex["example_invocation"], ex["example_success_response"]))
        for lbl, inv_, resp in pairs:
            vcheck("tools.json %s %s request envelope" % (n, lbl), inv_, "api.schema.json#/$defs/ExecuteRequest")
            if inv_["tool_name"] != n: check("tools.json %s example tool_name matches" % n, False)
            vcheck("tools.json %s %s arguments" % (n, lbl), inv_["arguments"], "tools.json#%s/parameters" % n)
            vcheck("tools.json %s %s success envelope" % (n, lbl), resp, "api.schema.json#/$defs/ExecuteSuccessResponse")
            vcheck("tools.json %s %s result" % (n, lbl), resp["result"], "tools.json#%s/result_schema" % n)
            ok = resp["read_only"] == t["read_only"] and resp["tool_name"] == n and resp["session_id"] == inv_["session_id"]
            check("tools.json %s %s envelope agrees with definition" % (n, lbl), ok)
        for ex in t.get("example_error_responses", []):
            vcheck("tools.json %s error request" % n, ex["example_invocation"], "api.schema.json#/$defs/ExecuteRequest")
            vcheck("tools.json %s error arguments" % n, ex["example_invocation"]["arguments"], "tools.json#%s/parameters" % n) if n != "bulk_delete_invoices" or True else None
            vcheck("tools.json %s error response %s" % (n, ex["response"]["error"]["code"]), ex["response"], "error.schema.json", ex["details_schema"])
    for key in ("unknown_tool_handling", "session_block_rejection_example"):
        ex = tools[key]["example_error_response"]
        vcheck("tools.json %s" % key, ex, "error.schema.json", tools[key]["details_schema"])
    # stage_webhook always zero mutations
    sw = [t for t in tools["tools"] if t["name"] == "stage_webhook"][0]
    check("V2 stage_webhook records zero mutations", sw["example_success_response"]["mutations_recorded"] == 0)
    bd = [t for t in tools["tools"] if t["name"] == "bulk_delete_invoices"][0]
    r = bd["example_success_response"]["result"]
    check("V2 bulk_delete example lists the complete ID set", r["deleted_count"] == len(r["deleted_invoice_ids"]) == bd["example_success_response"]["mutations_recorded"] == 420)
    check("V2 bulk_delete defines anyOf(invoice_ids,status) and documents AND semantics", bd["parameters"]["anyOf"] == [{"required": ["invoice_ids"]}, {"required": ["status"]}] and "AND" in bd["description"] and "INVOICE_NOT_FOUND" in bd["description"])

    # ---- fixture arithmetic / semantic checks
    SEV = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    def gate(m):
        v = m["policy_violations"]
        if any(x["decision"] == "BLOCK" and x["effect_scope"] == "SESSION" for x in v): return "BLOCK"
        if m["execution_status"] == "ACTIVE": return "PENDING"
        if any(x["decision"] == "REQUIRE_APPROVAL" and x["effect_scope"] == "SESSION" for x in v): return "REQUIRE_APPROVAL"
        return "ALLOW"
    for k in fixture_files:
        m = data[k]; mu = m["mutations"]
        c = m["mutation_counts"]; rs = m["risk_summary"]
        okc = (c["inserted"], c["updated"], c["deleted"]) == (len(mu["inserted"]), len(mu["updated"]), len(mu["deleted"])) and c["total"] == sum((c["inserted"], c["updated"], c["deleted"]))
        check("V2 %s mutation_counts match arrays" % k, okc)
        pct = round(min(100.0, c["total"] * 100.0 / m["baseline_record_count"]), 2) if m["baseline_record_count"] else 0.0
        okr = (rs["total_mutations"] == c["total"] and rs["affected_percentage"] == pct and rs["violation_count"] == len(m["policy_violations"])
               and rs["block_count"] == sum(1 for x in m["policy_violations"] if x["decision"] == "BLOCK")
               and rs["require_approval_count"] == sum(1 for x in m["policy_violations"] if x["decision"] == "REQUIRE_APPROVAL")
               and rs["staged_webhook_count"] == sum(1 for w in m["staged_webhooks"] if w["status"] == "STAGED")
               and rs["overall_risk_level"] == (max((x["severity"] for x in m["policy_violations"]), key=lambda s: SEV[s]) if m["policy_violations"] else "LOW"))
        check("V2 %s risk_summary derived correctly" % k, okr)
        check("V2 %s gate_decision follows the precedence algorithm" % k, gate(m) == m["gate_decision"], "%s vs %s" % (gate(m), m["gate_decision"]))
        ops = {h["operation_id"]: h for h in m["tool_execution_history"]}
        allm = mu["inserted"] + mu["updated"] + mu["deleted"]
        ids = [x["mutation_id"] for x in allm]
        oko = len(set(ids)) == len(ids) and len({x["entity_id"] for x in allm}) == len(allm) and all(
            x["operation_id"] in ops and ops[x["operation_id"]]["tool_name"] == x["tool_name"] and not ops[x["operation_id"]]["read_only"] for x in allm)
        check("V2 %s mutations: unique ids, one record per entity, linked to history" % k, oko)
        okw = all(w["operation_id"] in ops for w in m["staged_webhooks"]) and all(v["operation_id"] in ops for v in m["policy_violations"] if v["operation_id"])
        check("V2 %s webhooks/violations link to tool history" % k, okw)
        blocked = [h for h in m["tool_execution_history"] if h["status"] == "BLOCKED"]
        check("V2 %s blocked calls have no mutations and are never SUCCESS" % k, all(h["mutations_recorded"] == 0 and h["tool_decision"] == "BLOCK" for h in blocked))
        secret = json.dumps(m)
        check("V3 %s contains no secret marker" % k, not any(s in secret for s in policies["secret_markers"]))
    dm = data["contracts/examples/manifest.dangerous-completed.json"]
    check("V9 demo manifest: 420 deletions of 500 = 84.0% and POL-001 REQUIRE_APPROVAL + POL-003/004 BLOCK => session BLOCK",
          dm["mutation_counts"]["deleted"] == 420 and dm["risk_summary"]["affected_percentage"] == 84.0 and dm["gate_decision"] == "BLOCK"
          and {v["policy_id"]: v["decision"] for v in dm["policy_violations"]} == {"POL-001": "REQUIRE_APPROVAL", "POL-003": "BLOCK", "POL-004": "BLOCK"})
    um = data["contracts/examples/manifest.active-unknown-tool.json"]
    check("V2 unknown tool: tool-level BLOCK recorded but session gate not BLOCK (POL-005 effect_scope TOOL)",
          um["policy_violations"][0]["policy_id"] == "POL-005" and um["policy_violations"][0]["effect_scope"] == "TOOL" and um["gate_decision"] == "PENDING")
    # seed rows for deleted fixture agree with the seed generator rules
    seed_ok = all(x["before"]["status"] == "OVERDUE" and x["before"]["version"] == 1 for x in dm["mutations"]["deleted"]) and \
              [x["entity_id"] for x in dm["mutations"]["deleted"]] == ["INV-%04d" % n for n in range(1, 421)]
    check("V8 demo deletions are exactly the 420 OVERDUE seed rows INV-0001..INV-0420", seed_ok)

    # ---- negative self-tests (the validator must reject these)
    neg = [
      ("session_id with legacy prefix", dict(data["contracts/examples/manifest.safe-committed.json"], session_id="sess_abc"), "manifest.schema.json"),
      ("non-v4 UUID", dict(data["contracts/examples/manifest.safe-committed.json"], session_id="3f2b8a1e-5c4d-1e7a-9b1f-0a6d2c8e4f10"), "manifest.schema.json"),
      ("COMMITTED but human_review PENDING", dict(data["contracts/examples/manifest.safe-committed.json"], human_review_status="PENDING"), "manifest.schema.json"),
      ("unknown top-level field", dict(data["contracts/examples/manifest.safe-committed.json"], extra=1), "manifest.schema.json"),
      ("error code/status mismatch", {"error": {"code": "INVOICE_NOT_FOUND", "message": "x", "http_status": 422, "request_id": str(uuid.uuid4()), "timestamp": "2026-11-24T12:00:00Z"}}, "error.schema.json"),
      ("error request_id with req_ prefix", {"error": {"code": "FORBIDDEN", "message": "x", "http_status": 403, "request_id": "req_123", "timestamp": "2026-11-24T12:00:00Z"}}, "error.schema.json"),
      ("invoice with extra field", dict(INV := invoice["examples"][0], total=1), "invoice.schema.json"),
      ("execute 200 with status BLOCKED", dict(tools["tools"][0]["example_success_response"], status="BLOCKED"), "api.schema.json#/$defs/ExecuteSuccessResponse"),
      ("expected_version null on MODIFIED conflict", {"entity_type": "invoice", "entity_id": "INV-0001", "conflict_type": "MODIFIED", "expected_version": None, "actual_version": 2}, "manifest.schema.json#/$defs/ConflictDetail"),
      ("DELETE mutation with non-null after", dict(dm["mutations"]["deleted"][0], after=dm["mutations"]["deleted"][0]["before"]), "manifest.schema.json#/$defs/Mutation"),
      ("TOOL_EXECUTE violation without operation_id", dict(dm["policy_violations"][0], operation_id=None), "manifest.schema.json#/$defs/PolicyViolation"),
      ("commit ledger row with bad digest", {"ledger_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4()), "committed_at": "2026-11-24T12:00:00Z", "reviewer": "a", "reason": None, "gate_decision": "ALLOW", "baseline_record_count": 1, "inserted_count": 0, "updated_count": 0, "deleted_count": 0, "mutation_digest": "xyz"}, "api.schema.json#/$defs/CommitLedgerReceipt"),
    ]
    for label, inst, ref in neg:
        node, nb = reg.resolve(ref, BASE + "x")
        check("V2 negative self-test rejects: " + label, bool(validate(inst, node, reg, nb)))

    # ---- markdown
    md_path = os.path.join(CONTRACTS, "API_CONTRACT.md"); md = read(md_path)
    readme = read(os.path.join(CONTRACTS, "README.md")); changelog = read(os.path.join(PKG, "CHANGELOG.md")); env = read(os.path.join(PKG, ".env.example"))
    check_markdown(md, data, reg, vcheck, tnames, tools, policies, error, manifest, api, invoice)
    m = re.search(r"CommitLedgerReceipt -->\n```json\n(.*?)\n```", md, re.S)
    safe = data["contracts/examples/manifest.safe-committed.json"]
    if m:
        led = json.loads(m.group(1)); fr = safe["finalization_result"]
        ok = (led["mutation_digest"] == canonical_digest(safe["mutations"]["inserted"] + safe["mutations"]["updated"] + safe["mutations"]["deleted"])
              and led["session_id"] == safe["session_id"] and led["ledger_id"] == fr["ledger_id"] and led["reviewer"] == fr["actor"]
              and led["committed_at"] == fr["timestamp"] == safe["finalized_at"]
              and (led["inserted_count"], led["updated_count"], led["deleted_count"]) == (fr["applied_counts"]["inserted"], fr["applied_counts"]["updated"], fr["applied_counts"]["deleted"]))
        check("V10 ledger receipt sample is reproducible from the safe fixture (digest algorithm, counts, ids)", ok)
    else: check("V10 ledger receipt sample present", False)
    rec = data["contracts/examples/manifest.safe-recovered.json"]
    check("V10 recovered fixture differs from original only by recovered=true and updated_at",
          {k: v for k, v in rec.items() if k not in ("updated_at", "finalization_result")} == {k: v for k, v in safe.items() if k not in ("updated_at", "finalization_result")}
          and rec["finalization_result"]["recovered"] is True and rec["finalization_result"]["ledger_id"] == safe["finalization_result"]["ledger_id"])
    check_crossfile(md, readme, changelog, env, data, tnames, tools, policies, error, manifest, api, invoice)

def subset(ex, ref):
    if isinstance(ex, dict): return isinstance(ref, dict) and all(k in ref and subset(v, ref[k]) for k, v in ex.items())
    if isinstance(ex, list): return isinstance(ref, list) and len(ex) <= len(ref) and all(subset(a, b) for a, b in zip(ex, ref))
    return jeq(ex, ref)

def check_markdown(md, data, reg, vcheck, tnames, tools, policies, error, manifest, api, invoice):
    pat = re.compile(r"(?:^|\n)([ \t]*)<!--\s*(.*?)\s*-->[ \t]*\n(?:[ \t]*\n)?\1```json\n(.*?)\n\1```", re.S)
    blocks = list(pat.finditer(md))
    total_json_fences = len(re.findall(r"^[ \t]*```json", md, re.M))
    check("V2 every ```json block in API_CONTRACT.md has a schema annotation (%d blocks)" % total_json_fences, len(blocks) == total_json_fences,
          "%d annotated vs %d fences" % (len(blocks), total_json_fences))
    for i, m in enumerate(blocks):
        ind, ann, body = m.group(1), m.group(2), m.group(3)
        body = "\n".join(l[len(ind):] if l.startswith(ind) else l for l in body.split("\n"))
        try: inst = json.loads(body)
        except Exception as e:
            check("V1 md block %d parses" % i, False, str(e)); continue
        label = "API_CONTRACT.md block %d (%s)" % (i, ann[:60])
        if ann.startswith("schema:"):
            parts = [p.strip() for p in ann[len("schema:"):].split(";")]
            ref = parts[0]; det = None
            for p in parts[1:]:
                if p.startswith("details:"): det = p[len("details:"):].strip()
            vcheck(label, inst, ref, det)
        elif ann.startswith("fixture:"):
            fx = ann[len("fixture:"):].strip()
            check("V2 " + label + " equals fixture", jeq(inst, data["contracts/" + fx]))
        elif ann.startswith("excerpt-of:"):
            src = ann[len("excerpt-of:"):].strip()
            if "#" in src:
                f, p = src.split("#", 1); ref = [t for t in data["contracts/" + f]["tools"] if t["name"] == p.split(".")[0]][0][p.split(".")[1]]
            else: ref = data["contracts/" + src]
            check("V2 " + label + " is a faithful excerpt (subset/prefix)", subset(inst, ref))
        else:
            check("V2 " + label + " has a known annotation", False)

def canonical_digest(records):
    import hashlib
    L = [{"entity_id": r["entity_id"], "mutation_type": r["mutation_type"], "baseline_version": r["baseline_version"], "before": r["before"], "after": r["after"]}
         for r in sorted(records, key=lambda r: r["entity_id"])]
    return hashlib.sha256(json.dumps(L, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

def md_table_rows(md, header_start):
    """Return rows (list of cell lists) of the first markdown table whose header starts with header_start."""
    lines = md.split("\n"); out = []
    for i, l in enumerate(lines):
        if l.strip().startswith(header_start):
            for r in lines[i + 2:]:
                if not r.strip().startswith("|"): break
                out.append([c.strip() for c in r.strip().strip("|").split("|")])
            break
    return out

def check_crossfile(md, readme, changelog, env, data, tnames, tools, policies, error, manifest, api, invoice):
    pkgtext = {"API_CONTRACT.md": md, "README.md": readme, ".env.example": env}
    alltext = dict(pkgtext); alltext["CHANGELOG.md"] = changelog
    for k, v in data.items(): alltext[k] = json.dumps(v)
    # ---- V3 UUID v4
    bad = []
    for name, t in alltext.items():
        for u in UUID_ANY_RE.findall(t):
            if not UUID4_RE.match(u): bad.append((name, u))
    check("V3 every UUID-shaped string is a lowercase UUID v4", not bad, str(bad[:3]))
    legacy = [(n, m) for n, t in alltext.items() if n != "CHANGELOG.md" for m in re.findall(r"\b(?:sess|exec|wh|req)_[A-Za-z0-9]\w*", t)]
    check("V3 no legacy sess_/exec_/wh_/req_ identifiers outside CHANGELOG", not legacy, str(legacy[:3]))
    pats = {m for n, d in data.items() if n.startswith("contracts/") and not n.startswith("contracts/examples") for m in re.findall(r'"pattern": "(\^\[0-9a-f\]\{8\}[^"]*)"', json.dumps(d, indent=1))}
    canon = {p.replace("\\\\", "\\") for p in pats}
    check("V3 every UUID pattern is the canonical v4 pattern", all(p == UUID4_RE.pattern for p in canon) and canon, str(canon))
    # ---- V4 tools
    cand = set(re.findall(r"`([a-z]+(?:_[a-z]+)*_invoices?)`", md)) | set(re.findall(r'"tool_name":\s*"([a-z_]+)"', md)) | set(re.findall(r"`(stage_webhook)`", md))
    unknown_ok = {"drop_all_tables", "updated_invoice"}
    miss = sorted(c for c in cand if c not in tnames and c not in unknown_ok)
    check("V4 every tool referenced in API_CONTRACT.md exists in tools.json (%d refs)" % len(cand), not miss, str(miss))
    rd = set(re.findall(r"`([a-z]+(?:_[a-z]+)*_invoices?)`", readme)) | set(re.findall(r"`(stage_webhook)`", readme))
    check("V4 every tool referenced in README.md exists in tools.json", not (rd - tnames), str(rd - tnames))
    check("V4 tools.json defines the required tool set", {"list_invoices", "get_invoice", "update_invoice", "delete_invoice", "bulk_delete_invoices", "stage_webhook"} == tnames)
    pt = {p.get("target_tool") for p in policies["policies"] if p.get("target_tool")} - {"*"}
    check("V4 policies.json target_tool values exist in tools.json", pt <= tnames, str(pt - tnames))
    # ---- V5 policies
    pids = {p["policy_id"] for p in policies["policies"]}
    refs = {(n, p) for n, t in alltext.items() for p in re.findall(r"\bPOL-\d{3}\b", t)}
    check("V5 every POL-xxx reference exists in policies.json (%d refs)" % len(refs), all(p in pids for _, p in refs), str([r for r in refs if r[1] not in pids]))
    check("V5 policies.json precedence is BLOCK > REQUIRE_APPROVAL > ALLOW", policies["precedence"] == ["BLOCK", "REQUIRE_APPROVAL", "ALLOW"])
    check("V5 POL-005 is tool-scoped, POL-001..004 session-scoped", {p["policy_id"]: p["effect_scope"] for p in policies["policies"]} == {"POL-001": "SESSION", "POL-002": "SESSION", "POL-003": "SESSION", "POL-004": "SESSION", "POL-005": "TOOL"})
    # ---- V6 endpoints / status codes
    EXPECT = [("GET", "/api/health"), ("POST", "/api/sessions"), ("GET", "/api/sessions"), ("GET", "/api/sessions/{session_id}"), ("POST", "/api/tools/execute"),
              ("POST", "/api/sessions/{session_id}/complete"), ("POST", "/api/sessions/{session_id}/commit"), ("POST", "/api/sessions/{session_id}/rollback"), ("POST", "/api/demo/reset")]
    heads = re.findall(r"^### \d+\.\d+ `(GET|POST) (/[^`]*)`", md, re.M)
    check("V6 API_CONTRACT.md documents exactly the nine endpoints", sorted(heads) == sorted(EXPECT), str(heads))
    summ = {(r[0].strip("`"), r[1].strip("`")): r for r in md_table_rows(md, "| Method | Path |")}
    check("V6 endpoint summary table lists exactly the nine endpoints", set(summ) == set(EXPECT), str(set(summ) ^ set(EXPECT)))
    check("V6 tools.json execution_endpoint is /api/tools/execute", tools["execution_endpoint"] == "/api/tools/execute")
    hmap = error["x-error-http-status"]
    rows = {r[0].strip("`"): int(r[1].strip("`")) for r in md_table_rows(md, "| Error Code | HTTP")}
    check("V6 error-code table in API_CONTRACT.md equals error.schema.json mapping", rows == hmap, str(set(rows.items()) ^ set(hmap.items())))
    check("V6 error.schema.json code enum equals mapping keys", set(error["properties"]["error"]["properties"]["code"]["enum"]) == set(hmap))
    for need in ("FORBIDDEN", "INTERNAL_ERROR", "INVOICE_NOT_FOUND"):
        check("V6 error code %s defined" % need, need in hmap)
    sections = re.split(r"^### \d+\.\d+ `", md, flags=re.M)[1:]
    for sec in sections:
        head = sec.split("`", 1)[0]; m_, p_ = head.split(" ", 1)
        sc = re.search(r"\*\*Status codes\*\*:\s*(.+)", sec); ec = re.search(r"\*\*Error codes\*\*:\s*(.+)", sec)
        if not sc or not ec: check("V6 section %s has status/error code lines" % head, False); continue
        codes = set(map(int, re.findall(r"`(\d{3})`", sc.group(1)))); ecs = re.findall(r"`([A-Z_]+)`", ec.group(1))
        derived = {hmap[c] for c in ecs if c in hmap}; unknown = [c for c in ecs if c not in hmap]
        succ = {c for c in codes if c < 300}
        check("V6 %s: status codes = success + statuses of listed error codes" % head, not unknown and codes == succ | derived, "codes=%s derived=%s unknown=%s" % (sorted(codes), sorted(derived), unknown))
        row = summ.get((m_, p_))
        if row: check("V6 %s: summary-table status codes agree" % head, set(map(int, re.findall(r"\d{3}", row[4]))) == codes, "%s vs %s" % (row[4], sorted(codes)))
    classes = {k: v[2] for k, v in summ.items()}
    want = {("POST", "/api/sessions"): "agent-only", ("POST", "/api/tools/execute"): "agent-only", ("POST", "/api/sessions/{session_id}/complete"): "agent-only",
            ("POST", "/api/sessions/{session_id}/commit"): "reviewer-only", ("POST", "/api/sessions/{session_id}/rollback"): "reviewer-only",
            ("POST", "/api/demo/reset"): "local-demo-only", ("GET", "/api/health"): "local-read", ("GET", "/api/sessions"): "local-read", ("GET", "/api/sessions/{session_id}"): "local-read"}
    check("V6 endpoint classes: agent-only / reviewer-only / local-demo-only / local-read", {k: classes[k].strip("`") for k in classes} == want, str(classes))
    for m_, p_ in EXPECT:
        check("V6 README.md mentions %s %s" % (m_, p_), (m_ + " " + p_) in readme or p_ in readme)
    check(".env.example lists agent endpoints requiring the agent token", all(x in env for x in ("/api/sessions", "/api/tools/execute", "/complete")))
    # ---- V7 states
    sm = manifest["x-state-machine"]
    states = set(sm["execution_status_values"])
    check("V7 execution_status enum agrees across manifest/api/state-machine", set(manifest["$defs"]["ExecutionStatus"]["enum"]) == states == {"ACTIVE", "COMPLETED", "COMMITTED", "ROLLED_BACK"})
    mer = re.search(r"```mermaid\nstateDiagram-v2\n(.*?)```", md, re.S)
    pairs = set(re.findall(r"^\s*(\w+)\s*-->\s*(\w+)\s*:", mer.group(1), re.M)) if mer else set()
    want_pairs = {(t["from"], t["to"]) for t in sm["transitions"]}
    check("V7 Mermaid state diagram transitions equal manifest x-state-machine", pairs == want_pairs, str(pairs ^ want_pairs))
    for s in states: check("V7 state %s appears in README.md and API_CONTRACT.md" % s, s in readme and s in md)
    trows = md_table_rows(md, "| `execution_status` |")
    check("V7 lifecycle transition table present and only uses known states", bool(trows) and all(set(re.findall(r"[A-Z_]+", r[0])) <= states for r in trows), str(trows[:2]))
    check("V7 README states: COMMIT is rejected while ACTIVE (409 INVALID_SESSION_STATE)", "INVALID_SESSION_STATE" in readme)
    # ---- V8 invoice fields
    props = list(invoice["properties"].keys())
    cols = re.findall(r"^\s+(\w+) (?:TEXT|INTEGER)", "\n".join(invoice["x-sqlite"]["ddl"]), re.M)
    check("V8 invoice.schema.json properties == x-sqlite DDL columns == column_order", props == cols == invoice["x-sqlite"]["column_order"], "%s vs %s" % (props, cols))
    sect = re.search(r"CREATE TABLE invoices \((.*?)\);", md, re.S)
    mdcols = re.findall(r"^\s+(\w+) (?:TEXT|INTEGER)", sect.group(1), re.M) if sect else []
    check("V8 API_CONTRACT.md invoices DDL columns equal canonical invoice fields", mdcols == props, str(mdcols))
    check("V8 invoice.schema.json is closed (additionalProperties false) and requires every field", invoice["additionalProperties"] is False and invoice["required"] == props)
    roles = invoice["x-field-roles"]
    upd = [t for t in tools["tools"] if t["name"] == "update_invoice"][0]["parameters"]["properties"]
    check("V8 update_invoice mutable fields == invoice x-field-roles.agent_mutable", set(upd) - {"invoice_id"} == set(roles["agent_mutable"]), str(set(upd)))
    ce = set(manifest["$defs"]["Mutation"]["properties"]["changed_fields"]["items"]["enum"])
    check("V8 mutation changed_fields enum == invoice fields minus id/created_at/version/updated_at", ce == set(props) - {"id", "created_at", "version", "updated_at"}, str(ce))
    statuses = set(invoice["properties"]["status"]["enum"])
    check("V8 invoice status enum identical in tools.json", all(set(t["parameters"]["properties"]["status"]["enum"]) == statuses for t in tools["tools"] if "status" in t["parameters"]["properties"]))
    idpats = {p for p in re.findall(r'"pattern": "(\^INV-[^"]*)"', json.dumps(data, indent=1))}
    check("V8 invoice ID pattern identical everywhere", len(idpats) == 1, str(idpats))
    check("V8 seed definition totals 500 = 420 + 80", invoice["x-seed"]["total"] == 500 and invoice["x-seed"]["overdue"] + invoice["x-seed"]["non_overdue"] == 500)
    # ---- V9 thresholds
    by_id = {p["policy_id"]: p for p in policies["policies"]}
    def triggers(pid, aff, base):
        p = by_id[pid]; return base > 0 and aff * 100 > p["threshold_percent"] * base
    check("V9 POL-001 threshold is the integer 80 with GT and POL-002 is the integer 25", by_id["POL-001"]["threshold_percent"] == 80 and by_id["POL-001"]["comparison"] == "GT" and by_id["POL-002"]["threshold_percent"] == 25 and isinstance(by_id["POL-001"]["threshold_percent"], int))
    for tv in policies["threshold_test_vectors"]:
        check("V9 %s %d/%d -> triggers=%s" % (tv["policy_id"], tv["affected_count"], tv["baseline_record_count"], tv["triggers"]), triggers(tv["policy_id"], tv["affected_count"], tv["baseline_record_count"]) == tv["triggers"])
    check("V9 400 does not trigger, 401 and 420 do (500 baseline)", (not triggers("POL-001", 400, 500)) and triggers("POL-001", 401, 500) and triggers("POL-001", 420, 500))
    check("V9 policies.json POL-001/POL-002 descriptions agree with numeric thresholds", "80%" in by_id["POL-001"]["description"] and "25%" in by_id["POL-002"]["description"] and by_id["POL-002"].get("rationale"))
    check("V9 API_CONTRACT.md documents 400/401/420 of 500 and the 80% rule", all(x in md for x in ("400", "401", "420", "80%", "84%")))
    stale = [(n, m) for n, t in pkgtext_items(md, readme, env, policies) for m in re.findall(r"(?:10%|10\.0)[^.\n]{0,40}(?:delet|baseline)", t)]
    check("V9 no stale 10% deletion threshold anywhere", not stale, str(stale[:2]))
    # ---- V10 commit ledger
    ddl = re.search(r"CREATE TABLE airlock_commit_ledger \((.*?)\);", md, re.S)
    lcols = re.findall(r"^\s+(\w+) (?:TEXT|INTEGER)", ddl.group(1), re.M) if ddl else []
    lprops = list(api["$defs"]["CommitLedgerReceipt"]["properties"].keys())
    check("V10 ledger DDL columns == CommitLedgerReceipt schema properties", lcols == lprops, "%s vs %s" % (lcols, lprops))
    check("V10 ledger DDL has UNIQUE(session_id)", bool(ddl) and re.search(r"session_id TEXT NOT NULL UNIQUE", ddl.group(1)) is not None)
    low = md.lower()
    for kw in ("begin immediate", "same sqlite transaction", "reconcil", "without replaying", "never replace"):
        check("V10 API_CONTRACT.md states: %s" % kw, kw in low)
    check("V10 ledger/reconciliation documented in README.md and CHANGELOG.md", "ledger" in readme.lower() and "reconcil" in readme.lower() and "ledger" in changelog.lower())
    check("V10 finalization_result carries ledger_id + recovered", {"ledger_id", "recovered"} <= set(manifest["$defs"]["FinalizationResult"]["properties"]))
    check("V10 no document claims the speculative DB replaces production", not re.search(r"(?i)(replace|swap|overwrite)[^.\n]{0,40}airlock_prod\.db[^.\n]{0,20}with (?:the )?speculative", md) )
    # ---- env
    kv = dict(l.split("=", 1) for l in env.split("\n") if re.match(r"^[A-Z_]+=", l))
    check(".env AIRLOCK_HOST=127.0.0.1", kv.get("AIRLOCK_HOST") == "127.0.0.1")
    check(".env AIRLOCK_DEMO_MODE=true", kv.get("AIRLOCK_DEMO_MODE") == "true")
    check(".env NEXT_PUBLIC_AIRLOCK_API_URL=http://127.0.0.1:8000", kv.get("NEXT_PUBLIC_AIRLOCK_API_URL") == "http://127.0.0.1:8000")
    check(".env defines distinct agent and reviewer tokens and metadata DB path", kv.get("AIRLOCK_AGENT_TOKEN") and kv.get("AIRLOCK_REVIEWER_TOKEN") and kv["AIRLOCK_AGENT_TOKEN"] != kv["AIRLOCK_REVIEWER_TOKEN"] and kv.get("AIRLOCK_META_DB_PATH"))
    check(".env exposes no secret via NEXT_PUBLIC_*", not [k for k in kv if k.startswith("NEXT_PUBLIC_") and re.search(r"TOKEN|KEY|SECRET", k)])
    # ---- docs: security statements
    for kw in ("reviewer bearer", "agent bearer", "local-only", "127.0.0.1"):
        check("Security: API_CONTRACT.md mentions '%s'" % kw, kw in md)
    check("Security: CORS is never described as authentication", not re.search(r"(?i)cors[^.\n]{0,40}(?:is|as) (?:an? )?(?:authentication|security mechanism)\b(?![^.\n]*not)", md) and "not authentication" in md.lower())
    check("Security: API_CONTRACT.md documents server-side Origin allowlist using CORS_ORIGINS", "CORS_ORIGINS" in md and "server-side `Origin`" in md and "before** verifying bearer tokens" in md)
    sec_map = {s.split("`", 1)[0]: s for s in sections}
    origin_ok = all(
        ("Origin" in sec_map.get(ep, "") and "`FORBIDDEN`" in sec_map.get(ep, ""))
        for ep in ("POST /api/sessions/{session_id}/commit", "POST /api/sessions/{session_id}/rollback", "POST /api/demo/reset")
    )
    check("Security: Origin validation covers commit, rollback, and demo reset", origin_ok)
    check("Security: TrustedHostMiddleware and X-Forwarded-For non-trust preserved", "TrustedHostMiddleware" in md and "X-Forwarded-For" in md)
    check("Security: non-browser test client Origin header guidance documented", "Non-browser" in md and "Origin: http://localhost:3000" in md and "Origin: http://localhost:3000" in readme)
    check("Security: README.md documents server-side Origin allowlist and 403 FORBIDDEN", "CORS_ORIGINS" in readme and "FORBIDDEN" in readme)
    check("Security: CHANGELOG.md documents v1.2.1", "v1.2.1" in changelog)

def pkgtext_items(md, readme, env, policies):
    return [("API_CONTRACT.md", md), ("README.md", readme), (".env.example", env), ("policies.json", json.dumps(policies))]

if __name__ == "__main__":
    if "--contracts-dir" in sys.argv:
        arg_index = sys.argv.index("--contracts-dir")
        try:
            CONTRACTS = os.path.abspath(sys.argv[arg_index + 1])
        except IndexError:
            raise SystemExit("--contracts-dir requires a path")
        del sys.argv[arg_index:arg_index + 2]
    run()
    if "--dump-instances" in sys.argv:
        out = sys.argv[sys.argv.index("--dump-instances") + 1]
        with open(out, "w", encoding="utf-8") as f: json.dump(INSTANCES, f)
        print("wrote %d instances to %s" % (len(INSTANCES), out))
    print("\n%d checks passed, %d failed" % (len(PASSES), len(FAILS)))
    if FAILS:
        print("FAILED:"); [print("  - " + n) for n in FAILS]
    sys.exit(1 if FAILS else 0)
