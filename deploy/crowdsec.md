# CrowdSec — edge protection for the Caddy topology

CrowdSec (MIT, very active) parses Caddy's JSON access log + journald,
evaluates community scenarios, and blocks attackers via a bouncer. The
app's in-app `ip_bans` + slowapi rate limiting stay as the inner layer —
this covers the edge.

## Install sketch (Debian/Ubuntu VPS)

```bash
sudo apt install crowdsec                       # official repo
sudo cscli collections install crowdsecurity/caddy
sudo cscli collections install crowdsecurity/sshd        # + whitelist your own IP!
sudo cscli bouncers add caddy-bouncer           # API key → Caddy module / firewall bouncer
```

Remediation options:
- **nftables firewall bouncer** (`crowdsec-firewall-bouncer` package) —
  blocks at the kernel level, before Caddy even accepts the connection.
- **Caddy-native bouncer module** (hslatman/caddy-crowdsec-bouncer, built
  with `xcaddy`) — 403s inside the proxy; pairs naturally with the JSON
  logging already configured in the Caddyfile.

Hub updates run via the systemd timer shipped with the package
(`cscli hub update && cscli hub upgrade`).

Memory: agent + LAPI ≈ 80–120 MB. Lean alternative if every MB counts:
fail2ban (~40–60 MB, needs a hand-written Caddy log filter, no shared
blocklist).
