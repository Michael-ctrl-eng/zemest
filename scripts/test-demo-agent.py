"""Offline test of the demo agent brain — run inside the zemest venv."""
import sys
sys.path.insert(0, "/home/z/my-project/repos/zemest")

from app.services import demo_agent as A

sid = "test-session-123"

def say(msg):
    r = A.build_reply(msg, sid)
    img = " [IMG]" if r.get("image") else ""
    print(f"USER: {msg}")
    print(f"AGENT:{img} {r['reply']}")
    print(f"      quick: {r.get('quick_replies', [])}")
    print()

# Full order flow
say("hey")
say("is there a white nike shoes size 42?")
say("yes, order it")
say("12 Tahrir St, Dokki, Giza")
say("thank you!")

print("=" * 60)
# Shampoo flow (different category + new session)
sid = "test-session-456"
say("do you have shampoo?")
say("how much is it?")
say("order it please")
say("7 Gamal Abdel Nasser St, Alexandria")

print("=" * 60)
# Shipping question
sid = "test-session-789"
say("how much is shipping to Alexandria?")
say("what about cairo")

print("=" * 60)
# Arabic understanding
sid = "test-session-ar"
say("عندكم حذاء نايك أبيض مقاس ٤٢؟")
say("شامبو بكام؟")

print("=" * 60)
# Fallback
sid = "test-session-x"
say("what is the meaning of life?")
say("100kdkdkd nonsense")

print("=" * 60)
# Timing: 1000 messages
import time
sid = "bench"
t0 = time.perf_counter()
for i in range(1000):
    A.build_reply("do you have white nike shoes size 42 please", sid)
dt = (time.perf_counter() - t0) / 1000 * 1000
print(f"AVG LATENCY: {dt:.3f} ms/message")
