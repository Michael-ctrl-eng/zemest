"""Security tests — hacker simulation.

These tests simulate real attack vectors:
- IDOR (Insecure Direct Object Reference)
- SQL injection
- JWT tampering (alg=none, algorithm confusion, expired, payload tampering)
- Prompt injection
- Rate-limit evasion
- SSRF (Server-Side Request Forgery)
- XSS (Cross-Site Scripting)

**Important:** These tests verify defenses. They must NOT actually break
the system — they assert that attacks are blocked (4xx, not 5xx) and that
no sensitive data is leaked.

Run independently:
    pytest tests/security/ -v
"""
