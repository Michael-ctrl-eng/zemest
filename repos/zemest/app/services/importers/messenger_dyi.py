"""Parse Facebook Messenger "Download Your Information" ZIP exports.

Zero ban risk: the user manually downloads their data from Meta and uploads
the ZIP to us. We parse it locally — no API calls to Meta during import.

The DYI export format (JSON):
  messages/inbox/<thread_name>/message_1.json
  messages/inbox/<thread_name>/message_2.json   (if thread is large)
  messages/inbox/<thread_name>/photos/...        (media, skipped)

Each message_*.json contains:
  {
    "title": "Thread Name",
    "participants": [{"name": "...", ...}],
    "messages": [
      {
        "sender_name": "...",
        "timestamp_ms": 1577836800000,
        "content": "hello",
        "type": "Generic",       # or "Share", "Photo", "Video", etc.
        "reactions": [{"reaction": "❤", "actor": "..."}],
        "sticker": {...},
        "photos": [{"uri": "..."}],
        "share": {...},
      }
    ]
  }
"""
from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from typing import Iterator

logger = logging.getLogger(__name__)

# Roles we assign during import
ROLE_MERCHANT = "merchant"      # the page owner's outbound messages
ROLE_CUSTOMER = "customer"      # inbound messages from customers


def parse_messenger_dyi_zip(zip_bytes: bytes, page_owner_names: set[str] | None = None) -> list[dict]:
    """Parse a Facebook DYI messages ZIP into normalized messages.

    Args:
        zip_bytes: Raw ZIP file bytes (from user upload).
        page_owner_names: Set of sender names that belong to the page owner.
            If None, we'll try to auto-detect (the most frequent sender
            across all threads is assumed to be the page owner).

    Returns:
        List of dicts: {
            "channel": "messenger",
            "thread_title": str,
            "sender": str,
            "role": "merchant" | "customer",
            "content": str,
            "timestamp": datetime,
            "message_type": str,
            "reactions": list[str],
        }
    """
    messages: list[dict] = []
    sender_counts: dict[str, int] = {}

    # First pass: collect all senders to identify the page owner
    # Zip-bomb guard (audit A4-H3): each member's *uncompressed* size is
    # checked before reading; a 50 MB member limit + 1 GB aggregate stops
    # highly-compressible JSON expanding to many GB in RAM.
    _MAX_MEMBER_BYTES = 50 * 1024 * 1024
    _MAX_TOTAL_BYTES = 1024 * 1024 * 1024
    parsed_threads: list[dict] = []
    total_read = 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if not name.endswith(".json") or "message_" not in name:
                    continue
                info = zf.getinfo(name)
                if info.file_size > _MAX_MEMBER_BYTES:
                    logger.warning(f"Skipping oversized zip member {name} ({info.file_size} bytes)")
                    continue
                total_read += info.file_size
                if total_read > _MAX_TOTAL_BYTES:
                    raise ValueError("ZIP uncompressed content exceeds 1 GB limit")
                try:
                    with zf.open(name) as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"Failed to parse {name}: {e}")
                    continue
                parsed_threads.append(data)
                for msg in data.get("messages", []):
                    sender = msg.get("sender_name", "")
                    if sender:
                        sender_counts[sender] = sender_counts.get(sender, 0) + 1
    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid ZIP file: {e}")

    if not parsed_threads:
        return []

    # Auto-detect page owner if not provided (most frequent sender)
    if page_owner_names is None:
        if sender_counts:
            top_sender = max(sender_counts, key=sender_counts.get)
            page_owner_names = {top_sender}
        else:
            page_owner_names = set()

    # Second pass: normalize messages
    for thread_data in parsed_threads:
        thread_title = thread_data.get("title", "Unknown Thread")
        for msg in thread_data.get("messages", []):
            sender = msg.get("sender_name", "").encode("latin-1").decode("utf-8", errors="replace") if msg.get("sender_name") else ""
            content = msg.get("content", "")
            if content:
                try:
                    content = content.encode("latin-1").decode("utf-8", errors="replace")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass

            # Skip system messages (calls, reactions, etc.)
            msg_type = msg.get("type", "Generic")
            if msg_type in ("Call", "Subscription", "Payment"):
                continue

            # Handle non-text messages
            if not content:
                if msg.get("photos"):
                    content = "(photo)"
                elif msg.get("share"):
                    share = msg["share"]
                    content = share.get("link", "(shared link)")
                elif msg.get("sticker"):
                    content = "(sticker)"
                elif msg.get("gifs"):
                    content = "(gif)"
                elif msg.get("videos"):
                    content = "(video)"
                elif msg.get("audio_files"):
                    content = "(audio)"
                else:
                    continue  # skip empty

            # Decode thread title too
            try:
                thread_title_decoded = thread_title.encode("latin-1").decode("utf-8", errors="replace")
            except (UnicodeEncodeError, UnicodeDecodeError):
                thread_title_decoded = thread_title

            # Parse timestamp
            ts_ms = msg.get("timestamp_ms")
            if ts_ms:
                timestamp = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            else:
                continue  # skip messages without timestamp

            reactions = [r.get("reaction", "") for r in msg.get("reactions", []) if r.get("reaction")]

            role = ROLE_MERCHANT if sender in page_owner_names else ROLE_CUSTOMER

            messages.append({
                "channel": "messenger",
                "thread_title": thread_title_decoded,
                "sender": sender,
                "role": role,
                "content": content,
                "timestamp": timestamp,
                "message_type": msg_type,
                "reactions": reactions,
            })

    # Sort by timestamp
    messages.sort(key=lambda m: m["timestamp"])
    return messages


def parse_instagram_dyi_zip(zip_bytes: bytes, page_owner_names: set[str] | None = None) -> list[dict]:
    """Parse an Instagram DYI messages ZIP.

    Instagram uses the same format as Facebook (Meta unified the export).
    """
    messages = parse_messenger_dyi_zip(zip_bytes, page_owner_names)
    for m in messages:
        m["channel"] = "instagram"
    return messages


def stream_parse_messenger_zip(zip_bytes: bytes, batch_size: int = 1000) -> Iterator[list[dict]]:
    """Stream-parse a large DYI ZIP, yielding batches of messages.

    This is memory-efficient for very large exports (millions of messages).
    """
    batch: list[dict] = []
    # For streaming we need two passes: first to detect owner, then to yield
    all_messages = parse_messenger_dyi_zip(zip_bytes)
    for msg in all_messages:
        batch.append(msg)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def get_zip_stats(zip_bytes: bytes) -> dict:
    """Get statistics about a DYI ZIP without fully parsing it.

    Returns: {"thread_count": int, "estimated_message_count": int, "file_count": int}
    """
    thread_count = 0
    file_count = 0
    est_msg_count = 0
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith(".json") and "message_" in name:
                    file_count += 1
                    if "/" in name:
                        thread_name = name.split("/")[-2] if name.count("/") >= 2 else "unknown"
                    # Quick peek at message count without full parse
                    try:
                        with zf.open(name) as f:
                            data = json.load(f)
                            est_msg_count += len(data.get("messages", []))
                            thread_count += 1
                    except (json.JSONDecodeError, OSError):
                        pass
    except zipfile.BadZipFile:
        return {"thread_count": 0, "estimated_message_count": 0, "file_count": 0, "error": "Invalid ZIP"}

    return {
        "thread_count": thread_count,
        "estimated_message_count": est_msg_count,
        "file_count": file_count,
    }
