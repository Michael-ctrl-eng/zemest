# Z3 — AI Core Part 2: Language Engine, Arabizi, Order Collector, Postiz Chat, Style Learner

**Scope:** `app/ai/language.py` (121 LOC), `app/ai/language_engine.py` (320 LOC), `app/ai/arabizi_map.py` (388 LOC), `app/ai/order_collector.py` (102 LOC), `app/ai/postiz_chat.py` (405 LOC), `app/ai/style_learner.py` (489 LOC). Total 1,825 LOC.
**Method:** Full line-by-line read of all 6 files + call-site tracing (`agent.py`, `prompts.py`, `postiz_client.py`, `style_learning.py` API, `style_tasks.py`, `phone.py`, models) + executable simulation of detection/transliteration/order-regex edge cases.
**Mode:** RESEARCH ONLY — no code modified.

---

## 1. Language Detection Engine

### 1.1 `language.py` — legacy shim (121 LOC)

Backward-compatible façade. Delegates to `language_engine` and keeps original signatures `detect_language(text) -> str` and `normalize_arabic(text) -> str` so tests/callers don't break.

**`detect_language(text) -> str`** (language.py:32-47)
- Calls `detect_language_advanced(text)` and returns `detection.legacy_label` (3-class: `'arabic' | 'arabizi' | 'english'`).
- Wraps in `try/except Exception` → last-resort `_regex_detect_language(text)`.

**`normalize_arabic(text) -> str`** (language.py:50-60)
- Calls `normalize_arabic_advanced(text)`; on any exception falls back to `_regex_normalize_arabic`.

**`_regex_detect_language(text) -> str`** (language.py:68-108) — original pure-regex algorithm (fallback only):
1. Count Arabic chars: `[\u0600-\u06FF]`; count Latin `[a-zA-Z]`; `total = ar + lat`.
2. `total == 0` → `"english"` (digits/punctuation/emoji-only text).
3. `arabic_ratio > 0.3` → `"arabic"` (hardcoded 0.3 threshold).
4. Else match ~60 lowercase Arabizi word-regexes (Egyptian pronouns `ana/enta/enti`, `3ayez/3ayza`, `yalla`, `keda`, `mish/mesh/mafish`, `awy`, `bta3*`, `2olly`, `y3ni`, `3lshan`, commerce words `price/cost/order/delivery/instock`…). **Threshold: ≥ 2 distinct pattern hits → `"arabizi"`**, else `"english"`.
- Noteworthy: list contains duplicates (`keda` twice, language.py:85), and two patterns have a leading literal space (`r"\b ya3ni\b"`, `r"\b law 3ayez\b"`, language.py:98) making them effectively start-of-word-after-space matches.

**`_regex_normalize_arabic(text) -> str`** (language.py:111-121):
1. Strip tashkeel/diacritics `[\u0610-\u061A\u064B-\u065F\u0670]`.
2. Alef unification: `إأآا → ا`.
3. Taa marbuta: `ة → ه`.
4. Alef maqsura: `ى → ي`.
- Does **not** strip tatweel (unlike the advanced version) and does not unify Arabic-Indic digits.

### 1.2 `language_engine.py` — multi-dialect engine (320 LOC)

Docstring claims architecture = GlotLID v3 + camel_tools + rule-based Arabizi + code-switching. **Reality: GlotLID and fasttext are never imported/implemented; only camel_tools is optional.** (language_engine.py:1-10 — misleading docstring.)

**`LanguageDetection` dataclass** (language_engine.py:21-45):
- Fields: `primary_language` (arabic|english|arabizi|mixed), `arabic_dialect` (egyptian|gulf|levantine|maghrebi|iraqi|msa|none — docstring omits `sudanese` which `_map_camel_dialect` can return), `english_variant` (us|uk|indian|none — **only ever set to "us"**, :264; uk/indian never detected), `is_code_switched`, `detected_scripts`, `confidence`, `normalized_text`.
- `legacy_label` property (:32-45): collapses `mixed → arabic` (if any dialect) else `english`; other labels pass through. Used by `agent.process_customer_message` (agent.py:101) and the `language.py` shim.

**Module tables:**
- `ARABIZI_MAP` (language_engine.py:52-83): per-dialect char maps for 6 dialects (egyptian, gulf, levantine, maghrebi, iraqi, msa). Egyptian entry: `3→ع, 7→ح, 2→ء, 5→خ, 8→غ, 6→ط, 9→ق, 2→أ` (**duplicate key `"2"` — Python keeps the last, so effective mapping is `2→أ`, contradicting the documented `2=ء`**), plus `3'→غ, 5'→خ, 7'→خ, kh→خ, gh→غ, sh→ش, ch→تش, th→ث, aa→ا, ee→ي, oo→و`.
- `ARABIZI_DIALECT_WORDS` (:86-92): Latin-script dialect markers — egyptian (3ayez, keda, mesh, awy, aiwa, la2…), gulf (abghi, shlon, khallas…), levantine (biddi, shu, keef — with duplicates `3am`/`shu` listed twice), maghrebi (bghit, kifash, wach…), iraqi (shino, wayn…).

**Helper counters:**
- `_count_arabic_chars` (:99-100): `len(re.findall(r"[\u0600-\u06FF]", text))`.
- `_count_latin_chars` (:103-104): `[a-zA-Z]` count.
- `_has_arabizi_digits(text)` (:107-109): `re.search(r"[3782569]", text)` — **any occurrence of digits 2/3/5/6/7/8/9 anywhere** (character class is unordered: 3,7,8,2,5,6,9).

**`_detect_arabizi_dialect(text)`** (:112-122): substring matching (`w in text_lower`) against `ARABIZI_DIALECT_WORDS`; dialect with max hit count wins; **no hits → default "egyptian"**. Substring matching is prone to false hits (e.g., `"ana"` matches inside "banana"; `"eh"` matches inside "the").

**`_detect_arabic_dialect_by_words(text)`** (:125-142): Arabic-script dialect markers per dialect (egyptian: عايز، كده، مش، اوى، ازيك; msa: أريد، ماذا…; iraqi includes چنو/گلت with non-standard chars). Same max-count scoring; **no hits → None** (caller defaults to egyptian). Substring matching again: "مش" matches inside "مشكلة"; "وين" is a substring of "واين" so one word scores both levantine and iraqi (tie → levantine by dict insertion order).

**`transliterate_arabizi(text, dialect="egyptian")`** (:145-158):
- Gets dialect map from engine-local `ARABIZI_MAP` (falls back to egyptian), replaces **longest keys first** (`sorted(..., key=-len)`), plain `str.replace` over the whole text.
- **Case-sensitive** (no lowercasing — "KH"/"Kh" not matched), applies to **all** text including digits inside prices/phone numbers (see §7 risks).
- Docstring admits: "For production use, an LLM fallback (Qwen2.5) should handle ambiguous cases" — **not implemented**.
- Does **not** use the layered maps from `arabizi_map.py` (see §2) — its own docstring in arabizi_map.py:15-16 claims it does ("applies them in order: words → digraphs → digits → letters") which is **false**.

**`detect_code_switching(text) -> list[dict]`** (:161-183):
- Splits text on script boundaries: `re.split(r"([\u0600-\u06FF]+|[a-zA-Z][a-zA-Z0-9' ]*)", text)`; each part classified: pure Arabic run → `arabic`; Latin-initiated run (includes spaces/digits/apostrophes) → `arabizi` if it contains an Arabizi digit else `english`. Non-Latin non-Arabic tokens (digits, emoji) are dropped.
- **DEAD CODE — never called anywhere in the repo** (grep confirms only definition site). Result: per-segment code-switching info is computed nowhere; `is_code_switched` in the main detector is a simple char-count heuristic instead.

**`detect_language_advanced(text) -> LanguageDetection`** (:186-269) — the main entry point:
1. Empty/blank text → `english`, confidence 0.0, no scripts (:192-197).
2. Count arabic/latin chars; `total == 0` (digits/emoji only) → `english`, conf 0.0 (:199-208).
3. `arabic_ratio = ar / total`; `has_arabizi = _has_arabizi_digits(text) and latin_count > 0` (:210-211).
4. `detected_scripts`: `["arabic"]` if ar>0, `["latin"]` if lat>0 (both possible).
5. `is_code_switched = arabic_count > 5 and latin_count > 5` (:219 — hardcoded >5/>/>5 char counts).
6. **Branch cascade (order matters):**
   - `arabic_ratio > 0.3` → **arabic**; dialect = word-based (default egyptian); `confidence = min(0.95, 0.6 + ratio*0.4)` (i.e., 0.72–0.95) (:222-226).
   - `elif has_arabizi` → **arabizi**; dialect via `_detect_arabizi_dialect` (default egyptian); `normalized = transliterate_arabizi(text, dialect)`; **flat confidence 0.75** (:227-231).
   - `elif is_code_switched` → **mixed**; dialect via Arabic word markers (may be None); conf 0.8 (:232-236).
   - `else` → **english**; conf 0.85 (:237-241).
   - **Shadowing bug:** any mixed Arabic+English text that also contains a digit 2/3/5/6/7/8/9 is captured by the arabizi branch before the mixed branch is reached; conversely pure English containing any of those digits is misclassified as arabizi (verified — §7).
7. **camel_tools enhancement (optional)** (:243-259): lazy `DialectIdentifier.pretrained()` cached on the function attribute `detect_language_advanced._did` (module-level singleton; not thread-safe on first init); `did.predict([text])`; `top_dialect` mapped via `_map_camel_dialect`; on hit, dialect is **overridden** and confidence += 0.1 (capped 0.99). `ImportError` → silent pass; other exceptions → debug log. camel_tools prediction runs on **every** call when installed (cost on hot chat path).
8. Returns detection with `english_variant="us"` if primary in (english, mixed) else None (:264).

**`_map_camel_dialect(city)`** (:272-293): maps camel_tools 26-city labels → 6 groups + sudanese + msa (Cairo/Alexandria/Asyout→egyptian; Doha/Dubai/Kuwait/Manama/Muscat/Riyadh→gulf; Aleppo/Beirut/Damascus/Amman/Jerusalem→levantine; Tunis/Rabat/Casablanca/Algiers/Tripoli→maghrebi; Baghdad/Basra/Mosul→iraqi; Khartoum→sudanese; MSA→msa). Unknown city → None (keeps rule-based dialect).

**`normalize_arabic_advanced(text)`** (:296-311): same 4 rules as legacy fallback **plus** tatweel (`ـ`) removal. (Docstring parenthetically claims camel_tools superiority — not actually wired.)

**`detect_language(text)` backward-compat** (:315-320): duplicate of the `legacy_label` collapse logic (mixed→arabic if dialect else english).

### 1.3 Pipeline usage

`agent.process_customer_message` (agent.py:98-122):
- `detection = detect_language_advanced(message_text)`; `lang = detection.legacy_label` → drives `_get_fallback_response` language on LLM failure (arabic / arabizi hybrid-English / english, agent.py:477-484).
- If `primary_language == "arabizi"` → the **transliterated** `normalized_text` replaces the user message sent to the LLM (agent.py:106-112, 149) — "LLMs handle Arabic script far better than Latin Arabizi".
- Prompt dialect selection (agent.py:117-122): english → `"english"`; else detected `arabic_dialect`; else `"egyptian"`. Feeds `get_system_prompt(dialect=...)` → `DIALECT_PERSONA` in prompts.py (8 Arabic dialect personas + english; prompts.py:13-50 — includes sudanese/yemeni personas that the engine can never produce except sudanese-via-camel_tools).
- `style_learner` uses detection for `language_mix` (first 50 messages); `postiz_chat` uses `primary_language` for reply language selection (only `"arabic"` vs everything-else-English — arabizi/mixed users get English replies).

### 1.4 Tests
`tests/test_language.py` (10 detection cases + 4 normalization cases) covers: pure Arabic, Arabic-with-English-word (ratio>0.3), 3 Arabizi cases, 2 English cases, empty, digits-only ("12345"→english because latin_count==0), single-word Arabizi "3ayez price?" (2 patterns→arabizi). **No test covers English containing digits (the false-positive case) or mixed code-switching.**

---

## 2. Arabizi Mapping (`arabizi_map.py`, 388 LOC)

### 2.1 Structure & sizes (counted via AST)

| Table | Entries | Content |
|---|---|---|
| `ARABIZI_MAP` (:28-63) | 4 dialect dicts (egyptian 7, gulf 8, levantine 7, maghrebi 4) | digit/digraph → Arabic: 3→ع, 7→ح, 2→ء, 5→خ, 8→غ, 6→ط, 9→ق; gulf adds `q→ق`; maghrebi only kh/gh/7/9/2/5/8 (French-influenced) |
| `ARABIZI_DIGRAPHS` (:70-86) | 15 | universal multi-char: kh→خ, gh→غ, sh→ش, th→ث, ch→تش, ou→و, oo→و, ee→ي, aa→ا, 2a→أ, 2e→إ, 2o→أ, 3a→عا, 7a→حا, 9a→قا |
| `ARABIZI_LETTERS` (:93-120) | 26 | last-resort single letter: a→ا, b→ب, c→ك, d→د, e→ي, g→ج, h→ه, p→ب, v→ف, x→كس … (explicitly documented as lossy) |
| `ARABIZI_WORDS_SHARED` (:127-231) | 96 | high-precision whole-word lookups: pronouns (ana/enta/ehna…), verbs (3ayez/3andak/3amlt…), greetings (yalla/tayeb/keda/5alas/shukran/ya3ni), negation (mish/mesh/mosh/msh/fish/mafish), commerce (sillar/s3ar/price→سعر, order→طلب, delivery→توصيل, instock→متوفر), question words (kam/leh/ezay/fein), connectors (w/b/l/3la/3lshan/l2n/bs) |
| `ARABIZI_WORDS_EGYPTIAN` (:234-254) | 19 | enta/enta2/enta3, bta3 family, anhy, 2olly/2ol/2ollak, el→ال, 3aba→عباية, galabeya→جلابية |
| `ARABIZI_WORDS_GULF` (:257-282) | 24 | shlonik/shakbar/abhi/tabi/wayed/kidda/chithi/esh/shfeek/na3am/3afwan |
| `ARABIZI_WORDS_LEVANTINE` (:285-312) | 26 | shu/shou/shoo, shi, heek, ktir, halla2, nater, leish, 3am, ken, miish; **includes a profanity entry `sharmuta→شرمطة`** |
| `ARABIZI_WORDS_MAGHREBI` (:315-343) | 26 | wach/bghit/dyali/khouya/chnou/3afak/baraka/safi/bzaf/merci→شكرا (duplicate `wach` key — harmless in dict literal) |

### 2.2 Functions
- **`get_word_map(dialect)`** (:346-366): merges `SHARED` → always applies `EGYPTIAN` base layer → overlays gulf/levantine/maghhrebi if requested; iraqi/sudanese/yemeni/msa → shared+egyptian only. Returns merged dict.
- **`get_dialect_map(dialect)`** (:369-374): returns per-dialect `ARABIZI_MAP` entry, egyptian fallback.

### 2.3 Usage in pipeline: **NONE — the entire module is dead code**
Grep across the repo shows **zero imports** of `app.ai.arabizi_map` (only self-references and its own `__all__`). `language_engine.transliterate_arabizi` uses its own smaller inline `ARABIZI_MAP` and performs **character-level replacement only** — no word-level lookups, no digraph pre-pass per the documented layering, no letter fallback. The module docstring (arabizi_map.py:15-16) explicitly (and incorrectly) claims the engine applies these maps "in order: words → digraphs → digits → letters". Consequence: the pipeline never benefits from the 200+ curated word mappings; transliteration quality is the weak inline version (e.g., `el 3aba` → `el عaba` with Latin `el` left untranslated; "shipping" → "شipping" via the `sh` digraph).

---

## 3. Order Collector (`order_collector.py`, 102 LOC)

Extraction is **LLM-first, regex-parse-after**: the LLM is instructed (via the system prompt, prompts.py order-flow section) to emit a JSON block when an order is complete; this module scrapes/validates it. No rule-based item/qty/price parsing of customer free text exists here — the LLM does that; this file only parses the LLM's output.

**`extract_order_from_response(response_text) -> dict | None`** (:12-40):
1. Look for fenced JSON: ```` ```json\s*(\{.*?\})\s*``` ```` with DOTALL. Non-greedy but backtracks past inner `}` until the closing fence — correctly handles nested `order_data`/`items` objects (verified by simulation).
2. Fallback: unfenced greedy `\{"action":\s*"create_order".*\}` (DOTALL) — matches from the trigger to the **last** `}` in the whole response.
3. `raw = group(1) if json_match.lastindex else group(0)` (fenced has group 1; unfenced has no groups → group 0).
4. `json.loads`; require `data["action"] == "create_order"`; pass `data["order_data"]` to `validate_order_data`.
5. `json.JSONDecodeError`/`KeyError` → warning log, return None.
- **Only the first fenced block is inspected** — if the LLM emits a non-order JSON block first and the order block second, the order is missed (verified). Unfenced path requires the literal `"action": "create_order"` prefix (whitespace-flexible after colon).

**`validate_order_data(data) -> dict | None`** (:43-90):
- Required fields (all truthy): `customer_name, customer_phone, governorate, city, address_detail` — missing → None.
- Phone: `validate_egyptian_phone` (app/utils/phone.py:4-19): strips `\s-()+`, then `^01[0125]\d{8}$` or `^201[0125]\d{8}$` (Egyptian mobile prefixes 010/011/012/015; 8 more digits). Landlines rejected.
- **Dual format support:** new `{"items": [{"product_name", "quantity"}, ...]}` and legacy single `{"product_name", "quantity"}` (converted to 1-element items array). Items must be a non-empty list; each item requires `product_name`; `quantity` defaults to 1 (`setdefault`) — **no type/range validation** (string or negative quantity passes through).
- Defaults: `payment_method="cod"`, `area=""`, `payment_phone_last2=""`, `payment_trx_id=""`.
- **No price field is accepted from the LLM** — pricing is resolved server-side in `agent._create_order_from_data` (agent.py:346-452): product matched via `Product.name.ilike(f"%{product_name}%")` (first active match), `unit_price = attributes.discount_price or price`, unmatched product → unit_price 0; delivery fee via `_calc_delivery` (product-level override → free-delivery threshold → Cairo/Giza inside vs outside); then `create_order` + Celery notification with sync fallback.

**`clean_response_for_customer(response_text) -> str`** (:93-102):
- Strips the fenced JSON block (same non-greedy pattern) and the unfenced trigger-to-last-`}` span (greedy, DOTALL), then `.strip()`. Guarantees the customer never sees the machine-readable action block.

### Confirmation flow / address collection
There is **no explicit state machine or confirmation step** in this module. The address/phone/name collection flow lives in the system prompt (prompts.py "عملية الطلب" section: clarify product+qty first, then request name/phone/governorate/city/area/address in one go, then emit the JSON). Confirmation is implicit: order creation only happens once all required fields validate; `agent.py:174-184` sets `conversation.status="order_placed"` on success and overrides the reply with an Arabic error message if `_create_order_from_data` fails (so the customer isn't told an order succeeded when it didn't).

### Tests
`tests/test_order_collector.py` (7 cases: fenced extraction, missing fields, invalid phone, no-order, cleaning ×2, defaults) + `tests/property/test_order_data_property.py` (hypothesis-style: never-crash invariants, "must not leak the JSON action block" property). Good coverage for the happy path and robustness; no test for multi-item arrays with >1 item or the two-blocks edge case.

---

## 4. Postiz Chat (`postiz_chat.py`, 405 LOC)

**Purpose:** Owner-facing chat (NOT customer-facing) that lets a tenant owner converse with the agent about social-media content: generate post ideas, list connected accounts, best-time-to-post, published-post insights, scheduled-posts list. Delegates to the Postiz sidecar (NestJS scheduler at `POSTIZ_URL`, default `http://localhost:4007`) via `app/scheduling/postiz_client.py`, with fallbacks to Zemest's own LLM and native IG Graph API.

**Entry point: `handle_postiz_chat_request(tenant, user_message, user_id) -> dict`** (:33-71) — `user_id` is accepted but **never used** (dead parameter). Returns `{"reply": str|None, "action": str, "data": dict}`. Flow: `detect_language_advanced` → `_detect_intent` → dispatch to one of 5 handlers; unknown intent returns `reply=None, action="unknown"` signalling the caller should fall back to the normal agent.

**`_detect_intent(message)`** (:74-117): lowercase substring matching against 5 bilingual pattern lists, checked in priority order **generate_post > schedule_post > best_time > insights > list_posts**; first list containing a match wins. Patterns (Arabic MSA-ish + English): e.g., "اكتب بوست"/"write a post"; "جدول بوست"/"schedule a post"; "أفضل وقت"/"best time"; "إحصائيات"/"analytics"/"performance"; "البوستات بتاعتي"/"my posts". **No Arabizi patterns** (Egyptian owners writing "3ayez boist" → unknown intent → handled by the sales agent instead). Substring semantics can misfire ("أداء" matches inside longer words).

**Handlers:**
- **`_handle_generate_post(tenant, message, lang)`** (:124-199): extract topic → try `client.generate_posts(prompt=topic, number_of_posts=3)` (Postiz SSE streaming endpoint `POST /posts/generator`; client collects events named `"result"`). For each result dict, reads `r["content"]` (**assumes event shape has a `content` key — unverified against Postiz API**; strings pass through). If captions found → `_format_generated_posts`. Fallback: own LLM (`chat_completion_with_usage`) with a style hint built from `tenant.style_profile` (`tone`, `emoji_frequency` — correct keys), prompt requests JSON `{"captions": [...]}`, parsed with greedy `\{.*\}` regex. Final fallback: hardcoded Arabic/English apology with 🙏. Note: `topic` (user-controlled) is interpolated raw into the LLM prompt — **prompt-injection surface**.
- **`_handle_schedule_post(tenant, message, lang)`** (:202-243): `client.list_integrations()`; empty → "connect accounts" reply (`action="no_integrations"`); else lists accounts as bullets and asks the owner to say what/when (`action="awaiting_post_details"`). **It never actually schedules anything, and there is no follow-up handler** — the promised conversation ("Tell me what you want to post and when") has no state machine; a subsequent "post X at 5pm" message re-enters `_detect_intent` and won't match any pattern (no "post X at Y" scheduling regex), falling through to the sales agent. The `_format_generated_posts` footer ("Tell me which one you like and I'll schedule it! 📅") promises a flow that is **not implemented**.
- **`_handle_best_time(tenant, lang)`** (:246-287): `client.find_free_slot()` → replies with that slot. **Semantic mismatch:** Postiz find-slot is the next *free calendar slot* (availability), not an engagement-optimal best time. Fallback (only when Postiz raises/returns None): native IG insights `get_best_time_to_post(tenant.ig_access_token, tenant.ig_user_id)` (fields exist on Tenant, tenant.py:28-29), formats top 3 slots with scores.
- **`_handle_insights(tenant, lang)`** (:290-325): `client.list_posts(filter_type="published", limit=10)`; shows first 5 with caption[:50] and `stats.impressions` (**list_posts likely doesn't embed per-post stats — needs get_post_statistics per post; impressions will render "N/A"**). Error → bilingual apology.
- **`_handle_list_posts(tenant, lang)`** (:328-358): `client.list_posts(filter_type="scheduled", limit=10)`; bullets with caption[:60] + scheduled_at[:16].

**Helpers:**
- `_extract_topic(message, lang)` (:365-391): 5 Arabic + 5 English regexes anchored at message start (`اكتب بوست عن (.+)` / `write a post about (.+)`, IGNORECASE); requires the "عن/about" particle; **no match → returns the whole message as topic**. For English lang only English patterns are tried (operator-precedence ternary is correct).
- `_format_generated_posts(captions, lang)` (:394-405): numbered list with bilingual header ("إليك 3 اقتراحات للبوست" / "Here are 3 post ideas") and scheduling-CTA footer.

**Auth gap:** all handlers call `get_postiz_client()` (singleton) **without ensuring login**. The only login call in the app is `app/api/postiz.py:78` (explicit owner-supplied credentials). If the singleton has no/expired token, every Postiz call 401s → handlers report "no connected accounts" / generic errors — misleading UX. Additionally the singleton token is **shared across all tenants** — no per-tenant Postiz auth in this flow (multi-tenancy leakage risk: one tenant's logged-in Postiz account would be used for another tenant's post generation).

**Call site:** only `app/api/test_chat.py:100-140` (`POST /api/test/postiz-chat`, authenticated via `get_current_user`, tenant ownership enforced). Not wired into the Messenger owner-command flow.

---

## 5. Style Learner (`style_learner.py`, 489 LOC)

**Goal:** learn each tenant's (merchant's) communication style from chat history so the sales agent can mirror it. Pipeline: **collect → stratified sample 300 → heuristic features (CPU) → optional LLM deep extraction → merge → persist to `tenant.style_profile` (JSON) + `tenant.knowledge_built_at`**. Constants: `SAMPLE_SIZE=300` ("accuracy plateaus at ~300 messages"), `RECENT_WINDOW_DAYS=30`, `MID_WINDOW_DAYS=90`.

**`collect_merchant_messages(db, tenant_id, limit=100000)`** (:45-68):
- SQL: `select(Message).join(Message.conversation).where(Message.conversation.has(tenant_id=...), Message.role.in_(["assistant","merchant"])).order_by(created_at.desc()).limit(100000)`.
- Captures **both** imported human merchant messages (`role="merchant"`) **and AI agent replies (`role="assistant"`)** — intentional for continuity but introduces **self-reinforcing style drift** (the agent re-learns from its own output).
- Join + `.has()` is redundant (join already constrains); analysis capped at 100k most recent messages regardless of "millions" imported.

**`smart_sample(messages, sample_size=300)`** (:75-134):
- Short-circuit: ≤300 → all.
- Buckets by recency vs `datetime.utcnow()`: recent (<30d), mid (30–90d), old (>90d); tz-aware timestamps normalized to naive.
- Targets: **40% recent / 30% mid / 30% old**; `random.sample` per bucket; shortfall topped up from `[m for m in messages if m not in sampled]` (**O(N×M) identity scan — for 100k messages this is ~30M comparisons**, seconds of CPU) .
- `random.seed(42)` — reproducible but **mutates the global PRNG state for the whole process** (side effect on any other random usage, e.g., token generation elsewhere if reliant on `random`).
- Dedup: first-50-chars-lowercased prefix seen-set; empty-prefix messages always kept; truncated to sample_size.

**`extract_heuristic_features(messages)`** (:141-275) — millisecond-scale CPU feature extraction:
- **Length stats:** avg chars; buckets short <60 / medium 60–160 / long ≥160; pct of each.
- **Emoji:** counts chars with `ord(char) > 0x1F000` — catches most modern emoji but **misses legacy-block emoji (❤ U+2764, ☺ U+263A, ✔, ★) and ZWJ sequences are counted per-codepoint**; inventory top-10; frequency classification: 0→"none", <0.5/msg→"low", <2→"medium", else "high".
- **Language mix:** `detect_language_advanced` on the first 50 contents (bias: most recent, since collected DESC); ratios rounded to 2dp across arabic/arabizi/english/mixed.
- **Greetings:** 16 Arabic (أهلا، السلام عليكم، إزيك، عامل ايه…) + English (hi, hello, good morning…) substring match, **one greeting counted per message** (`break`); top-5.
- **Signoffs:** 15 patterns (شكرا، تسلم، في الخدمة، مع السلامة، thanks, bye, خالص، تمام، تم…) — note `تمام/تم/اوكي` are conversational acks, not just signoffs; top-5.
- **Formality:** formal markers (حضرتك، سيدي، سيدتي، تفضل، أرجو، رجاء) vs casual markers (يا عم، يا صاحبي، بقى، خلاص، يلا، طب) message counts; tone = formal if formal>casual, casual if casual>formal, else friendly; `formality_level` 0–10 via `min(10, 6+formal_count)` / `max(0, 4-casual_count)` / 5 — **saturates instantly** (any merchant with ≥4 formal messages hits 10).
- **Vocabulary:** top-15 words (len>2, tiny 17-word EN/AR stopword list, punctuation-stripped) — will surface product words.
- **Sample replies:** 5 representative messages at fixed length-quantiles (1/6…5/6 of length-sorted list), truncated to 200 chars — few-shot material for prompts.
- Returns 15-key dict (`tone, formality_level, greeting_patterns[], signoff_patterns[], emoji_frequency, emoji_inventory[], avg_response_length, avg_length_chars, language_mix{}, vocabulary[], sample_replies[], message_count_analyzed, short/medium/long_msg_pct`).

**`_empty_features()`** (:278-292): neutral defaults (tone friendly, formality 5, emoji none, language_mix 50/50 ar/en).

**`STYLE_EXTRACTION_PROMPT` + `llm_style_extraction(messages)`** (:299-357):
- Prompt embeds up to **50 messages × 200 chars** (labeled "chronological order, most recent first" — matches DESC collection order), asks for JSON-only with keys: tone, greeting_patterns, signoff_patterns, emoji_frequency, objection_handling, closing_patterns, personality_summary, sales_tactics, response_style — "quote actual phrases", null if undeterminable.
- Calls `chat_completion_with_usage`; parses first `\{.*\}` (greedy DOTALL); any exception → warning + None (graceful degradation to heuristics).

**`build_and_persist_personality(db, tenant, use_llm=True)`** (:364-418) — main entry:
- <6 messages → `_empty_features()` + count (comment: "using defaults").
- Else: sample → heuristics → optional LLM; **LLM values override heuristics key-by-key when non-null/non-empty-list**.
- Adds metadata (`built_at` ISO, `total_messages_available`); `tenant.style_profile = profile`; `tenant.knowledge_built_at = utcnow()`; **`await db.commit()`** (commits the caller's session — API and Celery callers both pass dedicated sessions, OK).
- Callers: `POST /api/tenants/{id}/rebuild-style` (style_learning.py:164, `use_llm` query param), `POST /api/tenants/{id}/import/chat-history` (via import helper), Celery beat weekly `rebuild_all_personalities` + per-tenant `rebuild_tenant_personality` (style_tasks.py:24-74, per-tenant sessions so one failure doesn't roll back others).

**`import_messages_and_build_style(db, tenant, messages, channel)`** (:425-489):
- Groups parser output by `thread_title`; per thread creates a `Conversation(id, tenant_id, customer_id=None, channel, status="imported")`, then one `Message` per dict (`role`, `content`, `channel`, `created_at=timestamp`) with UUIDs; sets `started_at`/`last_message_at` from first/last thread message; `flush` per thread; then `build_and_persist_personality`.
- **`customer_id=None` violates the schema:** `Conversation.customer_id` is `Mapped[uuid.UUID]` (NOT NULL, conversation.py:15) → **IntegrityError on flush** for any non-empty import (Postgres and SQLite alike). The endpoint `POST /api/tenants/{id}/import/chat-history` (style_learning.py:118) is therefore expected to 500 on real uploads; tests never exercise this path (they test `build_and_persist_personality` with pre-made conversations instead).
- `msg_data["role"]`/`["content"]`/`["timestamp"]`/`["thread_title"]` direct indexing — KeyError if parser contract changes.

### How the profile is applied
- **`agent.process_customer_message`** → `get_system_prompt(style_profile=...)` (prompts.py:115-134): reads `tone` ✔, but `greeting_pattern` / `signoff_pattern` (singular) and `emoji_use` (float, compared `> 0.2`) — **keys that `style_learner` never writes** (it writes `greeting_patterns`/`signoff_patterns` lists and `emoji_frequency` string). Net effect: **only `tone` survives into the customer-facing system prompt; greeting/signoff/emoji styling silently defaults** (cross-module contract bug, prompts.py:117-119 vs style_learner.py:262-265).
- `app/api/scheduling.py:232-241` and `app/api/postiz.py:266-267` use the **correct** keys (`greeting_patterns`, `signoff_patterns`, `emoji_frequency`, `language_mix`) — the mismatch is specific to the core sales prompt.
- `postiz_chat.py:161-163` uses correct keys (`tone`, `emoji_frequency`).

---

## 6. Function Inventory

| file | function/class | params | returns | purpose |
|---|---|---|---|---|
| language.py | `detect_language` | `text: str` | `str` ('arabic'\|'arabizi'\|'english') | Legacy 3-class shim → `detect_language_advanced().legacy_label`; regex fallback on exception |
| language.py | `normalize_arabic` | `text: str` | `str` | Shim → `normalize_arabic_advanced`; regex fallback on exception |
| language.py | `_regex_detect_language` | `text: str` | `str` | Original heuristic: arabic ratio >0.3 → arabic; ≥2 of ~60 Arabizi word-regexes → arabizi; else english |
| language.py | `_regex_normalize_arabic` | `text: str` | `str` | Strip tashkeel; unify alef/taa-marbuta/yaa (no tatweel removal) |
| language_engine.py | `LanguageDetection` (dataclass) | `primary_language, arabic_dialect=None, english_variant=None, is_code_switched=False, detected_scripts=[], confidence=0.0, normalized_text=None` | — | Advanced detection result; `legacy_label` property collapses mixed→arabic/english |
| language_engine.py | `_count_arabic_chars` | `text: str` | `int` | Count `[\u0600-\u06FF]` chars |
| language_engine.py | `_count_latin_chars` | `text: str` | `int` | Count `[a-zA-Z]` chars |
| language_engine.py | `_has_arabizi_digits` | `text: str` | `bool` | `[3782569]` present anywhere in text |
| language_engine.py | `_detect_arabizi_dialect` | `text: str` | `Optional[str]` | Substring-score dialect from `ARABIZI_DIALECT_WORDS`; default egyptian |
| language_engine.py | `_detect_arabic_dialect_by_words` | `text: str` | `Optional[str]` | Substring-score dialect from Arabic-script markers; None if no hits |
| language_engine.py | `transliterate_arabizi` | `text: str, dialect="egyptian"` | `str` | Longest-first `str.replace` using inline `ARABIZI_MAP` (digits+digraphs; case-sensitive; no word map) |
| language_engine.py | `detect_code_switching` | `text: str` | `list[dict]` | Split on script boundaries; label segments arabic/arabizi/english — **never called (dead code)** |
| language_engine.py | `detect_language_advanced` | `text: str` | `LanguageDetection` | Main detector: ratio>0.3→arabic; arabizi-digits+latin→arabizi (+transliterate); ar>5∧lat>5→mixed; else english; optional camel_tools dialect override (+0.1 conf) |
| language_engine.py | `_map_camel_dialect` | `city: str` | `Optional[str]` | Map camel_tools 26-city label → 6 groups + sudanese/msa |
| language_engine.py | `normalize_arabic_advanced` | `text: str` | `str` | Tashkeel strip, alef/taa-marbuta/yaa unify, tatweel strip |
| language_engine.py | `detect_language` | `text: str` | `str` | Backward-compat wrapper duplicating `legacy_label` collapse |
| arabizi_map.py | `ARABIZI_MAP` (dict-of-dicts) | — | — | Per-dialect digit/digraph maps (4 dialects) — **unused** |
| arabizi_map.py | `ARABIZI_DIGRAPHS` (dict) | — | — | 15 universal digraph→Arabic mappings — **unused** |
| arabizi_map.py | `ARABIZI_LETTERS` (dict) | — | — | 26 single-letter→Arabic fallbacks — **unused** |
| arabizi_map.py | `ARABIZI_WORDS_SHARED/EGYPTIAN/GULF/LEVANTINE/MAGHREBI` (dicts) | — | — | 96/19/24/26/26 whole-word translation tables — **unused** |
| arabizi_map.py | `get_word_map` | `dialect: str` | `dict[str,str]` | Merge shared+egyptian(+dialect) word maps — **unused** |
| arabizi_map.py | `get_dialect_map` | `dialect: str` | `dict[str,str]` | Per-dialect digit map with egyptian fallback — **unused** |
| order_collector.py | `extract_order_from_response` | `response_text: str` | `dict \| None` | Scrape fenced/unfenced `{"action":"create_order",...}` JSON from LLM reply; validate |
| order_collector.py | `validate_order_data` | `data: dict` | `dict \| None` | Require 5 customer fields + valid Egyptian mobile phone; normalize legacy single-item→items[]; default payment/area/payment fields |
| order_collector.py | `clean_response_for_customer` | `response_text: str` | `str` | Strip order JSON blocks from the reply before sending to customer |
| postiz_chat.py | `handle_postiz_chat_request` | `tenant: Tenant, user_message: str, user_id: str` | `dict{reply,action,data}` | Owner chat router: language detect → intent detect → dispatch; unknown → reply None |
| postiz_chat.py | `_detect_intent` | `message: str` | `str` | Priority-ordered bilingual substring match → generate_post/schedule_post/best_time/insights/list_posts/unknown |
| postiz_chat.py | `_handle_generate_post` | `tenant, message, lang` | `dict` | Topic extraction → Postiz AI `generate_posts` (3 posts) → own-LLM fallback → error message |
| postiz_chat.py | `_handle_schedule_post` | `tenant, message, lang` | `dict` | List Postiz integrations; prompt owner for post details (no actual scheduling; no follow-up state) |
| postiz_chat.py | `_handle_best_time` | `tenant, lang` | `dict` | Postiz `find_free_slot` (next free calendar slot); fallback native IG insights top-3 slots |
| postiz_chat.py | `_handle_insights` | `tenant, lang` | `dict` | Postiz `list_posts(published)` → top-5 with impressions |
| postiz_chat.py | `_handle_list_posts` | `tenant, lang` | `dict` | Postiz `list_posts(scheduled)` → bullets caption+time |
| postiz_chat.py | `_extract_topic` | `message: str, lang: str` | `str` | Regex `اكتب بوست عن (.+)` / `write a post about (.+)`; fallback = whole message |
| postiz_chat.py | `_format_generated_posts` | `captions: list[str], lang: str` | `str` | Numbered bilingual caption list + "I'll schedule it" CTA footer |
| style_learner.py | `collect_merchant_messages` | `db, tenant_id, limit=100000` | `list[Message]` | Fetch outbound (assistant+merchant) messages for tenant, newest first, ≤100k |
| style_learner.py | `smart_sample` | `messages: list[Message], sample_size=300` | `list[Message]` | Stratified 40/30/30 recent(30d)/mid(90d)/old sample; seeded; prefix-50 dedup |
| style_learner.py | `extract_heuristic_features` | `messages: list[Message]` | `dict` | 15-key style profile: tone, formality, greetings, signoffs, emoji, language mix, vocabulary, sample replies, length stats |
| style_learner.py | `_empty_features` | — | `dict` | Neutral default profile |
| style_learner.py | `STYLE_EXTRACTION_PROMPT` (const) | — | — | LLM prompt requesting 9-key deep-style JSON with quoted phrases |
| style_learner.py | `llm_style_extraction` | `messages: list[Message]` | `dict \| None` | LLM deep extraction over ≤50×200-char messages; greedy JSON parse; graceful None |
| style_learner.py | `build_and_persist_personality` | `db, tenant, use_llm=True` | `dict` | Orchestrator: collect→sample→heuristics→(LLM merge)→persist style_profile+knowledge_built_at (commits) |
| style_learner.py | `import_messages_and_build_style` | `db, tenant, messages: list[dict], channel` | `dict{imported, style_profile}` | Import parsed DYI/WhatsApp threads as Conversations+Messages, then build profile (**customer_id=None → NOT NULL violation**) |

---

## 7. Issues / Risks

**CRITICAL**
1. **English text containing digits is misclassified as Arabizi** — language_engine.py:107-109 + 211 + 227-231. `_has_arabizi_digits` matches *any* 2/3/5/6/7/8/9 anywhere; branch order puts arabizi before mixed/english. Verified by simulation: `"I want 2 items please"`, `"size 7 please"`, `"my order 25 dollars total 350"` → all `arabizi` (conf 0.75). Consequences: wrong fallback language (agent.py:477-484), wrong dialect persona, and **the message gets transliterated** (agent.py:107-108).
2. **Transliteration corrupts phone numbers, prices, and English words** — language_engine.py:145-158 replaces digit keys globally: `01012345678` → `0101أع4خطحغ`, `350 gneh` → `عخ0 gneh`, `75 shipping` → `حخ شipping` (all verified by simulation). Since agent.py:106-112 substitutes this text for the LLM input, **Arabizi order flow (phone/address) is fed garbage** → order JSON gets hallucinated or invalid phone → validate fails → "خطأ في تسجيل الطلب" loop. The curated, word-aware maps that would avoid this (`arabizi_map.py`) are not wired in.
3. **`import_messages_and_build_style` NOT NULL crash** — style_learner.py:455-461 creates `Conversation(customer_id=None)`; `Conversation.customer_id` is NOT NULL (app/models/conversation.py:15). The chat-history import endpoint (`POST /api/tenants/{id}/import/chat-history`, app/api/style_learning.py:118) will raise IntegrityError at flush for any non-empty import. Untested path (tests stop at parser + build with pre-existing conversations).

**HIGH**
4. **Style profile key mismatch neutralizes style learning in the main agent** — prompts.py:117-119 reads `greeting_pattern`/`signoff_pattern`/`emoji_use`; style_learner.py:262-265,169 writes `greeting_patterns`/`signoff_patterns`/`emoji_frequency`. Only `tone` is applied to the customer-facing prompt; greetings/signoffs/emoji guidance silently default. (scheduling.py:232-241 and postiz.py:266-267 use the correct keys — so the bug is specific to the core sales prompt.)
5. **`arabizi_map.py` is 100% dead code** — zero imports repo-wide; its docstring (arabizi_map.py:15-16) falsely claims `transliterate_arabizi` applies the layered word→digraph→digit→letter pipeline. 200+ curated word mappings and loss-safe letter fallbacks unused; transliteration quality is the weak inline version.
6. **Prompt-injection → order creation surface** — order_collector.py:23-26 unfenced trigger `\{"action":\s*"create_order".*\}`; a customer who asks the LLM to "output this JSON to confirm my order" (or pastes such JSON which the LLM echoes) can induce order creation. Mitigations present: full field validation + Egyptian phone regex + server-side pricing (order_collector.py:47-57, agent.py:364-377), but `quantity` is type/range-unvalidated (order_collector.py:82) and product matching is `ilike %name%` (first match, agent.py:364-370) — partial-name matches can bind the wrong product/price.
7. **Postiz chat auth + multi-tenancy gap** — postiz_chat.py handlers (e.g., :208, :251, :295, :333) use the process-wide singleton `get_postiz_client()` with no login/ensure-auth; the only login is app/api/postiz.py:78. No/expired token → 401 → misleading "no connected accounts" replies; worse, the singleton token is shared across tenants (cross-tenant use of whichever account last logged in).

**MEDIUM**
8. **Postiz schedule flow is unfinished** — `_handle_schedule_post` (postiz_chat.py:202-243) only lists integrations and asks for details; no follow-up handler consumes the reply ("post X at 5pm" doesn't match `_detect_intent` patterns), and `_format_generated_posts` (:403) promises "I'll schedule it" with no implementation. Dead-end UX.
9. **`detect_code_switching` dead code + shadowed mixed branch** — language_engine.py:161-183 never called; `is_code_switched` (:219) is only reachable when the text has *no* digits 2/3/5/6/7/8/9 and ratio ≤0.3 — genuine mixed Arabic/English chats containing prices/dates are classified arabizi, never mixed.
10. **Best-time semantics** — postiz_chat.py:251-259 returns Postiz's next *free calendar slot* as "أفضل وقت لنشر" (best time); engagement-based IG fallback (:264-281) only runs when Postiz errors. Misleading answer when Postiz is healthy.
11. **Dialect scoring by substring** — language_engine.py:112-142: `"ana"` in "banana", `"eh"` in "the", `"مش"` in "مشكلة", `"وين"` inside "واين" (double-count levantine+iraqi, tie broken by dict order). Dialect misattribution risk is low-impact (persona selection) but real for Gulf/Levantine customers.
12. **Style drift via self-learning** — collect_merchant_messages (style_learner.py:58-67) includes `role="assistant"` (AI's own replies); weekly Celery rebuild (style_tasks.py:24-30) re-learns increasingly from the agent's own output — feedback loop with no decay/guardrail.

**LOW**
13. Duplicate key `"2"` in engine `ARABIZI_MAP` egyptian (language_engine.py:54-55) — effective `2→أ`, documented `2=ء`.
14. Misleading docstrings: GlotLID/fasttext never used (language_engine.py:1-9, language.py:8-9); `english_variant` uk/indian never produced (language_engine.py:26,264); camel_tools "more advanced normalization" not wired (:299); arabizi_map.py layering claim (see #5).
15. `smart_sample` performance/side effects — `random.seed(42)` global mutation (style_learner.py:111); O(N×M) top-up scan `[m for m in messages if m not in sampled]` (:120-121).
16. Emoji detection misses pre-0x1F000 block emoji (❤, ☺, ✔, ★) — style_learner.py:163-166; formality_level saturates at 0/10 with ≥4 marker hits (:220-225).
17. Order extraction inspects only the first fenced JSON block (order_collector.py:15-26); `generate_posts` result shape assumption `r["content"]` unverified against the Postiz API (postiz_chat.py:141); `list_posts` "stats.impressions" likely always "N/A" (:303); `user_id` param unused (:33-37); `_detect_intent` has no Arabizi patterns (:79-99) — Egyptian owners writing Arabizi commands fall through to the sales agent.
18. `tests/test_language.py` lacks cases for English-with-digits and code-switched text — the highest-risk detection paths are untested; `datetime.utcnow()` deprecation used throughout style_learner.

---

## 8. Quality Ratings

| File | Rating | Justification |
|---|---|---|
| `language.py` | **7/10** | Clean, well-documented shim with true last-resort fallbacks; keeps legacy API/tests working. Deducted for duplicated/gappy pattern list (dup `keda`, leading-space patterns) and being mostly pass-through. |
| `language_engine.py` | **5/10** | Good breadth ambition (6+ dialects, optional camel_tools, graceful degradation) and a sensible dataclass API — but the core heuristic has a **verified critical false positive** (any English text with digits 2/3/5/6/7/8/9 → arabizi + destructive transliteration), dead `detect_code_switching`, duplicate dict key, substring dialect scoring, and docstrings promising GlotLID/fasttext that don't exist. The transliteration fed into the LLM can corrupt phone/price data in the flagship Arabizi use case. |
| `arabizi_map.py` | **6/10** | Well-organized, layered, sensibly curated (96 shared + 95 dialect-specific words, digraphs, letter fallbacks, documented conventions, pure-dict zero-deps). But it is **entirely unused** and its docstring mis-describes integration — high-value code rotting at 0% coverage in the pipeline. |
| `order_collector.py` | **7.5/10** | Small, focused, single-responsibility; dual-format order support, strict required-field + Egyptian phone validation, server-side pricing (no LLM price trust), cleanup invariant covered by property tests. Deducted for first-block-only extraction, unvalidated quantity types, and the unfenced-trigger injection surface. |
| `postiz_chat.py` | **5/10** | Nice bilingual owner UX and layered fallbacks (Postiz → own LLM → canned error), correct style-profile keys. But the schedule flow is a dead end, best-time answers conflate availability with engagement, Postiz auth is never ensured, the singleton client leaks across tenants, several Postiz response-shape assumptions are unverified, and `user_id` is dead. |
| `style_learner.py` | **7/10** | Thoughtful design: recency-stratified sampling with documented rationale, fast CPU heuristics merged with optional LLM extraction, graceful degradation, per-tenant Celery isolation, decent tests. Deducted for the NOT NULL import crash (untested path), downstream key mismatch that nullifies most learned features in the main prompt, self-drift via assistant messages, global `random.seed`, and emoji/formality heuristic weaknesses. |

**Overall AI-core-2 verdict:** solid product thinking (Arabizi-first Egyptian UX, style mirroring, LLM-order-scrape with server-side validation), but three pipeline-integrity defects — the digit→arabizi false positive, digit-corrupting transliteration, and the style-profile key mismatch — mean the flagship features underperform their design, and one (chat-history import) is expected to crash in production.
