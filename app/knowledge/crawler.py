from __future__ import annotations

import asyncio
import logging
import re
import shutil
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Realistic browser headers to avoid bot detection
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


async def crawl_website(url: str, depth: int = 2, max_pages: int = 30) -> list[dict]:
    """Crawl a website and extract text content.

    Strategy:
    1. Try httpx + trafilatura (fast, works on simple sites)
    2. If that fails (Cloudflare, JS-rendered), use Playwright for everything
    3. Also try Katana for extra URL discovery if Docker is available
    """
    # Step 1: Quick test — can we even fetch the homepage with httpx?
    homepage_html = await _quick_fetch(url)
    use_playwright = False

    if homepage_html:
        # Check if we got real content or a Cloudflare challenge
        text = trafilatura.extract(homepage_html, include_tables=True)
        if not text or len(text.strip()) < 50:
            logger.info(f"httpx got HTML but trafilatura found no content — likely JS/Cloudflare site")
            use_playwright = True
        else:
            logger.info(f"httpx + trafilatura works for {url}")
    else:
        logger.info(f"httpx failed to fetch {url} — using Playwright")
        use_playwright = True

    if use_playwright:
        return await _crawl_with_playwright(url, depth, max_pages)
    else:
        return await _crawl_with_httpx(url, depth, max_pages)


async def _quick_fetch(url: str) -> str | None:
    """Quick test fetch to check if httpx can get real HTML."""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.text) > 500:
                return resp.text
    except Exception as e:
        logger.warning(f"Quick fetch failed for {url}: {e}")
    return None


async def _crawl_with_httpx(url: str, depth: int, max_pages: int) -> list[dict]:
    """Fast path: crawl using httpx + trafilatura (no browser needed)."""
    # Discover URLs
    all_urls = set()

    katana_urls, manual_urls = await asyncio.gather(
        _discover_urls_katana(url, depth, max_pages),
        _discover_urls_manual(url, depth, max_pages),
    )

    if katana_urls:
        logger.info(f"Katana discovered {len(katana_urls)} URLs")
        all_urls.update(katana_urls)
    if manual_urls:
        logger.info(f"Manual discovery found {len(manual_urls)} URLs")
        all_urls.update(manual_urls)

    if not all_urls:
        all_urls = {url}

    discovered_urls = sorted(all_urls)[:max_pages]
    logger.info(f"Total unique URLs to crawl: {len(discovered_urls)}")

    # Extract content
    results = []
    for page_url in discovered_urls:
        page_data = await _fetch_and_extract(page_url)
        if page_data:
            results.append(page_data)

    logger.info(f"httpx crawl: {len(results)} pages with content from {url}")
    return results


async def _crawl_with_playwright(url: str, depth: int, max_pages: int) -> list[dict]:
    """Full browser crawl for Cloudflare-protected or JS-rendered sites."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright not installed — cannot crawl JS/Cloudflare sites")
        return []

    results = []
    visited = set()
    to_visit = [url]
    base_domain = urlparse(url).netloc

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=BROWSER_UA,
                locale="en-US",
                viewport={"width": 1920, "height": 1080},
            )

            for current_depth in range(depth + 1):
                next_level = []
                for page_url in to_visit:
                    if page_url in visited or len(results) >= max_pages:
                        break
                    visited.add(page_url)

                    page_data = await _playwright_fetch_page(context, page_url)
                    if not page_data:
                        continue

                    results.append({
                        "url": page_url,
                        "title": page_data["title"],
                        "content": page_data["content"],
                    })
                    logger.info(
                        f"Playwright [{current_depth}]: {page_url} "
                        f"({len(page_data['content'])} chars, "
                        f"{len(page_data['links'])} links)"
                    )

                    # Collect links for next depth level
                    if current_depth < depth:
                        for link in page_data["links"]:
                            parsed = urlparse(link)
                            if (
                                parsed.netloc == base_domain
                                and link not in visited
                                and parsed.scheme in ("http", "https")
                            ):
                                next_level.append(link)

                to_visit = next_level[:max_pages - len(results)]

            await browser.close()

    except Exception as e:
        logger.error(f"Playwright browser error: {e}")

    logger.info(f"Playwright crawl: {len(results)} pages with content from {url}")
    return results


async def _playwright_fetch_page(context, url: str) -> dict | None:
    """Fetch a single page with Playwright, extract content and links."""
    try:
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)

        # Wait for content to render
        await page.wait_for_timeout(3000)

        # Try to dismiss popups
        for selector in [
            "button:has-text('Accept')", "button:has-text('OK')",
            "button:has-text('Close')", "[class*='cookie'] button",
            "[class*='popup'] button",
        ]:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=500):
                    await btn.click()
                    await page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        # Scroll to trigger lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await page.wait_for_timeout(1500)

        html = await page.content()

        # Extract links before closing page
        links = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(h => h.startsWith('http'))
        """)

        await page.close()

        if len(html) < 200:
            return None

        # Extract text — try trafilatura first, then BeautifulSoup
        text = trafilatura.extract(html, include_comments=False, include_tables=True)

        if not text or len(text.strip()) < 50:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg", "path"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = []
            seen = set()
            for line in text.split("\n"):
                line = line.strip()
                if len(line) > 10 and line not in seen:
                    lines.append(line)
                    seen.add(line)
            text = "\n".join(lines)

        text = _sanitize_text(text)
        if not text or len(text.strip()) < 50:
            return None

        # Get title
        title = ""
        try:
            soup = BeautifulSoup(html, "html.parser")
            tag = soup.find("title")
            if tag:
                title = tag.get_text(strip=True)
        except Exception:
            pass

        # Filter links — skip static assets
        skip_ext = (
            ".css", ".js", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
            ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".zip",
            ".pdf", ".map", ".webp",
        )
        clean_links = []
        for link in links:
            parsed = urlparse(link)
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if not any(clean.lower().endswith(ext) for ext in skip_ext):
                if clean not in clean_links:
                    clean_links.append(clean)

        return {
            "title": title,
            "content": text[:5000],
            "links": clean_links[:100],
        }

    except Exception as e:
        logger.warning(f"Playwright failed for {url}: {e}")
        return None


# ── httpx-based helpers (fast path) ──────────────────────────────────────

async def _discover_urls_katana(url: str, depth: int, max_pages: int) -> list[str]:
    """Use Katana via Docker to discover URLs with anti-bot bypass."""
    docker_path = shutil.which("docker")
    if not docker_path:
        return []

    try:
        cmd = [
            "docker", "run", "--rm",
            "projectdiscovery/katana",
            "-u", url,
            "-d", str(depth),
            "-silent",
            "-fs", "fqdn",
            "-rl", "10",
            "-timeout", "60",
            "-H", f"User-Agent: {BROWSER_UA}",
            "-H", "Accept-Language: en-US,en;q=0.9,ar;q=0.8",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=180)

        if process.returncode != 0 or not stdout.strip():
            logger.warning(f"Katana returned no results for {url}")
            return []

        urls = []
        skip_ext = (
            ".css", ".js", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico",
            ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".zip",
            ".pdf", ".map", ".webp",
        )
        for line in stdout.decode().strip().split("\n"):
            line = line.strip()
            if line and line.startswith("http"):
                if not any(line.lower().endswith(ext) for ext in skip_ext):
                    urls.append(line)

        logger.info(f"Katana discovered {len(urls)} URLs")
        return urls[:max_pages]

    except asyncio.TimeoutError:
        logger.warning("Katana timed out")
        return []
    except Exception as e:
        logger.warning(f"Katana error: {e}")
        return []


async def _discover_urls_manual(url: str, depth: int, max_pages: int) -> list[str]:
    """Fallback: manual link discovery with httpx + BeautifulSoup."""
    visited = set()
    to_visit = [url]
    discovered = []
    base_domain = urlparse(url).netloc

    for current_depth in range(depth + 1):
        next_level = []
        for page_url in to_visit:
            if page_url in visited or len(discovered) >= max_pages:
                break
            visited.add(page_url)
            discovered.append(page_url)
            if current_depth < depth:
                links = await _find_links(page_url, base_domain)
                next_level.extend(l for l in links if l not in visited)
        to_visit = next_level[:max_pages - len(discovered)]

    return discovered


def _sanitize_text(text: str) -> str:
    """Remove all HTML, code, scripts, and junk from extracted text."""
    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Remove HTML entities
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)

    # Remove JavaScript/CSS code patterns
    text = re.sub(r'\{[^}]*:[^}]*\}', ' ', text)
    text = re.sub(r'function\s*\([^)]*\)\s*\{', ' ', text)
    text = re.sub(r'var\s+\w+\s*=', ' ', text)
    text = re.sub(r'const\s+\w+\s*=', ' ', text)
    text = re.sub(r'let\s+\w+\s*=', ' ', text)
    text = re.sub(r'=>', ' ', text)
    text = re.sub(r'console\.\w+\(', ' ', text)
    text = re.sub(r'document\.\w+', ' ', text)
    text = re.sub(r'window\.\w+', ' ', text)

    # Remove URLs
    text = re.sub(r'https?://\S+', '', text)

    # Remove file paths
    text = re.sub(r'[/\\][\w./\\-]+\.(js|css|png|jpg|svg|woff|ttf|map|json)', '', text)

    # Remove hex colors, base64 data
    text = re.sub(r'#[0-9a-fA-F]{6}\b', '', text)
    text = re.sub(r'data:image/[^;]+;base64,[A-Za-z0-9+/=]+', '', text)

    # Remove excessive whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n', text)

    # Remove lines that look like code or navigation noise
    arabic_letter_re = re.compile(r"[\u0621-\u064A\u0660-\u0669]")
    clean_lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or len(line) < 5:
            continue
        alpha_ratio = sum(1 for c in line if c.isalpha() or arabic_letter_re.match(c)) / max(len(line), 1)
        if alpha_ratio < 0.3 and len(line) > 20:
            continue
        skip_patterns = [
            'copyright', 'all rights reserved',
            'powered by', 'loading...', 'please wait',
        ]
        if any(p in line.lower() for p in skip_patterns):
            continue
        clean_lines.append(line)

    return '\n'.join(clean_lines).strip()


async def _find_links(page_url: str, base_domain: str) -> list[str]:
    """Find same-domain links on a page."""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0),
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        ) as client:
            resp = await client.get(page_url)
            if resp.status_code != 200:
                return []
        soup = BeautifulSoup(resp.text, "html.parser")
        links = []
        skip = (".jpg", ".png", ".gif", ".pdf", ".zip", ".css", ".js", ".svg")
        for a in soup.find_all("a", href=True):
            absolute = urljoin(page_url, a["href"])
            parsed = urlparse(absolute)
            if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
                clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if clean not in links and not any(clean.lower().endswith(e) for e in skip):
                    links.append(clean)
        return links[:50]
    except Exception:
        return []


async def _fetch_and_extract(url: str) -> dict | None:
    """Fetch URL with browser headers, extract text with trafilatura."""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=15.0),
            follow_redirects=True,
            headers=BROWSER_HEADERS,
        ) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return None
            html = resp.text

        if len(html) < 100:
            return None

        text = trafilatura.extract(html, include_comments=False, include_tables=True, favor_precision=True)
        if not text or len(text.strip()) < 30:
            return None

        text = _sanitize_text(text)
        if not text or len(text.strip()) < 30:
            return None

        title = ""
        try:
            soup = BeautifulSoup(html, "html.parser")
            tag = soup.find("title")
            if tag:
                title = tag.get_text(strip=True)
        except Exception:
            pass

        return {"url": url, "title": title, "content": text}
    except Exception as e:
        logger.warning(f"Fetch failed for {url}: {e}")
        return None
