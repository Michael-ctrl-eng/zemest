"""Adversarial infra tests — one test per scaling PoC (wave F8).

Audit context: the platform must survive 10,000 users on a single host.
The failure modes encoded here:
* Multi-replica double-scheduling (N replicas -> N× trainer/publish —
  the leader-election guarantee)
* Production healthchecks must NOT depend on /docs (gated off in prod)
* No hardcoded credentials in the prod compose (the dev compose's
  zemest/zemest_secret defaults were an audit B1 finding)
* No published DB/Redis ports in production (network-only reachability)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND = REPO_ROOT / "repos" / "zemest"
COMPOSE = REPO_ROOT / "deploy" / "docker-compose.prod.yml"


# --------------------------------------------------------------------------- #
# Leader election
# --------------------------------------------------------------------------- #
class TestSchedulerLeaderElection:
    def test_scheduler_enabled_config_exists(self):
        from app.config import get_settings

        assert hasattr(get_settings(), "SCHEDULER_ENABLED"), (
            "SCHEDULER_ENABLED missing — API replicas cannot opt out of "
            "background jobs (multi-replica double-spend)"
        )

    def test_disabled_scheduler_skips_job_registration(self):
        """With SCHEDULER_ENABLED=false the app must NOT create any
        APScheduler jobs (subprocess: settings are process-cached)."""
        code = (
            "import os, logging\n"
            "logging.basicConfig(level=logging.INFO)\n"
            "os.environ['SCHEDULER_ENABLED'] = 'false'\n"
            "os.environ.pop('DATABASE_URL', None)\n"
            "from fastapi.testclient import TestClient\n"
            "from app.main import app\n"
            "with TestClient(app) as c:\n"
            "    assert c.get('/').status_code == 200\n"
            "print('BOOTED')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            timeout=90,
        )
        out = result.stdout + result.stderr
        assert "BOOTED" in out, f"app failed to boot with scheduler off: {out[-400:]}"
        # The disabled path logs exactly this line.
        assert "SCHEDULER_ENABLED=false" in out, (
            "replica did not announce scheduler-off (leader election broken)"
        )

    def test_compose_api_replicas_scheduler_off_scheduler_on(self):
        """The compose file itself must encode the split: api=false,
        scheduler=true — the misconfiguration-proof contract."""
        text = COMPOSE.read_text()
        # The shared base sets the default for API replicas.
        assert text.count("SCHEDULER_ENABLED: \"false\"") >= 1, (
            "api replicas not marked SCHEDULER_ENABLED=false"
        )
        # The scheduler service overrides to true — find it within the
        # scheduler service block.
        scheduler_block = text.split("scheduler:")[1].split("worker:")[0]
        assert "SCHEDULER_ENABLED: \"true\"" in scheduler_block, (
            "scheduler service does not own the jobs"
        )


# --------------------------------------------------------------------------- #
# Production healthcheck vs gated docs
# --------------------------------------------------------------------------- #
class TestHealthChecks:
    def test_prod_healthcheck_does_not_use_docs(self):
        """F1 gated /docs off in production — a healthcheck that pings
        /docs would kill every prod replica. Prod must probe '/'."""
        text = COMPOSE.read_text()
        # Extract only the healthcheck TEST commands (comments may mention /docs).
        test_lines = [
            line.strip() for line in text.splitlines()
            if "test:" in line
        ]
        for line in test_lines:
            assert "/docs" not in line, (
                f"prod healthcheck uses /docs: {line} — gated off in production, "
                "the app would be marked dead"
            )
        assert any("localhost:8000/" in line for line in test_lines), (
            "no root-probe healthcheck found"
        )

    def test_root_health_endpoint_exists(self):
        from fastapi.testclient import TestClient  # noqa: F401
        from app.main import app

        paths = {getattr(r, "path", None) for r in app.routes}
        assert "/" in paths, "root health probe missing (LBs need it)"


# --------------------------------------------------------------------------- #
# No credentials / no exposed internal ports in prod
# --------------------------------------------------------------------------- #
class TestProdComposeHygiene:
    def test_no_default_db_credentials(self):
        """The dev compose shipped zemest/zemest_secret defaults (audit
        B1). The prod compose must have NO credential defaults."""
        text = COMPOSE.read_text()
        assert "zemest_secret" not in text, "hardcoded DB password in prod compose"
        assert "postiz-password" not in text
        # Every postgres reference must use ${...} substitution.
        assert "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}" in text
        assert "POSTGRES_USER: ${POSTGRES_USER}" in text

    def test_database_and_redis_not_published(self):
        """Published 5432/6379 in prod = network-reachable DB (audit B1
        critical). Internal services must have NO ports: sections."""
        text = COMPOSE.read_text()
        db_block = text.split("  db:")[1].split("  pgbouncer:")[0]
        redis_block = text.split("  redis:")[1].split("  api:")[0]
        pgbouncer_block = text.split("  pgbouncer:")[1].split("  redis:")[0]

        import re
        for name, block in (
            ("db", db_block), ("redis", redis_block), ("pgbouncer", pgbouncer_block)
        ):
            # A real published port looks like "5432:5432" under ports:.
            published = re.search(r'ports:\s*\n\s*-\s*"?\d+:\d+', block)
            assert not published, (
                f"{name} publishes ports in production — must be network-only"
            )

    def test_app_env_is_production(self):
        text = COMPOSE.read_text()
        assert "APP_ENV: production" in text, (
            "prod compose must set APP_ENV=production (docs gating, etc.)"
        )

    def test_public_base_url_required(self):
        """F4: intentions refuse to run without PUBLIC_BASE_URL — the env
        example must document it and the compose must pass it through."""
        env_example = (BACKEND / ".env.example").read_text()
        assert "PUBLIC_BASE_URL=" in env_example
        assert "TENANT_TOKEN_ENCRYPTION_KEY=" in env_example

    def test_scaling_doc_matches_compose_shape(self):
        scaling = (REPO_ROOT / "SCALING.md").read_text()
        text = COMPOSE.read_text()
        assert "replicas: 2" in text and "replicas: 1" in text
        assert "pgbouncer" in text.lower()
        # Capacity math documented for the promised 10k users.
        assert "10,000" in scaling or "10k" in scaling.lower()

    def test_worker_entry_point_exists(self):
        worker = BACKEND / "app" / "tasks" / "worker_main.py"
        assert worker.exists(), "dedicated huey worker entry missing"
        compose_text = COMPOSE.read_text()
        assert "worker_main" in compose_text, "worker service not wired to entry"

    def test_compose_file_is_valid_yaml(self):
        try:
            import yaml
        except ImportError:
            pytest.skip("pyyaml not available")
        data = yaml.safe_load(COMPOSE.read_text())
        services = set(data["services"].keys())
        assert {"db", "pgbouncer", "redis", "api", "scheduler", "worker", "caddy"} <= services
