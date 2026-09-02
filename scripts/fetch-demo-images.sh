#!/bin/bash
# Fetch demo product images for the Zemest Store demo agent (v2 - parse stdout).
set -u
cd /home/z/my-project
mkdir -p /tmp/demo-img

fetch() {
  local name="$1"; local query="$2"
  echo "=== $name ==="
  z-ai image-search -q "$query" --count 2 --gl us --no-rank > "/tmp/demo-img/$name.raw" 2>/dev/null
  python3 - "$name" << 'EOF'
import json, sys, subprocess, re
name = sys.argv[1]
raw = open(f"/tmp/demo-img/{name}.raw").read()
# strip CLI banner lines before JSON
i = raw.find("{")
if i < 0:
    print(f"  FAIL {name}: no JSON in output"); sys.exit(0)
try:
    d = json.loads(raw[i:])
except Exception as e:
    print(f"  FAIL {name}: parse {e}"); sys.exit(0)
if d.get("success") and d.get("results"):
    url = d["results"][0]["original_url"]
    r = subprocess.run(["curl", "-sL", "--max-time", "50", "-o", f"/tmp/demo-img/{name}.img", url])
    import os
    sz = os.path.getsize(f"/tmp/demo-img/{name}.img") if os.path.exists(f"/tmp/demo-img/{name}.img") else 0
    print(f"  {'OK' if sz > 5000 else 'SMALL?'} {name}: {sz//1024}KB from {url[:70]}")
else:
    print(f"  FAIL {name}: {d.get('error')}")
EOF
}

fetch "nike-white" "white Nike Air Max sneakers product photo on clean background"
fetch "nike-black" "black Nike running shoes product photo on clean background"
fetch "sneakers-red" "red Adidas sneakers product photo on clean background"
fetch "tshirt-white" "plain white cotton t-shirt product photo folded"
fetch "hoodie-black" "black hoodie sweatshirt product photo"
fetch "perfume-oud" "luxury oud perfume bottle product photo"
fetch "perfume-floral" "elegant floral perfume bottle product photo"
fetch "shampoo" "argan oil shampoo bottle product photo"
fetch "face-cream" "white face cream jar cosmetic product photo"
fetch "bag-leather" "brown leather handbag product photo"
fetch "watch" "black analog wrist watch product photo"
fetch "earbuds" "wireless earbuds product photo on clean background"
fetch "phone-case" "minimal black phone case product photo"
fetch "sunglasses" "black sunglasses product photo on clean background"
fetch "dress" "summer floral dress product photo"
echo "ALL DONE"
