"""Scraper defense tests.

Simulates a malicious scraper trying to:
- Enumerate all products rapidly (100+ requests/sec)
- Extract all customer PII
- Bypass bot detection by rotating User-Agents
- Walk pagination to harvest the entire dataset

These tests verify rate-limiting and tenant isolation defenses work
under high-volume access patterns.

Run:
    pytest tests/scraper/ -v
"""
