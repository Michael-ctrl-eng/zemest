# R4 — Small-Model Fine-Tuning + Serving with Crash-Resume (GitHub Research)

**Agent:** R4 (github-research) · **Mode:** research only, zero code changes
**Scope:** tools for the roadmap item "INVISIBLE per-tenant self-training → eventually FINE-TUNE a small model on work chats only" on a modest VPS.

## Grounding in the current code (read before researching)

- Inference is SOLVED: internal z-ai OpenAI-compatible API (glm-4.6) is provider #1 in `app/ai/llm_client.py` (Task 18, worklog line ~1041), with a bounded 45s fallback ladder.
- `app/ai/silent_trainer.py` (st-2): scans all tenants → classifies (cc-2) commerce/junk → rebuilds `tenant.style_profile` from commerce chats only, with **granular DB-commit checkpoints** (`CLASSIFY_BATCH_COMMIT = 25`), monotonic watermarks (`classified_at`), per-tenant exponential backoff self-heal, maturity gating. State lives in `tenant.training_state` (JSON column).
- `app/ai/chat_classifier.py`: pure-CPU Egyptian-commerce lexicon/regex scorer (µs, no LLM).
- `app/ai/style_learner.py`: smart-sampled (300-msg) LLM structured extraction; heuristics fallback.
- `app/tasks/training_worker.py`: inline asyncio loop, one cycle / 45 s, never raises, crash-resumes from DB state; fetchWithHeal revives the whole daemon.
- **Hardware reality (this box): 2 vCPU, 3.9 GB RAM, 9.9 GB disk, NO GPU.** Training any ≥0.6 B model *in-process* is impossible here; serving a 0.6–1.7 B Q4 model is fine. Architecture below is designed for "modest VPS serving + burst/rented GPU training".

## Research method

Direct GitHub API lookups (`curl -sL https://api.github.com/repos/<owner>/<repo>`), no search API (avoids 403s). **12 GitHub API calls + 9 raw doc fetches (READMEs / Modelfile / llama-server docs) ≈ 21 network calls total.** All `pushed_at` values below are as returned by the API this run (all repos actively pushed within ~1 day of each other).

## Full research matrix (10 repos)

| Repo (URL) | Stars | Last push | License | What it is |
|---|---|---|---|---|
| [huggingface/transformers](https://github.com/huggingface/transformers) | 164,674 | 2026-09-01 | Apache-2.0 | Model framework + `Trainer` (canonical resume support) |
| [ollama/ollama](https://github.com/ollama/ollama) | 179,850 | 2026-09-01 | MIT | Local serving runtime (GGUF), REST :11434 |
| [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | 126,545 | 2026-09-01 | MIT | C/C++ inference; `llama-server` is OpenAI-compatible, **multi-LoRA routing verified** (below) |
| [vllm-project/vllm](https://github.com/vllm-project/vllm) | 90,630 | 2026-09-01 | Apache-2.0 | High-throughput serving engine, multi-LoRA hot-swap (GPU) |
| [unslothai/unsloth](https://github.com/unslothai/unsloth) | 75,367 | 2026-09-01 | Apache-2.0 | Fast single-GPU LoRA/QLoRA/RL training + GGUF export; now also a local run/train UI |
| [hiyouga/LlamaFactory](https://github.com/hiyouga/LlamaFactory) | 74,481 | 2026-08-31 | Apache-2.0 | Config-driven fine-tuning of 100+ LLMs (renamed from LLaMA-Factory) |
| [huggingface/peft](https://github.com/huggingface/peft) | 21,617 | 2026-08-31 | Apache-2.0 | LoRA/QLoRA/IA³… adapter library (tiny per-tenant adapters) |
| [Lightning-AI/litgpt](https://github.com/Lightning-AI/litgpt) | 13,640 | 2026-08-31 | Apache-2.0 | Pretrain→finetune→deploy stack, small codebase (6 MB repo) — NOT archived, active |
| [axolotl-ai-cloud/axolotl](https://github.com/axolotl-ai-cloud/axolotl) | 12,431 | 2026-09-01 | Apache-2.0 | YAML-driven multi-method fine-tuning (moved orgs from openaccess-ai-collective) |
| [meta-pytorch/torchtune](https://github.com/meta-pytorch/torchtune) | 5,802 | 2026-08-31 | BSD-3-Clause | PyTorch-native post-training recipes (moved from pytorch org; not archived) |

### Doc-verified facts (raw fetches this run)

- **llama.cpp `llama-server`** (from `tools/server/README.md`, master): `--lora FNAME` (comma-separated / multiple = several adapters on ONE shared base), `--lora-scaled FNAME:SCALE`, `--lora-init-without-apply`, per-request `"lora": [{"id": 0, "scale": 0.5}]` field, `GET /lora-adapters`, `POST /lora-adapters`. Caveat documented: requests with *different* LoRA configs are not batched together (perf, not correctness).
- **ollama** (`docs/modelfile.md`): the old experimental `ADAPTER` Modelfile directive is **gone from current docs** → no per-tenant LoRA routing in Ollama today; a per-tenant model means a *merged* GGUF (base duplicated per tenant, ~1–2 GB each).
- **unsloth README**: LoRA/QLoRA/full/RL/GRPO/DPO/FP8 training; **GGUF export** (→ llama.cpp/Ollama), NVFP4/FP8; "Skip PyTorch (GGUF-only mode)" serving path; connects to vLLM/Ollama servers. GPU (NVIDIA/AMD) required for training.
- torchtune: README confirms activity + activation-checkpointing/W&B checkpoint logging; resume is via its checkpointer (`resume_from_checkpoint=True` recipe arg) — training-knowledge, not re-verified.
- LlamaFactory / axolotl: both build on HF `Trainer` semantics (auto-resume latest checkpoint in `output_dir` / `resume_from_checkpoint: auto` config; LlamaFactory also has `resume_lora_training`). Long-standing documented behavior; READMEs no longer surface the exact wording.

---

## Ranked top 5 for zemest (max 5, ranked)

### #1 — PEFT + transformers `Trainer` (huggingface/peft + huggingface/transformers)

- **URL:** https://github.com/huggingface/peft · https://github.com/huggingface/transformers
- **Stats:** 21.6k★ + 164.7k★ · pushed 2026-08-31 / 2026-09-01 · **Apache-2.0** (both)
- **Resume/checkpoint: the gold standard.** `Trainer(resume_from_checkpoint="path"|"auto")` restores model + optimizer + LR scheduler + RNG state; `save_strategy="steps"`, `save_steps`, `save_total_limit=2` bounds disk; `save_only_model` option for inference-only saves. Checkpoint dirs contain `adapter_model.safetensors` + `adapter_config.json` + training state — a crash mid-run loses at most `save_steps` steps. This is the *exact* crash-resume contract our `silent_trainer` already models (granular commits + watermark + resume).
- **Hardware:** the **only engine here that trains on CPU**. LoRA fp32 on 0.5–1.7 B fits 4–8 GB RAM (only adapter params get optimizer state — MBs, not GBs); gradient-checkpointing + small batch keep activations low. GPU optional. Training 1.7 B on this 2 vCPU box is *possible* but slow — plan for a rented GPU above 1.7 B.
- **Disk footprint:** pip env ~1.5–2 GB; base weights 1–3.5 GB (0.6–1.7 B); rank-16 adapter ≈ **10–30 MB/tenant**; per-run checkpoint dir ≈ 60–100 MB (adapter + 2× optimizer).
- **Integration sketch (with `silent_trainer`):**
  1. New `app/ai/ft_runner.py` launched as a **detached subprocess** (`python -m app.ai.ft_runner --tenant <id>`) — torch never loads in the API process (import alone ~1–2 GB).
  2. Dataset: export JSONL from commerce conversations only — reuse `_filter_commerce_set()` + `is_fallback` filtering (Task-18 fix guarantees no canned-apology contamination) + exemplar-pair format as chat samples. Digest it (like `_profile_signature`).
  3. `LoraConfig(r=16, alpha=32, dropout=0.05, target_modules=[...])` on a small Arabic-strong base; `Trainer(save_strategy="steps", save_steps=20, save_total_limit=2, resume_from_checkpoint=last)`.
  4. Ledger: new `ft_state` JSON on the tenant row (same pattern as `training_state`): run_id, engine, base+digest, dataset_digest, step, checkpoint path, status, consecutive_errors, next_attempt_at. The 45 s inline worker (or Celery beat) promotes tenants to training, reaps stuck runs, respawns → Trainer resumes. Self-heal composes, nothing new invented.
- **Verdict: ADOPT — the engine.** Cheapest, most controllable, only CPU-viable path, cleanest resume semantics, Apache-2.0, tiny per-tenant artifacts. Slightly more code than turnkey tools — that's the point for us.

### #2 — Unsloth (unslothai/unsloth)

- **URL:** https://github.com/unslothai/unsloth
- **Stats:** 75,367★ · pushed 2026-09-01 · **Apache-2.0** · repo 258 MB
- **Resume/checkpoint:** rides the HF `Trainer` (same `resume_from_checkpoint` semantics as #1) plus its own `save_pretrained` adapter snapshots. Crash-resume = identical contract to #1.
- **Hardware:** **GPU required** (NVIDIA CUDA / AMD ROCm; no CPU training). ~2× throughput and ~40–70 % less VRAM via Triton kernels; QLoRA 4-bit fits 3 B models in ~8–12 GB VRAM. Ideal as a *rented burst* (spot GPU, Colab, vast.ai): adapters are portable files, train off-box, deploy on the VPS.
- **Disk:** env ~3–4 GB (GPU stack). Repo also publishes ready quantized GGUFs ("Dynamic Quants") — we can consume those for serving without training anything.
- **Integration sketch:** an `engine="unsloth"` branch in `ft_runner.py`: `FastLanguageModel.from_pretrained(..., load_in_4bit=True, max_seq_length=512)` → `get_peft_model` → SFTTrainer → at end `model.save_pretrained(...)` (16-bit merged) **+ `save_pretrained_gguf(..., quantization_method="q4_k_m")`** → drop the per-tenant `.gguf` adapter straight into the llama-server adapters dir (see #3). One training run produces both the HF adapter (future vLLM) and the GGUF adapter (llama.cpp today).
- **Verdict: ADOPT as the GPU fast-path** for tenants/data above CPU scale; keep #1 as the always-works fallback. Apache-2.0 code; check model licenses separately (their model cards cover this).

### #3 — llama.cpp / `llama-server` (ggml-org/llama.cpp)

- **URL:** https://github.com/ggml-org/llama.cpp
- **Stats:** 126,545★ · pushed 2026-09-01 · **MIT** · repo 436 MB (binary far smaller)
- **Resume/checkpoint:** N/A for us — its built-in training tools are toys; it's the **serving** half of the pipeline. (Its inference-side "resume" story is stateless HTTP.)
- **Hardware: CPU-first — this is the only serving engine that fits our 2 vCPU / 3.9 GB box.** A 0.6–1.7 B Q4_K_M GGUF is 0.4–1.1 GB of RAM; threads tunable to 2 cores; partial GPU offload later. Verified **multi-LoRA on one shared base**: `--lora a.gguf --lora b.gguf ...`, `--lora-init-without-apply`, per-request `"lora":[{"id":N,"scale":1.0}]`, `GET/POST /lora-adapters` at runtime. That is *exactly* the per-tenant shape we need: **1 base model in RAM + N adapters × 10–30 MB on disk, routed per request.** (Known caveat: differing-LoRA requests aren't batched together — fine at our QPS.)
- **Disk:** build + base GGUF 1–2 GB; adapters 10–30 MB each → hundreds of tenants on a 20 GB disk.
- **Integration sketch:** systemd/Docker sidecar `llama-server -m qwen3-1.7b-Q4_K_M.gguf --port 8010 --host 127.0.0.1 --lora adapters/<tenant>.gguf ...`; add a `local-lora` provider to the existing `llm_client` ladder (`base_url=http://127.0.0.1:8010/v1`, OpenAI-compatible, `extra_body={"lora":[{"id":k,"scale":1.0}]}`) placed above/below z-ai per config. Existing bounded-45s ladder + fallback keeps availability. Adapter registry = `ft_state` rows (adapter_path, loaded id).
- **Verdict: ADOPT — the serving backbone on a modest VPS.** MIT, zero Python serving deps, and the only runtime with verified per-request LoRA routing that runs on CPU.

### #4 — LLaMA-Factory / LlamaFactory (hiyouga/LlamaFactory)

- **URL:** https://github.com/hiyouga/LlamaFactory
- **Stats:** 74,481★ · pushed 2026-08-31 · **Apache-2.0** · repo 14 MB
- **Resume/checkpoint:** builds on HF `Trainer`: **auto-resumes from the latest checkpoint found in `output_dir`** on relaunch + `resume_lora_training` flag (continue a LoRA from saved adapter rather than re-init). Crash → relaunch same YAML → continues. There is also a dedicated `export` stage (merge / GGUF / vLLM layouts).
- **Hardware:** practical targets GPU (same physics as #1; CPU technically possible, slow). Deps ~2–3 GB env (full stack: Liger, etc.).
- **Integration sketch:** `ft_state` → generate per-tenant YAML (dataset: sharegpt/alpaca JSONL from our commerce export, `finetuning_type: lora`, `lora_rank: 16`, `output_dir: /var/lib/zemest/ft/<tenant>`, `save_steps`, `cutoff_len: 512`) → subprocess `llamafactory-cli train tenant.yaml` → `llamafactory-cli export ... -gguf q4_k_m` → adapters dir. The "one YAML in, one artifact out, auto-resume in between" contract maps 1:1 onto our crash-resume worker; the WebUI stays unused (we're invisible by design).
- **Verdict: keep as the turnkey alternative to #1** (config-not-code, 100+ models pre-wired, easiest swap of base model per tenant). Cut from the critical path only because we need process-level control of checkpoints/queueing that #1 gives natively — but if we later want ops-tweaks without code changes, this is the drop-in.

### #5 — vLLM (vllm-project/vllm)

- **URL:** https://github.com/vllm-project/vllm
- **Stats:** 90,630★ · pushed 2026-09-01 · **Apache-2.0**
- **Resume/checkpoint:** N/A (serving only).
- **Hardware:** GPU-first (6–16 GB VRAM incl. KV cache for small models); CPU inference exists but is not the design point. RAM footprint (paged attention, CUDA graphs) rules out our current box.
- **Multi-LoRA:** `--enable-lora --lora-modules name=path` at boot **+ dynamic hot-swap via REST** (`POST /v1/load_lora_adapter`, `POST /v1/unload_lora_adapter`) — best-in-class multi-tenant serving: continuous batching *across* different LoRA requests (solves the llama.cpp batching caveat), per-adapter paging. OpenAI-compatible → same `llm_client` provider shape as #3.
- **Integration sketch:** identical to #3 but on a GPU node: tenant promoted → trainer writes adapter (PEFT/unsloth format — vLLM consumes HF PEFT adapters directly) → platform POSTs load_lora_adapter → `llm_client` routes `model="tenant-<id>"`. No restarts, no GGUF conversion needed.
- **Verdict: ADOPT when a GPU arrives** (dedicated inference node or the rented burst box doubling as trainer+server). Not viable on the current CPU VPS.

---

## Also evaluated — cut (one-liners)

- **axolotl** (12.4k★, Apache-2.0, active, `resume_from_checkpoint: auto` in YAML): excellent multi-GPU/RL/evals kitchen sink; overlaps LlamaFactory with more moving parts (DeepSpeed/FSDP knobs) than our single-device, one-tenant-at-a-time queue needs. Cut.
- **torchtune** (5.8k★, BSD-3-Clause, active): clean PyTorch-native recipes, checkpointer-based resume, no-HF-dependency philosophy; smaller Arabic-instruct model coverage than the HF ecosystem and a second config system to learn. Cut (license is fine).
- **litgpt** (13.6k★, Apache-2.0, active, *not* archived): pretrain→finetune→deploy monorepo, tiny codebase; we don't pretrain and its serving lacks per-request multi-LoRA routing. Cut.
- **ollama** (179.9k★, MIT): best single-model local UX, but `ADAPTER` is gone from the current Modelfile docs → per-tenant LoRA routing impossible; per-tenant merged GGUFs duplicate the base (1–2 GB × N tenants) on a 9.9 GB disk. Cut for multi-tenant serving; fine as a dev-laptop convenience.
- **torchtune/axolotl/litgpt all have solid resume stories** — none lost on crash-resume grounds; they lost on fit (Arabic model coverage, dependency weight, or multi-tenant LoRA serving).

---

## Recommended training architecture for zemest

**Answering the brief's two explicit questions up front:**

1. **SQLite-stored checkpoints? NO for weights, YES for the ledger.** Keep model/adapter/checkpoint artifacts on the filesystem (HF format dirs, GGUF files) and store *state + pointers* in the DB. SQLite is superb for the metadata ledger — our existing pattern (`training_state` JSON, granular commits, monotonic watermarks, backoff) is already the right design and needs zero new machinery. Multi-MB/GB BLOBs in SQLite would bloat WAL, slow every commit, and break the 25-conversation-granularity resume story. Ledger fields for a new `ft_state` JSON column: `run_id, engine, base_model, base_digest, dataset_digest, rows, step, eval_loss, checkpoint_dir, adapter_path, gguf_path, status (queued|running|done|failed), heartbeat_at, consecutive_errors, next_attempt_at` (mirror `_record_error` backoff). Crash → worker sees `status=running` + stale heartbeat → respawns subprocess → engine auto-resumes from `checkpoint_dir` → ledger watermark advances. **`silent_trainer`'s self-heal loop composes with HF Trainer's resume; we invent nothing new.**
2. **Per-tenant LoRA adapters? YES — but gated, not unconditional.** Adapters are 10–30 MB, tenant-isolated (offboarding/GDPR = `rm -rf` + one DB row), hot-swappable per request in llama-server (verified) and vLLM, and trainable one-tenant-at-a-time without cross-tenant data leakage. Gate: only tenants with maturity ≥ current `MATURE_THRESHOLD` and e.g. **≥300 clean merchant replies** in commerce threads get a fine-tune; everyone else keeps the already-working exemplar few-shot + glm-4.6 path (identical UX, zero risk). Concurrency cap: 1 training run per box (DB queue). Escape hatch if adapter count explodes (>~200): style-cluster adapters (tenants grouped by the dialect/tone features `style_learner` already extracts).

**Phased plan (each phase independently shippable):**

- **Phase 0 — data flywheel (now, zero new deps, pure DB work):** per-tenant commerce-only dataset export (JSONL, chat format, reusing `_filter_commerce_set` + `is_fallback` filters), dataset digest + row counts in `ft_state`, dry-run "would-train" counts. This is the same invisible-machinery philosophy as st-2. **Benchmark first:** before any training, measure exemplar+glm-4.6 reply quality on held-out Egyptian Arabic threads — if the bar is already met, fine-tuning drops in priority.
- **Phase 1 — CPU pilot (transformers+PEFT, tool #1):** 1–3 mature tenants, base = 0.6–1.7 B Arabic-strong model, rank-16 LoRA, subprocess `ft_runner`, checkpoints on disk + ledger in DB, crash-resume by respawn. Serve A/B locally via llama-server (tool #3) against the glm-4.6 provider.
- **Phase 2 — GPU burst (unsloth, tool #2) + GGUF adapters:** rent a GPU for a night, batch-train the backlog, `save_pretrained_gguf(q4_k_m)` per tenant, drop adapters into llama-server's `--lora` list; `POST /lora-adapters` refresh without restart.
- **Phase 3 — GPU node (vLLM, tool #5):** when traffic justifies a GPU: vLLM + PEFT adapters + dynamic load/unload; llama-server stays as the CPU fallback region.

**Base-model candidates (verify each model card's license before shipping):** Qwen3-family 0.6 B/1.7 B (Apache-2.0 weights, strong Arabic) as the default; Llama-3.2 1 B/3 B (Llama community license, gated); Gemma-2/3 small (gated); Jais-family (Arabic-native, per-model license check); Nile-Chat-3B (Egyptian-dialect, worth a zero-shot benchmark). Small = feasible on our box and on Egyptian-domain data volumes (hundreds, not millions, of chats per tenant — LoRA is exactly the right regime for that).

**Disk/RAM budget on a modest VPS (8 GB RAM / 20–40 GB disk):** base GGUF 1–2 GB + torch env 2 GB (training box only) + N adapters × 10–30 MB + ≤2 checkpoints × ~100 MB per active run + dataset JSONLs (MBs). Comfortably hundreds of tenants.

**What we deliberately do NOT do:** train in the API process (RAM), store weights in SQLite (WAL bloat), fine-tune every tenant regardless of data (noise + disk), use Ollama for multi-tenant adapters (no routing), or build our own trainer loop (all five tools already implement resume — we wrap, not reimplement).
