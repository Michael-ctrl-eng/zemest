"""Safe JSON extraction from LLM output.

Problem (audit A6-H3): the previous extraction used a greedy regex
(``\\{"action":\\s*"create_order".*\\}``) that spans to the LAST closing
brace in the whole response. Any trailing prose containing a brace (a second
JSON block, an emoji-art ``}``, "{checkout more}!") makes the extracted span
invalid JSON → the order is silently dropped while the customer is told the
order was placed.

Fix: use ``json.JSONDecoder().raw_decode()`` anchored at the first ``{`` of
the candidate region. ``raw_decode`` parses exactly one complete, balanced
JSON object and ignores whatever follows — braces inside string literals are
handled correctly by the real JSON tokenizer, and trailing text is never
consumed. This is linear-time and cannot backtrack catastrophically.

Public API:
    >>> extract_first_json_object('prose {"a": {"b": 1}} trailing {junk}')
    ({"a": {"b": 1}}, 6, 28)
"""
from __future__ import annotations

import json
import logging
from re import Pattern
import re

logger = logging.getLogger(__name__)

_DECODER = json.JSONDecoder()

# A fenced ```json ... ``` block is extracted verbatim first (the model is
# instructed to emit the order block in a fence).
_FENCE_RE: Pattern[str] = re.compile(r"```json\s*(.*?)```", re.DOTALL)
_FENCE_START = "```json"


def extract_first_json_object(
    text: str,
    anchor: str | None = None,
) -> tuple[dict | None, int, int]:
    """Extract the first complete JSON object from ``text``.

    Args:
        text: LLM output (or any text).
        anchor: optional substring (e.g. ``'{"action"'``) — extraction starts
            at the first occurrence of the anchor instead of the first ``{``.

    Returns:
        ``(obj, start, end)`` where ``obj`` is the parsed object (or ``None``
        when no valid object was found) and ``start``/``end`` are the character
        span of the raw JSON inside ``text`` (``-1, -1`` when nothing found).
        Only ``dict`` results are returned; arrays / scalars are rejected.

    Never raises.
    """
    if not text or not isinstance(text, str):
        return None, -1, -1

    candidates: list[tuple[int, int]] = []  # (start, end) scan windows

    # 1) Fenced blocks get priority — the model is told to fence the order.
    for m in _FENCE_RE.finditer(text):
        candidates.append((m.start(1), m.end(1)))

    # 2) Anchor position (if given) and first brace position.
    if anchor:
        idx = text.find(anchor)
        if idx >= 0:
            candidates.append((idx, len(text)))
    brace_idx = text.find("{")
    if brace_idx >= 0:
        candidates.append((brace_idx, len(text)))

    for start, end in candidates:
        obj, span = _raw_decode_span(text[start:end])
        if obj is not None:
            return obj, start + span[0], start + span[1]

    return None, -1, -1


def _raw_decode_span(region: str) -> tuple[dict | None, tuple[int, int]]:
    """Decode the first JSON object in ``region``; return (obj, (start, end))."""
    region = region.lstrip()
    if not region.startswith("{"):
        return None, (-1, -1)
    offset = len(region) - len(region.lstrip())
    try:
        obj, end = _DECODER.raw_decode(region)
    except (json.JSONDecodeError, ValueError):
        return None, (-1, -1)
    if isinstance(obj, dict):
        return obj, (offset, end)
    return None, (-1, -1)


__all__ = ["extract_first_json_object"]
