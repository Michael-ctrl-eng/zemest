"""Product image understanding using Gemini Vision (free tier)."""

import asyncio
import base64
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

GEMINI_VISION_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


@dataclass
class ImageAnalysis:
    product_name: str
    category: str
    color: str
    details: str
    price_hint: str
    # Token usage from the Gemini Vision call — populated by the caller
    # (agent._analyze_images) into a TokenUsage row with usage_type="vision".
    prompt_tokens: int = 0
    completion_tokens: int = 0


async def analyze_product_image(
    image_url: str,
    api_key: str,
    product_context: str = "",
) -> ImageAnalysis | None:
    """Analyze a product image using Gemini Vision.

    Returns structured product info or None if analysis fails.
    """
    if not api_key:
        return None

    try:
        # Download image
        async with httpx.AsyncClient(timeout=15.0) as client:
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            img_bytes = img_resp.content

            if len(img_bytes) > 10 * 1024 * 1024:  # 10MB cap
                logger.warning("Image too large for vision analysis")
                return None

            # Determine mime type
            content_type = img_resp.headers.get("content-type", "image/jpeg")
            mime = content_type.split(";")[0] if ";" in content_type else content_type

            # Encode to base64
            img_b64 = base64.b64encode(img_bytes).decode()

        # Build Gemini Vision request
        parts = [
            {
                "inline_data": {
                    "mime_type": mime,
                    "data": img_b64,
                }
            },
            {
                "text": f"""حلل صورة المنتج دي وأعد JSON بالشكل ده:
{{"product_name": "اسم المنتج بالعربي", "category": "الفئة", "color": "اللون", "details": "تفاصيل إضافية", "price_hint": "تقدير السعر لو ظاهر"}}

{f"معلومات إضافية عن منتجات الصفحة: {product_context}" if product_context else ""}

ممنوع تختلق معلومات. لو مش واضح حاجة اكتب "غير واضح".
IMPORTANT: Return ONLY the JSON object, no other text."""
            }
        ]

        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 256,
            },
        }

        # Call Gemini Vision
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                GEMINI_VISION_URL,
                json=body,
                headers={"x-goog-api-key": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract text
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            text = ""
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    text = part["text"]
                    break

            if not text:
                return None

            # Token usage from Gemini's usageMetadata (best-effort)
            usage_meta = data.get("usageMetadata", {}) or {}
            prompt_tokens = int(usage_meta.get("promptTokenCount", 0) or 0)
            completion_tokens = int(usage_meta.get("candidatesTokenCount", 0) or 0)

            # Parse JSON
            import json
            import re

            text = text.strip()
            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                else:
                    return None

            return ImageAnalysis(
                product_name=parsed.get("product_name", ""),
                category=parsed.get("category", ""),
                color=parsed.get("color", ""),
                details=parsed.get("details", ""),
                price_hint=parsed.get("price_hint", ""),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

    except Exception as e:
        logger.warning(f"Gemini Vision analysis failed: {e}")
        return None
