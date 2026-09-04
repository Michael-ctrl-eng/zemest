"""Disposable / throwaway email detection for signup abuse prevention.

Product rule: a 7-day free trial is granted once per signup IP. Disposable
inboxes (10minutemail, mailinator, …) are the other classic trial-farming
vector, so registrations using them are refused (the register endpoint keeps
its uniform anti-enumeration 202 — the attacker learns nothing, the account
simply never exists).

The list is a compact curated set of the most-abused providers plus their
known alias domains. It is intentionally in-code (no runtime download — a
remote blocklist would be an availability and trust dependency for a signup
gate).
"""
from __future__ import annotations

import re

DISPOSABLE_DOMAINS: frozenset[str] = frozenset({
    # 10minutemail family
    "10minutemail.com", "10minutemail.net", "10minutemail.org",
    "20minutemail.com", "tempmail.com", "temp-mail.org", "temp-mail.io",
    "tempmailo.com", "tempmail.dev", "tempmail.plus", "tempmailo.net",
    # mailinator family
    "mailinator.com", "mailinator.net", "mailinator.org", "sogetthis.com",
    "spamherelots.com", "suremail.info", "binkmail.com", "bobmail.info",
    # guerrillamail family
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org",
    "guerrillamail.biz", "guerrillamailblock.com", "grr.la",
    "sharklasers.com", "guerrillamail.info", "pokemail.net",
    "spam4.me",
    # yopmail family
    "yopmail.com", "yopmail.net", "yopmail.fr", "yopmail.org",
    "cool.fr.nf", "jetable.fr.nf", "nospam.ze.tc", "nomail.xl.cx",
    # other well-known throwaways
    "throwawaymail.com", "throwawaymail.net", "maildrop.cc",
    "dispostable.com", "sharklasers.net", "fakeinbox.com",
    "mailnesia.com", "mailnull.com", "mytemp.email", "muellmail.com",
    "emailondeck.com", "getairmail.com", "getnada.com", "nada.email",
    "inboxbear.com", "tempinbox.com", "tmpmail.org", "tmpmail.net",
    "mohmal.com", "moakt.com", "tmail.ws", "tmails.net", "1secmail.com",
    "1secmail.org", "1secmail.net", "esiix.com", "wwjmp.com",
    "mail-temporaire.fr", "discard.email", "discardmail.com",
    "spambog.com", "spambog.de", "spambog.ru", "mailcatch.com",
    "trashmail.com", "trashmail.net", "trashmail.de", "trash-mail.com",
    "kurzepost.de", "objectmail.com", "proxymail.eu", "rcpt.at",
    "trash2009.com", "wegwerfmail.de", "wegwerfmail.net", "wegwerfmail.org",
    "incognitomail.com", "incognitomail.org", "incognitomail.net",
    "mailde.de", "mailde.info", "mail-beta.info", "inboxalias.com",
    "zetmail.com", "huskmail.info", "dodgeit.com", "gishpuppy.com",
    "mailexpire.com", "mail4temp.com", "mailquack.com", "mintemail.com",
    "notmailinator.com", "reallymymail.com", "sofort-mail.de",
    "trbvm.com", "vipmail.name", "vipsohu.net", "wolfmail.com.tw",
    "bezmail.com", "mail-temp.com", "linshiyouxiang.net",
    "maildehub.com", "mintemail.net", "mail-temporaire.com",
    # catch-all for common typos of the above
    "10minuteemail.com", "tempemail.net", "temporaryemail.net",
    "tempmailaddress.com", "fake-mail.net", "fakemailgenerator.com",
})

# Sanity: domains must be lowercase hostnames (no scheme, no @).
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def _domain_of(email: str) -> str:
    """Extract and validate the lowercase domain of an email address."""
    if not email or "@" not in email:
        return ""
    domain = email.rsplit("@", 1)[1].strip().lower().rstrip(".")
    return domain if _DOMAIN_RE.match(domain) else ""


def is_disposable_email(email: str | None) -> bool:
    """True when the email's domain is a known disposable provider.

    Never raises: malformed input is simply *not* disposable (the register
    endpoint's own validators reject malformed addresses anyway).
    """
    if not email:
        return False
    domain = _domain_of(email)
    if not domain:
        return False
    if domain in DISPOSABLE_DOMAINS:
        return True
    # Providers that serve subdomains (e.g. <anything>.mailinator.com)
    parts = domain.split(".")
    for i in range(1, len(parts)):
        if ".".join(parts[i:]) in DISPOSABLE_DOMAINS:
            return True
    return False


__all__ = ["DISPOSABLE_DOMAINS", "is_disposable_email"]
