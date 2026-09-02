"""Parse WhatsApp "Export Chat" ZIP files.

WhatsApp's built-in "Export Chat" feature produces a ZIP containing:
  - _chat.txt  (the conversation log in text format)
  - media files (photos, videos, voice notes)

Format of _chat.txt lines:
  [12/31/23, 11:59:59 PM] Sender Name: message content
  [1/1/24, 12:00:01 AM] +20 100 123 4567: hello

Multi-line messages have continuation lines without the timestamp prefix.

Zero ban risk: user manually exports from their WhatsApp app.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import datetime
from typing import Iterator

logger = logging.getLogger(__name__)

# WhatsApp export line format
# [date, time] sender: content
# Date: M/D/YY or MM/DD/YYYY
# Time: H:MM AM/PM or HH:MM:SS
WA_LINE_RE = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s*[APap]?[Mm]?)\]\s*([^:]+):\s*(.*)$"
)

# System messages (not real messages)
WA_SYSTEM_SENDERS = {"System", "WhatsApp", "Messages and calls are end-to-end encrypted"}


def _parse_wa_timestamp(date_str: str, time_str: str) -> datetime | None:
    """Parse WhatsApp date+time into datetime."""
    # Try multiple formats
    formats = [
        "%m/%d/%y %I:%M:%S %p",
        "%m/%d/%y %I:%M %p",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%y %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d/%m/%y %H:%M:%S",
        "%d/%m/%y %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
    ]
    datetime_str = f"{date_str} {time_str}"
    for fmt in formats:
        try:
            return datetime.strptime(datetime_str, fmt)
        except ValueError:
            continue
    return None


def parse_whatsapp_export_zip(zip_bytes: bytes, page_owner_name: str | None = None) -> list[dict]:
    """Parse a WhatsApp "Export Chat" ZIP into normalized messages.

    Args:
        zip_bytes: Raw ZIP file bytes.
        page_owner_name: The name of the page owner in the chat.
            If None, we'll try to auto-detect (the sender that appears
            most frequently is assumed to be the page owner).

    Returns:
        List of normalized message dicts.
    """
    messages: list[dict] = []
    sender_counts: dict[str, int] = {}

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Find the .txt file
            txt_name = None
            for name in zf.namelist():
                if name.endswith(".txt"):
                    txt_name = name
                    break

            if not txt_name:
                raise ValueError("No .txt file found in WhatsApp export ZIP")

            # Zip-bomb guard (audit A4-H3): check uncompressed size first.
            _MAX_MEMBER_BYTES = 100 * 1024 * 1024  # 100 MB of chat text
            info = zf.getinfo(txt_name)
            if info.file_size > _MAX_MEMBER_BYTES:
                raise ValueError(
                    f"Chat export too large ({info.file_size // (1024*1024)} MB); "
                    f"max {_MAX_MEMBER_BYTES // (1024*1024)} MB"
                )

            with zf.open(txt_name) as f:
                lines = f.read().decode("utf-8", errors="replace").splitlines()

    except zipfile.BadZipFile as e:
        raise ValueError(f"Invalid ZIP file: {e}")

    # First pass: parse lines and collect senders
    parsed: list[tuple[datetime, str, str]] = []
    current_msg: tuple[datetime | None, str, str] | None = None

    for line in lines:
        match = WA_LINE_RE.match(line)
        if match:
            # Save previous message if exists
            if current_msg and current_msg[0] is not None:
                parsed.append(current_msg)  # type: ignore[arg-type]
                sender_counts[current_msg[1]] = sender_counts.get(current_msg[1], 0) + 1

            date_str, time_str, sender, content = match.groups()
            sender = sender.strip()
            timestamp = _parse_wa_timestamp(date_str, time_str)
            if timestamp:
                current_msg = (timestamp, sender, content)
            else:
                current_msg = None
        else:
            # Continuation line — append to current message
            if current_msg:
                current_msg = (current_msg[0], current_msg[1], current_msg[2] + "\n" + line)

    # Don't forget the last message
    if current_msg and current_msg[0] is not None:
        parsed.append(current_msg)  # type: ignore[arg-type]
        sender_counts[current_msg[1]] = sender_counts.get(current_msg[1], 0) + 1

    # Auto-detect page owner if not provided
    if page_owner_name is None:
        # Filter out system senders
        real_senders = {s: c for s, c in sender_counts.items() if s not in WA_SYSTEM_SENDERS}
        if real_senders:
            page_owner_name = max(real_senders, key=real_senders.get)

    # Second pass: normalize
    for timestamp, sender, content in parsed:
        if sender in WA_SYSTEM_SENDERS:
            continue

        # Skip media-only messages
        if content.strip() in ("<Media omitted>", "<media omitted>", "image omitted", "video omitted"):
            content = "(media)"

        role = "merchant" if sender == page_owner_name else "customer"

        messages.append({
            "channel": "whatsapp",
            "thread_title": "WhatsApp Chat",
            "sender": sender,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "message_type": "Generic",
            "reactions": [],
        })

    return messages


def stream_parse_whatsapp_zip(zip_bytes: bytes, batch_size: int = 500) -> Iterator[list[dict]]:
    """Stream-parse a WhatsApp export, yielding batches."""
    all_messages = parse_whatsapp_export_zip(zip_bytes)
    for i in range(0, len(all_messages), batch_size):
        yield all_messages[i : i + batch_size]
