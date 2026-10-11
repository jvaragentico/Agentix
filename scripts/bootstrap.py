"""Idempotent private local setup. Credentials are written only to an ignored file."""

import json
import os
import secrets
from pathlib import Path

import httpx

path = Path(".runtime/access.json")
if path.exists():
    print("Already initialized; retained existing credentials.")
    raise SystemExit(0)
admin = os.environ["AGENTIX_ADMIN_TOKEN"]
base = os.environ.get("AGENTIX_BASE_URL", "http://127.0.0.1:8000")
c = httpx.Client(base_url=base, timeout=30)
admin_headers = {"Authorization": f"Bearer {admin}"}
owner = c.post("/v1/admin/owners", headers=admin_headers, json={"name": "Your creator workspace"})
owner.raise_for_status()
creator = owner.json()
h = {"Authorization": f"Bearer {creator['api_key']}"}
r = c.post(
    f"/v1/admin/owners/{creator['id']}/test-funding",
    headers={**admin_headers, "Idempotency-Key": secrets.token_urlsafe(20)},
    json={"amount": 10000},
)
r.raise_for_status()
agents = []
for name, framework, slug, description in [
    ("Marketing specialist", "openai-compatible", "marketing", "Write compelling marketing copy"),
    ("Code collaborator", "hermes-compatible", "coding", "Explain and review code"),
]:
    r = c.post(
        "/v1/agents",
        headers=h,
        json={
            "name": name,
            "framework": framework,
            "endpoint": "https://owner-managed.example/agent",
            "capacity": 5,
        },
    )
    r.raise_for_status()
    a = r.json()
    r = c.post(
        f"/v1/agents/{a['id']}/skills",
        headers=h,
        json={"slug": slug, "version": "1", "description": description},
    )
    r.raise_for_status()
    c.patch(
        f"/v1/agents/{a['id']}/availability", headers=h, json={"available": True}
    ).raise_for_status()
    c.patch(
        f"/v1/agents/{a['id']}/allowance", headers=h, json={"project_allowance": 1000}
    ).raise_for_status()
    agents.append(a)
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps({"admin": admin, "creator": creator, "agents": agents}, indent=2))
path.chmod(0o600)
print("Created private workspace. Credentials saved in ignored .runtime/access.json.")
