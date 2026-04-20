#!/usr/bin/env python3
"""Issue a long-lived access token for Claude Team / Claude Code MCP connections.

Usage:
    MCP_JWT_SECRET=<secret> uv run scripts/issue_long_lived_token.py <email> [--days N]

Default: 365 days.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_exec.jwt_tokens import TokenIssuer

parser = argparse.ArgumentParser()
parser.add_argument("email", help="Email to embed in the token (must be in allowlist)")
parser.add_argument("--days", type=int, default=365, help="Token validity in days")
args = parser.parse_args()

secret = os.environ.get("MCP_JWT_SECRET")
if not secret:
    sys.exit("Error: MCP_JWT_SECRET env var is required")

ttl_s = args.days * 86400
issuer = TokenIssuer(secret=secret, issuer="mcp-exec-azzas", access_ttl_s=ttl_s, refresh_ttl_s=ttl_s)
token, exp = issuer._encode("access", args.email, ttl_s)

from datetime import datetime, timezone
exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc).strftime("%Y-%m-%d")
print(f"\nToken (valid until {exp_dt}):\n")
print(token)
print(f"\n--- Claude Code ---")
print(f'claude mcp add --transport sse bq-analista https://bq-analista-production.up.railway.app/mcp --header "Authorization: Bearer {token}"')
