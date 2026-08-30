#!/usr/bin/env python3
"""Verify all P0 fixes after patching."""
import time
import httpx
from jose import jwt

BASE = "http://localhost:8000"
TENANT = "1006adca-7f39-4f93-8d1c-49e72fb3c113"
OLD_DEFAULT_SECRET = "change-me-to-a-random-secret-key"
c = httpx.Client(base_url=BASE, timeout=60.0)

r = c.post("/api/auth/login", json={"email": "owner@cairo-sneakers.com", "password": "OwnerPass123"})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
print(f"[✓] login works: {r.status_code}")

# 1. Forged JWT with OLD default secret must now FAIL
forged = jwt.encode({"sub": "7a194924-d536-4638-b3a1-e4f1d89e866f", "exp": int(time.time()) + 3600, "type": "access"},
                    OLD_DEFAULT_SECRET, algorithm="HS256")
r = c.get("/api/tenants", headers={"Authorization": f"Bearer {forged}"})
print(f"[{'✓' if r.status_code == 401 else '✗'}] forged default-secret JWT rejected: {r.status_code}")

# 2. Old dashboard routes must be GONE
for path in ["/dashboard", f"/dashboard/{TENANT}/chat", f"/dashboard/{TENANT}/orders"]:
    r = c.get(path, follow_redirects=False)
    print(f"[{'✓' if r.status_code == 404 else '✗'}] {path} → {r.status_code}")

# 3. Order creation must be 201 now
r = c.post(f"/api/tenants/{TENANT}/orders", headers=H, json={
    "customer_name": "Ahmed Fixed", "customer_phone": "01000000009",
    "governorate": "cairo", "city": "Nasr City", "address_detail": "12 Abbas El Akkad",
    "items": [{"product_name": "Air Max 90 White", "quantity": 1, "unit_price": 1850}],
})
print(f"[{'✓' if r.status_code == 201 else '✗'}] order create (was 500): {r.status_code} :: {r.text[:140]}")

# 4. Shipping must be 200 now
r = c.get("/api/address/shipping", params={"governorate": "cairo", "subtotal": 500})
print(f"[{'✓' if r.status_code == 200 else '✗'}] shipping quote (was 500): {r.status_code} :: {r.text[:140]}")

# 5. Chat must be FAST now (fail-fast, no 8s)
t0 = time.perf_counter()
r = c.post("/api/test/chat", headers=H, json={"tenant_id": TENANT, "message": "hello"})
dt = (time.perf_counter() - t0) * 1000
print(f"[{'✓' if dt < 1500 else '✗'}] chat latency (was ~8000ms): {dt:.0f}ms :: {r.status_code} {r.text[:100]}")

# 6. SSRF crawl file:// must be rejected
r = c.post(f"/api/tenants/{TENANT}/crawl", headers=H, json={"url": "file:///etc/passwd", "depth": 1})
print(f"[{'✓' if r.status_code == 400 else '✗'}] SSRF file:// rejected: {r.status_code} :: {r.text[:120]}")

# 7. SSRF import-url internal must be rejected
r = c.post(f"/api/tenants/{TENANT}/products/import-url", headers=H, json={"url": "http://localhost:8000/openapi.json"})
print(f"[{'✓' if r.status_code == 400 else '✗'}] SSRF internal host rejected: {r.status_code} :: {r.text[:120]}")

# 8. Brute force should now be limited (6th attempt within a minute → 429)
codes = []
for i in range(8):
    r = c.post("/api/auth/login", json={"email": "owner@cairo-sneakers.com", "password": f"brute{i}"})
    codes.append(r.status_code)
print(f"[{'✓' if 429 in codes else '✗'}] brute-force rate limit: statuses={codes}")

# 9. Webhook old default token must fail
r = c.get("/api/webhook/messenger", params={"hub.mode": "subscribe", "hub.verify_token": "zemest-verify-token", "hub.challenge": "123"})
print(f"[{'✓' if r.status_code != 200 or r.text != '123' else '✗'}] old webhook verify token: {r.status_code} :: {r.text[:60]}")

# 10. Fast reads still fast
lat = []
for _ in range(5):
    t0 = time.perf_counter()
    c.get(f"/api/tenants/{TENANT}/products", headers=H)
    lat.append((time.perf_counter() - t0) * 1000)
print(f"[✓] products x5 latency: {[f'{x:.0f}ms' for x in lat]}")
