"""IP geolocation using MaxMind GeoLite2 (graceful fallback if not installed).

The MaxMind ``GeoLite2-City.mmdb`` file is **not** bundled with the app —
operators must download it from https://dev.maxmind.com/geoip/geolite2-free-
geolocation-database and place it at ``data/GeoLite2-City.mmdb`` (path
overridable via the ``GEOLITE2_DB`` env var).

If ``geoip2`` is not installed or the database file is missing, every
lookup returns ``None`` — callers must treat a None result as "unknown"
and skip geo-enrichment silently. This keeps the app fully functional
without geo support.

The reader is cached module-level (mmdb files are mmap'd; opening per
request would be wasteful).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Path to the GeoLite2-City database file. Override via env var.
GEOLITE2_DB = os.environ.get(
    "GEOLITE2_DB",
    os.path.join("data", "GeoLite2-City.mmdb"),
)

_reader = None  # cached geoip2 reader (or None if unavailable)
_reader_initialized = False


def _get_reader():
    """Return a cached geoip2 reader, or None if unavailable.

    Subsequent calls return the cached reader without re-opening the file.
    """
    global _reader, _reader_initialized
    if _reader_initialized:
        return _reader
    _reader_initialized = True
    try:
        import geoip2.database  # type: ignore
    except ImportError:
        logger.info("geoip2 not installed — geolocation disabled")
        return None
    if not os.path.exists(GEOLITE2_DB):
        logger.info("GeoLite2 DB not found at %s — geolocation disabled", GEOLITE2_DB)
        return None
    try:
        _reader = geoip2.database.Reader(GEOLITE2_DB)
        logger.info("GeoLite2 reader loaded from %s", GEOLITE2_DB)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to open GeoLite2 DB: %s", exc)
        _reader = None
    return _reader


def locate_ip(ip: str) -> Optional[dict]:
    """Geolocate an IP address.

    Returns a dict ``{country, country_code, city, lat, lon}`` or ``None``
    if the IP cannot be geolocated (private IP, geoip2 missing, DB missing,
    or address not in DB).
    """
    if not ip:
        return None

    # Quick reject for obviously non-geolocatable addresses.
    if ip in {"127.0.0.1", "::1", "localhost"} or ip.startswith("10.") \
            or ip.startswith("192.168.") or ip.startswith("172."):
        return None

    reader = _get_reader()
    if reader is None:
        return None

    try:
        resp = reader.city(ip)
        country = resp.country.name
        country_code = resp.country.iso_code
        city = resp.city.name
        lat = resp.location.latitude
        lon = resp.location.longitude
        return {
            "country": country,
            "country_code": country_code,
            "city": city,
            "lat": lat,
            "lon": lon,
        }
    except Exception as exc:  # noqa: BLE001 — geoip2 raises AddressNotFoundError
        # among others; we treat all as "could not geolocate".
        logger.debug("geoip2 lookup failed for %s: %s", ip, exc)
        return None


def detect_device_type(user_agent: str) -> str:
    """Cheap heuristic device classifier from a User-Agent string.

    Returns one of ``"mobile"``, ``"tablet"``, ``"desktop"``, ``"bot"``,
    or ``"unknown"``. No external deps.
    """
    if not user_agent:
        return "unknown"
    ua = user_agent.lower()
    if "bot" in ua or "crawler" in ua or "spider" in ua:
        return "bot"
    if "ipad" in ua or "tablet" in ua or "playbook" in ua:
        return "tablet"
    if (
        "mobile" in ua
        or "iphone" in ua
        or "android" in ua
        or "windows phone" in ua
        or "blackberry" in ua
    ):
        return "mobile"
    if "windows" in ua or "macintosh" in ua or "linux" in ua or "x11" in ua:
        return "desktop"
    return "unknown"


__all__ = ["locate_ip", "detect_device_type", "GEOLITE2_DB"]
