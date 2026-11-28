"""HTTP adapter for the three agent-only Airlock operations."""

import json
from pathlib import Path
from urllib.parse import quote

import httpx
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
SCHEMAS = {
    name: json.loads((CONTRACTS / name).read_text(encoding="utf-8"))
    for name in ("api.schema.json", "error.schema.json", "manifest.schema.json",
                 "invoice.schema.json")
}
REGISTRY = Registry().with_resources(
    (schema["$id"], Resource.from_contents(schema)) for schema in SCHEMAS.values()
)
API = SCHEMAS["api.schema.json"]["$id"] + "#/$defs/"
TOOL_SPEC = json.loads((CONTRACTS / "tools.json").read_text(encoding="utf-8"))
TOOLS = {tool["name"]: tool for tool in TOOL_SPEC["tools"]}


class AgentError(Exception):
    """A failure that can be reported without logging bodies or credentials."""


class ApiError(AgentError):
    def __init__(self, status, error):
        self.status = status
        self.code = error["code"]
        self.details = error.get("details", {})
        super().__init__(f"Airlock HTTP {status} {self.code} (request {error['request_id']})")


def validate(value, schema, label):
    validator = Draft202012Validator(
        {"$id": "https://airlock.local/contracts/agent-validation.json", "allOf": [schema]},
        registry=REGISTRY,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )
    if not validator.is_valid(value):
        raise AgentError(f"{label} does not match the Airlock contract.")


class Airlock:
    def __init__(self, client, token):
        self.client = client
        self.headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _post(self, path, body, expected_status):
        try:
            response = self.client.post(path, json=body, headers=self.headers)
        except httpx.RequestError:
            raise AgentError(f"Airlock request failed for {path}. Outcome may be unknown.") from None
        try:
            data = response.json()
        except ValueError:
            raise AgentError(f"Airlock returned an invalid JSON response (HTTP {response.status_code}).") from None
        if response.status_code == expected_status:
            return data
        schema = SCHEMAS["error.schema.json"]
        validate(data, {"$ref": schema["$id"]}, f"Error response (HTTP {response.status_code})")
        error = data["error"]
        if error["http_status"] != response.status_code:
            raise AgentError("Airlock error envelope disagrees with the HTTP status.")
        raise ApiError(response.status_code, error)

    def create(self, agent_name, task_description):
        body = {"agent_name": agent_name, "task_description": task_description}
        validate(body, {"$ref": API + "CreateSessionRequest"}, "Session request")
        data = self._post("/api/sessions", body, 201)
        validate(data, {"$ref": API + "CreateSessionResponse"}, "Session response")
        return data

    def execute(self, session_id, name, arguments):
        if name not in TOOLS:
            raise AgentError("Tool is absent from the Airlock allowlist.")
        tool = TOOLS[name]
        body = {"session_id": session_id, "tool_name": name, "arguments": arguments}
        validate(body, {"$ref": API + "ExecuteRequest"}, "Tool request")
        validate(arguments, tool["parameters"], "Tool arguments")
        data = self._post(TOOL_SPEC["execution_endpoint"], body, 200)
        validate(data, {"$ref": API + "ExecuteSuccessResponse"}, "Tool response")
        validate(data["result"], tool["result_schema"], "Tool result")
        if (data["session_id"], data["tool_name"], data["read_only"]) != (
            session_id, name, tool["read_only"]
        ):
            raise AgentError("Airlock tool response disagrees with the invocation.")
        return data

    def complete(self, session_id, summary):
        validate(session_id, {"$ref": "manifest.schema.json#/$defs/Uuid4"}, "Session ID")
        body = {"agent_summary": summary}
        validate(body, {"$ref": API + "CompleteRequest"}, "Completion request")
        path = f"/api/sessions/{quote(session_id, safe='')}/complete"
        data = self._post(path, body, 200)
        validate(data, {"$ref": SCHEMAS["manifest.schema.json"]["$id"]}, "Completion manifest")
        if data["session_id"] != session_id or data["execution_status"] != "COMPLETED":
            raise AgentError("Airlock completion response disagrees with the session.")
        return data
