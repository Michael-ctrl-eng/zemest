"""Universal product extractor — works on any website.

Tries multiple methods in order (cheapest first):
1. JSON-LD structured data (zero LLM)
2. OG meta tags (zero LLM)
3. HTML price regex + title (zero LLM)
4. LLM extraction from page text (fallback, ~300 tokens)
"""
import json
import logging
import re

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}


async def extract_product_from_url(url: str) -> dict | None:
    """Extract product data from a single URL. Returns dict or None.

    Tries: JSON-LD → OG tags → regex → Playwright → LLM fallback.
    """
    html = await _fetch_page(url)
    if not html:
        # Try Playwright for JS-rendered sites
        html = await _fetch_with_playwright(url)
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Try extraction methods in order (cheapest first)
    product = _try_jsonld(soup, url)
    if product and product.get("price"):
        logger.info(f"Extracted via JSON-LD: {product.get('name')}")
        return product

    product = _try_og_tags(soup, url)
    if product and product.get("price"):
        logger.info(f"Extracted via OG tags: {product.get('name')}")
        return product

    product = _try_html_regex(soup, url)
    if product and product.get("price"):
        logger.info(f"Extracted via HTML regex: {product.get('name')}")
        return product

    # LLM fallback — extract from page text
    product = await _try_llm_extraction(soup, url)
    if product:
        logger.info(f"Extracted via LLM: {product.get('name')}")
        return product

    return None


async def _fetch_page(url: str) -> str | None:
    """Fetch page HTML with browser headers.

    SSRF hardening (audit A3-C1): routed through :class:`SafeHTTPClient` so
    every redirect hop is re-validated — a public redirector URL could
    previously 302 to internal/metadata endpoints and hand the content to
    the extraction pipeline (and the LLM) for readback. Byte cap added.
    """
    from app.middleware.ssrf_protection import SafeHTTPClient, UnsafeURLError

    _MAX_HTML_BYTES = 5 * 1024 * 1024  # 5 MB

    try:
        client = SafeHTTPClient(timeout=30.0, connect_timeout=10.0, headers=BROWSER_HEADERS)
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        ct = resp.headers.get("content-type", "")
        if "text/html" not in ct and "xhtml" not in ct:
            return None
        if len(resp.text) > _MAX_HTML_BYTES:
            logger.warning(f"Page too large for import-url: {url}")
            return None
        return resp.text
    except UnsafeURLError as e:
        logger.warning(f"SSRF guard blocked {url}: {e}")
        return None
    except Exception as e:
        logger.warning(f"HTTP fetch failed for {url}: {e}")
        return None


async def _fetch_with_playwright(url: str) -> str | None:
    """Fallback: render JS-heavy pages with Playwright.

    SSRF hardening (audit A3-C1): a route interceptor aborts every
    in-browser request/navigation whose target fails the SSRF guard, so
    attacker JS cannot navigate the browser to internal endpoints and
    have ``page.content()`` serialize the response.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    try:
        from app.middleware.ssrf_protection import is_safe_url

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=BROWSER_HEADERS["User-Agent"])

            async def _block_unsafe(route):
                target = route.request.url
                safe, _reason = is_safe_url(target)
                if not safe:
                    logger.warning(f"Playwright SSRF guard aborted request to {target}")
                    await route.abort()
                else:
                    await route.continue_()

            await context.route("**/*", _block_unsafe)

            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=20000)
            await page.wait_for_timeout(2000)
            html = await page.content()
            await browser.close()
            return html if len(html) > 500 else None
    except Exception as e:
        logger.warning(f"Playwright failed for {url}: {e}")
        return None


def _try_jsonld(soup: BeautifulSoup, url: str) -> dict | None:
    """Extract product from JSON-LD structured data."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") == "Product":
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}

                    price = offers.get("price")
                    if price:
                        price = float(str(price).replace(",", ""))

                    avail = offers.get("availability", "")
                    stock = "in_stock" if "InStock" in avail else "out_of_stock" if "OutOfStock" in avail else "unknown"

                    return {
                        "name": item.get("name", ""),
                        "price": price,
                        "description": (item.get("description") or "")[:500],
                        "image_url": item.get("image", ""),
                        "stock_status": stock,
                        "url": url,
                        "brand": item.get("brand", {}).get("name", "") if isinstance(item.get("brand"), dict) else str(item.get("brand", "")),
                        "sku": item.get("sku", ""),
                    }
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def _try_og_tags(soup: BeautifulSoup, url: str) -> dict | None:
    """Extract product from Open Graph meta tags."""
    og_title = soup.find("meta", property="og:title")
    og_price = soup.find("meta", property="product:price:amount")
    og_avail = soup.find("meta", property="product:availability")
    og_desc = soup.find("meta", property="og:description")
    og_image = soup.find("meta", property="og:image")

    if not og_price:
        return None

    try:
        price = float(str(og_price.get("content", "0")).replace(",", ""))
    except (ValueError, TypeError):
        return None

    if price <= 0:
        return None

    name = og_title.get("content", "") if og_title else ""
    if not name and soup.title:
        name = soup.title.string.strip().split("|")[0].split("–")[0].strip()

    stock = "unknown"
    if og_avail:
        avail = og_avail.get("content", "").lower()
        if "in stock" in avail:
            stock = "in_stock"
        elif "out of stock" in avail or "sold out" in avail:
            stock = "out_of_stock"

    return {
        "name": name,
        "price": price,
        "description": (og_desc.get("content", "") if og_desc else "")[:500],
        "image_url": og_image.get("content", "") if og_image else "",
        "stock_status": stock,
        "url": url,
    }


def _try_html_regex(soup: BeautifulSoup, url: str) -> dict | None:
    """Extract product from HTML text using regex patterns."""
    text = soup.get_text()

    # Extract price
    prices = re.findall(r"(?:EGP|E£|ج\.م)\s*([\d,]+\.?\d*)", text)
    if not prices:
        prices = re.findall(r"([\d,]+\.?\d*)\s*(?:EGP|E£|ج\.م)", text)
    if not prices:
        return None

    # Filter out tiny numbers (not real prices)
    valid_prices = []
    for p in prices:
        try:
            val = float(p.replace(",", ""))
            if val >= 10:
                valid_prices.append(val)
        except ValueError:
            continue

    if not valid_prices:
        return None

    price = valid_prices[0]

    # Get name from title tag
    name = ""
    if soup.title:
        name = soup.title.string.strip().split("|")[0].split("–")[0].split("-")[0].strip()

    # Try h1 tag as product name
    if not name or len(name) < 3:
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)

    if not name:
        return None

    # Detect stock status from keywords (English + Egyptian Arabic)
    text_lower = text.lower()
    out_keywords = ["out of stock", "sold out", "stock out", "مش متوفر", "نفد", "currently unavailable"]
    in_keywords = ["add to cart", "buy now", "in stock", "أضف للسلة", "اطلب دلوقتي", "اشتري الآن"]

    stock = "unknown"
    if any(k in text_lower for k in out_keywords):
        stock = "out_of_stock"
    elif any(k in text_lower for k in in_keywords):
        stock = "in_stock"

    # Get image
    og_image = soup.find("meta", property="og:image")
    image_url = og_image.get("content", "") if og_image else ""

    return {
        "name": name,
        "price": price,
        "stock_status": stock,
        "image_url": image_url,
        "url": url,
    }


async def _try_llm_extraction(soup: BeautifulSoup, url: str) -> dict | None:
    """Last resort: use LLM to extract product from page text."""
    # Get clean text
    for tag in soup(["script", "style", "noscript", "svg", "path"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    # Only first 2000 chars to keep token cost low
    text = text[:2000]
    if len(text) < 50:
        return None

    try:
        from app.ai.llm_client import chat_completion

        prompt = f"""Extract the product from this page. Return ONLY a JSON object:
{{"name":"...","price":NUMBER,"description":"...","stock_status":"in_stock or out_of_stock"}}

Page text:
{text}"""

        response = await chat_completion(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
        )

        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            product = json.loads(match.group())
            if product.get("name") and product.get("price"):
                product["url"] = url
                product["price"] = float(str(product["price"]).replace(",", ""))
                return product
    except Exception as e:
        logger.warning(f"LLM extraction failed for {url}: {e}")

    return None
