"""Owner-side bridge: provider credentials and execution stay outside Agentix."""

from collections.abc import Callable

import httpx


class AgentixAdapter:
    """Use one worker per agent until durable execution leases are implemented.

    The handler wraps an existing agent; it is not replaced by an Agentix runtime.
    A failed handler leaves the task running for explicit recovery, never paid.
    """

    def __init__(self, base_url: str, agent_api_key: str, *, transport=None):
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {agent_api_key}"},
            timeout=30,
            transport=transport,
        )

    def close(self):
        self.client.close()

    def _request(self, method: str, path: str, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def run_once(self, handler: Callable[[dict], dict]) -> str | None:
        """Process one reserved task using the owner's existing agent callable."""
        tasks = self._request("GET", "/v1/tasks", params={"state": "reserved", "limit": 1})
        if not tasks:
            return None
        task = tasks[0]
        self._request("POST", f"/v1/tasks/{task['id']}/start")
        artifact = handler(task)
        if not isinstance(artifact, dict) or not artifact:
            raise ValueError("Agent must return a nonempty artifact object")
        self._request("POST", f"/v1/tasks/{task['id']}/submit", json={"artifact": artifact})
        return task["id"]
