"""Blog + SEO module tests — blocks, scoring, publish gate, public pages,
sitemap, AI writer, plan gating."""
from __future__ import annotations

import uuid

import json

import pytest
from unittest.mock import AsyncMock, patch

from app.ai.llm_client import LLMResponse
from app.services.blog_service import (
    score_seo,
    slugify,
    validate_blocks,
    render_blocks_to_html,
)


GOOD_BLOCKS = [
    {"type": "heading", "level": 2, "text": "أفضل جلابيات قطن للصيف"},
    {"type": "paragraph", "text": "الجلابيات القطنية هي الخيار الأول للصيف المصري لأن القماش بيتنفس. " * 24},
    {"type": "heading", "level": 3, "text": "الأقمشة"},
    {"type": "paragraph", "text": "اختاري القطن المصري 100% لامتصاص العرق والملمس الناعم. " * 16},
    {"type": "image", "url": "https://cdn.example/galabiya.jpg", "alt": "جلابية قطن صيفية"},
    {"type": "paragraph", "text": "شوكي المجموعة كاملة هنا https://shop.example/galabiya"},
    {"type": "paragraph", "text": "ولو محتارة في المقاس، دليل المقاسات https://shop.example/sizes"},
    {"type": "quote", "text": "القطن بيتنفس — أهم نصيحة للصيف", "cite": "خبيرة أزياء"},
]


@pytest.fixture
def growth_user_headers(client, db_session, test_user, auth_headers):
    """Growth-plan headers (blog is a Growth+ feature)."""
    test_user.plan = "growth"
    db_session.commit()
    return auth_headers


# ---------------------------------------------------------------------------
# Blocks & validation
# ---------------------------------------------------------------------------

class TestBlockValidation:
    def test_valid_blocks_pass(self):
        clean = validate_blocks(GOOD_BLOCKS)
        assert len(clean) == len(GOOD_BLOCKS)
        assert clean[0]["type"] == "heading"

    def test_unknown_type_rejected(self):
        with pytest.raises(ValueError):
            validate_blocks([{"type": "script", "text": "<script>"}])

    def test_heading_level_bounds(self):
        with pytest.raises(ValueError):
            validate_blocks([{"type": "heading", "level": 1, "text": "x"}])

    def test_bad_image_url_rejected(self):
        with pytest.raises(ValueError):
            validate_blocks([{"type": "image", "url": "javascript:alert(1)"}])

    def test_non_list_rejected(self):
        with pytest.raises(ValueError):
            validate_blocks({"type": "paragraph"})

    def test_slugify(self):
        # \w matches Arabic — only English stopwords are stripped
        assert slugify("أفضل 10 نصائح للعناية بالجلابيات") == "أفضل-10-نصائح-للعناية-بالجلابيات"
        assert slugify("How to Choose the Best Cotton") == "choose-cotton"
        assert slugify("the of and")  # all stopwords → fallback slug, not empty


# ---------------------------------------------------------------------------
# SEO scoring — measurable
# ---------------------------------------------------------------------------

class TestSEOScoring:
    def _make_post(self, **overrides):
        from app.models.blog_post import BlogPost

        defaults = dict(
            id=uuid.uuid4(), tenant_id=uuid.uuid4(),
            slug="best-summer-galabiya", title="أفضل جلابيات قطن للصيف 2026",
            keyword="جلابيات قطن",
            meta_description="دليلك الكامل لاختيار الجلابيات القطنية الأفضل للصيف: الأقمشة والمقاسات والأسعار.",
            blocks=GOOD_BLOCKS, status="draft",
        )
        defaults.update(overrides)
        post = BlogPost(**{k: v for k, v in defaults.items() if k in BlogPost.__table__.columns.keys()})
        return post

    def test_good_post_scores_high(self):
        post = self._make_post()
        score, checks = score_seo(post)
        assert score >= 70, f"good content scored only {score}: {checks}"
        by_check = {c["check"]: c for c in checks}
        assert by_check["title_length"]["points"] == 15
        assert by_check["meta_description"]["points"] == 15
        assert by_check["image_alt"]["points"] == 10

    def test_thin_post_scores_low_with_hints(self):
        post = self._make_post(
            title="قصير",
            meta_description="",
            keyword=None,
            blocks=[{"type": "paragraph", "text": "نص قصير"}],
        )
        score, checks = score_seo(post)
        assert score <= 45
        hints = [c["hint"] for c in checks if c["hint"]]
        assert hints, "thin content must produce actionable hints"

    def test_missing_alt_text_flagged(self):
        blocks = [dict(b) for b in GOOD_BLOCKS]
        blocks[4] = {"type": "image", "url": "https://cdn.example/x.jpg", "alt": ""}
        post = self._make_post(blocks=blocks)
        _score, checks = score_seo(post)
        by_check = {c["check"]: c for c in checks}
        assert by_check["image_alt"]["points"] < 10
        assert "alt" in (by_check["image_alt"]["hint"] or "")

    def test_keyword_missing_from_first_paragraph(self):
        blocks = [dict(b) for b in GOOD_BLOCKS]
        blocks[1] = {"type": "paragraph", "text": "نص بدون الكلمة المفتاحية نهائياً. " * 10}
        post = self._make_post(blocks=blocks)
        _score, checks = score_seo(post)
        by_check = {c["check"]: c for c in checks}
        assert by_check["keyword"]["points"] < 10


# ---------------------------------------------------------------------------
# API: CRUD + publish gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestBlogCRUD:
    async def _create(self, client, headers, tenant, **overrides):
        payload = {
            "title": "أفضل جلابيات قطن للصيف",
            "keyword": "جلابيات قطن",
            "meta_description": "دليلك الكامل لاختيار الجلابيات القطنية مع نصائح الخبراء.",
            "blocks": GOOD_BLOCKS,
        }
        payload.update(overrides)
        return await client.post(
            f"/api/tenants/{tenant.id}/blog/posts", json=payload, headers=headers
        )

    async def test_create_draft(self, client, db_session, growth_user_headers, test_tenant):
        resp = await self._create(client, growth_user_headers, test_tenant)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "draft"
        assert data["seo_score"] >= 50
        assert data["word_count"] >= 100
        assert data["slug"]

    async def test_free_plan_blocked(self, client, auth_headers, test_tenant):
        """Blog is a Growth+ feature — free accounts get 402 + upgrade path."""
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/blog/posts",
            json={"title": "Any Title"},
            headers=auth_headers,
        )
        assert resp.status_code == 402
        assert resp.json()["detail"]["code"] == "blog_feature"

    async def test_publish_gate_blocks_thin_content(self, client, db_session, growth_user_headers, test_tenant):
        """Thin content is refused — junk posts hurt the whole domain."""
        resp = await self._create(
            client, growth_user_headers, test_tenant,
            blocks=[{"type": "paragraph", "text": "نص قصير"}],
        )
        post_id = resp.json()["id"]
        pub = await client.post(
            f"/api/tenants/{test_tenant.id}/blog/posts/{post_id}/publish",
            headers=growth_user_headers,
        )
        assert pub.status_code == 422
        assert "thin" in pub.json()["detail"].lower()

    async def test_publish_and_public_listing(self, client, db_session, growth_user_headers, test_tenant):
        resp = await self._create(client, growth_user_headers, test_tenant)
        post_id = resp.json()["id"]

        pub = await client.post(
            f"/api/tenants/{test_tenant.id}/blog/posts/{post_id}/publish",
            headers=growth_user_headers,
        )
        assert pub.status_code == 200
        assert pub.json()["status"] == "published"

        listing = await client.get("/blog")
        assert listing.status_code == 200
        slugs = [p["slug"] for p in listing.json()["posts"]]
        assert pub.json()["slug"] in slugs

    async def test_unpublish_hides_from_public(self, client, db_session, growth_user_headers, test_tenant):
        resp = await self._create(client, growth_user_headers, test_tenant)
        post_id = resp.json()["id"]
        await client.post(
            f"/api/tenants/{test_tenant.id}/blog/posts/{post_id}/publish",
            headers=growth_user_headers,
        )
        await client.post(
            f"/api/tenants/{test_tenant.id}/blog/posts/{post_id}/unpublish",
            headers=growth_user_headers,
        )
        listing = await client.get("/blog")
        assert resp.json()["slug"] not in [p["slug"] for p in listing.json()["posts"]]

    async def test_draft_not_publicly_visible(self, client, growth_user_headers, test_tenant):
        resp = await self._create(client, growth_user_headers, test_tenant)
        slug = resp.json()["slug"]
        pub = await client.get(f"/blog/{slug}")
        assert pub.status_code == 404

    async def test_update_recalculates_seo(self, client, growth_user_headers, test_tenant):
        resp = await self._create(client, growth_user_headers, test_tenant)
        post_id = resp.json()["id"]
        before = resp.json()["seo_score"]

        update = await client.patch(
            f"/api/tenants/{test_tenant.id}/blog/posts/{post_id}",
            json={"meta_description": ""},
            headers=growth_user_headers,
        )
        assert update.status_code == 200
        assert update.json()["seo_score"] < before

    async def test_xss_safe_rendering(self, client, db_session, growth_user_headers, test_tenant):
        """Editor text with HTML is escaped on the public page — XSS by
        construction is impossible."""
        resp = await self._create(
            client, growth_user_headers, test_tenant,
            blocks=[
                {"type": "paragraph", "text": "<script>alert('xss')</script> عادي"},
                {"type": "paragraph", "text": "text. " * 200},
            ],
        )
        post_id = resp.json()["id"]
        await client.post(
            f"/api/tenants/{test_tenant.id}/blog/posts/{post_id}/publish",
            headers=growth_user_headers,
        )
        page = await client.get(f"/blog/{resp.json()['slug']}")
        assert page.status_code == 200
        html = page.json()["html"]
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    async def test_sitemap_lists_published_only(self, client, db_session, growth_user_headers, test_tenant):
        resp = await self._create(client, growth_user_headers, test_tenant)
        draft_slug = resp.json()["slug"]
        await client.post(
            f"/api/tenants/{test_tenant.id}/blog/posts/{resp.json()['id']}/publish",
            headers=growth_user_headers,
        )
        published_slug = draft_slug  # now published

        sm = await client.get("/sitemap.xml")
        assert sm.status_code == 200
        assert "application/xml" in sm.headers["content-type"]
        from urllib.parse import quote
        assert quote(published_slug) in sm.text

        # Unpublish → gone from sitemap
        await client.post(
            f"/api/tenants/{test_tenant.id}/blog/posts/{resp.json()['id']}/unpublish",
            headers=growth_user_headers,
        )
        sm2 = await client.get("/sitemap.xml")
        assert quote(published_slug) not in sm2.text

    async def test_robots_txt(self, client):
        resp = await client.get("/robots.txt")
        assert resp.status_code == 200
        body = resp.text
        assert "Disallow: /api" in body
        assert "Allow: /blog" in body
        assert "Sitemap:" in body

    async def test_ai_draft_generation(self, client, growth_user_headers, test_tenant):
        """The AI writer returns a validated block structure."""
        para = "نص مفيد عن العناية بالجلابيات القطنية. " * 80
        fake_draft = json.dumps({
            "title": "دليل العناية بالجلابيات",
            "keyword": "جلابيات",
            "meta_description": "نصائح عملية للعناية بالجلابيات القطنية تدوم سنين.",
            "blocks": [
                {"type": "heading", "level": 2, "text": "مقدمة"},
                {"type": "paragraph", "text": para},
            ],
        }, ensure_ascii=False)
        with patch(
            "app.ai.llm_client.chat_completion_with_usage",
            new=AsyncMock(return_value=LLMResponse(
                content=fake_draft + " شكرا {done}", model="t",
                prompt_tokens=10, completion_tokens=10, total_tokens=20,
            )),
        ):
            resp = await client.post(
                f"/api/tenants/{test_tenant.id}/blog/generate",
                json={"topic": "العناية بالجلابيات القطنية"},
                headers=growth_user_headers,
            )
        assert resp.status_code == 200, resp.text
        draft = resp.json()["draft"]
        assert draft["title"]
        assert isinstance(draft["blocks"], list)
        assert draft["blocks"][0]["type"] in ("heading", "paragraph")

    async def test_delete(self, client, growth_user_headers, test_tenant):
        resp = await self._create(client, growth_user_headers, test_tenant)
        post_id = resp.json()["id"]
        dele = await client.delete(
            f"/api/tenants/{test_tenant.id}/blog/posts/{post_id}",
            headers=growth_user_headers,
        )
        assert dele.status_code == 200
        gone = await client.get(
            f"/api/tenants/{test_tenant.id}/blog/posts/{post_id}",
            headers=growth_user_headers,
        )
        assert gone.status_code == 404


# ---------------------------------------------------------------------------
# Rendering unit
# ---------------------------------------------------------------------------

class TestRendering:
    def test_escaping(self):
        html = render_blocks_to_html([
            {"type": "paragraph", "text": "<img src=x onerror=alert(1)>"},
            {"type": "quote", "text": "hi", "cite": "<b>me</b>"},
        ])
        assert "<img src=x" not in html
        assert "&lt;img" in html
        assert "<blockquote>" in html

    def test_shop_link_appended(self):
        html = render_blocks_to_html(
            [{"type": "paragraph", "text": "x"}], shop_url="https://shop.example"
        )
        assert 'href="https://shop.example"' in html
        assert "rel=&#x27;nofollow&#x27;" in html or 'rel="nofollow"' in html

    def test_image_lazy_alt(self):
        html = render_blocks_to_html([
            {"type": "image", "url": "https://cdn.example/a.jpg", "alt": "وصف"}
        ])
        assert 'loading="lazy"' in html
        assert 'alt="وصف"' in html
