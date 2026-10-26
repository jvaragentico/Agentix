"""Owner-side bridge: provider credentials and execution stay outside Agentix."""

import math
import random
import re
import secrets
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from threading import Event, Thread

import httpx

from agentix.payload_limits import MAX_REQUEST_BYTES, SIZE_ERROR


class LeaseLostError(RuntimeError):
    """Execution stopped being authorized; its result must not be submitted."""


class LeaseContext:
    """Cooperative notification of observed renewal failure; contains no credentials.

    The owner runtime decides how to stop its tools. A healthy flag is not proof
    that the server lease is still valid, and this context cannot cancel a thread.
    """

    def __init__(self):
        self._lost = Event()

    @property
    def lease_lost(self) -> bool:
        return self._lost.is_set()

    def wait_for_loss(self, timeout: float | None = None) -> bool:
        """Wait up to timeout seconds; return True when renewal failure is observed."""
        return self._lost.wait(timeout)

    def raise_if_lost(self):
        if self.lease_lost:
            raise LeaseLostError("Lease renewal failed; stop local work")


class AgentixAdapter:
    """Claim one task atomically and renew the execution lease during local work.

    The handler wraps an existing agent; it is not replaced by an Agentix runtime.
    A failed handler leaves the task leased until expiry, never paid automatically.
    request_timeout_seconds bounds HTTPX connect/read/write/pool waits per attempt,
    not total request duration, handler execution or the full retry sequence.
    """

    def __init__(
        self,
        base_url: str,
        agent_api_key: str,
        *,
        transport=None,
        lease_seconds=300,
        sites_service_token: str | None = None,
        max_retries: int = 2,
        retry_base_seconds: float = 0.25,
        max_retry_seconds: float = 5,
        backoff_jitter: bool = True,
        request_timeout_seconds: float = 30,
    ):
        if not isinstance(lease_seconds, int) or not 30 <= lease_seconds <= 900:
            raise ValueError("Lease duration must be between 30 and 900 seconds")
        if type(max_retries) is not int or not 0 <= max_retries <= 3:
            raise ValueError("max_retries must be an integer between 0 and 3")
        if not 0 < retry_base_seconds <= max_retry_seconds <= 30:
            raise ValueError("Retry delays must satisfy 0 < base <= maximum <= 30")
        if type(backoff_jitter) is not bool:
            raise ValueError("backoff_jitter must be a boolean")
        if type(request_timeout_seconds) not in (int, float) or not (
            0 < request_timeout_seconds <= 30
        ):
            raise ValueError(
                "request_timeout_seconds must be a number greater than 0 and at most 30"
            )
        self.backoff_jitter = backoff_jitter
        self.max_retries = max_retries
        self.retry_base_seconds = retry_base_seconds
        self.max_retry_seconds = max_retry_seconds
        self.lease_seconds = lease_seconds
        headers = {"Authorization": f"Bearer {agent_api_key}"}
        if sites_service_token:
            headers["OAI-Sites-Authorization"] = f"Bearer {sites_service_token}"
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=headers,
            follow_redirects=False,
            timeout=request_timeout_seconds,
            transport=transport,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def discover(self) -> dict:
        """Read the versioned, credential-free Agentix protocol manifest."""
        return self._request("GET", "/.well-known/agentix.json")

    @staticmethod
    def _task_path(task_id: str) -> str:
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
            raise ValueError(
                "task_id must contain 1–128 ASCII letters, digits, underscores or hyphens"
            )
        return f"/v1/tasks/{task_id}"

    def get_task(self, task_id: str) -> dict:
        """Read a visible assignment without claiming, renewing or settling it."""
        return self._request("GET", self._task_path(task_id))

    @staticmethod
    def _page_params(limit: int, offset: int) -> dict:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")
        if type(offset) is not int or not 0 <= offset <= 9_007_199_254_740_991:
            raise ValueError("offset must be a nonnegative safe integer")
        return {"limit": limit, "offset": offset}

    def get_task_events(self, task_id: str, *, limit: int = 50, offset: int = 0) -> list[dict]:
        """Read one execution-history page; the server enforces participant visibility."""
        path = self._task_path(task_id)
        return self._request("GET", f"{path}/events", params=self._page_params(limit, offset))

    def list_tasks(
        self, *, state: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[dict]:
        """Read one provider-inbox page, without claiming work or renewing leases."""
        params = self._page_params(limit, offset)
        if state is not None:
            if not isinstance(state, str) or state not in {
                "reserved",
                "running",
                "submitted",
                "accepted",
                "cancelled",
            }:
                raise ValueError("state must be a supported task state or None")
            params["state"] = state
        return self._request("GET", "/v1/tasks", params=params)

    def run_forever(
        self,
        handler: Callable[..., dict],
        *,
        stop: Event,
        poll_seconds: float = 2,
        max_poll_seconds: float = 30,
        max_tasks: int | None = None,
        max_session_seconds: float | None = None,
        pass_context: bool = False,
    ):
        """Poll with bounded idle backoff. Exhausted request errors propagate.

        Setting stop interrupts idle waiting; an active handler completes and submits
        under its renewable lease before shutdown. Handlers own their tool timeouts.
        max_tasks bounds successful submissions in this invocation, not elapsed time.
        Idle polls do not count. max_session_seconds bounds when new claims start,
        not active work or delivery retries. None disables each optional limit.
        """
        if type(pass_context) is not bool:
            raise ValueError("pass_context must be a boolean")
        if not 0 < poll_seconds <= max_poll_seconds <= 300:
            raise ValueError("Polling intervals must satisfy 0 < initial <= maximum <= 300")
        if max_tasks is not None and (type(max_tasks) is not int or max_tasks < 1):
            raise ValueError("max_tasks must be a positive integer or None")
        if max_session_seconds is not None and (
            type(max_session_seconds) not in (int, float) or not 0 < max_session_seconds <= 86400
        ):
            raise ValueError(
                "max_session_seconds must be a number greater than 0 and at most 86400"
            )
        deadline = (
            time.monotonic() + max_session_seconds if max_session_seconds is not None else None
        )
        completed = 0
        delay = poll_seconds
        while not stop.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                break
            task_id = (
                self.run_once(handler, pass_context=True)
                if pass_context
                else self.run_once(handler)
            )
            if task_id is not None:
                completed += 1
                if max_tasks is not None and completed >= max_tasks:
                    break
                delay = poll_seconds
                continue
            wait_seconds = self._jitter(delay)
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                wait_seconds = min(wait_seconds, remaining)
            if stop.wait(wait_seconds):
                break
            delay = min(delay * 2, max_poll_seconds)

    def close(self):
        self.client.close()

    def _jitter(self, delay):
        return random.uniform(delay / 2, delay) if self.backoff_jitter else delay

    def _retry_delay(self, response, attempt):
        delay = self._jitter(min(self.retry_base_seconds * (2**attempt), self.max_retry_seconds))
        retry_after = response.headers.get("Retry-After") if response is not None else None
        if retry_after:
            try:
                requested = float(retry_after)
            except ValueError:
                try:
                    date = parsedate_to_datetime(retry_after)
                    if date.tzinfo is None:
                        date = date.replace(tzinfo=UTC)
                    requested = (date - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    return delay
            if math.isfinite(requested):
                if requested > self.max_retry_seconds:
                    return None  # Do not retry earlier than the server requested.
                delay = max(delay, requested, 0)
        return delay

    def _request(self, method: str, path: str, **kwargs):
        # Serialize once so a retry sends the exact same token and JSON bytes.
        request = self.client.build_request(method, path, **kwargs)
        if len(request.content) > MAX_REQUEST_BYTES:
            raise ValueError(SIZE_ERROR)
        safe = method.upper() == "GET" or (
            method.upper() == "POST"
            and request.headers.get("X-Execution-Token")
            and (
                path == "/v1/tasks/claim"
                or re.fullmatch(r"/v1/tasks/[^/]+/(heartbeat|submit)", path)
            )
        )
        retries = self.max_retries if safe else 0
        for attempt in range(retries + 1):
            try:
                response = self.client.send(request)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
                if attempt == retries:
                    raise
                time.sleep(self._retry_delay(None, attempt))
                continue
            if response.status_code in {429, 502, 503, 504} and attempt < retries:
                delay = self._retry_delay(response, attempt)
                if delay is not None:
                    response.close()
                    time.sleep(delay)
                    continue
            response.raise_for_status()
            if response.status_code == 204:
                return None
            return response.json()
        raise AssertionError("Retry loop must return or raise")

    def run_once(self, handler: Callable[..., dict], *, pass_context: bool = False) -> str | None:
        """Process one task; pass_context opts into handler(task, LeaseContext).

        Handlers must make external side effects idempotent and implement their own
        cancellation. Renewal failure always withholds results before delivery.
        """
        if type(pass_context) is not bool:
            raise ValueError("pass_context must be a boolean")
        token = secrets.token_urlsafe(32)
        headers = {"X-Execution-Token": token}
        lease = {"lease_seconds": self.lease_seconds}
        task = self._request("POST", "/v1/tasks/claim", headers=headers, json=lease)
        if task is None:
            return None
        stopped = Event()
        context = LeaseContext() if pass_context else None
        failures = []

        def renew():
            while not stopped.wait(self.lease_seconds / 3):
                try:
                    self._request(
                        "POST", f"/v1/tasks/{task['id']}/heartbeat", headers=headers, json=lease
                    )
                except Exception as exc:
                    failures.append(exc)
                    if context is not None:
                        context._lost.set()
                    return

        worker = Thread(target=renew, daemon=True)
        worker.start()
        try:
            artifact = handler(task, context) if pass_context else handler(task)
            if failures:
                raise LeaseLostError(
                    "Lease renewal failed; result was not submitted"
                ) from failures[0]
            if not isinstance(artifact, dict) or not artifact:
                raise ValueError("Agent must return a nonempty artifact object")
            # Keep renewal alive through transport retries. Once delivery starts, the
            # submit endpoint is authoritative: a heartbeat may race a committed
            # submission and fail while its same-token replay still succeeds.
            self._request(
                "POST",
                f"/v1/tasks/{task['id']}/submit",
                headers=headers,
                json={"artifact": artifact},
            )
            return task["id"]
        finally:
            stopped.set()
            worker.join()
