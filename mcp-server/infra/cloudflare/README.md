# Cloudflare Tunnel setup

1. Install `cloudflared` on the Mac mini: `brew install cloudflared`.
2. Authenticate: `cloudflared tunnel login` → browser flow.
3. Create tunnel: `cloudflared tunnel create mcp-azzas` (writes credentials JSON).
4. Copy `config.yml.example` → `~/.cloudflared/config.yml`, fill `<TUNNEL_ID>` and hostname.
5. DNS: `cloudflared tunnel route dns mcp-azzas mcp-azzas.<corp-domain>`.
6. Run as launchd service: `sudo cloudflared service install`.
7. In Cloudflare dashboard → Access → create application for this hostname, restrict by issuer/domain. Rate-limit 100/min per IP.

## WAF rules

Add a WAF rule: allow only `user-agent contains "Claude"` OR requests coming from `claude.ai` in the `Origin` header. This blocks direct scraping of the public URL.
