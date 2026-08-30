#!/usr/bin/env python3
"""
Zemest word-swap — executed in the terminal.

Replaces every clone-leftover word in user-visible copy so the whole
platform reads as ZEMEST (our commerce-moderation platform), not the
reference site we cloned from:

  1. "Tavus"                      -> "Zemest"   (visible text only — CSS
     tokens like --tavus-*, asset paths like /tavus-hero.avif, and code
     identifiers like TavusButton are all lowercase/compound and are
     deliberately NOT touched by the case-sensitive \bTavus\b match)
  2. "Human Computing"            -> "Conversational Commerce" (positioning)
  3. "HubSpot, Braze, Salesforce" -> "WhatsApp, Messenger, Instagram"
     (integration stack that actually fits our platform)

Prints a full report of every file + line changed.
"""
import re
import sys
from pathlib import Path

ROOT = Path("/home/z/my-project/src")
SWAPS = [
    (re.compile(r"\bTavus\b"), "Zemest"),
    (re.compile(r"\bHuman Computing\b"), "Conversational Commerce"),
    (re.compile(r"\bhuman computing\b"), "conversational commerce"),
    (re.compile(r"HubSpot, Braze, Salesforce, or your own app"), "WhatsApp, Messenger, Instagram, or your own app"),
]

total_files = 0
total_lines = 0

print("=" * 72)
print("ZEMEST WORD SWAP — making every word fit our platform")
print("=" * 72)

for path in sorted(ROOT.rglob("*")):
    if path.suffix not in {".tsx", ".ts", ".jsx", ".js"}:
        continue
    if "node_modules" in path.parts:
        continue
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = 0
    out = []
    for i, line in enumerate(lines, 1):
        new = line
        for pattern, repl in SWAPS:
            new = pattern.sub(repl, new)
        if new != line:
            changed += 1
            rel = path.relative_to(ROOT.parent)
            print(f"[{rel}:{i}]")
            print(f"   - {line.strip()[:110]}")
            print(f"   + {new.strip()[:110]}")
        out.append(new)
    if changed:
        path.write_text("".join(out), encoding="utf-8")
        total_files += 1
        total_lines += changed

print("=" * 72)
print(f"DONE: {total_lines} lines updated across {total_files} files")

# --- verification scan: no visible 'Tavus' should remain in string literals ---
leftovers = []
for path in sorted(ROOT.rglob("*.tsx")):
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"\bTavus\b", line):
            leftovers.append(f"{path.relative_to(ROOT.parent)}:{i}")
if leftovers:
    print(f"\nWARNING: {len(leftovers)} capitalized 'Tavus' mentions remain:")
    for l in leftovers[:20]:
        print(f"  {l}")
    sys.exit(1)
print("VERIFIED: zero visible 'Tavus' words remain in src/")
