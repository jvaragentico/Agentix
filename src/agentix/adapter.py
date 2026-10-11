"""Owner-side bridge: provider credentials and execution stay outside Agentix."""

import secrets
from collections.abc import Callable
from threading import Event, Thread

import httpx


class LeaseLostError(RuntimeError):
    """Execution stopped being authorized; its result must not be submitted."""


class AgentixAdapter:
    """Claim one task atomically and renew the execution lease during local work.

    The handler wraps an existing agent; it is not replaced by an Agentix runtime.
    A failed handler leaves the task leased until expiry, never paid automatically.
    """

    def __init__(
        self,
        base_url: str,
        agent_api_key: str,
        *,
        transport=None,
        lease_seconds=300,
        sites_service_token: str | None = None,
    ):
        if not isinstance(lease_seconds, int) or not 30 <= lease_seconds <= 900:
            raise ValueError("Lease duration must be between 30 and 900 seconds")
        self.lease_seconds = lease_seconds
        headers = {"Authorization": f"Bearer {agent_api_key}"}
        if sites_service_token:
            headers["OAI-Sites-Authorization"] = f"Bearer {sites_service_token}"
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            follow_redirects=False,
            timeout=30,
            transport=transport,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def discover(self) -> dict:
        """Read the versioned, credential-free Agentix protocol manifest."""
        return self._request("GET", "/.well-known/agentix.json")

    def run_forever(
        self,
        handler: Callable[[dict], dict],
        *,
        stop: Event,
        poll_seconds: float = 2,
        max_poll_seconds: float = 30,
    ):
        """Poll with bounded idle backoff. Errors propagate without replaying work.

        Setting stop interrupts idle waiting; an active handler completes and submits
        under its renewable lease before shutdown. Handlers own their tool timeouts.
        """
        if not 0 < poll_seconds <= max_poll_seconds <= 300:
            raise ValueError("Polling intervals must satisfy 0 < initial <= maximum <= 300")
        delay = poll_seconds
        while not stop.is_set():
            task_id = self.run_once(handler)
            if task_id is not None:
                delay = poll_seconds
                continue
            if stop.wait(delay):
                break
            delay = min(delay * 2, max_poll_seconds)

    def close(self):
        self.client.close()

    def _request(self, method: str, path: str, **kwargs):
        response = self.client.request(method, path, **kwargs)
        response.raise_for_status()
        if response.status_code == 204:
            return None
        return response.json()

    def run_once(self, handler: Callable[[dict], dict]) -> str | None:
        """Process one task. Handlers must make external side effects idempotent."""
        token = secrets.token_urlsafe(32)
        headers = {"X-Execution-Token": token}
        lease = {"lease_seconds": self.lease_seconds}
        task = self._request("POST", "/v1/tasks/claim", headers=headers, json=lease)
        if task is None:
            return None
        stopped = Event()
        failures = []

        def renew():
            while not stopped.wait(self.lease_seconds / 3):
                try:
                    self._request(
                        "POST", f"/v1/tasks/{task['id']}/heartbeat", headers=headers, json=lease
                    )
                except Exception as exc:
                    failures.append(exc)
                    return

        worker = Thread(target=renew, daemon=True)
        worker.start()
        try:
            artifact = handler(task)
        finally:
            stopped.set()
            worker.join()
        if failures:
            raise LeaseLostError("Lease renewal failed; result was not submitted") from failures[0]
        if not isinstance(artifact, dict) or not artifact:
            raise ValueError("Agent must return a nonempty artifact object")
        self._request(
            "POST", f"/v1/tasks/{task['id']}/submit", headers=headers, json={"artifact": artifact}
        )
        return task["id"]
