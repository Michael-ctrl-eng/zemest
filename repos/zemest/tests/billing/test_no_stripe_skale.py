"""Adversarial regression test: the Stripe and SKALE removal.

The billing refactor removed EVERY trace of Stripe (the old primary
rail) and SKALE (the old crypto sidecar). This test fails the build if
either creeps back into the backend source, the config surface, the
provider registry, the route map, or the docker-compose topology.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# Backend production surface that must stay free of the removed rails.
# tests/ is intentionally NOT scanned: adversarial tests legitimately
# reference the removed rail names when asserting they are rejected.
BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = [
    BACKEND_ROOT / "app",
    BACKEND_ROOT / "alembic",
    BACKEND_ROOT / "docker-compose.yml",
    BACKEND_ROOT / ".env.example",
]
SCAN_GLOBS = ("*.py", "*.yml", "*.yaml", "*.ini", "*.example")

# Whole-word matches only — 'skale' must not match 'scale'.
STRIPE_RE = re.compile(r"\bstripe\b", re.IGNORECASE)
SKALE_RE = re.compile(r"\bskale\b", re.IGNORECASE)

# This very file (and the pytest marker files) legitimately MENTION the
# forbidden words — self-references are exempt.
SELF_PATH = Path(__file__).resolve()


def _source_files():
    for entry in SCAN_DIRS:
        if entry.is_file():
            yield entry
            continue
        for pattern in SCAN_GLOBS:
            for path in entry.rglob(pattern):
                yield path


def _violations() -> list[tuple[str, int, str]]:
    bad = []
    for path in _source_files():
        if path == SELF_PATH or not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if STRIPE_RE.search(line) or SKALE_RE.search(line):
                bad.append((str(path.relative_to(BACKEND_ROOT)), lineno, line.strip()))
    return bad


def test_no_stripe_or_skale_in_backend_source():
    violations = _violations()
    assert not violations, (
        "Stripe/SKALE remnants found (they were removed from the "
        "architecture):\n"
        + "\n".join(f"{f}:{n}: {line}" for f, n, line in violations)
    )


def test_no_stripe_settings_in_config():
    from app.config import Settings

    secret_fields = [
        name for name in Settings.model_fields if name.upper().startswith("STRIPE")
    ]
    assert secret_fields == [], f"STRIPE_* settings must not exist: {secret_fields}"


def test_provider_registry_rejects_stripe_and_skale():
    from app.services.billing.providers import get_provider
    from app.services.billing.providers.base import ProviderConfigError

    for name in ("stripe", "skale"):
        with pytest.raises(ProviderConfigError):
            get_provider(name)


def test_no_stripe_or_skale_routes():
    from app.main import app

    spec = app.openapi()
    for path in spec["paths"]:
        assert "stripe" not in path.lower(), f"stripe route found: {path}"
        assert "skale" not in path.lower(), f"skale route found: {path}"
    # The two (and only two) webhook routes of the post-Stripe stack:
    assert "/api/payments/webhook/payoneer" in spec["paths"]
    assert "/api/payments/webhook/paymob" in spec["paths"]


def test_docker_compose_has_no_stripe_or_skale_services():
    compose = (BACKEND_ROOT / "docker-compose.yml").read_text()
    assert STRIPE_RE.search(compose) is None
    assert SKALE_RE.search(compose) is None
    assert "celery" not in compose, (
        "dead celery services (app.tasks.celery_app no longer exists) must "
        "not come back"
    )


def test_payment_methods_are_exactly_the_post_stripe_rails():
    from app.models.billing import PaymentMethod

    assert set(PaymentMethod.ALL) == {"payoneer", "paymob", "usdc_solana"}
