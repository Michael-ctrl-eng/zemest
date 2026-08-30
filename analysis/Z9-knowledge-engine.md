# Z9 — Knowledge Engine Deep Analysis (app/knowledge/)

**Scope:** `crawler.py` (474L), `indexer.py` (247L), `product_extractor.py` (285L), `retriever.py` (217L), `tree_sync.py` (207L), `__init__.py` (0L) — 1,430 LOC total.
**Method:** line-by-line read of all 6 files + call-site tracing (`crawl.py`, `crawl_tasks.py`, `agent.py`, `products.py`, `product_service.py`, `prompts.py`, `llm_client.py`, models, migrations) + filesystem/git verification of the `lib/pageindex` dependency + executable simulation of two suspected retriever bugs (both confirmed).

---

## 0. Executive Summary — the headline finding

**The "PageIndex" RAG architecture is dead code in practice.** `indexer.py:25-27` prepends `../../lib/pageindex` to `sys.path` and `indexer.py:146` does `from pageindex.page_index_md import md_to_tree` — **but `lib/pageindex` does not exist anywhere in the repo** (verified: not on disk, not in `git ls-files`, no `pageindex` match in any file). The import raises `ModuleNotFoundError`, is swallowed by `except Exception` (indexer.py:181), and the **fallback `_build_simple_tree()` runs on 100% of crawls**. Consequences:

- No LLM-generated summaries, no hierarchy, no node `_type` markers from crawled content.
- The `_UsageCollector`/litellm token-accounting machinery (indexer.py:33-60, 134-195) never captures anything — every crawl logs a `TokenUsage` row of 0 tokens.
- The retriever's TOC (which is designed around summaries and `[P]`/`[K]` type tags) degrades to bare page titles.
- The entire "LLM builds hierarchical tree → LLM navigates TOC → zero-cost retrieval" story in the module docstrings and MASTER_PROMPT.md:141-143 describes an aspirational design, not the shipped behavior. What actually ships: **flat list of ≤30 page blobs → LLM picks 3 by title → first 500 chars of each into the system prompt**.

Second headline: **retrieval is agentic-lexical, not embeddings.** There are zero embeddings anywhere (no pgvector, no sentence-transformers, no embedding API calls — grep-verified). pg_trgm exists but is used only for *product dedup* in `product_service.py:63-93`, not retrieval. The "retriever" is one LLM call per customer message that reads a text TOC and returns node IDs.

---

## 1. Crawler (`crawler.py`, 474L)

### Architecture
Two-path strategy chosen by a homepage probe:

```
crawl_website(url, depth=2, max_pages=30)
  ├─ _quick_fetch(url)                     # httpx probe, 30s timeout, follow redirects
  │    └─ trafilatura.extract(homepage_html) # if <50 chars of text → "JS/Cloudflare site"
  ├─ probe OK  → _crawl_with_httpx(url, depth, max_pages)   # fast path
  └─ probe FAIL→ _crawl_with_playwright(url, depth, max_pages) # browser path
```

- **`crawl_website(url, depth=2, max_pages=30)`** (crawler.py:32-59) — entry point. Defaults depth=2/max=30, but callers pass depth=3 (`CrawlRequest.depth: int = 3`, schemas/webhook.py:35) with **no upper bound validation anywhere** (crawler.py:32 accepts any int; API does not clamp).
- **`_quick_fetch(url)`** (62-75) — single httpx GET with spoofed Chrome-131 headers (`BROWSER_UA`, crawler.py:16-29). Success = status 200 **and** `len(resp.text) > 500`. Any exception → `None` → Playwright path. This is the SSRF gate — there is none: no scheme allowlist, no private-IP block, no DNS-resolution check.
- **`_crawl_with_httpx(url, depth, max_pages)`** (78-109) — URL *discovery* phase, then fetch phase:
  1. Runs Katana and manual discovery **concurrently** (`asyncio.gather`, line 83-86).
  2. Union of both URL sets; if empty, falls back to `{url}`.
  3. **`sorted(all_urls)[:max_pages]`** (line 98) — pages selected for crawling in *alphabetical URL order*, not relevance/priority. `/about` beats `/products` alphabetically.
  4. Sequential `_fetch_and_extract` per URL (103-106).
- **`_crawl_with_playwright(url, depth, max_pages)`** (112-175) — **BFS level-order crawl**: `for current_depth in range(depth + 1)` with a `to_visit` frontier and `next_level` accumulation (depth=3 ⇒ 4 levels). One Chromium instance, one context (UA spoof + `locale="en-US"` + 1920×1080 viewport, lines 128-132), pages opened/closed sequentially. Domain scoping for *discovered links* is exact `netloc == base_domain` string equality (159-164) — `www.x.com` ≠ `x.com`, subdomains excluded, and **redirect targets are NOT re-scoped** (`follow_redirects=True` in httpx means an open-redirect on the seed URL silently re-homes the crawl onto another domain).
- **`_playwright_fetch_page(context, url)`** (178-273) — per-page pipeline:
  1. `page.goto(url, wait_until="domcontentloaded", timeout=45000)`.
  2. Fixed `wait_for_timeout(3000)` render wait.
  3. **Popup dismissal** (188-200): clicks first visible match of `button:has-text('Accept'/'OK'/'Close')`, `[class*='cookie'] button`, `[class*='popup'] button` — blind clicking of consent dialogs (legally dubious for crawling, functionally helpful).
  4. **Lazy-load trigger**: `window.scrollTo(0, document.body.scrollHeight / 2)` + 1.5s wait (203-204) — scrolls only *half* the page height once; infinite-scroll/lazy content below the fold is never triggered.
  5. `page.content()` → link harvest via `document.querySelectorAll('a[href]')` filtered to `http*` (209-213).
  6. Text extraction: trafilatura first (`include_comments=False, include_tables=True`), then a BeautifulSoup fallback that decomposes script/style/noscript/svg/path and dedups lines >10 chars (224-235).
  7. `_sanitize_text` → title via `<title>` → static-asset link filtering → returns `{"title", "content": text[:5000], "links": clean_links[:100]}`.
  8. Rejection thresholds: html <200 chars, text <50 chars → None.
- **`_discover_urls_katana(url, depth, max_pages)`** (278-329) — shells out to **Docker**: `docker run --rm projectdiscovery/katana -u <url> -d <depth> -silent -fs fqdn -rl 10 -timeout 60` with spoofed UA headers. 180s `asyncio.wait_for` on `communicate()`. Parses stdout lines starting with `http`, filters static extensions, caps at max_pages. Notes: (a) requires the app container to have the **Docker socket** — root-equivalent privilege; (b) first run pulls the image (minutes, uncapped); (c) on timeout the katana process is **never killed** (`wait_for` cancels the await, not the subprocess) → orphaned container; (d) `-rl 10` rate-limits to 10 req/s — for 180s that's up to ~1,800 requests to a third-party site = **crawl-storm surface** when depth is attacker-controlled.
- **`_discover_urls_manual(url, depth, max_pages)`** (332-351) — same BFS as Playwright path but with httpx: `_find_links` per page, frontier capped per level. Exact-netloc scoping, scheme http/https only.
- **`_sanitize_text(text)`** (354-406) — 15 regex passes: strip residual HTML tags/entities, JS/CSS patterns (`{...:...}`, `function(...)`, `var/const/let x =`, `=>`, `console.`, `document.`, `window.`), URLs, file paths, hex colors, base64 images; collapse whitespace; then line filtering: drop lines <5 chars, drop lines >20 chars with alpha-ratio <0.3 (with an explicit Arabic-letter regex `[\u0621-\u064A\u0660-\u0669]`, line 389 — partially redundant since Python `str.isalpha()` already returns True for Arabic letters, but the range also counts Arabic-Indic digits ٠-٩ as "letters", slightly inflating alpha-ratio), drop lines containing `copyright/all rights reserved/powered by/loading.../please wait` (English boilerplate only — Arabic equivalents like "جميع الحقوق محفوظة" pass through).
- **`_find_links(page_url, base_domain)`** (409-432) — httpx GET + BS4 `find_all("a", href=True)`, `urljoin` to absolute, exact-netloc + scheme filter, query-string-stripped normalization (`f"{scheme}://{netloc}{path}"`), static-ext skip, cap 50 links/page.
- **`_fetch_and_extract(url)`** (435-474) — per-page fetch for the fast path: new AsyncClient **per URL** (no pooling), content-type must be html/xhtml, html ≥100 chars, trafilatura with `favor_precision=True`, text ≥30 chars pre- and post-sanitize. **No length cap** on the returned content (unlike the Playwright path's `[:5000]`) — a huge page yields a huge blob.

### Politeness / robots / dedup / recovery — scorecard
| Concern | Status |
|---|---|
| robots.txt | **Absent entirely** (grep-verified: zero "robots" mentions in `app/`) |
| Rate limiting / delay between requests | httpx path: **none** (sequential but zero sleep); Playwright path: implicit ~5s/page of fixed waits; Katana: `-rl 10` only |
| Cross-page content dedup | **None** — same nav/footer text re-extracted on every page (trafilatura mitigates partially) |
| URL dedup | Yes — `visited` sets + query-string stripping + asset-ext filters |
| Error recovery | Per-page try/except → skip page; whole-crawl try/except → empty list; caller marks job "failed" if 0 pages |
| Redirect safety | `follow_redirects=True` with no cross-domain re-check |
| JS rendering | Playwright fallback only (no stealth plugin; UA + locale + viewport spoofing only; headless Chromium detectable) |
| Concurrency | Fully sequential (one page at a time) — no crawl storm from concurrency, but 30 JS pages × ~5s waits ≈ 2.5–24 min/crawl |

### Full crawl pipeline (as orchestrated by `crawl.py:78-134` / `crawl_tasks.py:27-83`)
1. `POST /api/tenants/{id}/crawl` → CrawlJob row (status pending) → Celery `.delay()` if a worker pings OK, else BackgroundTasks in the **API process**.
2. status=crawling → `crawl_website(url, depth)` → ≤30 pages `[{"url","title","content"}]`.
3. status=indexing → `build_knowledge_index(db, tenant_id, pages)` (indexer).
4. LLM product extraction from page text (crawl.py:137-229 / crawl_tasks.py:86-171) → `create_product` per item → each triggers `rebuild_product_tree` (tree_sync).
5. status=completed, `pages_found`/`products_extracted` set.

---

## 2. Indexer (`indexer.py`, 247L)

- **`_UsageCollector`** (33-60) — callable injected as a global `litellm.success_callback`; sums prompt/completion tokens across all LiteLLM calls during one `md_to_tree` run. **Global mutable state**: two concurrent tenant crawls in one process would cross-contaminate (and clobber each other's callback lists at indexer.py:141 and 191). Dead in practice (PageIndex missing ⇒ zero LLM calls).
- **`_get_pageindex_model()`** (63-72) — returns `openrouter/{settings.OPENROUTER_MODEL}` (default `meta-llama/llama-4-maverick:free`, config.py:28) and stuffs the API key into `os.environ["OPENROUTER_API_KEY"]` — a process-global side effect from a "getter".
- **`_pages_to_markdown(pages)`** (75-100) — every page becomes `# {title}` (or `# {url}`) + `Source: {url}` + raw content, joined with blank lines. **This is the entire chunking strategy**: no chunk sizing, no overlap, no per-page splitting — the whole site is one markdown document fed to `md_to_tree`.
- **`build_knowledge_index(db, tenant_id, pages)`** (103-228) — the only public function:
  1. Empty pages / empty markdown → return None (silent).
  2. Markdown → temp file (`delete=False`, unlinked in `finally` — correct cleanup).
  3. Register litellm callback → import PageIndex → **always fails** → fallback.
  4. `md_to_tree(md_path, if_thinning=False, if_add_node_summary="yes", summary_token_threshold=200, model=..., if_add_doc_description="no", if_add_node_text="yes", if_add_node_id="yes")` — intended: LLM-thresholded summaries per node.
  5. Persist `TokenUsage(usage_type="knowledge")` row (always 0/0/0 today).
  6. **Upsert**: `SELECT KnowledgeBase WHERE tenant_id` (tenant_id is UNIQUE, one KB per tenant) → if exists, **wholesale replace** `tree_json`, `source_documents`, `last_indexed_at`; else insert. `db.flush()`, no commit (caller commits).
- **`_build_simple_tree(pages)`** (231-247) — the *actual* always-used tree builder: one node per page `{"title", "node_id": "0001"..., "text": content[:2000], "line_num"}` — flat list, no summaries, no `_type`, no children, no dedup. 2000-char node cap means long pages are silently truncated at indexing time.

### Storage schema
`knowledge_bases` (migration 5179285ae0ae): `id UUID PK`, `tenant_id UUID UNIQUE FK`, `tree_json JSON` (**`json`, not `jsonb`** — no GIN indexing possible, whole-row rewrite on every update), `source_documents JSON`, `last_indexed_at`, timestamps. The entire knowledge base is **one JSON blob per tenant**.

### Incremental updates / deletion handling
**None.** Every re-crawl is a full replace: previous knowledge nodes are discarded (no diffing, no versioning, no soft-delete). Deleted site pages simply vanish. Worse, the replace also **wipes product nodes** inserted by `tree_sync` (they live in the same `tree_json`); they are only re-created afterwards because step 4 of the pipeline runs product extraction → `create_product` → `rebuild_product_tree`. If product extraction fails or returns 0 items (LLM error, non-e-commerce site), **a re-crawl leaves the tree with zero product nodes** even though products still exist in the `products` table — retrieval then can't see any products until the next manual product CRUD.

---

## 3. Product Extractor (`product_extractor.py`, 285L)

Called only from `POST /products/import-url` (products.py:102-144, takes a raw `dict` body with no URL validation — same SSRF surface as the crawler).

- **`extract_product_from_url(url)`** (29-65) — escalation ladder, cheapest first; a method "wins" only if it yields a **price** (name alone is insufficient for the first three methods):
  1. `_try_jsonld` → 2. `_try_og_tags` → 3. `_try_html_regex` → 4. `_try_llm_extraction`. httpx fetch first; if None, a **full Chromium launch** for one page (`_fetch_with_playwright`, networkidle+2s wait, new browser per call).
- **`_fetch_page(url)`** (68-85) — httpx GET, status 200 + html/xhtml content-type, returns full HTML.
- **`_fetch_with_playwright(url)`** (88-106) — fresh `chromium.launch` per URL (no browser reuse, ~300MB per invocation), `wait_until="networkidle"`, 20s timeout, rejects HTML <500 chars.
- **`_try_jsonld(soup, url)`** (109-140) — parses every `<script type="application/ld+json">` (list or single), matches `@type == "Product"` (**exact match only** — `["@type": ["Product","Thing"]]` arrays are missed). Takes first match. Reads `offers.price` (first offer if list), strips commas, `float()`. Availability string mapped to `in_stock/out_of_stock/unknown`. Returns name/price/description[:500]/image/stock/url/brand (dict or scalar handled)/sku. **Ignores `priceCurrency`** — a USD/GBP price is imported as EGP verbatim.
- **`_try_og_tags(soup, url)`** (143-181) — requires `product:price:amount` meta; float, rejects ≤0. Name from `og:title`, else `<title>` split on `|`/`–` (note: the regex path also splits on `-`, this one doesn't). Stock from `product:availability` keyword matching ("in stock"/"out of stock"/"sold out").
- **`_try_html_regex(soup, url)`** (184-245) — Egyptian-market price regexes: `(?:EGP|E£|ج\.م)\s*([\d,]+\.?\d*)` then reversed order; filters values <10 ("not real prices" — rejects legit ≤9.99 items); **takes `valid_prices[0]`** — on a *category listing page* the first price on the page is paired with the page's `<title>`/`<h1>` → fabricated product (wrong name-price pairing). Name from title split `|`/`–`/`-`, fallback `<h1>`. Stock from bilingual keyword lists (EN + Egyptian Arabic: "مش متوفر", "نفد", "أضف للسلة", "اطلب دلوقتي", "اشتري الآن"). Image from `og:image`.
- **`_try_llm_extraction(soup, url)`** (248-285) — strips script/style/etc., first **2000 chars** of page text, prompt asks for `{"name","price","description","stock_status"}` JSON, `temperature=0.0, max_tokens=200` via the shared `chat_completion` (with its paid-model fallback chain). Parse via greedy `re.search(r"\{.*\}", re.DOTALL)`. **Prompt-injection surface**: page text goes into the prompt verbatim; a hostile page can dictate the returned "product" (name/price) which is then stored and later served to customers by the agent. No price sanity bounds, no confidence score.
- **Confidence scoring: none.** Trust is purely the ladder order (JSON-LD most trusted → LLM least). No provenance field records which method produced a product.

### The *other* product extractor (in the crawl pipeline)
`crawl.py:137-229` / `crawl_tasks.py:86-171` do NOT use `product_extractor.py` at all — they run a **bulk LLM extraction** over the joined page text: `pages[:20]`, 2000 chars each, then **the whole prompt truncated to `all_content[:6000]`** (crawl.py:165) — i.e. only ~3 pages' worth of a 30-page crawl actually reach the LLM; products beyond the cut are silently lost. One `chat_completion` call, `temperature=0.1, max_tokens=3000`, greedy `\[.*\]` regex parse. Each parsed item → `create_product` (which runs a pg_trgm similarity>0.7 duplicate check and a **full tree rebuild per product** — see §8).

---

## 4. Retriever (`retriever.py`, 217L)

**This is not a search index — it is one LLM call per customer message.**

- **`retrieve_context(db, tenant_id, query, max_nodes=3)`** (24-97) — the entry point called on **every** agent turn (agent.py:93-95):
  1. Load the tenant's single `KnowledgeBase` row; missing → `("","")`.
  2. Extract `structure` from `tree_json` (pageindex shape, plus legacy `"children"` fallback — vestigial format support).
  3. `_build_toc(structure)` → compact text TOC.
  4. `_select_nodes(toc, query, max_nodes)` → LLM returns node IDs.
  5. Persist `TokenUsage(usage_type="retrieval")` — **one DB row per customer message, unbounded growth**.
  6. **Child expansion** (85-92): if a selected node has children, all child IDs are added to the set ("if a category is selected, include all its products").
  7. `_extract_content(structure, expanded_ids)` → `(products_text, knowledge_text)`.
- **`_select_nodes(toc, query, max_nodes)`** (100-140) — prompt: "Pick the most relevant sections… Return ONLY a JSON array… e.g. ["0001","0005","0003"]", `temperature=0.0, max_tokens=50` via `chat_completion_with_usage` (primary `llama-4-maverick:free`, fallbacks include **paid** `gemini-2.0-flash-001` and `qwen-2.5-72b-instruct` — every customer message risks falling back to a paid model just for node selection). Parse: first `\[.*?\]` via regex → `json.loads` → int IDs are `zfill(4)`-padded but **string IDs are not** (line 134) — an LLM answering `["1","5"]` produces IDs that match nothing → silently empty context. Any parse error discards the token accounting (`return [], None`, line 140).
- **`_build_toc(nodes, indent=0)`** (143-166) — recursive indented text: `[P]`/`[K]` tag from `_type` containing "product", `[{node_id}] {title} — {summary[:100]}`. **Bug (cosmetic):** `lines.append(_build_toc(children, indent+1))` (line 164) appends the child block as one already-joined string — with 2-space indent it produces misaligned/nested-but-flattened output rather than proper line-by-line indentation; if children yield nothing, an empty line is appended.
- **`_flatten_all(nodes)`** (169-177) — preorder flatten keeping child references (used only for the expansion step).
- **`_extract_content(nodes, selected_ids)`** (180-217) — recursive traversal splitting selected nodes into product vs. knowledge buckets:
  - category node (`children and "product" in ntype`) → append **all children's texts**;
  - product leaf → append its text;
  - else knowledge → `"## {title}\n{text}"` truncated to **500 chars**;
  - children always traversed (line 211-213).
  - **CONFIRMED BUG (simulated): double-counting.** Because `retrieve_context` pre-expands selected category IDs with their children's IDs (lines 85-92), a selected category causes every child product to be appended **twice** — once by the category branch (199-203) and once by the child's own `nid in target_set` hit (204-205). Simulation with a 2-product category returned each product text 2×. For a 20-product selected category, `products_context` contains 40 product blocks — duplicated prompt tokens and doubled context.
  - Products are joined with `\n\n---\n\n`, knowledge with `\n\n`.
- **Context assembly into the prompt** (prompts.py:94-96, 157-159): `products_context` is dropped verbatim into the `## المنتجات` section of the Arabic system prompt; `knowledge_context` into `## معلومات الصفحة` with the instruction "use for policy/shipping/price questions". No escaping/sanitization of tree content against prompt injection (Z2 already flagged this as the second-order injection vector).
- **Language handling:** none explicit — the bet is that a multilingual LLM matches an Arabic/Arabizi query against (mostly English) TOC titles. The raw customer message is passed (before the Arabizi transliteration damage Z3 found in the agent path — actually good). There is **no lexical fallback**: if the LLM selection fails/returns garbage, both contexts are `""` and the agent answers with an empty products section — even though pg_trgm and a fully-written lexical ranker (`product_service.search_relevant_products`, with Egyptian-Arabic/Arabizi stopword lists) exist **and are never called by anything** (grep-verified: zero callers).

### Retrieval quality tradeoffs (Arabic/Arabizi)
- TOC entries are page `<title>`s / LLM product names — typically English or transliterated on Egyptian e-commerce sites. Free-tier Llama-4-Maverick is decent at Arabic→English semantic matching, so Arabic queries usually work; **Arabizi** ("3ayz as3ar el 3asal") relies entirely on the LLM's dialect competence — no transliteration/normalization layer exists in the retrieval path.
- A crawl of an **Arabic-content site** produces Arabic node text; the TOC then is Arabic titles — fine for Arabic queries, but the 500-char knowledge cap and 2000-char simple-tree cap bite harder in Arabic (Arabic text is denser per token for some models).
- No synonym expansion, no typo tolerance beyond the LLM's own, no re-ranking — single-shot selection of ≤3 IDs from a TOC that (today) has no summaries, i.e. the LLM matches on titles alone.

---

## 5. Tree Sync (`tree_sync.py`, 207L)

Maintains the "business catalog" half of the tree; docstring (lines 6-21) documents the intended shape: root → `[Products]` (category → product leaves) + `[Knowledge]` (crawl pages).

- **`rebuild_product_tree(db, tenant_id)`** (35-83) — public entry, called by `product_service._sync_product_tree` after **every** create/update/soft-delete (product_service.py:41, 140, 150) — and therefore **N times inside one crawl's product-insert loop**. Loads all active products (ordered by name), builds nodes, then either merges into the existing KB or creates a KB with only products. `flush()` only. Failures are swallowed by the caller (product_service.py:361-363) — a failing sync never blocks a product write (good resilience, silent drift risk).
- **`_build_product_nodes(products)`** (86-158) — groups products by `attributes.category` (default "Other"); per product builds a markdown-ish text block: `# name`, optional `Arabic: {name_ar}`, `Price: {p.price} EGP`, optional `Discount Price`, `Stock: {icon} {status}` (✅/❌/⚠️/📦), optional description, **`PRODUCT LINK (share with customer): {url}`** (explicitly encourages the agent to send it), then all remaining attributes as `k: v` lines. Child node: `{title: "name — price EGP icon", node_id (zfill 4), text, line_num, summary: "name, price EGP, stock. desc[:100]", _product_id, _type: "product"}`. Category node: `title: "Cat (N products)"`, summary = first-5 product names, `_type: "product_category"`, children. **Node IDs assigned sequentially during build — then immediately reassigned by `_reassign_ids` in the merge (redundant double-assignment).**
- **`_merge_into_tree(kb, product_nodes)`** (161-194) — the "diffing" mechanism: there is **no diff** — it partitions the existing top-level structure into `knowledge_nodes` (anything whose `_type` is not product/product_category) and discards product nodes, then concatenates `product_nodes + knowledge_nodes` and reassigns all IDs sequentially (depth-first). Updates `metadata.products_count` and `last_product_sync`. **Two hazards:** (a) product nodes are identified only by top-level `_type` — any non-top-level or legacy-format product data is silently classified as "knowledge"; (b) the whole `tree_json` is rewritten per call (JSON column, whole-row update).
- **`_reassign_ids(nodes, start=1)`** (197-207) — depth-first sequential renumbering of `node_id`/`line_num`. **ID instability:** every product CRUD renumbers *every* node in the tree, including knowledge nodes — harmless because retrieval re-reads the tree each message, but it means node IDs can never be used as stable references (e.g., for caching or analytics).

**Race condition:** `rebuild_product_tree` is a read-modify-write of the KB row with no `SELECT … FOR UPDATE` / optimistic version — two concurrent product writes for the same tenant (or a product write racing a crawl's `build_knowledge_index` full-replace) lose updates silently.

---

## 6. RAG Quality Assessment

**Is it true RAG?** No. It is *agentic retrieval over a title index*:
- No embeddings (grep-verified: zero pgvector/sentence-transformers/embedding-API usage in the entire backend).
- No vector store — the "index" is a JSON blob of markdown-ish nodes.
- No BM25/FTS either — PostgreSQL full-text search is never used.
- pg_trgm exists (init.sql, migration a89fe0001:50-53,193-198) but is used only for product dedup — and with a query (`similarity(name, :name)`, product_service.py:68) that **cannot use the GIN index** built on `lower(name)` (a89fe0001:198) → sequential scan per candidate insert.

**Effective retrieval pipeline per customer message:** load full KB JSON → build text TOC → 1 LLM call (max_nodes=3) → expand children → extract texts (products full, knowledge capped 500 chars) → splice into system prompt. Recall depends entirely on one ≤50-token completion from a free-tier model.

**Tradeoffs of this design:**
- *Strengths:* genuinely cheap per call at small scale (TOC of ~10 nodes ≈ a few hundred tokens); multilingual by construction (the LLM does cross-lingual matching); handles synonym/typo queries as well as the underlying model does; product tree is always exactly in sync with the DB (rebuilt on every write).
- *Weaknesses:* (1) TOC grows linearly with catalog size — the "~50-100 tokens" docstring claim (retriever.py:9,35) is false beyond toy catalogs; 50 products ≈ 2-4K-token TOC on **every message**; (2) single-point LLM failure = zero context, no fallback; (3) title-only matching today (no summaries exist — PageIndex dead); (4) max 3 nodes + child expansion can balloon products_context unboundedly (a 100-product category selected → 100 product texts, doubled by the double-count bug); (5) Arabizi queries rely purely on the free model's dialect ability; (6) latency: +1 LLM roundtrip (up to 4 model attempts with 1s sleeps) added to every reply.

**Chunk sizing / overlap:** none in the classic sense. Effective chunks: per-page trafilatura text → `[:5000]` (Playwright path) or uncapped (httpx) → `[:2000]` per tree node (indexer) → `[:500]` per knowledge node at retrieval (retriever.py:208). Hard truncation at every stage with **no sliding window, no overlap, no sentence-boundary respect** — a policy paragraph spanning char 480-700 of a node is cut mid-sentence at 500. Products escape truncation (full text) which is the correct priority, but knowledge is squeezed to ~1.5K chars total (3×500).

**Verdict:** for the target market (small Egyptian shops, <100 products, few policy pages), the design is *workable* but is currently degraded to its worst case (no summaries, double-counted products, no fallback). For anything larger it scales poorly in both cost (TOC per message) and recall (3 nodes).

---

## 7. Function Inventory

| file | function | params | returns | purpose |
|---|---|---|---|---|
| crawler.py | `crawl_website` | `url: str, depth=2, max_pages=30` | `list[dict]` (url/title/content) | Entry point; probe site → pick httpx or Playwright path |
| crawler.py | `_quick_fetch` | `url: str` | `str \| None` | Single httpx GET probe; HTML>500 chars & 200 OK |
| crawler.py | `_crawl_with_httpx` | `url, depth, max_pages` | `list[dict]` | Fast path: gather Katana+manual URLs, sorted, fetch each |
| crawler.py | `_crawl_with_playwright` | `url, depth, max_pages` | `list[dict]` | BFS level-order browser crawl, same-domain links only |
| crawler.py | `_playwright_fetch_page` | `context, url` | `dict \| None` (title/content[:5000]/links[:100]) | One page: goto, popup dismissal, half-scroll, extract, sanitize |
| crawler.py | `_discover_urls_katana` | `url, depth, max_pages` | `list[str]` | `docker run projectdiscovery/katana` URL discovery (fqdn scope, rl 10) |
| crawler.py | `_discover_urls_manual` | `url, depth, max_pages` | `list[str]` | BFS link discovery with httpx+BS4, exact netloc scope |
| crawler.py | `_sanitize_text` | `text: str` | `str` | 15 regex strips (HTML/JS/URLs/colors) + line filters (len, alpha-ratio, boilerplate) |
| crawler.py | `_find_links` | `page_url, base_domain` | `list[str]` | Same-domain absolute links from a page, query-stripped, ≤50 |
| crawler.py | `_fetch_and_extract` | `url: str` | `dict \| None` | httpx fetch + trafilatura (favor_precision) + sanitize; no length cap |
| indexer.py | `_UsageCollector.__init__` | – | – | Zero token counters + model name |
| indexer.py | `_UsageCollector.__call__` | `kwargs, completion_response, start_time, end_time` | None | LiteLLM success callback; accumulate token usage |
| indexer.py | `_get_pageindex_model` | – | `str` | `openrouter/{OPENROUTER_MODEL}`; sets os.environ key |
| indexer.py | `_pages_to_markdown` | `pages: list[dict]` | `str` | Pages → one big markdown doc (# title / Source: url / content) |
| indexer.py | `build_knowledge_index` | `db, tenant_id, pages` | `KnowledgeBase \| None` | PageIndex tree build (dead) → simple tree fallback → upsert KB row |
| indexer.py | `_build_simple_tree` | `pages: list[dict]` | `dict` (doc_name/line_count/structure) | Flat tree: node/page, content[:2000] — the real builder |
| product_extractor.py | `extract_product_from_url` | `url: str` | `dict \| None` | Ladder: JSON-LD → OG → regex → LLM; requires price |
| product_extractor.py | `_fetch_page` | `url: str` | `str \| None` | httpx GET, html content-type check |
| product_extractor.py | `_fetch_with_playwright` | `url: str` | `str \| None` | Fresh Chromium, networkidle+2s, HTML>500 |
| product_extractor.py | `_try_jsonld` | `soup, url` | `dict \| None` | `@type=="Product"` JSON-LD; price/availability/brand/sku; ignores currency |
| product_extractor.py | `_try_og_tags` | `soup, url` | `dict \| None` | `product:price:amount` OG meta; title fallback splits `\|`/`–` |
| product_extractor.py | `_try_html_regex` | `soup, url` | `dict \| None` | EGP/E£/ج.م regex; first price ≥10; title/h1 name; bilingual stock keywords |
| product_extractor.py | `_try_llm_extraction` | `soup, url` | `dict \| None` | 2000-char text → LLM JSON; injection surface |
| retriever.py | `retrieve_context` | `db, tenant_id, query, max_nodes=3` | `tuple[str, str]` (products_ctx, knowledge_ctx) | Load KB → TOC → LLM node pick → expand children → extract |
| retriever.py | `_select_nodes` | `toc, query, max_nodes` | `tuple[list[str], dict \| None]` | LLM returns JSON array of node IDs; regex+json parse; zfill ints only |
| retriever.py | `_build_toc` | `nodes, indent=0` | `str` | Indented TOC lines: `[P]/[K] [id] title — summary[:100]` |
| retriever.py | `_flatten_all` | `nodes` | `list[dict]` | Preorder flatten w/ children intact |
| retriever.py | `_extract_content` | `nodes, selected_ids` | `tuple[str, str]` | Split selected nodes into product/knowledge text; knowledge[:500]; double-count bug |
| tree_sync.py | `rebuild_product_tree` | `db, tenant_id` | `None` | Rebuild product section from products table; merge or create KB |
| tree_sync.py | `_build_product_nodes` | `products: list[Product]` | `list[dict]` | Category grouping; markdown-ish product text; `_type: product(_category)` |
| tree_sync.py | `_merge_into_tree` | `kb, product_nodes` | `None` | Keep non-product top-level nodes, prepend new product nodes, rewrite storage |
| tree_sync.py | `_reassign_ids` | `nodes, start=1` | `int` | Depth-first sequential node_id/line_num renumbering |
| __init__.py | — | — | — | Empty file; no package exports |

---

## 8. Issues / Risks (prioritized, with file:line)

**CRITICAL**
1. **PageIndex library missing → flagship indexer is dead code; every KB is the flat fallback.** indexer.py:25-27,146,181-184 — verified absent from repo & git. Docstrings/prompts advertise summaries + hierarchy that never exist. Downgrade of the entire RAG quality story.
2. **SSRF / local file read via crawl + import-url.** No scheme/host/IP validation anywhere: crawler.py:32,62-75 (httpx probe), 182 (`page.goto` accepts `file:///etc/passwd` after httpx rejects the scheme — exactly the file:// surface prior analysis found), 285-296 (Katana via Docker can scan internal networks, `-u` attacker-controlled); products.py:113-120 + product_extractor.py:29-39 same ladder. Playwright also renders internal/metadata endpoints (169.254.169.254) that httpx-layer network policies might otherwise express.
3. **Docker socket dependency for Katana = root-equivalent privilege in the app container.** crawler.py:280-298 — `docker run` requires socket mount; any RCE in the app is instantly host-root. Orphaned katana process on timeout (no `process.kill()` after `wait_for` cancellation, crawler.py:303-326).

**HIGH**
4. **Products double-counted in retrieval context (simulated & confirmed).** retriever.py:85-92 (child expansion) + 199-205 (category branch + child self-hit) → every product under a selected category appears twice in `products_context`; prompt bloat + doubled context.
5. **Re-crawl wipes product nodes when extraction yields 0 products.** indexer.py:214-216 wholesale `tree_json` replace + pipeline order (crawl.py:115-121): products only survive because extraction re-creates them; LLM failure/hiccup → tree has knowledge only; agent temporarily "forgets" the whole catalog.
6. **No retrieval fallback; dead lexical ranker.** retriever.py:137-140 — any LLM/parse failure → `("","")`; meanwhile `product_service.search_relevant_products` (with Arabic/Arabizi stopwords, pg_trgm-adjacent scoring) has **zero callers**. Single LLM point of failure on every customer message, plus paid-model fallbacks (llm_client.py:18-22) billed per message.
7. **Node-ID format mismatch silently nullifies retrieval.** retriever.py:134 — ints are zfill(4)-padded, strings aren't; an LLM returning `["1","5"]` matches nothing → empty context with no error.
8. **Unbounded prompt injection surface into the system prompt.** crawler.py `_sanitize_text` strips code, not instructions; retriever.py:180-217 returns raw node text; prompts.py:157-159 splices it into the system prompt verbatim (compounds Z2's finding).
9. **Crawl-storm / abuse of third parties.** No robots.txt (grep-verified), no politeness delay on the httpx path (crawler.py:103-106), Katana `-rl 10` for up to 180s ≈ 1,800 reqs (crawler.py:285-303), unbounded `depth` from the API (schemas/webhook.py:35 → crawl.py → crawler.py:32; max_pages=30 caps pages but not Katana's traversal). Blind "Accept" button clicking (crawler.py:188-200) is a consent/legal gray zone.

**MEDIUM**
10. **Index bloat / write amplification.** `tree_json` is `json` (not `jsonb`) — whole-row rewrite per product CRUD via tree_sync (tree_sync.py:193); the crawl loop triggers a **full tree rebuild per inserted product** (product_service.py:41 ← crawl.py:214): N products = N full KB rewrites; plus one `TokenUsage` row per customer message (retriever.py:66-80) — unbounded table growth.
11. **Concurrent-write races on the KB row.** tree_sync.py:161-194 and indexer.py:199-227 are unlocked read-modify-write cycles on the same row; concurrent product writes / crawl+write lose updates silently.
12. **Product-extraction prompt truncation.** crawl.py:147-165 / crawl_tasks.py:94-118 — 20 pages × 2000 chars joined then `[:6000]` → ~85% of crawled content never reaches the LLM; products silently missed.
13. **Wrong name-price pairing on listing pages.** product_extractor.py:208 (`valid_prices[0]`) + title/h1 name → fabricated products from category pages; ≥10 filter rejects sub-10-EGP items and accepts e.g. shipping fees.
14. **Currency blindness.** product_extractor.py:121-123 ignores `priceCurrency`; USD prices stored as EGP (Egyptian-market assumption baked in).
15. **Global litellm callback clobbering + cross-tenant usage attribution.** indexer.py:140-142,186-195 — process-global `success_callback` replace/restore; concurrent crawls misattribute tokens (dormant while PageIndex is missing).
16. **Duplicate-product GIN index unusable by its query.** a89fe0001:198 indexes `lower(name)` but product_service.py:68 calls `similarity(name, …)` → seq scan per insert on large catalogs.

**LOW**
17. `_build_toc` appends child block as a single joined string (retriever.py:164) — malformed indentation; empty lines for childless parents.
18. Half-page-only scroll for lazy loading (crawler.py:203); `locale="en-US"` may force English variants of Arabic sites (crawler.py:130).
19. Alphabetical page selection (`sorted(all_urls)`, crawler.py:98) — arbitrary 30-page sample.
20. Redirect re-homing: `follow_redirects=True` without re-checking the target domain (crawler.py:67,413,440).
21. Content caps inconsistent: 5000 (Playwright) vs uncapped (httpx) vs 2000 (node) vs 500 (retrieval) — silent truncation at every hop, no sentence-boundary logic.
22. Zero test coverage for all five modules (tests/test_crawl.py only exercises mocked API endpoints; no crawler/indexer/retriever/tree_sync/extractor unit tests).
23. `__init__.py` empty — no package surface; callers reach into submodules (fine, but no re-exports/versioning).

---

## 9. Quality Ratings

| File | Rating | Justification |
|---|---|---|
| `crawler.py` | **6/10** | Thoughtful dual-path strategy (probe → fast/browser), good UA/header hygiene, asset filtering, per-page error isolation; but no robots/politeness, SSRF-wide-open, Docker-socket dependency, orphaned subprocess on timeout, alphabetic page selection, no stealth, inconsistent caps. Solid prototype, not production-hardened. |
| `indexer.py` | **3/10** | The core dependency (`lib/pageindex`) **does not exist** — the module's entire reason (LLM tree + summaries) is unreachable and silently degrades on every run; wholesale replace semantics wipe product nodes; global litellm state mutation; correct temp-file cleanup and token-audit trail intent are the only redeeming parts. |
| `product_extractor.py` | **6.5/10** | Clean escalation ladder, genuine Egyptian-market awareness (EGP/E£/ج.م, bilingual stock keywords), zero-LLM-first cost discipline; but first-price-wins mispairing on listing pages, no currency check, no confidence/provenance, per-URL Chromium launch, injection surface in the LLM step, and it is bypassed by the actual crawl pipeline (duplicated logic in crawl.py). |
| `retriever.py` | **4.5/10** | Genuinely clever *idea* (TOC navigation, child expansion, product/knowledge split, token accounting) undermined by: confirmed double-count bug, zfill format mismatch, no fallback when the LLM fails, docstring cost claims that don't scale, 500-char knowledge truncation, one unthrottled LLM call (with paid fallbacks) per customer message. |
| `tree_sync.py` | **6.5/10** | The most correct file: deterministic, zero-LLM, rich product text with explicit shareable link, safe failure isolation at the caller; but no diffing (full rewrite per CRUD), ID instability, unlocked read-modify-write race, and N-rebuilds-per-crawl write amplification. |
| `__init__.py` | **n/a (—)** | Empty; nothing to rate. |

**Overall knowledge engine: 4.5/10.** The architecture (crawl → tree → LLM-navigated retrieval → tree_sync for live catalog) is a coherent, cost-conscious design well matched to the small-tenant Egyptian market — but its centerpiece is missing (PageIndex), its retrieval path has two confirmed correctness bugs, it has no failure fallback, and the security posture (SSRF, docker socket, injection) is unshippable as-is. Fixing §8 items 1, 4, 5, 6, 7 would move it to ~7/10 without changing the architecture.
