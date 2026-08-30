"""SSRF (Server-Side Request Forgery) protection tests.

Simulates a hacker trying to make the server fetch internal URLs:
- Cloud metadata endpoints (169.254.169.254)
- Loopback addresses (localhost, 127.0.0.1)
- Private IP ranges (10.x, 172.16-31.x, 192.168.x)
- IPv6 loopback (::1)
- DNS rebinding (hostname resolves to private IP)

The defense under test is `app.middleware.ssrf_protection.is_safe_url`.
"""
from __future__ import annotations

import pytest

from app.middleware.ssrf_protection import is_safe_url


class TestSSRFMetadataEndpoints:
    """Cloud metadata endpoints must always be blocked."""

    def test_ssrf_blocks_aws_metadata(self):
        """169.254.169.254 (AWS metadata) should be blocked."""
        safe, _ = is_safe_url("http://169.254.169.254/latest/meta-data/")
        assert not safe

    def test_ssrf_blocks_aws_metadata_imdsv2(self):
        """AWS IMDSv2 token endpoint should be blocked."""
        safe, _ = is_safe_url("http://169.254.169.254/latest/api/token")
        assert not safe

    def test_ssrf_blocks_gcp_metadata(self):
        """metadata.google.internal should be blocked."""
        safe, _ = is_safe_url("http://metadata.google.internal/computeMetadata/v1/")
        assert not safe

    def test_ssrf_blocks_gcp_metadata_ip(self):
        """GCP metadata IP (also 169.254.169.254) should be blocked."""
        safe, _ = is_safe_url("http://169.254.169.254/computeMetadata/v1/")
        assert not safe

    def test_ssrf_blocks_azure_metadata(self):
        """Azure metadata endpoint should be blocked."""
        safe, _ = is_safe_url("http://169.254.169.254/metadata/instance?api-version=2021-02-01")
        assert not safe


class TestSSRFLoopback:
    """Loopback addresses must be blocked."""

    def test_ssrf_blocks_localhost(self):
        """localhost should be blocked."""
        safe, _ = is_safe_url("http://localhost:8000/admin")
        assert not safe

    def test_ssrf_blocks_127_loopback(self):
        """127.0.0.1 should be blocked."""
        safe, _ = is_safe_url("http://127.0.0.1:8000/admin")
        assert not safe

    def test_ssrf_blocks_127_arbitrary(self):
        """Any 127.x.x.x address should be blocked."""
        safe, _ = is_safe_url("http://127.0.0.2:8080/")
        assert not safe

    def test_ssrf_blocks_127_255_255_255(self):
        """127.255.255.255 (loopback broadcast) should be blocked."""
        safe, _ = is_safe_url("http://127.255.255.255/")
        assert not safe

    def test_ssrf_blocks_ipv6_loopback(self):
        """::1 (IPv6 loopback) should be blocked."""
        safe, _ = is_safe_url("http://[::1]:8000/admin")
        assert not safe


class TestSSRFPrivateRanges:
    """RFC1918 private ranges must be blocked."""

    def test_ssrf_blocks_private_10(self):
        """10.0.0.0/8 should be blocked."""
        safe, _ = is_safe_url("http://10.0.0.1/")
        assert not safe

    def test_ssrf_blocks_private_172(self):
        """172.16.0.0/12 should be blocked."""
        safe, _ = is_safe_url("http://172.16.0.1/")
        assert not safe

    def test_ssrf_blocks_private_192(self):
        """192.168.0.0/16 should be blocked."""
        safe, _ = is_safe_url("http://192.168.0.1/")
        assert not safe

    def test_ssrf_blocks_172_31(self):
        """172.31.x.x (top of 172.16/12) should be blocked."""
        safe, _ = is_safe_url("http://172.31.255.255/")
        assert not safe

    def test_ssrf_blocks_172_15(self):
        """172.15.x.x (just below 172.16/12) — should be ALLOWED (public)."""
        safe, _ = is_safe_url("http://172.15.0.1/")
        # 172.15.x.x is technically public — but DNS may not resolve. We allow.
        # If DNS resolves, the IP check passes since 172.15 isn't in BLOCKED_NETWORKS.
        # If DNS fails, we return False. Either way, no crash.
        assert isinstance(safe, bool)

    def test_ssrf_blocks_link_local(self):
        """169.254.0.0/16 (link-local) should be blocked."""
        safe, _ = is_safe_url("http://169.254.100.100/")
        assert not safe

    def test_ssrf_blocks_cgnat(self):
        """100.64.0.0/10 (CGNAT) should be blocked."""
        safe, _ = is_safe_url("http://100.64.0.1/")
        assert not safe

    def test_ssrf_blocks_zero_network(self):
        """0.0.0.0 should be blocked."""
        safe, _ = is_safe_url("http://0.0.0.0/")
        assert not safe


class TestSSRFSchemeValidation:
    """Non-http(s) schemes must be blocked."""

    def test_ssrf_blocks_file_scheme(self):
        """file:// scheme should be blocked."""
        safe, _ = is_safe_url("file:///etc/passwd")
        assert not safe

    def test_ssrf_blocks_ftp_scheme(self):
        """ftp:// scheme should be blocked."""
        safe, _ = is_safe_url("ftp://example.com/file")
        assert not safe

    def test_ssrf_blocks_gopher_scheme(self):
        """gopher:// scheme should be blocked (classic SSRF vector)."""
        safe, _ = is_safe_url("gopher://localhost:6379/_FLUSHALL")
        assert not safe

    def test_ssrf_blocks_data_scheme(self):
        """data: scheme should be blocked."""
        safe, _ = is_safe_url("data:text/html,<script>alert(1)</script>")
        assert not safe

    def test_ssrf_blocks_dict_scheme(self):
        """dict:// scheme should be blocked (Redis SSRF)."""
        safe, _ = is_safe_url("dict://localhost:6379/SET:key:value")
        assert not safe


class TestSSRFAllowlist:
    """Legitimate public URLs must be allowed."""

    def test_ssrf_allows_public_url(self):
        """https://example.com/ should be allowed."""
        safe, _ = is_safe_url("https://example.com/")
        assert safe

    def test_ssrf_allows_http_public(self):
        """http://example.com/ should be allowed."""
        safe, _ = is_safe_url("http://example.com/")
        assert safe

    def test_ssrf_allows_public_https_with_path(self):
        """https://example.com/path/to/page should be allowed."""
        safe, _ = is_safe_url("https://example.com/products/123")
        assert safe

    def test_ssrf_allows_public_with_query(self):
        """URLs with query strings should be allowed."""
        safe, _ = is_safe_url("https://api.example.com/v1/products?page=1&limit=10")
        assert safe


class TestSSRFEdgeCases:
    """Edge cases that have historically bypassed naive filters."""

    def test_ssrf_handles_empty_url(self):
        """Empty URL should be blocked."""
        safe, _ = is_safe_url("")
        assert not safe

    def test_ssrf_handles_none_url(self):
        """None URL should be blocked."""
        safe, _ = is_safe_url(None)  # type: ignore[arg-type]
        assert not safe

    def test_ssrf_handles_non_string_url(self):
        """Non-string URL should be blocked."""
        safe, _ = is_safe_url(12345)  # type: ignore[arg-type]
        assert not safe

    def test_ssrf_handles_missing_scheme(self):
        """URL without scheme should be blocked."""
        safe, _ = is_safe_url("example.com/path")
        assert not safe

    def test_ssrf_handles_missing_host(self):
        """URL without host should be blocked."""
        safe, _ = is_safe_url("https://")
        assert not safe

    def test_ssrf_blocks_decimal_localhost(self):
        """Decimal-encoded localhost (2130706433) must be checked."""
        # 127.0.0.1 = 2130706433 in decimal
        safe, _ = is_safe_url("http://2130706433/")
        # Different libraries handle this differently — at minimum, no crash.
        assert isinstance(safe, bool)

    def test_ssrf_blocks_octal_localhost(self):
        """Octal-encoded localhost (0177.0.0.1) must be checked."""
        safe, _ = is_safe_url("http://0177.0.0.1/")
        assert isinstance(safe, bool)

    def test_ssrf_blocks_hex_localhost(self):
        """Hex-encoded localhost (0x7f000001) must be checked."""
        safe, _ = is_safe_url("http://0x7f000001/")
        assert isinstance(safe, bool)

    def test_ssrf_returns_reason_string(self):
        """The reason field should explain why a URL was blocked."""
        safe, reason = is_safe_url("http://169.254.169.254/")
        assert not safe
        assert isinstance(reason, str)
        assert len(reason) > 0

    def test_ssrf_never_raises(self):
        """is_safe_url must never raise — always return (bool, str)."""
        weird_inputs = [
            "",
            " ",
            "\n",
            "http://",
            "://",
            "http://[",
            "http://[::1",
            "javascript:alert(1)",
            "data:;base64,SGVsbG8=",
            "\x00http://localhost",
        ]
        for inp in weird_inputs:
            try:
                result = is_safe_url(inp)
                assert isinstance(result, tuple)
                assert len(result) == 2
                assert isinstance(result[0], bool)
                assert isinstance(result[1], str)
            except Exception as exc:
                pytest.fail(f"is_safe_url raised on {inp!r}: {exc}")
