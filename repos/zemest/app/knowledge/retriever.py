"""Retrieve products and knowledge from PageIndex tree using LLM navigation.

The LLM reads the tree TOC (titles + summaries — small, ~200 tokens)
and picks which nodes to fetch. This handles:
- Arabic (Egyptian), English queries
- Typos and spelling variations
- Synonyms

Cost: ~50-100 tokens for TOC navigation (just returns node numbers)
"""
import json
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


async def retrieve_context(
    db: AsyncSession,
    tenant_id,
    query: str,
    max_nodes: int = 3,
) -> tuple[str, str]:
    """Retrieve relevant products AND knowledge from PageIndex tree.

    Returns (products_context, knowledge_context) — both as formatted strings.
    The LLM navigates the tree TOC to find relevant nodes.

    Cost: ~50-100 tokens (TOC + node selection).
    """
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant_id)
    )
    kb = result.scalar_one_or_none()

    if not kb or not kb.tree_json:
        return "", ""

    storage = kb.tree_json

    # Get tree structure
    if storage.get("type") == "pageindex":
        tree_data = storage.get("tree", {})
        structure = tree_data.get("structure", [])
    else:
        structure = storage.get("children", storage.get("structure", []))

    if not structure:
        return "", ""

    # Build compact TOC (titles + summaries only — no full text)
    toc = _build_toc(structure)
    if not toc:
        return "", ""

    # Ask LLM which nodes are relevant
    selected_ids, token_info = await _select_nodes(toc, query, max_nodes)

    # Persist token usage for the retrieval LLM call (best-effort).
    if token_info:
        try:
            from app.models.token_usage import TokenUsage
            usage = TokenUsage(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                usage_type="retrieval",
                model=token_info.get("model", "unknown"),
                prompt_tokens=token_info.get("prompt_tokens", 0),
                completion_tokens=token_info.get("completion_tokens", 0),
                total_tokens=token_info.get("total_tokens", 0),
            )
            db.add(usage)
        except Exception as e:
            logger.warning(f"Failed to track retrieval token usage: {e}")

    if not selected_ids:
        return "", ""

    # Also include child node IDs (if a category is selected, include all its products)
    expanded_ids = set(selected_ids)
    for node in _flatten_all(structure):
        if node.get("node_id") in expanded_ids:
            for child in node.get("nodes", []):
                child_id = child.get("node_id")
                if child_id:
                    expanded_ids.add(child_id)

    # Fetch content from selected + expanded nodes
    products_text, knowledge_text = _extract_content(structure, list(expanded_ids))

    return products_text, knowledge_text


async def _select_nodes(toc: str, query: str, max_nodes: int) -> tuple[list[str], dict | None]:
    """Ask LLM to pick relevant nodes from the TOC. Cost: ~50 tokens.

    Returns ``(selected_ids, token_info)`` where ``token_info`` is the LLM
    usage dict (or None if the LLM was not called / failed).
    """
    try:
        from app.ai.llm_client import chat_completion_with_usage

        prompt = f"""Pick the most relevant sections for this customer query. Return ONLY a JSON array of node IDs.

Query: "{query}"

Sections:
{toc}

Return [{max_nodes} most relevant node IDs], e.g. ["0001","0005","0003"]. ONLY the JSON array."""

        result = await chat_completion_with_usage(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=50,
        )
        response = result.content
        token_info = {
            "model": result.model,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
        }

        match = re.search(r'\[.*?\]', response)
        if match:
            ids = json.loads(match.group())
            return [str(i).zfill(4) if isinstance(i, int) else str(i) for i in ids], token_info
        return [], token_info

    except Exception as e:
        logger.warning(f"PageIndex node selection failed: {e}")

    return [], None


def _build_toc(nodes: list, indent: int = 0) -> str:
    """Build compact TOC from tree. Shows node_id, title, summary."""
    lines = []
    for node in nodes:
        if not isinstance(node, dict):
            continue

        nid = node.get("node_id", "?")
        title = node.get("title", "")
        summary = node.get("summary", node.get("prefix_summary", ""))
        ntype = node.get("_type", "")

        prefix = "  " * indent
        tag = "[P]" if "product" in ntype else "[K]"
        entry = f"{prefix}{tag} [{nid}] {title}"
        if summary:
            entry += f" — {summary[:100]}"
        lines.append(entry)

        children = node.get("nodes", [])
        if children:
            lines.append(_build_toc(children, indent + 1))

    return "\n".join(lines)


def _flatten_all(nodes: list) -> list[dict]:
    """Flatten tree keeping node references (with children intact)."""
    flat = []
    for node in nodes:
        if isinstance(node, dict):
            flat.append(node)
            if node.get("nodes"):
                flat.extend(_flatten_all(node["nodes"]))
    return flat


def _extract_content(nodes: list, selected_ids: list[str]) -> tuple[str, str]:
    """Extract text from selected nodes, separating products from knowledge."""
    target_set = set(selected_ids)
    product_parts = []
    knowledge_parts = []

    def _traverse(node_list):
        for node in node_list:
            if not isinstance(node, dict):
                continue

            nid = node.get("node_id", "")
            if nid in target_set:
                text = node.get("text", "")
                title = node.get("title", "")
                ntype = node.get("_type", "")

                # If this is a category node, format each child product clearly
                children = node.get("nodes", [])
                if children and "product" in ntype:
                    for child in children:
                        ct = child.get("text", "")
                        if ct:
                            product_parts.append(ct)
                elif "product" in ntype:
                    product_parts.append(text)
                else:
                    content = f"## {title}\n{text}" if title else text
                    knowledge_parts.append(content[:500])

            # Also check children directly
            children = node.get("nodes", [])
            if children:
                _traverse(children)

    _traverse(nodes)

    return "\n\n---\n\n".join(product_parts), "\n\n".join(knowledge_parts)
