#!/usr/bin/env python3
"""Follow-up: complete the bug proofs with valid full payloads."""
import time
import sqlite3
import httpx
from jose import jwt

BASE = "http://localhost:8000"
TENANT = "1006adca-7f39-4f93-8d1c-49e72fb3c113"
c = httpx.Client(base_url=BASE, timeout=60.0)

r = c.post("/api/auth/login", json={"email": "owner@cairo-sneakers.com", "password": "OwnerPass123"})
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}

# ---- 1. AI chat WITH auth (LLM key empty → how does it fail? how slow?) ----
t0 = time.perf_counter()
r = c.post("/api/test/chat", headers=H, json={"tenant_id": TENANT, "message": "hi, what shoes do you have?"})
dt = (time.perf_counter() - t0) * 1000
print(f"[1] AI CHAT: {r.status_code} in {dt:.0f}ms :: {r.text[:300]}")

# ---- 2. Orders with FULL valid payload → MissingGreenlet proof ----
r = c.post(f"/api/tenants/{TENANT}/orders", headers=H, json={
    "customer_name": "Ahmed Test", "customer_phone": "01000000001",
    "governorate": "cairo", "city": "Nasr City", "address_detail": "12 Abbas El Akkad St",
    "items": [{"product_name": "Air Max 90 White", "quantity": 1, "unit_price": 1850}],
})
print(f"[2] ORDER CREATE (MissingGreenlet): {r.status_code} :: {r.text[:300]}")

# ---- 3. Stored XSS with full payload ----
r = c.post(f"/api/tenants/{TENANT}/orders", headers=H, json={
    "customer_name": "<img src=x onerror=alert(1)>", "customer_phone": "01000000002",
    "governorate": "giza", "city": "Giza", "address_detail": "X",
    "items": [{"product_name": "Air Force 1 Black", "quantity": 1, "unit_price": 1650}],
})
print(f"[3] STORED XSS: {r.status_code} :: stored={'<img' in r.text} :: {r.text[:200]}")

# ---- 4. Crawl job status + knowledge base exfil check (direct DB) ----
r = c.get(f"/api/tenants/{TENANT}/crawl/jobs", headers=H)
print(f"[4] CRAWL JOBS: {r.status_code} :: {r.text[:400]}")

con = sqlite3.connect("/home/z/my-project/repos/zemest/zemest_local.db")
cur = con.cursor()
try:
    rows = cur.execute("SELECT url, status, pages_found, products_extracted, error_message FROM crawl_jobs ORDER BY created_at DESC LIMIT 5").fetchall()
    print("[4b] crawl_jobs rows:", rows)
except Exception as e:
    print("[4b] crawl_jobs err:", e)
try:
    kb = cur.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()
    print("[4c] knowledge_bases count:", kb)
except Exception as e:
    print("[4c] KB err:", e)
# check tenants.knowledge_base JSON col
try:
    tn = cur.execute("SELECT substr(knowledge_base,1,300) FROM tenants WHERE page_name='Cairo Sneakers'").fetchone()
    print("[4d] tenant.knowledge_base:", tn)
except Exception as e:
    print("[4d] err:", e)
con.close()

# ---- 5. Speed check: repeat authed reads (user wants FAST) ----
lat = []
for _ in range(5):
    t0 = time.perf_counter()
    c.get(f"/api/tenants/{TENANT}/products", headers=H)
    lat.append((time.perf_counter() - t0) * 1000)
print(f"[5] products x5 latency: {[f'{x:.0f}ms' for x in lat]}")

# ---- 6. chat latency x3 (LLM path speed) ----
lat2 = []
for msg in ["hello", "how much is air max?", "عندك مقاس 42؟"]:
    t0 = time.perf_counter()
    r = c.post("/api/test/chat", headers=H, json={"tenant_id": TENANT, "message": msg})
    lat2.append(((time.perf_counter() - t0) * 1000, r.status_code))
print(f"[6] chat x3 latency/status: {[(f'{a:.0f}ms', b) for a, b in lat2]}")
