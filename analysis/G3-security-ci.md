# G3 — Security Scanning + CI Research (Python + TypeScript monorepo)

- **Agent:** G3 (github-research), 2026-09-01
- **Scope:** automated security scanning + CI for `github.com/Michael-ctrl-eng/zemest` (public merged monorepo: Next.js/TS at root `src/`, FastAPI backend at `repos/zemest/`, backend deps in `repos/zemest/requirements.txt`, frontend lockfile = `bun.lock`)
- **Ground truth from prior tasks:** E10/X1 security posture (JWT hardened, XFF bypass fixed, **no security headers on Next**, 46-finding X1 audit with 10 criticals), **a GitHub PAT was already exposed once** (worklog: "GIT PUSH BLOCKED: rotate the exposed PAT"; ZEMEST_MASTER_FIX_LIST.md S5: hardcoded FB verify token "in public repo"), R10: **NO CI exists at all** (verified again this session: no `.github/` directory in the repo).
- **Repo visibility:** PUBLIC (per `.gitignore` comment "public repo: keep it lean & secret-free" + S5 fix note) → CodeQL, secret scanning, Dependabot alerts are all **free**.

---

## 1. Method & budget

≤ 15 GitHub research fetches, **exactly 15 used** (HTML page + commits.atom per repo; the shared-IP REST-API quota was exhausted at start — `remaining: 0` — so R10's scrape fallback was reused):

| # | Fetch | Fields obtained |
|---|---|---|
| 1–2 | gitleaks/gitleaks (HTML + atom) | 29,044★, push 2026-07-22 |
| 3–4 | pypa/pip-audit | 1,359★, push 2026-08-31 |
| 5–6 | woodruffw/zizmor (redirects → zizmorcore) | 6,425★, push 2026-08-30 |
| 7–8 | semgrep/semgrep | 16,458★, push 2026-08-25 |
| 9–10 | PyCQA/bandit | 8,249★, push 2026-08-29 |
| 11–12 | github/codeql-action | 1,631★, push 2026-08-27 |
| 13 | zizmorcore/zizmor (HTML) | license MIT, canonical home |
| 14 | gitleaks/gitleaks-action (HTML) | 641★, MIT, `@v3`, README usage snippet |
| 15 | trufflesecurity/trufflehog (HTML) | 27,644★, AGPL-3.0 |

Plus **local validation runs in the sandbox (no GitHub API)** — this is the part that makes the rankings evidence-based rather than vibes-based:

- `uvx pip-audit -r repos/zemest/requirements.txt` → **38 known vulnerabilities in 10 packages** (full list §2)
- `uvx bandit -r repos/zemest/app -ll` → 22 issues (1 HIGH, 1 MEDIUM at `-ll`) on 14,721 LOC
- `bun pm audit` / `bun pm scan` (bun 1.3.14) → **audit subcommand does not exist; `scan` requires a scanner package configured in bunfig.toml** ("no security scanner configured") — bun's audit story is not turnkey
- 1 PyPI metadata call (bandit license: Apache-2.0, v1.9.4)

---

## 2. What the scanners found on OUR code today (proof of value)

### 2.1 pip-audit — 38 vulns / 10 packages in `repos/zemest/requirements.txt`

| Package | Pinned | Advisories | Fix version | Risk note |
|---|---|---|---|---|
| **python-jose** | 3.3.0 | 5 (PYSEC-2024-232/233 = the CVE-2024-33663 algorithm-confusion + CVE-2024-33664 JWE pair, + PYSEC-2025-185) | 3.4.0 (one advisory has no fix) | **This is our JWT auth library.** X1/Z4 already flagged it; the exact regression class the just-hardened JWT stack must not keep. Long-term: consider `pyjwt`/`joserfc`. |
| **python-multipart** | 0.0.20 | 6 (PYSEC-2026-1852/3036–3040) | 0.0.22 → 0.0.31 | Form/file-upload parsing on every auth route |
| **starlette** (transitive via fastapi 0.115.6) | 0.41.3 | 9 | 0.47.2 … 1.3.1 | Transitive — needs a fastapi bump, not a direct pin; proves why tree resolution matters |
| **litellm** | 1.83.0 | 10 | 1.83.7 → 1.84.0 | LLM gateway path |
| **jinja2** | 3.1.5 | 1 | 3.1.6 | Renders the (X1-flagged unescaped) dashboard templates |
| python-dotenv | 1.0.1 | 1 | 1.2.2 | |
| aiosmtplib | 3.0.2 | 2 (incl. CVE-2026-55558) | 5.1.1/5.1.2 | |
| sqladmin | 0.24.0 | 1 | 0.25.1 | Admin panel surface |
| pytest | 8.3.4 | 1 | 9.0.3 | dev-only |
| ecdsa | 0.19.2 | 1 (PYSEC-2026-1325) | none | python-jose transitive side-channel |

pip-audit exits non-zero on findings → usable as a CI gate; start with `continue-on-error: true`, flip to gating after the upgrade batch.

### 2.2 bandit — 22 issues on 14.7k LOC (at `-ll` = confidence+level medium)

- **HIGH B324** `repos/zemest/app/ai/silent_trainer.py:600` — `hashlib.sha1(raw.encode()).hexdigest()[:16]` (weak hash; likely a dedup fingerprint, but it's the only High on the whole backend)
- **MED B104** `repos/zemest/app/config.py:10` — bind `0.0.0.0` (dev default)
- 20 Low (asserts, etc.) — noise; threshold at `-ll` keeps signal
- Verified: bandit 1.9.4 output formats = `{csv,custom,html,json,screen,txt,xml,yaml}` — **no native SARIF**

### 2.3 Frontend dependency auditing — the bun wrinkle

- bun 1.3.14 has no `bun pm audit`; `bun pm scan` errors with "no security scanner configured" (needs `[install.security] scanner = "…"` in bunfig.toml)
- Workable today: `npm install --package-lock-only --ignore-scripts && npm audit --audit-level=high` in CI (generates a lockfile from `package.json`; approximation of bun.lock pins)
- Dependabot does **not** parse `bun.lock` for the npm ecosystem yet — verify status before relying on it for JS deps

---

## 3. Ranked top 5 (all metadata scraped this session unless noted)

### #1 — Gitleaks (+ gitleaks-action wrapper)
| Field | Value |
|---|---|
| URL | https://github.com/gitleaks/gitleaks · wrapper https://github.com/gitleaks/gitleaks-action |
| Stars / last push | 29,044★ / 2026-07-22 (wrapper: 641★) |
| License | MIT (both) |
| Catches | Secrets across **full git history + working tree**: GitHub PATs (`ghp_…`), API keys, DB URLs, private keys — 150+ regex/entropy detectors |
| Placement | **Both sandbox and CI.** Pre-commit hook before the commit ever lands; CI job with `fetch-depth: 0` scans every commit + all history; GitHub-native secret scanning/push protection as the SaaS third layer |
| Cost | ~30 s/CI run; **free for personal accounts** — README (scraped): `GITLEAKS_LICENSE` "required for organizations, not required for user accounts" → Michael-ctrl-eng is a user account → free |
| Integration | See `security.yml` job `gitleaks` in §5 (snippet taken from the action's README verbatim: `actions/checkout@v6` + `fetch-depth: 0` + `gitleaks/gitleaks-action@v3`) |
| **Verdict** | **ADOPT FIRST.** The PAT-exposure incident is exactly this failure mode, on a public repo, with pushes currently blocked on rotation. Run locally once **before** the next push (20+ uncommitted files + 3 local-only commits are waiting). |

### #2 — pip-audit (PyPA)
| Field | Value |
|---|---|
| URL | https://github.com/pypa/pip-audit |
| Stars / last push | 1,359★ / 2026-08-31 (very active) |
| License | MIT |
| Catches | Known CVEs/PYSEC for **pinned + transitive** Python deps (PyPI Advisory DB → OSV); `--fix` emits an upgrade script; `-f json`/`cyclonedx-json` (SBOM-ready) |
| Placement | **Both.** Sandbox: `uvx pip-audit -r …` (zero install — proven this session); CI: gate + weekly `schedule:` to catch *newly published* CVEs against *pinned* old versions |
| Cost | ~60–90 s/CI run (resolves the full tree incl. camel-tools/fasttext) |
| Integration | `uvx pip-audit -r repos/zemest/requirements.txt` via `astral-sh/setup-uv` (§5) |
| **Verdict** | **ADOPT.** Highest value-per-line-of-YAML in existence for this repo: it already found 38 vulns including the entire auth stack (§2.1). Beats `safety` (free, PyPA-maintained, OSV data) — see §4. |

### #3 — CodeQL (github/codeql-action)
| Field | Value |
|---|---|
| URL | https://github.com/github/codeql-action (action, MIT; the CodeQL *engine* itself is proprietary, free for public-repo analysis) |
| Stars / last push | 1,631★ / 2026-08-27 (ships near-daily) |
| Catches | **Dataflow-based injection classes** in Python *and* JS/TS: SQL injection, XSS, path traversal, request forgery (SSRF-adjacent), hardcoded credentials, weak crypto — i.e., X1's critical bucket (SQLi via the `ilike` order path, stored XSS via customer_name, the crawl SSRF chain) |
| Placement | **CI-only.** GitHub-hosted `ubuntu-latest`, **free while the repo is public** (private → needs GitHub Advanced Security; fallback then = semgrep, §4) |
| Cost | ~3–5 min/run (two languages); SARIF results land in the repo **Security tab** with PR annotations |
| Integration | Canonical `codeql.yml` (§5); even faster path: repo Settings → Code security → **CodeQL default setup** (one click, no YAML). Python is buildless; for `javascript-typescript` the autobuild step installs deps (bun.lock caveat: if resolution is poor, add an install step) |
| **Verdict** | **ADOPT.** Best signal-to-effort for code-level injection; zero infra; integrates with the same Security tab the other SARIF tools upload to. Guard-rails the freshly hardened JWT/XFF fixes against regression. |

### #4 — zizmor (Actions static analysis)
| Field | Value |
|---|---|
| URL | https://github.com/zizmorcore/zizmor (woodruffw/zizmor now redirects there; docs zizmor.sh) |
| Stars / last push | 6,425★ / 2026-08-30 |
| License | MIT |
| Catches | GitHub **Actions security misconfigurations**: unpinned third-party actions, `${{ }}` template injection into `run:`, over-broad `permissions:`, `pull_request_target` dangers, secret exfiltration patterns — the tj-actions/changed-files supply-chain incident class |
| Placement | **CI-only** (scans `.github/workflows/`); SARIF → Security tab |
| Cost | ~5 s/CI run |
| Integration | `uvx zizmor --format sarif --output zizmor.sarif .` + `github/codeql-action/upload-sarif@v3` (§5) |
| **Verdict** | **ADOPT the same day the first workflow lands.** We are about to trust ≥4 third-party actions on day one (checkout, gitleaks-action, setup-uv, upload-sarif) — zizmor is the seatbelt for exactly that. Cheapest tool on this list. |

### #5 — Bandit (PyCQA)
| Field | Value |
|---|---|
| URL | https://github.com/PyCQA/bandit |
| Stars / last push | 8,249★ / 2026-08-29 |
| License | Apache-2.0 (verified via PyPI, v1.9.4) |
| Catches | Python-specific unsafe patterns: weak hashes (found our `silent_trainer.py:600` SHA1), subprocess shell, pickle, SQL string building, `assert` in security code, B104 all-interfaces bind |
| Placement | **Both.** Sandbox (`uvx bandit -r repos/zemest/app -ll`) + CI; no cross-file dataflow, so it complements rather than replaces CodeQL |
| Cost | ~10 s/CI run; no native SARIF (txt/json only — keep it console-gated) |
| Integration | §5 job `bandit` + official pre-commit hook |
| **Verdict** | **ADOPT as the cheap fifth.** 22 findings prove it works on this codebase; threshold `-ll` keeps it low-noise. If you must cut one tool, cut this (CodeQL subsumes most of it). |

---

## 4. Evaluated and deferred (with data where fetched)

| Tool | Data | Why deferred |
|---|---|---|
| **semgrep** | 16,458★, push 2026-08-25, LGPL-2.1 (core engine; registry rules carry mixed licenses) | Strong overlap with CodeQL for py+ts; heavier setup (engine + rule curation); OSS registry/private-repo policy friction. **First fallback if the repo ever goes private** (CodeQL needs GHAS there). |
| **trufflehog** | 27,644★, AGPL-3.0 | Unique power = secret **verification** (checks whether leaked creds are live across 800+ APIs — would have told us if the exposed PAT was still active). Overkill vs gitleaks for detect-only; AGPL + heavier runtime. Adopt if a verification workflow is wanted. |
| **safety** (pyupio) | not fetched (~1.6k★, MIT) | Advisory DB went commercial (Safety CLI tiers); pip-audit gives the same coverage free from PyPA/OSV. Skip. |
| **betterer** | not fetched (MIT) | Lint *ratchet* — needs an existing lint/test baseline to ratchet from; repo has zero lint CI (E7/R10). Revisit after eslint runs in CI. |
| **ruff** | not fetched (MIT, huge) | Excellent linter, but **deliberately does not implement flake8-bandit's `S` rules** (long-open feature request) → it is a lint tool, not a security scanner. Pair it with bandit; don't count it as security coverage. |
| **pre-commit framework** | not fetched (~13k★, MIT, stable) | Not a scanner — the **local glue layer**. Included in the pipeline below (§5.4) wrapping gitleaks/bandit/pip-audit so the PAT-class leak dies at commit time, before any push. |
| **bun pm scan / npm audit** | validated locally (§2.3) | bun audit not turnkey (needs bunfig scanner config); npm-audit job included in pipeline as the pragmatic bridge. |

---

## 5. Recommended minimal CI pipeline (4 files, ~10 min setup, all free)

Design: one security workflow (4 fast jobs) + CodeQL workflow + Dependabot config + local pre-commit. Total CI wall time ≈ 5–7 min/run on free GitHub-hosted runners; all adopted licenses permissive (MIT ×5, Apache-2.0 ×1; CodeQL engine proprietary-but-free-for-public).

### 5.1 `.github/workflows/security.yml`

```yaml
name: security
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  schedule:
    - cron: "17 4 * * 1"   # weekly: newly published CVEs vs our pins
permissions:
  contents: read
  security-events: write    # SARIF upload (zizmor)

jobs:
  gitleaks:
    name: secrets (gitleaks)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0            # full history — where the PAT incident lived
      - uses: gitleaks/gitleaks-action@v3
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          # GITLEAKS_LICENSE: only required for orgs — personal account = free

  pip-audit:
    name: python deps (pip-audit)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v5
      - run: uvx pip-audit -r repos/zemest/requirements.txt
        # 38 known vulns today (G3 report §2.1) — add `continue-on-error: true`
        # until the upgrade batch lands, then let it gate.

  npm-audit:
    name: js deps (npm audit)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v5
        with:
          node-version: 22
      - run: npm install --package-lock-only --ignore-scripts
      - run: npm audit --audit-level=high
        # bun.lock stays canonical; this is the CI-only bridge (G3 §2.3)

  zizmor:
    name: workflows (zizmor)
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v5
      - run: uvx zizmor --format sarif --output zizmor.sarif .
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: zizmor.sarif

  bandit:
    name: python sast-lite (bandit)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v5
      - run: uvx bandit -r repos/zemest/app -ll -f txt
        # -ll = medium+ only: 1 HIGH (B324 silent_trainer.py:600) + 1 MED (B104) today
```

### 5.2 `.github/workflows/codeql.yml`

```yaml
name: codeql
on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  schedule:
    - cron: "23 2 * * 5"
permissions:
  contents: read
  security-events: write
jobs:
  analyze:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        language: [python, javascript-typescript]
    steps:
      - uses: actions/checkout@v6
      - uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}
      - uses: github/codeql-action/autobuild@v3
      - uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{ matrix.language }}"
# python: buildless. javascript-typescript: autobuild installs deps;
# if resolution is poor under bun.lock, add a manual install step before analyze.
```

### 5.3 `.github/dependabot.yml`

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: /repos/zemest
    schedule:
      interval: weekly
    groups:
      dependencies:
        patterns: ["*"]
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
  # NOTE: npm ecosystem not enabled — Dependabot doesn't parse bun.lock yet.
  # If a committed package-lock.json ever appears, add an npm entry here.
```

### 5.4 `.pre-commit-config.yaml` (sandbox/local layer — kills the PAT-class leak at commit time)

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.28.0          # pin to the latest release tag at install time
    hooks:
      - id: gitleaks
  - repo: https://github.com/PyCQA/bandit
    rev: 1.9.4
    hooks:
      - id: bandit
        args: ["-ll", "-r", "repos/zemest/app"]
  - repo: local
    hooks:
      - id: pip-audit
        name: pip-audit (backend deps)
        entry: uvx pip-audit -r repos/zemest/requirements.txt
        language: system
        pass_filenames: false
```

Run: `pip install pre-commit && pre-commit install` (hooks then run on every commit; `pre-commit run --all-files` for the first sweep).

### 5.5 Zero-YAML GitHub-native layer (do this first — 5 minutes, no files)

Repo **Settings → Code security**: enable **secret scanning + push protection** (free, public repo — would have blocked the PAT push outright), **Dependabot alerts + security updates**, and optionally **CodeQL default setup** (the no-YAML version of §5.2).

---

## 6. Roll-out order & next actions

1. **Rotate the exposed PAT** (prerequisite — pushes are blocked; CI can't run on unpushed commits).
2. Run `uvx pip-audit -r repos/zemest/requirements.txt` + gitleaks **locally once** before pushing the 20+ uncommitted files and 3 local commits.
3. Flip on the GitHub-native layer (§5.5): secret scanning + push protection + Dependabot alerts.
4. Commit the two workflow files (§5.1, §5.2) + `dependabot.yml` (§5.3) → first CI run within minutes; watch gitleaks/pip-audit results on the Security tab.
5. **Remediation batch** (from §2.1): `python-jose 3.3.0→3.4.0`, `python-multipart →0.0.31`, `jinja2 →3.1.6`, `python-dotenv →1.2.2`, `aiosmtplib →5.1.2`, `sqladmin →0.25.1`, `litellm →1.84.0+`, fastapi bump for starlette; then remove `continue-on-error` and let pip-audit gate.
6. Fix bandit B324 (`silent_trainer.py:600`: sha1 → sha256, or `usedforsecurity=False`) and B104 (bind env-driven).
7. Install pre-commit locally (§5.4).
8. Later/optional: trufflehog for live-credential verification; semgrep if the repo goes private; betterer once lint CI exists; fold into R10's test workflow when that lands (one shared `on:` graph).
