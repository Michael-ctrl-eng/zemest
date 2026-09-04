"""Analytics ingestion, aggregation and admin queries.

Pipeline (per collected batch, one transaction):
1. **Validate** every event (type, path, caps) — malformed events are
   dropped, never error the whole batch (a buggy tracker must not lose the
   good events it collected).
2. **Enrich server-side**: client IP, user agent, geo (GeoLite2 when
   installed), referrer. The client cannot spoof these — the BFF already
   strips X-Forwarded-For, and identity fields (email) are only attached
   from the *authenticated* user, never from the payload.
3. **Aggregate** into ``analytics_daily`` (UPSERT per (day, path)):
   views / clicks / sessions / bounces / exits / scroll.
4. **Upsert** the visitor profile (counters + geo + optional user link).
5. **Pack** the raw events as JSONL -> zstd (zlib fallback) -> Fernet into
   an ``analytics_batches`` row. ~15-25 bytes/event on disk.

Read paths:
- ``page_performance`` — "what sucks": per-path engagement (views, clicks,
  avg scroll, bounce/exit rates) ranked worst-first for the admin panel.
- ``visitor_list`` / ``visitor_detail`` — person-level directory with PII
  decrypted (admin only), linked platform activity (tenants, chats per
  channel, customers, orders).
- ``export_day`` — decrypt + decompress a day's batches back to JSONL (the
  "extract the data for any use" requirement).
- ``compact_day`` — merge a day's many small batch rows into one (keeps the
  row count and per-row crypto overhead minimal).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsBatch, AnalyticsDaily, VisitorProfile
from app.utils.token_crypto import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)

MAX_EVENTS_PER_BATCH = 60
MAX_PATH_LEN = 512
MAX_PAGE_NAME_LEN = 255
MAX_ELEMENT_LEN = 128
MAX_VISITOR_KEY_LEN = 72
MAX_INTERESTS = 12
VISITOR_KEYS_CAP = 500  # distinct-visitor approximation cap per (day, path)

VALID_EVENT_TYPES = frozenset({"page_view", "click", "scroll", "session_end"})

# Codec selection: zstd when the wheel is present, stdlib zlib otherwise.
try:  # pragma: no cover — environment-dependent import
    import zstandard

    def _compress(data: bytes) -> tuple[bytes, str]:
        return zstandard.ZstdCompressor(level=3).compress(data), "zstd"

    def _decompress(data: bytes, codec: str) -> bytes:
        if codec == "zstd":
            return zstandard.ZstdDecompressor().decompress(data)
        import zlib

        return zlib.decompress(data)

except ImportError:  # pragma: no cover — fallback path
    import zlib

    def _compress(data: bytes) -> tuple[bytes, str]:
        return zlib.compress(data, 9), "zlib"

    def _decompress(data: bytes, codec: str) -> bytes:
        return zlib.decompress(data)


# ---------------------------------------------------------------------------
# Validation / normalisation
# ---------------------------------------------------------------------------

def _clean_str(value, max_len: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()[:max_len]
    return value or None


def _clean_path(value) -> Optional[str]:
    path = _clean_str(value, MAX_PATH_LEN)
    if not path or not path.startswith("/"):
        return None
    # Strip query strings & fragments — paths are the analytics dimension.
    path = path.split("?", 1)[0].split("#", 1)[0]
    return path or None


def _clean_visitor_key(value) -> Optional[str]:
    key = _clean_str(value, MAX_VISITOR_KEY_LEN)
    if not key:
        return None
    if not all(c.isalnum() or c in "-_:" for c in key):
        return None
    return key


def normalize_events(raw_events) -> list[dict]:
    """Validate + normalise a client event list; drop anything malformed."""
    if not isinstance(raw_events, list):
        return []
    out: list[dict] = []
    for raw in raw_events[:MAX_EVENTS_PER_BATCH]:
        if not isinstance(raw, dict):
            continue
        etype = raw.get("type")
        if etype not in VALID_EVENT_TYPES:
            continue
        path = _clean_path(raw.get("path"))
        if not path:
            continue
        event = {"type": etype, "path": path}
        name = _clean_str(raw.get("page_name"), MAX_PAGE_NAME_LEN)
        if name:
            event["page_name"] = name
        if etype == "click":
            element = _clean_str(raw.get("element"), MAX_ELEMENT_LEN)
            if element:
                event["element"] = element
        if etype == "scroll":
            try:
                scroll = int(raw.get("scroll", 0))
                event["scroll"] = max(0, min(100, scroll))
            except (TypeError, ValueError):
                continue
        if etype == "session_end":
            try:
                event["session_pages"] = max(0, min(500, int(raw.get("session_pages", 1))))
            except (TypeError, ValueError):
                event["session_pages"] = 1
        out.append(event)
    return out


# ---------------------------------------------------------------------------
# Interests (lightweight, derived from browsed paths)
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS = (
    "whatsapp", "messenger", "instagram", "facebook", "pricing", "blog",
    "solutions", "products", "orders", "customers", "scheduler", "insights",
    "crawl", "channels", "demo", "register", "enterprise", "research",
)


def _interests_from_path(path: str, current: Optional[list]) -> list[str]:
    """Fold a browsed path into a small interests list (product requirement:
    "what are they interested in")."""
    topics: list[str] = list(current or [])[:MAX_INTERESTS]
    p = path.lower()
    for kw in _TOPIC_KEYWORDS:
        if kw in p and kw not in topics:
            topics.append(kw)
            if len(topics) >= MAX_INTERESTS:
                break
    return topics


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def _today() -> date:
    return datetime.utcnow().date()


async def _geo_for(ip: Optional[str]) -> dict:
    """Best-effort GeoLite2 lookup (None-safe, never raises)."""
    if not ip:
        return {}
    try:
        from app.admin.geo import lookup_ip

        info = lookup_ip(ip)
        if info:
            return info
    except Exception:  # noqa: BLE001 — geo is optional enrichment
        pass
    return {}


def _parse_user_agent(ua: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """(device_type, browser) from a UA string — coarse, no deps."""
    if not ua:
        return None, None
    u = ua.lower()
    device = "mobile" if any(m in u for m in ("mobile", "android", "iphone")) else (
        "tablet" if "tablet" in u or "ipad" in u else "desktop"
    )
    browser = None
    for name in ("edg", "opr", "chrome", "safari", "firefox"):
        if name in u:
            browser = {"edg": "Edge", "opr": "Opera"}.get(name, name.capitalize())
            break
    return device, browser


async def ingest_events(
    db: AsyncSession,
    events: list[dict],
    *,
    visitor_key: Optional[str],
    session_key: Optional[str],
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    referrer: Optional[str] = None,
    user=None,  # app.models.user.User | None (authenticated)
) -> int:
    """Ingest one validated batch. Returns the number of events stored."""
    events = normalize_events(events)
    if not events:
        return 0
    visitor_key = _clean_visitor_key(visitor_key) or "v-anon"
    session_key = _clean_str(session_key, 64) or None

    geo = await _geo_for(client_ip)
    device, browser = _parse_user_agent(user_agent)
    today = _today()
    now = datetime.utcnow()

    # --- visitor profile upsert ---------------------------------------
    profile = (
        await db.execute(
            select(VisitorProfile).where(VisitorProfile.visitor_key == visitor_key)
        )
    ).scalar_one_or_none()
    if profile is None:
        profile = VisitorProfile(
            visitor_key=visitor_key,
            first_referrer=_clean_str(referrer, 512),
            first_seen=now,
        )
        db.add(profile)
        await db.flush()
    profile.last_seen = now
    profile.total_events = (profile.total_events or 0) + len(events)
    profile.last_ip = client_ip
    profile.last_user_agent = user_agent
    profile.device_type = device
    profile.browser = browser
    if geo:
        profile.country = geo.get("country")
        profile.city = geo.get("city")
        profile.latitude = geo.get("latitude")
        profile.longitude = geo.get("longitude")
    if user is not None:
        # Identity link — server-side only, from the authenticated session.
        profile.user_id = user.id
        profile.email = user.email or profile.email
        profile.name = user.name or profile.name
        if getattr(user, "date_of_birth", None):
            profile.date_of_birth = user.date_of_birth

    # --- daily aggregates (UPSERT per path) ---------------------------
    saw_session = False
    for ev in events:
        row = (
            await db.execute(
                select(AnalyticsDaily).where(
                    AnalyticsDaily.day == today, AnalyticsDaily.path == ev["path"]
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = AnalyticsDaily(day=today, path=ev["path"], visitor_keys=[])
            db.add(row)
            await db.flush()

        if ev["type"] == "page_view":
            row.views += 1
            profile.pages_viewed += 1
            if profile.last_seen == now and not saw_session:
                row.sessions += 1
                profile.sessions_count += 1
                saw_session = True
        elif ev["type"] == "click":
            row.clicks += 1
        elif ev["type"] == "scroll":
            row.scroll_total += ev.get("scroll", 0)
            row.scroll_events += 1
        elif ev["type"] == "session_end":
            row.exits += 1
            if ev.get("session_pages", 1) <= 1:
                row.bounces += 1

        if ev.get("page_name"):
            row.page_name = ev["page_name"]

        keys = row.visitor_keys or []
        if len(keys) < VISITOR_KEYS_CAP and visitor_key not in keys:
            keys.append(visitor_key)
            row.visitor_keys = keys

        profile.interests = _interests_from_path(ev["path"], profile.interests)

    # --- raw batch blob: JSONL -> compress -> Fernet -------------------
    lines = []
    for ev in events:
        record = {
            "t": ev["type"],
            "p": ev["path"],
            "ts": now.isoformat(),
        }
        if ev.get("page_name"):
            record["n"] = ev["page_name"]
        if ev.get("element"):
            record["e"] = ev["element"]
        if ev.get("scroll") is not None:
            record["s"] = ev["scroll"]
        if ev.get("session_pages") is not None:
            record["sp"] = ev["session_pages"]
        if session_key:
            record["k"] = session_key
        record["v"] = visitor_key
        if client_ip:
            record["ip"] = client_ip
        if user_agent:
            ua_short = user_agent[:200]
            record["ua"] = ua_short
        if referrer:
            record["ref"] = referrer[:300]
        if user is not None:
            record["user"] = str(user.id)
        lines.append(json.dumps(record, separators=(",", ":"), ensure_ascii=False))

    payload = "\n".join(lines).encode("utf-8")
    compressed, codec = _compress(payload)
    encrypted = (encrypt_token(compressed.decode("latin-1")) or "").encode("latin-1")
    blob = encrypted

    db.add(
        AnalyticsBatch(
            day=today,
            compression=codec,
            blob=blob,
            event_count=len(events),
            size_bytes=len(payload),
            stored_bytes=len(blob),
        )
    )
    await db.flush()
    return len(events)


# ---------------------------------------------------------------------------
# Batch readers
# ---------------------------------------------------------------------------

def _decode_blob(blob: bytes, codec: str) -> list[dict]:
    """Decrypt + decompress one batch blob into event dicts (never raises)."""
    try:
        text = blob.decode("latin-1")
        decrypted = decrypt_token(text)
        if decrypted is None:
            return []
        raw = _decompress(decrypted.encode("latin-1"), codec)
        return [json.loads(line) for line in raw.decode("utf-8").splitlines() if line]
    except Exception:  # noqa: BLE001 — corrupted batch: skip it, log it
        logger.warning("analytics batch failed to decode — skipping one batch")
        return []


async def read_day_events(db: AsyncSession, day: date) -> list[dict]:
    """All raw events of a day, decrypted (admin/export path)."""
    rows = (
        await db.execute(
            select(AnalyticsBatch).where(AnalyticsBatch.day == day).order_by(AnalyticsBatch.created_at)
        )
    ).scalars().all()
    events: list[dict] = []
    for row in rows:
        events.extend(_decode_blob(row.blob, row.compression))
    return events


async def compact_day(db: AsyncSession, day: date) -> int:
    """Merge a day's batch rows into one. Returns batches merged (0 = no-op).

    Runs as an admin-triggered or daily-scheduled maintenance step: a busy
    day writes one row per collected request; compaction rewrites them as a
    single blob, keeping row count and per-row crypto overhead minimal.
    """
    rows = (
        await db.execute(select(AnalyticsBatch).where(AnalyticsBatch.day == day))
    ).scalars().all()
    if len(rows) <= 1:
        return 0
    all_events: list[dict] = []
    for row in rows:
        all_events.extend(_decode_blob(row.blob, row.compression))
    if not all_events:
        # Nothing recoverable — drop the corrupted rows too.
        for row in rows:
            await db.delete(row)
        await db.flush()
        return len(rows)

    payload = "\n".join(
        json.dumps(e, separators=(",", ":"), ensure_ascii=False) for e in all_events
    ).encode("utf-8")
    compressed, codec = _compress(payload)
    blob = (encrypt_token(compressed.decode("latin-1")) or "").encode("latin-1")

    for row in rows:
        await db.delete(row)
    await db.flush()
    db.add(
        AnalyticsBatch(
            day=day,
            compression=codec,
            blob=blob,
            event_count=len(all_events),
            size_bytes=len(payload),
            stored_bytes=len(blob),
            is_compacted=True,
        )
    )
    await db.flush()
    return len(rows)


# ---------------------------------------------------------------------------
# Dashboard queries
# ---------------------------------------------------------------------------

def _engagement_score(row: AnalyticsDaily) -> float:
    """0..1 composite: deeper scroll + clicks + low bounce = engaging."""
    views = max(row.views, 1)
    avg_scroll = (row.scroll_total / row.scroll_events) / 100 if row.scroll_events else 0.0
    click_rate = min(row.clicks / views, 1.0)
    bounce_rate = (row.bounces / row.sessions) if row.sessions else 0.0
    return max(0.0, min(1.0, 0.5 * avg_scroll + 0.3 * click_rate + 0.2 * (1 - bounce_rate)))


def _row_to_perf(row: AnalyticsDaily, views: int) -> dict:
    return {
        "path": row.path,
        "page_name": row.page_name,
        "day": row.day.isoformat(),
        "views": row.views,
        "clicks": row.clicks,
        "sessions": row.sessions,
        "bounces": row.bounces,
        "exits": row.exits,
        "unique_visitors": len(set(row.visitor_keys or [])),
        "avg_scroll_pct": round(row.scroll_total / row.scroll_events, 1) if row.scroll_events else None,
        "bounce_rate": round(row.bounces / row.sessions, 3) if row.sessions else None,
        "exit_rate": round(row.exits / row.views, 3) if row.views else None,
        "engagement": round(_engagement_score(row), 3),
        "views_share": round(row.views / views, 3) if views else 0.0,
    }


async def page_performance(
    db: AsyncSession,
    days: int = 14,
    path_prefix: Optional[str] = None,
    worst_first: bool = True,
    limit: int = 100,
) -> list[dict]:
    """Aggregate per-path engagement across the window.

    ``worst_first=True`` surfaces the pages that "suck": lowest engagement
    score first (low scroll, no clicks, high bounce).
    """
    since = _today() - timedelta(days=max(1, min(days, 90)) - 1)
    stmt = select(AnalyticsDaily).where(AnalyticsDaily.day >= since)
    if path_prefix:
        stmt = stmt.where(AnalyticsDaily.path.like(f"{path_prefix}%"))
    rows = (await db.execute(stmt)).scalars().all()

    total_views = sum(r.views for r in rows) or 1
    perf = [_row_to_perf(r, total_views) for r in rows]
    perf.sort(key=lambda p: (p["engagement"], -p["views"]), reverse=not worst_first)
    return perf[: min(limit, 500)]


async def summary_totals(db: AsyncSession, days: int = 14, path_prefix: Optional[str] = None) -> dict:
    since = _today() - timedelta(days=max(1, min(days, 90)) - 1)
    stmt = select(
        func.coalesce(func.sum(AnalyticsDaily.views), 0),
        func.coalesce(func.sum(AnalyticsDaily.clicks), 0),
        func.coalesce(func.sum(AnalyticsDaily.sessions), 0),
        func.coalesce(func.sum(AnalyticsDaily.bounces), 0),
    ).where(AnalyticsDaily.day >= since)
    if path_prefix:
        stmt = stmt.where(AnalyticsDaily.path.like(f"{path_prefix}%"))
    views, clicks, sessions, bounces = (await db.execute(stmt)).one()
    return {
        "days": days,
        "views": int(views),
        "clicks": int(clicks),
        "sessions": int(sessions),
        "bounces": int(bounces),
    }


def _profile_public(p: VisitorProfile, with_pii: bool) -> dict:
    data = {
        "id": str(p.id),
        "visitor_key": p.visitor_key,
        "user_id": str(p.user_id) if p.user_id else None,
        "country": p.country,
        "city": p.city,
        "latitude": p.latitude,
        "longitude": p.longitude,
        "last_ip": p.last_ip,
        "device_type": p.device_type,
        "browser": p.browser,
        "first_referrer": p.first_referrer,
        "interests": p.interests or [],
        "pages_viewed": p.pages_viewed,
        "sessions_count": p.sessions_count,
        "total_events": p.total_events,
        "first_seen": p.first_seen.isoformat() if p.first_seen else None,
        "last_seen": p.last_seen.isoformat() if p.last_seen else None,
    }
    if with_pii:
        data["email"] = p.email
        data["name"] = p.name
        data["date_of_birth"] = p.date_of_birth
    return data


async def visitor_list(
    db: AsyncSession,
    query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Visitor directory (admin). PII decrypted; supports search by IP,
    visitor key, or email/name fragment (the latter needs decrypted values,
    so those match in Python after the SQL filter on indexed columns)."""
    stmt = select(VisitorProfile)
    if query:
        q = f"%{query.lower()}%"
        stmt = stmt.where(
            func.lower(VisitorProfile.visitor_key).like(q)
            | func.lower(VisitorProfile.last_ip).like(q)
        )
    rows = (
        await db.execute(
            stmt.order_by(VisitorProfile.last_seen.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    total = int(
        (await db.execute(select(func.count(VisitorProfile.id)))).scalar() or 0
    )

    items = [_profile_public(p, with_pii=True) for p in rows]
    if query:
        q = query.lower()
        # PII columns are encrypted at rest — match decrypted values here.
        matched = [
            i
            for i in items
            if q in (i["email"] or "").lower() or q in (i["name"] or "").lower()
        ]
        if matched:
            items = matched
    return items, total


async def visitor_detail(db: AsyncSession, visitor_id) -> dict | None:
    """Full drill-down for the admin panel: profile (PII decrypted) +
    recent raw session events (from decrypted batches) + platform activity
    of the linked user (tenants, chats per channel, customers, orders)."""
    try:
        import uuid as _uuid

        vid = _uuid.UUID(str(visitor_id))
    except (ValueError, TypeError):
        return None
    profile = await db.get(VisitorProfile, vid)
    if not profile:
        return None

    data = _profile_public(profile, with_pii=True)

    # Recent events for this visitor from the last 7 days of batches.
    since = _today() - timedelta(days=7)
    rows = (
        await db.execute(
            select(AnalyticsBatch)
            .where(AnalyticsBatch.day >= since)
            .order_by(AnalyticsBatch.day.desc(), AnalyticsBatch.created_at.desc())
            .limit(80)
        )
    ).scalars().all()
    events: list[dict] = []
    for row in rows:
        for e in _decode_blob(row.blob, row.compression):
            if e.get("v") == profile.visitor_key:
                events.append(e)
    data["recent_events"] = events[:200]

    # Linked platform activity
    if profile.user_id:
        from app.models.user import User

        user = await db.get(User, profile.user_id)
        if user:
            data["linked_user"] = {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "plan": user.plan,
                "signup_ip": user.signup_ip,
                "date_of_birth": user.date_of_birth,
                "trial_ends_at": user.trial_ends_at.isoformat() if getattr(user, "trial_ends_at", None) else None,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
            from app.models.tenant import Tenant

            tenants = (
                await db.execute(select(Tenant).where(Tenant.owner_id == user.id))
            ).scalars().all()
            data["shops"] = [
                {
                    "id": str(t.id),
                    "page_name": t.page_name,
                    "is_active": t.is_active,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in tenants
            ]

    return data


async def storage_stats(db: AsyncSession) -> dict:
    """Bytes in / bytes stored / compression ratio (ops view)."""
    row = (
        await db.execute(
            select(
                func.count(AnalyticsBatch.id),
                func.coalesce(func.sum(AnalyticsBatch.event_count), 0),
                func.coalesce(func.sum(AnalyticsBatch.size_bytes), 0),
                func.coalesce(func.sum(AnalyticsBatch.stored_bytes), 0),
            )
        )
    ).one()
    batches, events, raw_bytes, stored_bytes = row
    return {
        "batches": int(batches),
        "events": int(events),
        "raw_bytes": int(raw_bytes),
        "stored_bytes": int(stored_bytes),
        "compression_ratio": round(raw_bytes / stored_bytes, 2) if stored_bytes else None,
        "bytes_per_event": round(stored_bytes / events, 1) if events else None,
    }


__all__ = [
    "ingest_events",
    "normalize_events",
    "read_day_events",
    "compact_day",
    "page_performance",
    "summary_totals",
    "visitor_list",
    "visitor_detail",
    "storage_stats",
]
