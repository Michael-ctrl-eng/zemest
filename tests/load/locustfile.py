"""Locust load test — simulates merchant traffic.

Run with:

    locust -f tests/load/locustfile.py --host=http://localhost:8000

Then open http://localhost:8089 to configure number of users and spawn rate.

For headless runs (e.g., CI):

    locust -f tests/load/locustfile.py \\
        --host=http://localhost:8000 \\
        --headless -u 1000 -r 50 --run-time 5m

Scenarios covered:
- Merchant logs in (once per user, on_start)
- Views product list (3x weight — most common action)
- Views order list (1x weight)
- Sends a test chat message (1x weight — most expensive, hits LLM)
- Views tenant stats (1x weight)
"""
from __future__ import annotations

import json
import os
import random

# Locust is optional — only imported when actually running load tests.
try:
    from locust import HttpUser, between, task, events
except ImportError:
    # Allow `import locustfile` from tests/load/test_locust_smoke.py
    HttpUser = object  # type: ignore[misc, assignment]
    def task(*args, **kwargs):  # type: ignore[no-redef]
        if args and callable(args[0]):
            return args[0]
        def deco(fn):
            return fn
        return deco
    def between(*args, **kwargs):  # type: ignore[no-redef]
        return 1.0
    events = None  # type: ignore[assignment]


# Test messages in Egyptian Arabic — what real customers send.
CHAT_MESSAGES = [
    "السلام عليكم، إيه المنتجات عندك؟",
    "كم سعر الجلابية؟",
    "عايز أطلب 2 قطعة",
    "عندي استفسار عن الشحن للإسكندرية",
    "إيه طرق الدفع المتاحة؟",
    "hi, what products do you have?",
    "عندي مشكلة في الطلب الأخير",
    "هل في خصم على الكمية؟",
    "what's the shipping cost to Cairo?",
    "عايز أعرف آخر العروض",
]


class MerchantUser(HttpUser):
    """Simulates a logged-in merchant interacting with the dashboard API.

    Weight distribution (via @task decorators):
        - view_products:    3 (most common — refresh product list)
        - view_orders:      1
        - view_stats:       1
        - test_chat:        1 (most expensive — hits LLM)
        - view_conversations: 1
        - list_tenants:     1
    """

    # Wait 1-5 seconds between requests (realistic think time).
    wait_time = between(1, 5)

    # Default weight — can be overridden via --tags when running multiple User classes.
    weight = 1

    def on_start(self):
        """Called once per user when they start.

        Logs in and caches the JWT + tenant_id for subsequent requests.
        """
        self.token: str | None = None
        self.tenant_id: str | None = os.getenv("LOAD_TEST_TENANT_ID", "")
        self.headers: dict = {"Content-Type": "application/json"}

        email = os.getenv("LOAD_TEST_EMAIL", "loadtest@zemest.test")
        password = os.getenv("LOAD_TEST_PASSWORD", "LoadTest123!")

        with self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            name="POST /api/auth/login",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"Login failed: {resp.status_code} {resp.text}")
                return
            try:
                self.token = resp.json()["access_token"]
            except (KeyError, json.JSONDecodeError):
                resp.failure("Login response missing access_token")
                return
            resp.success()

        self.headers["Authorization"] = f"Bearer {self.token}"

        # If tenant_id not pre-configured, fetch the user's tenants and pick one.
        if not self.tenant_id:
            with self.client.get(
                "/api/tenants",
                headers=self.headers,
                name="GET /api/tenants (auto-discover)",
                catch_response=True,
            ) as resp:
                if resp.status_code == 200:
                    try:
                        tenants = resp.json()
                        if tenants:
                            self.tenant_id = tenants[0]["id"]
                    except (KeyError, json.JSONDecodeError, IndexError):
                        pass

    def on_stop(self):
        """Called when user is stopped — nothing to clean up."""

    @task(3)
    def view_products(self):
        """List products — most common action."""
        if not self._ready():
            return
        page = random.randint(1, 3)
        with self.client.get(
            f"/api/tenants/{self.tenant_id}/products?page={page}&page_size=50",
            headers=self.headers,
            name="GET /api/tenants/{id}/products",
            catch_response=True,
        ) as resp:
            self._check(resp, expected=(200,))

    @task(1)
    def view_orders(self):
        """List orders."""
        if not self._ready():
            return
        with self.client.get(
            f"/api/tenants/{self.tenant_id}/orders?page=1&page_size=20",
            headers=self.headers,
            name="GET /api/tenants/{id}/orders",
            catch_response=True,
        ) as resp:
            self._check(resp, expected=(200,))

    @task(1)
    def view_conversations(self):
        """List conversations."""
        if not self._ready():
            return
        with self.client.get(
            f"/api/tenants/{self.tenant_id}/conversations?page=1&page_size=20",
            headers=self.headers,
            name="GET /api/tenants/{id}/conversations",
            catch_response=True,
        ) as resp:
            self._check(resp, expected=(200,))

    @task(1)
    def view_stats(self):
        """View tenant stats dashboard."""
        if not self._ready():
            return
        with self.client.get(
            f"/api/tenants/{self.tenant_id}/stats",
            headers=self.headers,
            name="GET /api/tenants/{id}/stats",
            catch_response=True,
        ) as resp:
            self._check(resp, expected=(200,))

    @task(1)
    def test_chat(self):
        """Send a test chat message — heaviest endpoint (LLM call)."""
        if not self._ready():
            return
        message = random.choice(CHAT_MESSAGES)
        with self.client.post(
            "/api/test/chat",
            json={
                "tenant_id": self.tenant_id,
                "message": message,
            },
            headers=self.headers,
            name="POST /api/test/chat",
            catch_response=True,
        ) as resp:
            # 200 = success, 500 = LLM not configured, 429 = rate-limited
            self._check(resp, expected=(200, 500, 429))
            if resp.status_code == 500:
                resp.failure(f"LLM error: {resp.text[:200]}")

    @task(1)
    def list_tenants(self):
        """List the user's tenants (lightweight)."""
        if not self.token:
            return
        with self.client.get(
            "/api/tenants",
            headers=self.headers,
            name="GET /api/tenants",
            catch_response=True,
        ) as resp:
            self._check(resp, expected=(200,))

    @task(1)
    def view_me(self):
        """GET /api/auth/me — token validation."""
        if not self.token:
            return
        with self.client.get(
            "/api/auth/me",
            headers=self.headers,
            name="GET /api/auth/me",
            catch_response=True,
        ) as resp:
            self._check(resp, expected=(200,))

    # ---------- helpers ----------

    def _ready(self) -> bool:
        """Return True if this user has a valid token + tenant_id."""
        return bool(self.token and self.tenant_id)

    def _check(self, resp, expected: tuple[int, ...]) -> None:
        """Mark response as success/failure based on expected status codes."""
        if resp.status_code in expected:
            resp.success()
        else:
            resp.failure(
                f"Unexpected status {resp.status_code}: {resp.text[:200]}"
            )


class AnonymousUser(HttpUser):
    """Simulates unauthenticated traffic hitting public endpoints.

    Used to verify rate-limiting & abuse handling on public surfaces
    (login page, docs, webhook verification).
    """

    wait_time = between(0.5, 2)
    weight = 1  # lower weight than authenticated users

    @task(2)
    def view_login_page(self):
        with self.client.get(
            "/dashboard/login",
            name="GET /dashboard/login (anon)",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Login page returned {resp.status_code}")

    @task(1)
    def view_docs(self):
        with self.client.get(
            "/docs",
            name="GET /docs (anon)",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Docs returned {resp.status_code}")

    @task(1)
    def view_openapi(self):
        with self.client.get(
            "/openapi.json",
            name="GET /openapi.json (anon)",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"OpenAPI returned {resp.status_code}")

    @task(1)
    def failed_login_attempt(self):
        """Simulate brute-force attempts (should be rate-limited)."""
        with self.client.post(
            "/api/auth/login",
            json={"email": "nonexistent@test.com", "password": "wrong"},
            name="POST /api/auth/login (failed)",
            catch_response=True,
        ) as resp:
            # 401 = expected, 429 = rate-limited (good!), 500 = bad
            if resp.status_code in (401, 429):
                resp.success()
            else:
                resp.failure(f"Failed login returned {resp.status_code}")


# Optional: emit a summary event when the load test ends.
if events is not None and hasattr(events, "quitting"):
    @events.quitting.add_listener
    def _quitting(environment, **kwargs):
        """Fail the load test if too many requests errored."""
        if environment.stats.total.fail_ratio > 0.1:
            print(f"\n[WARN] {environment.stats.total.fail_ratio:.0%} failure ratio — above 10% threshold")
            environment.process_exit_code = 1
        else:
            print(f"\n[OK] {environment.stats.total.fail_ratio:.0%} failure ratio")
