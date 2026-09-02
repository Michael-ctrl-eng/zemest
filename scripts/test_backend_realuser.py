#!/usr/bin/env python3
"""Real-user API test against the live zemest backend on :8000.
Covers: auth, tenants, products, chat, orders, shipping, analytics, crawl.
Measures response times — user cares about SPEED.
"""
import json
import time
import uuid
import httpx

BASE = "http://localhost:8000"
client = httpx.Client(base_url=BASE, timeout=30.0)
results = []


def call(name, method, path, *, token=None, expect=None, **kwargs):
    t0 = time.perf_counter()
    try:
        headers = kwargs.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        r = client.request(method, path, headers=headers, **kwargs)
        dt = (time.perf_counter() - t0) * 1000
        status_ok = (expect is None and r.status_code < 500) or (expect and r.status_code == expect)
        body_preview = r.text[:220].replace("\n", " ")
        results.append((name, r.status_code, dt, status_ok, body_preview))
        return r
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        results.append((name, "EXC", dt, False, str(e)[:220]))
        return None


print("=" * 100)
print("REAL-USER API TEST — zemest backend @ localhost:8000")
print("=" * 100)

# 1. Health / docs
call("GET /docs (OpenAPI UI)", "GET", "/docs")
call("GET /openapi.json", "GET", "/openapi.json")
call("GET / (root redirect)", "GET", "/")

# 2. Auth — real user journey: register a NEW user
email = f"test-{uuid.uuid4().hex[:8]}@shop.com"
r = call("POST /api/auth/register", "POST", "/api/auth/register",
         json={"email": email, "password": "TestPass123", "name": "Test Shop Owner"}, expect=200)
# fallback: maybe fields differ
if r is None or r.status_code >= 400:
    r = call("POST /api/auth/register (alt)", "POST", "/api/auth/register",
             json={"email": email, "password": "TestPass123", "full_name": "Test Shop Owner"})

# 3. Login with the BOOTSTRAP owner (known creds)
r = call("POST /api/auth/login", "POST", "/api/auth/login",
         json={"email": "owner@cairo-sneakers.com", "password": "OwnerPass123"}, expect=200)
token = None
if r is not None and r.status_code == 200:
    try:
        token = r.json().get("access_token")
    except Exception:
        pass
if not token:
    # try form login
    r = call("POST /api/auth/login (form)", "POST", "/api/auth/login",
             data={"username": "owner@cairo-sneakers.com", "password": "OwnerPass123"})
    if r is not None and r.status_code == 200:
        token = r.json().get("access_token")

if not token:
    print("!! LOGIN FAILED — stopping authed tests")
else:
    # 4. Me / profile
    call("GET /api/auth/me", "GET", "/api/auth/me", token=token)

    # 5. Tenants
    r = call("GET /api/tenants", "GET", "/api/tenants", token=token)
    tenant_id = None
    if r is not None and r.status_code == 200:
        try:
            data = r.json()
            if isinstance(data, list) and data:
                tenant_id = data[0].get("id")
            elif isinstance(data, dict):
                items = data.get("items") or data.get("tenants") or []
                if items:
                    tenant_id = items[0].get("id")
        except Exception:
            pass
    print(f"   tenant_id = {tenant_id}")

    if tenant_id:
        # 6. Products
        call("GET /api/tenants/{id}/products", "GET", f"/api/tenants/{tenant_id}/products", token=token)
        call("POST /api/tenants/{id}/products (create)", "POST", f"/api/tenants/{tenant_id}/products",
             token=token, json={"name": "Test Item Alpha", "price": 99.5, "stock": 3})

        # 7. Chat (the flagship AI feature — expect LLM failure w/o key)
        call("POST /api/test/chat (AI reply)", "POST", f"/api/tenants/{tenant_id}/test/chat",
             token=token, json={"message": "hi, what shoes do you have?"})

        # 8. Orders — the KNOWN MissingGreenlet 500 bug
        call("POST /api/tenants/{id}/orders (KNOWN BUG)", "POST", f"/api/tenants/{tenant_id}/orders",
             token=token, json={"customer_psid": "test_psid_1", "items": [{"product_name": "Air Max 90 White", "quantity": 1}]})
        call("GET /api/tenants/{id}/orders", "GET", f"/api/tenants/{tenant_id}/orders", token=token)

        # 9. Analytics / insights
        call("GET /api/tenants/{id}/analytics", "GET", f"/api/tenants/{tenant_id}/analytics", token=token)
        call("GET /api/tenants/{id}/insights/overview", "GET", f"/api/tenants/{tenant_id}/insights/overview", token=token)

        # 10. Knowledge base
        call("GET /api/tenants/{id}/knowledge", "GET", f"/api/tenants/{tenant_id}/knowledge", token=token)

# 11. Address / shipping — the KNOWN float(dict) 500 bug
call("GET /api/address/shipping (KNOWN BUG)", "GET", "/api/address/shipping")
call("GET /api/address/governorates", "GET", "/api/address/governorates")

# 12. Unauthenticated access to protected route (should 401/403)
call("GET /api/tenants (NO AUTH)", "GET", "/api/tenants")

print()
print("=" * 100)
print(f"{'TEST':<48} {'STATUS':<8} {'MS':>8}  {'OK?':<5} BODY")
print("=" * 100)
for name, status, dt, ok, body in results:
    print(f"{name:<48} {str(status):<8} {dt:>7.0f}  {'✓' if ok else '✗ FAIL':<5} {body[:110]}")
fails = sum(1 for x in results if not x[3])
print(f"\nTOTAL: {len(results)} calls | {fails} failures/errors | avg latency {sum(x[2] for x in results)/len(results):.0f}ms")
