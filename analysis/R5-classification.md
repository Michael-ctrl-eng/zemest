# R5 — Text Classification & Language/Dialect ID Library Research

**Agent:** R5 (github-research) · **Mode:** research only, zero code changes
**Date:** 2026-09 · **API calls used:** 16/25 (GitHub search only; core budget was exhausted by other agents — cross-checked via raw.githubusercontent.com, PyPI, HuggingFace, ReadTheDocs, plus *live micro-benchmarks in the actual repo venv*)

## Grounding: what zemest has today

| File | Current state |
|---|---|
| `repos/zemest/app/ai/chat_classifier.py` | "cc-2": pure-CPU Egyptian-commerce regex/lexicon scorer → commerce/junk/mixed + explainable signals. No learning — weights are hand-tuned. |
| `repos/zemest/app/ai/silent_trainer.py` | "st-2": 45s loop, per-tenant checkpointed DISCOVER→CLASSIFY→EXTRACT→CONSOLIDATE. **Re-trains on every new batch of chats** → any ML model must be cheap to re-train (seconds) or support true online updates. |
| `repos/zemest/app/ai/language_engine.py` | Multi-dialect engine. Already *documents* GlotLID v3 (layer 1, optional), `camel_tools.DialectIdentifier` (layer 2, optional), rule-based Arabizi map, code-switch detection. Graceful regex fallback. |
| `repos/zemest/requirements.txt` | `camel-tools>=1.5.0`, `fasttext-wheel>=0.2.5` — **optional, and camel-tools is NOT installed** in the live venv (regex fallback active). |

**Live venv facts (measured, not assumed):** Python 3.12, `fasttext-wheel 0.9.2` + `fasttext_pybind`, `numpy 2.1.3`, `scikit-learn 1.9.0`, `onnxruntime 1.29.0` already installed; camel_tools / lingua / langdetect / setfit / sentence_transformers NOT installed.

**Live benchmark (1500 Egyptian-commerce vs junk messages built from the real cc-2 lexicons, incl. Arabizi):**
- fastText `train_supervised` (1500 docs × 10 epochs, wordNgrams=2) = **0.73 s**; predict = **0.002 ms/message** (low-level `m.f.predict` API)
- sklearn `HashingVectorizer(char_wb 2–4)` + `SGDClassifier.partial_fit` ×10 = **0.02 s**; predict incl. vectorization = **0.27 ms/msg**; **single-message online update = 0.81 ms**
- fastText default `bucket=2M` → **780 MB** model file; `bucket=100k, dim=50` → **19.5 MB** (must tune!)
- ⚠️ **REAL BUG FOUND:** installed `fasttext-wheel 0.9.2`'s Python wrapper `model.predict()` **crashes with numpy 2.1.3** (`ValueError: Unable to avoid copy while creating an array…` — the known numpy-2 ABI break). Workarounds: swap to `fasttext-numpy2-wheel` (GlotLID's own recommendation) or call the low-level pybind API `m.f.predict(text, k, threshold, "strict")` which returns Python lists, no numpy. Also `model.quantize()` **segfaults** in this pybind build (observed twice) → train small (bucket/dim) instead of post-hoc quantization.

---

## TOP 5 (ranked)

### #1 — fastText + wheel packages ⭐ RECOMMENDED PRIMARY CLASSIFIER
- **Repos:** https://github.com/facebookresearch/fastText (★26,534, last push 2024-03-22 — frozen/mature), wheels: https://github.com/messense/fasttext-wheel (★28, MIT, cp312 manylinux wheels ✓) and `fasttext-numpy2-wheel` 0.9.2 (PyPI, cp310–cp312 ✓, numpy-2-safe build)
- **License:** code MIT (commercial ✓). LID models CC-BY-SA 3.0 (lid.176.bin 126 MB / **lid.176.ftz 917 KB**). ⚠️ NLLB `lid218e.bin` is **CC-BY-NC** — do not use commercially.
- **Model size / latency:** 2-class supervised model ≈ **19.5 MB** with sane params (measured); inference **~2 µs/message** — 3–5 orders of magnitude below our per-message LLM budget. Training: **0.73 s per 1.5k messages × 10 epochs** — fits the 45 s trainer cycle with room to spare.
- **Incremental training:** no per-example online update in the Python API, but **full retrain is so cheap it doesn't matter** for our corpus sizes (per-tenant: hundreds–low-thousands of chats → <1 s). True streaming is delegated to pick #2.
- **Arabic/Egyptian quality:** char n-gram hashing → **works on raw Arabic with no tokenizer, no preprocessing, and on Latin-script Arabizi unchanged** ("el tshrt 3ndk blon a7mar" classified correctly in benchmark once trained on mixed-script data). Character-level features are exactly why fastText has historically won Arabic dialect-ID shared tasks.
- **Integration sketch:**
  - `requirements.txt`: `fasttext-wheel>=0.2.5` → **`fasttext-numpy2-wheel>=0.9.2`** (numpy-2 fix, keeps cp312 wheels).
  - `app/ai/chat_classifier.py`: keep cc-2 lexicon as stage-1 (explainability + cold start); add stage-2 learned model: `predict = model.f.predict(normalized_text, 1, 0.0, "strict")`; when both agree → high confidence; disagreement → "mixed"/review bucket. New constant `CLASSIFIER_VERSION = "cc-3"`.
  - `app/ai/silent_trainer.py`: each epoch appends `(text, cc-2-label-or-owner-correction)` rows to `data/models/{tenant_id}/train.txt`, retrains (sub-second), atomic save `classifier.ft` + version/holdout-accuracy into `tenant.training_state` (existing JSON). One **global model** (all tenants) seeds cold-start pages; per-tenant model takes over as its own data accumulates.
  - `app/ai/language_engine.py`: optional `lid.176.ftz` (917 KB) as sentence LID fallback when GlotLID isn't downloaded.
- **Verdict:** ★★★★★ ADOPT. Dormant repo is a feature (stable C++ core, 26k★, 8 years of production use). The measured 0.73 s retrain + 2 µs inference is a perfect match for silent_trainer's hot loop; already half-integrated (optional pin exists, package installed).

### #2 — scikit-learn (HashingVectorizer + SGDClassifier) ⭐ TRUE ONLINE-LEARNING BASELINE
- **Repo:** https://github.com/scikit-learn/scikit-learn (★67,113, last push 2026-08-31, very active; v1.9.0, BSD-3-Clause)
- **Model size / latency:** model = **KBs** (a sparse coefficient vector); measured **0.27 ms/msg** predict (incl. char-ngram hashing) and **0.81 ms single-message online update**. `partial_fit` over 1500 docs = 0.02 s.
- **Incremental training:** ✅ **genuine streaming** via `SGDClassifier.partial_fit` / `PassiveAggressiveClassifier` — the only top-5 tool where each newly-classified chat updates the model *immediately* (matches "trainer re-trains on new chats" literally, even between 45 s cycles).
- **Arabic quality:** `HashingVectorizer(analyzer="char_wb", ngram_range=(2,4))` mirrors fastText's feature space; script-agnostic, Arabizi needs nothing special. Predictions are well-calibrated with `loss="log_loss"` (`predict_proba` → confidence 0..1 fits the existing `Classification.confidence` field).
- **Integration sketch:** same files as #1 — the learned stage can be *either* fastText or an SGD model behind one `predict(text)->(label, prob)` interface. `app/ai/silent_trainer.py` calls `partial_fit` on each newly labelled conversation; serialize with `joblib` to `data/models/{tenant_id}/classifier.joblib`. Explainability: top n-gram coefficients per class → reuse the `signals` list format.
- **Verdict:** ★★★★★ ADOPT (already installed — literally zero new dependencies). Recommended as the *default* learned stage; fastText as the cross-check/global model.

### #3 — GlotLID v3 (fastText LID, 2102 labels incl. Egyptian Arabic + Arabizi)
- **Repo:** https://github.com/cisnlp/GlotLID (★215, last push 2026-04-15, EMNLP 2023; model on HF `cis-lmu/glotlid`)
- **License:** Apache-2.0 **plus an additional notice** about training-data provenance (read LICENSE before shipping; commercial use is permitted with notices).
- **Model size / latency:** `model.bin` (v3) = **1.69 GB** (HF-verified) — heavy for our 1-VPS box; inference is fastText-speed (~0.01 ms/sentence). **ONNX alternative:** [TigreGotico/linguonnx](https://github.com/TigreGotico/linguonnx) (Apache-2.0, new/0★, push 2026-08-25) serves GlotLID as **int8 ONNX = 425 MB**, torch-free, with `collapse_varieties=True` convenience and `detect_raw()` → `arz_Arab`-style labels.
- **Incremental training:** n/a — inference-only LID (that's fine; it replaces heuristics, not the learner).
- **Arabic/Egyptian quality — the killer feature:** v3 has explicit labels `arz_Arab` (**Egyptian Arabic, F≈0.897 on 196k sentences**), `arb_Arab` (MSA, F≈0.845), `arb_Latn` (**Latin-script Arabic = Arabizi**, small data), `apc_Arab` (Levantine), `arq/ary` (Algerian/Moroccan). This gives `language_engine.py` exactly the sentence-level LID + dialect grouping it already sketches in its own docstring, including code-switch detection (mixed arz_Arab/eng_Latn sentences).
- **Integration sketch:** `app/ai/language_engine.py` layer 1: `hf_hub_download("cis-lmu/glotlid", "model_v3.bin")` (or linguonnx int8 when RAM-constrained) → per-sentence predict → map `{arz→egyptian, apc→levantine, arb_Latn→arabizi, eng_Latn→english}`; aggregate per conversation into the existing `LanguageDetection` dataclass. Gate with `GLOTLID_ENABLED` + memory check; existing regex fallback stays.
- **Verdict:** ★★★★½ ADOPT for the language engine. Only risk = 1.7 GB RAM (use int8/ONNX or lid.176.ftz fallback); already designed-for in our code comments.

### #4 — camel-tools (CAMeL) DialectIdentifier — 26-city Arabic dialect ID
- **Repo:** https://github.com/CAMeL-Lab/camel_tools (★576, last push 2026-06-08, MIT; PyPI **1.6.0 requires Python ≥3.11 — works with our 3.12** ✓; ⚠️ DID component not available on Windows — we're Linux/Docker, fine)
- **Model size / latency:** DID data package `dialectid-model26` = **261.8 MB** (`model6` = 122 MB; sizes from the official camel-tools-data catalogue); 4 pretrained `.dill` models + 52 char/word n-gram LMs. Latency: n-gram LM ensemble — ms-scale per sentence (fine for the trainer's EXTRACT phase; too heavy for per-webhook-message use).
- **Incremental training:** ✅ unusual for this list — `DIDModel26`/`DIDModel6` expose a public `train()` API (we'd never need it; MADAR data suffices).
- **Arabic/Egyptian quality:** 25 city dialects + MSA (Salameh/Bouamor/Habash MADAR system). **CAI (Cairo) + ALX (Alexandria) labels = Egyptian** — exactly the 26→6 mapping `language_engine.py::_map_camel_dialect` already implements (the code path exists and is waiting for the install). Bonus: MSA normalizer + sentiment component for preprocessing/junk signals.
- **Integration sketch:** literally `pip install camel-tools==1.6.0` + `camel_data install did` (it's *already optional in requirements.txt* and *already imported in language_engine.py:245*). Only real work: CI/Docker image size (+262 MB) and Linux-only note.
- **Verdict:** ★★★★ ADOPT as the EXTRACT-phase dialect oracle (thread-level Egyptian verification that feeds the buyer persona, already 94% "egyptian" via heuristics today). Skip if image size is sacred.

### #5 — SetFit (few-shot classification for cold-start pages)
- **Repo:** https://github.com/huggingface/setfit (★2,788, last push 2026-05-26, Apache-2.0; PyPI 1.1.3)
- **Model size / latency:** backbone `intfloat/multilingual-e5-small` or `paraphrase-multilingual-MiniLM-L12-v2` ≈ 118M params (~470 MB fp32, ~120 MB int8 ONNX); CPU inference ~10–30 ms/msg (~5–10 ms via ONNX int8). **Training: minutes on CPU** — NOT for the 45 s loop.
- **Incremental training:** ❌ refit-only (but few-shot: 8–16 labelled examples/class → strong from tiny data — matches Task-19's "new pages with few messages must still understand buyers" requirement).
- **Arabic quality:** multilingual backbones handle Arabic + Arabizi reasonably (e5 covers 100+ languages); not dialect-aware.
- **Integration sketch:** `app/ai/silent_trainer.py` cold-start branch only: when a tenant has <25 labelled chats, use the existing optional LLM deep-extract (z-ai glm-4.6, already provider #1 in `llm_client.py`) to label ~20 seed conversations → train a SetFit model in a Celery/ARQ job → serve via ONNX int8 (`huggingface/optimum` ★3,474 Apache-2.0) with `onnxruntime 1.29.0` **already in the venv**. Hand off to sklearn/fastText once ≥100 real labels exist.
- **Verdict:** ★★★½ SELECTIVE — only if cold-start accuracy of the 2-class filter proves insufficient with lexicon+LLM bootstrap; adds torch to the dependency tree otherwise.

---

## Also-rans (researched, ranked out — with reasons)

| Tool | Repo / stars / push / license | Why not top-5 |
|---|---|---|
| simpletransformers | ThilinaRajapakse/simpletransformers, ★4,253, 2026-05-31, Apache-2.0 | Full BERT fine-tuning wrapper: torch+transformers (~1 GB+ deps), no online training, minutes-per-retrain on CPU, overkill for 2-class spam filtering; SetFit dominates it in the few-shot regime. |
| spaCy v3 textcategorizer | explosion/spaCy, ★33,863, 2026-08-24, MIT (v3.8.16) | `textcat` has no incremental training (full retrain per update), **no official Arabic pipeline in core** (only third-party models), pipeline overhead per message; sklearn+fastText deliver the same linear-classifier quality at 1/10 the moving parts. Great lib, wrong shape for this job. |
| lingua-py | pemistahl/lingua-py, ★1,788, 2026-07-20, Apache-2.0 (v2.2.0) | Best-in-class *short-text* LID incl. Arabic, but **800 MB–3 GB memory** (repo itself 303 MB), no dialect granularity (Arabic = one language), slower than fastText. GlotLID+camel cover Arabic better at a fraction of the footprint. |
| langdetect (+forks) | Mimino666/langdetect ★1,903, 2025-03-03, license NOASSERTION (unverified port) | Weak on <50-char messages (our exact input), non-deterministic (needs random seed), no Arabic dialects, murky license file. Forks that wrap fastText instead — **LlmKira/fast-langdetect** ★320 MIT (2026-05-25; offline lite model, 45–60 MB RSS, no numpy, py3.9–3.14) and zafercavdar/fasttext-langdetect ★173 MIT — are nice packaging but redundant once we load `lid.176.ftz` (917 KB) directly. |
| Arabic-DID academic repos | swshon/arabic-dialect-identification ★55 MIT (stale: 2019); UBC-NLP/aoc_id ★24 (2019); qcri/QADI ★7 (**no license** — dataset, 18 country labels incl. EG); elyadata/ADI-20 ★7 (2026); Lafifi-24 (BERT, 2023) | These are *training data / paper code*, not maintained libraries. Value: QADI/NADI/MADAR tweets = ready-made labelled Egyptian-dialect corpora if we ever train our **own** fastText dialect model. Not shippable as deps. |
| ONNX Runtime (as a "classifier") | microsoft/onnxruntime ★21,687, 2026-09-01, MIT; v1.29.0 **already in venv** | Not a classifier — the *deployment layer*: GlotLID int8 (linguonnx), SetFit embedders via optimum (huggingface/optimum ★3,474 Apache-2.0). Zero new dependency to use it; folded into picks #3/#5. |
| Zero-shot via small LLM | (no repo — uses existing z-ai glm-4.6 in `app/ai/llm_client.py`; HF `bart-large-mnli` is English-centric) | Seconds-per-message latency and per-message cost — wrong for the hot loop, **right for one-shot bootstrap**: label 20–50 ambiguous "mixed" conversations per cold-start tenant, then let sklearn/fastText take over. Already wired; no new dep. |

## Recommended architecture (hybrid, matches silent_trainer's design)

```
per message (webhook path, <1 ms):   cc-2 lexicon (unchanged)  ─┐
per 45 s trainer epoch (seconds):    sklearn SGD.partial_fit + fastText retrain (0.73 s/1.5k)
                                       labels: cc-2 + owner corrections + optional z-ai LLM bootstrap
EXTRACT phase (thread-level):        GlotLID v3 sentence LID (arz/arb/arb_Latn/eng) + camel DIDModel26 (CAI/ALX)
cold start (<25 labelled chats):     LLM bootstrap labels → SetFit (optional) → handoff at 100 labels
```

**Phasing:** (1) numpy-2 wheel fix + sklearn learned stage — ~½ day, zero new deps, fixes a *live* crash vector; (2) fastText global+per-tenant models — ~1 day; (3) GlotLID int8 wiring in language_engine — hours (RAM-gated); (4) camel-tools install (image +262 MB) — trivial, code already present; (5) SetFit only if measured cold-start accuracy demands it.

**Cross-cutting caveats:** fastText LID models are CC-BY-SA (code MIT); GlotLID Apache-2.0-with-notice — both commercial-safe, attribute properly. Avoid NLLB `lid218e.bin` (CC-BY-NC). fastText default `bucket=2M` → 780 MB models — always pass `bucket≈100k, dim=50` for MB-size classifiers. `quantize()` segfaults in the current pybind build.
