#!/usr/bin/env bash
# Rebuild image, render plist with secrets from Keychain, reload launchd service.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_DIR="$SCRIPT_DIR/.."

echo "==> Building mcp-azzas:latest"
docker build -t mcp-azzas:latest "$MCP_DIR"

read_kc() {
  security find-generic-password -w -a mcp -s "$1" 2>/dev/null || {
    echo "missing Keychain entry: $1" >&2
    exit 1
  }
}

MCP_BQ_SA_KEY=$(read_kc bq_sa_key)
MCP_GITHUB_PAT=$(read_kc github_pat)
MCP_AZURE_TENANT_ID=$(read_kc azure_tenant_id)
MCP_AZURE_CLIENT_ID=$(read_kc azure_client_id)
MCP_AZURE_CLIENT_SECRET=$(read_kc azure_client_secret)
MCP_JWT_SECRET=$(read_kc jwt_secret)

TMP_PLIST=$(mktemp)
cp "$SCRIPT_DIR/launchd/com.azzas.mcp.plist" "$TMP_PLIST"
for k in MCP_BQ_SA_KEY MCP_GITHUB_PAT MCP_AZURE_TENANT_ID MCP_AZURE_CLIENT_ID MCP_AZURE_CLIENT_SECRET MCP_JWT_SECRET; do
  v=$(eval echo "\$$k")
  v_escaped=$(python3 -c "import sys,xml.sax.saxutils as x; print(x.escape(sys.argv[1]))" "$v")
  perl -0777 -i -pe "s/<key>$k<\\/key>\s*<string>__set_via_keychain_wrapper__<\\/string>/<key>$k<\\/key><string>$v_escaped<\\/string>/" "$TMP_PLIST"
done

DEST=~/Library/LaunchAgents/com.azzas.mcp.plist
launchctl unload "$DEST" 2>/dev/null || true
mv "$TMP_PLIST" "$DEST"
chmod 600 "$DEST"
launchctl load "$DEST"

echo "==> MCP loaded. Tail logs:"
echo "   tail -f /var/log/mcp/stderr.log"
