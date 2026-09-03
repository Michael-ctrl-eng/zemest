"""No-secrets-in-the-client regression gate.

Product requirement: "no APIs in the client side or in developer tools in
any browser, like the network setting … not be hackable."

The architecture already guarantees this:
- every AI provider call (OpenRouter / Gemini / Z.ai / Groq) happens in the
  FastAPI backend; keys live in server env only;
- the browser talks SAME-ORIGIN to the Next.js BFF (/api/zemest/*), which
  swaps the httpOnly cookie for a Bearer header server-side;
- no NEXT_PUBLIC_* variable may ever carry a secret.

This test scans the frontend source for key-shaped strings and forbidden
browser-side provider calls so a future commit cannot silently regress it.
Skipped when the frontend tree isn't present (backend-only checkouts).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FRONTEND_SRC = Path(__file__).resolve().parents[4] / "src"

pytestmark = pytest.mark.skipif(
    not (FRONTEND_SRC / "app" / "layout.tsx").exists(),
    reason="frontend src/ tree not present in this checkout",
)

# Key-shaped patterns: provider prefixes, PEM blocks, generic assignments.
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),                    # OpenAI-style
    re.compile(r"sk-or-v1-[A-Za-z0-9]{16,}"),              # OpenRouter
    re.compile(r"gsk_[A-Za-z0-9]{16,}"),                   # Groq
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),                # Google/Gemini
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),           # Slack
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),                   # GitHub PAT
    re.compile(r"gh_[A-Za-z0-9]{30,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"eyJhbGciOi[A-Za-z0-9_-]{20,}\."),          # raw JWT literals
]

# Variables whose NAME marks them as secrets; NEXT_PUBLIC_ variants are
# shipped to the browser, so any of these must fail loudly.
FORBIDDEN_NEXT_PUBLIC = re.compile(
    r"NEXT_PUBLIC_[A-Z0-9_]*(KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)[A-Z0-9_]*"
)

# Browser code must not call AI/social provider APIs directly — everything
# goes through our own /api/* BFF routes.
DIRECT_PROVIDER_CALL = re.compile(
    r"""fetch\s*\(\s*["'](https?://[^"']*)["']""",
)

ALLOWED_EXTERNAL_HOSTS = {
    "www.facebook.com",  # OAuth dialog (redirect target, no keys)
    "calendar.google.com",  # public calendar render link
    "gc.zgo.at",  # optional GoatCounter script (no PII, no keys)
    "www.w3.org",
}

TS_GLOBS = ("**/*.ts", "**/*.tsx")


def _iter_source():
    for path in sorted(FRONTEND_SRC.rglob("*.ts")) + sorted(FRONTEND_SRC.rglob("*.tsx")):
        yield path


class TestNoClientSideSecrets:
    def test_no_key_shaped_strings_in_frontend(self):
        offenders = []
        for path in _iter_source():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_PATTERNS:
                m = pattern.search(text)
                if m:
                    offenders.append(f"{path.relative_to(FRONTEND_SRC)}: {m.group(0)[:24]}…")
        assert not offenders, f"key-shaped strings in client code: {offenders}"

    def test_no_next_public_secret_variables(self):
        offenders = []
        for path in _iter_source():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for m in FORBIDDEN_NEXT_PUBLIC.finditer(text):
                offenders.append(f"{path.relative_to(FRONTEND_SRC)}: {m.group(0)}")
        assert not offenders, (
            "NEXT_PUBLIC_* vars are embedded in the browser bundle — "
            f"never allowed for secrets: {offenders}"
        )

    def test_browser_fetch_targets_own_api_or_whitelist(self):
        """Every literal fetch() URL must be same-origin (/api/…) or an
        allowed public redirect host — never a provider endpoint."""
        offenders = []
        for path in _iter_source():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for m in DIRECT_PROVIDER_CALL.finditer(text):
                url = m.group(1)
                if url.startswith("/"):
                    continue
                host = url.split("//", 1)[-1].split("/", 1)[0].lower()
                if host not in ALLOWED_EXTERNAL_HOSTS:
                    offenders.append(f"{path.relative_to(FRONTEND_SRC)}: {url}")
        assert not offenders, (
            "browser code calls an external API directly — route it through "
            f"the backend BFF instead: {offenders}"
        )

    def test_no_zai_sdk_client_usage(self):
        """The z-ai-web-dev-sdk (client-side AI SDK) was removed from deps;
        importing it anywhere would reintroduce a key-exposure surface."""
        offenders = []
        for path in _iter_source():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "z-ai-web-dev-sdk" in text:
                offenders.append(str(path.relative_to(FRONTEND_SRC)))
        assert not offenders, f"z-ai-web-dev-sdk must not be used client-side: {offenders}"
