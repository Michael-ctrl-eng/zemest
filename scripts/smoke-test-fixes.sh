#!/bin/bash
# Zemest full smoke test — verifies the Task-19 fix batch end to end.
set -u
BASE="http://localhost:8000"
PASS=0; FAIL=0
t() { curl -s -o /dev/null -w "%{http_code}|%{time_total}" -m 60 "$@"; }

echo "=== 1. LOGIN (bcrypt off-loop + new JWT secret) ==="
LOGIN=$(curl -s -m 30 -X POST "$BASE/api/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"owner@cairo-sneakers.com","password":"OwnerPass123"}')
TOKEN=$(echo "$LOGIN" | python3 -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
if [ -n "$TOKEN" ] && [ "$TOKEN" != "None" ]; then echo "PASS: login → token"; PASS=$((PASS+1)); else echo "FAIL: login ($LOGIN)"; FAIL=$((FAIL+1)); fi
AUTH="Authorization: Bearer $TOKEN"

TENANT=$(curl -s -m 15 "$BASE/api/tenants" -H "$AUTH" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
echo "tenant: $TENANT"

echo ""
echo "=== 2. STATS (collapsed queries + 20s TTL cache) ==="
S1=$(t "$BASE/api/tenants/$TENANT/stats" -H "$AUTH")
S2=$(t "$BASE/api/tenants/$TENANT/stats" -H "$AUTH")
S3=$(t "$BASE/api/tenants/$TENANT/stats" -H "$AUTH")
echo "runs: $S1 / $S2 / $S3 (1st=cold, then warm cache — 2nd/3rd should be ~0.0x s)"

echo ""
echo "=== 3. CUSTOMERS (N+1 killed → 3 batched aggregates) ==="
C1=$(t "$BASE/api/tenants/$TENANT/customers?page_size=50" -H "$AUTH")
echo "customers(page_size=50): $C1"

echo ""
echo "=== 4. REAL LLM CHAT (zai provider — was canned apology before) ==="
CHAT_START=$(date +%s.%N)
CHAT=$(curl -s -m 90 -X POST "$BASE/api/test/chat" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT\",\"message\":\" عندكم نايك اير ماكس بمقاس 42 ؟ وده سعره كام\",\"sender_psid\":\"smoke-test-user\",\"channel\":\"messenger\"}")
CHAT_END=$(date +%s.%N)
echo "$CHAT" | python3 -c "
import json,sys
d=json.load(sys.stdin)
r=d.get('reply') or d.get('response') or d.get('content') or ''
tokens=d.get('tokens_used') or 0
print(f'reply: {r[:200]}')
print(f'tokens_used: {tokens}')
print('VERDICT:', 'REAL LLM' if tokens and tokens>0 and len(r)>30 and 'unable' not in r.lower() and 'msh a2dar' not in r else 'SUSPECT/FALLBACK')
" 2>&1
echo "elapsed: $(echo "$CHAT_END - $CHAT_START" | bc)s"

echo ""
echo "=== 5. IMPORT CHAT HISTORY (was 500 FK bug) ==="
ZIPB=/tmp/zemest-smoke-import.zip
python3 - << 'PYEOF'
import zipfile, json, io
# WhatsApp-style export JSON with 2 threads (one commerce, one friend-chatter)
data = json.dumps([
  {"thread_title":"Buyer Ahmed","role":"customer","content":"السلام عليكم، النايك بسعر كام؟","timestamp":"2026-08-20T10:00:00"},
  {"thread_title":"Buyer Ahmed","role":"merchant","content":"أهلاً بيك، النايك بـ 1500 جنيه والتوصيل مجاني فوق 300","timestamp":"2026-08-20T10:01:00"},
  {"thread_title":"Buyer Ahmed","role":"customer","content":"تمام، اطلبلي مقاس 42","timestamp":"2026-08-20T10:02:00"},
  {"thread_title":"Friend Mona","role":"customer","content":"تعال نلعب بولينج الجمعة؟ 😂","timestamp":"2026-08-21T18:00:00"},
  {"thread_title":"Friend Mona","role":"merchant","content":"اه يا صاحبي إن شاء الله أشوفك","timestamp":"2026-08-21T18:05:00"},
])
with zipfile.ZipFile("/tmp/zemest-smoke-import.zip","w") as z:
    z.writestr("chat_history.json", data)
print("import zip ready")
PYEOF
IMP=$(curl -s -m 60 -o /tmp/import-result.json -w "%{http_code}" -X POST "$BASE/api/tenants/$TENANT/import/chat-history" -H "$AUTH" -F "file=@$ZIPB")
echo "import status: $IMP"
head -c 300 /tmp/import-result.json; echo ""

echo ""
echo "=== 6. is_superadmin in /auth/me ==="
curl -s -m 15 "$BASE/api/auth/me" -H "$AUTH" | python3 -m json.tool 2>/dev/null | head -8

echo ""
echo "=== 7. READ ENDPOINTS SWEEP ==="
for EP in conversations products orders schedule/posts style-profile insights/overview; do
  R=$(t "$BASE/api/tenants/$TENANT/$EP" -H "$AUTH")
  echo "$EP: $R"
done

echo ""
echo "=== 8. WAL + is_fallback column ==="
cd /home/z/my-project/repos/zemest && .venv/bin/python -c "
import sqlite3
c = sqlite3.connect('zemest_local.db')
print('journal_mode:', c.execute('PRAGMA journal_mode').fetchone()[0])
cols = [r[1] for r in c.execute('PRAGMA table_info(messages)').fetchall()]
print('messages.is_fallback present:', 'is_fallback' in cols)
idx = [r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='messages'\").fetchall()]
print('fb_message_id unique idx:', any('fb_message_id_unique' in i for i in idx))
"

echo ""
echo "SUMMARY: PASS=$PASS FAIL=$FAIL"
