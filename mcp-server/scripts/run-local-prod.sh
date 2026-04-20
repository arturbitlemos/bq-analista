#!/usr/bin/env bash
# Run mcp-exec-server locally with the full Azure AD flow (prod parity).
#
# Reads AZURE_* vars from ../.env.local (same source the frontend uses) and
# maps them to the MCP_AZURE_* vars the server expects.
#
# Usage: ./scripts/run-local-prod.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$HERE")"
REPO_ROOT="$(dirname "$SERVER_DIR")"

ENV_FILE="$REPO_ROOT/.env.local"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found" >&2
  exit 1
fi

# Load AZURE_* vars without exporting everything in the file.
# Values in .env.local may be quoted (`AZURE_FOO="bar"`) — strip surrounding quotes.
_read_env() {
  local key="$1"
  local line
  line=$(grep -E "^${key}=" "$ENV_FILE" | head -1 | cut -d= -f2-)
  line="${line%\"}"
  line="${line#\"}"
  line="${line%\'}"
  line="${line#\'}"
  printf '%s' "$line"
}
AZURE_CLIENT_ID=$(_read_env AZURE_CLIENT_ID)
AZURE_CLIENT_SECRET=$(_read_env AZURE_CLIENT_SECRET)
AZURE_TENANT_ID=$(_read_env AZURE_TENANT_ID)

for v in AZURE_CLIENT_ID AZURE_CLIENT_SECRET AZURE_TENANT_ID; do
  if [[ -z "${!v:-}" ]]; then
    echo "ERROR: $v missing in $ENV_FILE" >&2
    exit 1
  fi
done

export MCP_AZURE_CLIENT_ID="$AZURE_CLIENT_ID"
export MCP_AZURE_CLIENT_SECRET="$AZURE_CLIENT_SECRET"
export MCP_AZURE_TENANT_ID="$AZURE_TENANT_ID"
export MCP_AZURE_REDIRECT_URI="${MCP_AZURE_REDIRECT_URI:-http://localhost:8765/}"

# Persist JWT secret so tokens survive server restarts.
JWT_FILE="$SERVER_DIR/.mcp_jwt_secret"
if [[ ! -f "$JWT_FILE" ]]; then
  openssl rand -hex 32 > "$JWT_FILE"
  chmod 600 "$JWT_FILE"
fi
export MCP_JWT_SECRET="$(cat "$JWT_FILE")"

export MCP_SETTINGS="$SERVER_DIR/config/settings.toml"
export MCP_ALLOWLIST="$SERVER_DIR/config/allowed_execs.json"
export MCP_REPO_ROOT="$REPO_ROOT"
export MCP_GIT_PUSH="${MCP_GIT_PUSH:-1}"

echo "▶ mcp-exec-server (prod mode, local)"
echo "   tenant      : $MCP_AZURE_TENANT_ID"
echo "   client_id   : $MCP_AZURE_CLIENT_ID"
echo "   redirect_uri: $MCP_AZURE_REDIRECT_URI"
echo "   git push    : $MCP_GIT_PUSH"
echo ""

cd "$SERVER_DIR"
exec uv run mcp-exec-server
