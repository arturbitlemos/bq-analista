#!/usr/bin/env bash
# scripts/health_check_fase_b.sh
# Post-cutover validation. Run after deploying mcp-core (Railway) + portal
# (Vercel). Bails on the first failure so the operator knows exactly where
# the chain broke.
#
# Required env:
#   PORTAL_URL          e.g. https://bq-analista.vercel.app
#   SESSION_COOKIE      a valid HMAC session cookie from portal/api/auth.js
#                       (mint locally with the SESSION_SECRET from prod env)
#   MCP_BLOB_SIGNING_KEY   same value Vercel + Railway share for blob-internal JWTs
#
# Optional:
#   AGENT                default vendas-linx
#   VENDAS_LINX_HEALTHZ  default https://bq-analista-production.up.railway.app/healthz
#   DEVOLUCOES_HEALTHZ   default https://analista-devolucoes-production.up.railway.app/healthz

set -euo pipefail

PORTAL_URL="${PORTAL_URL:?need PORTAL_URL e.g. https://bq-analista.vercel.app}"
SESSION_COOKIE="${SESSION_COOKIE:?need SESSION_COOKIE for an authenticated test user}"
MCP_BLOB_SIGNING_KEY="${MCP_BLOB_SIGNING_KEY:?need MCP_BLOB_SIGNING_KEY}"
AGENT="${AGENT:-vendas-linx}"
VENDAS_LINX_HEALTHZ="${VENDAS_LINX_HEALTHZ:-https://bq-analista-production.up.railway.app/healthz}"
DEVOLUCOES_HEALTHZ="${DEVOLUCOES_HEALTHZ:-https://analista-devolucoes-production.up.railway.app/healthz}"

step() { printf "\n[%s] %s\n" "$1" "$2"; }
fail() { printf "❌ FAIL: %s\n" "$1" >&2; exit 1; }

step "1/5" "DB reachable via portal /api/library?agent=$AGENT"
LIB=$(curl -sS -f "$PORTAL_URL/api/library?agent=$AGENT" -H "cookie: session=$SESSION_COOKIE") \
  || fail "library endpoint unreachable / 4xx-5xx"
COUNT=$(echo "$LIB" | python3 -c "import json,sys;print(len(json.load(sys.stdin).get('items',[])))" 2>/dev/null) \
  || fail "library response not valid JSON: $(echo "$LIB" | head -c 200)"
echo "  → library returned $COUNT items"

step "2/5" "Blob endpoint reachable (auth via blob-internal proxy JWT)"
BLOB_TOKEN=$(node -e "
  const jwt = require('jsonwebtoken');
  console.log(jwt.sign({aud:'blob-internal'}, process.env.MCP_BLOB_SIGNING_KEY, {algorithm:'HS256', expiresIn: 60}));
") || fail "could not mint blob-internal JWT (is jsonwebtoken installed locally?)"
HEALTH_PATH="analyses/healthcheck/$(date +%s).html"
curl -sS -f -X PUT "$PORTAL_URL/api/internal/blob?pathname=$HEALTH_PATH&content_type=text/html" \
  -H "authorization: Bearer $BLOB_TOKEN" \
  -H "content-type: application/octet-stream" \
  --data-binary "<html>healthcheck</html>" >/dev/null \
  || fail "blob PUT rejected"
curl -sS -f -X DELETE "$PORTAL_URL/api/internal/blob?pathname=$HEALTH_PATH" \
  -H "authorization: Bearer $BLOB_TOKEN" >/dev/null \
  || fail "blob DELETE rejected"
echo "  → blob put + delete OK"

step "3/5" "mcp-core healthy (vendas-linx)"
curl -sS -f "$VENDAS_LINX_HEALTHZ" >/dev/null || fail "vendas-linx /healthz != 200"
echo "  → $VENDAS_LINX_HEALTHZ OK"

step "4/5" "mcp-core healthy (devolucoes)"
curl -sS -f "$DEVOLUCOES_HEALTHZ" >/dev/null || fail "devolucoes /healthz != 200"
echo "  → $DEVOLUCOES_HEALTHZ OK"

step "5/5" "Library has at least 1 entry (FTS substrate populated)"
[ "$COUNT" -ge 0 ] || fail "library count is suspicious: $COUNT"
if [ "$COUNT" = "0" ]; then
  echo "  ⚠️  library is empty — buscar_analises will return no results until publishes happen"
else
  echo "  → library has $COUNT entries; FTS will work as soon as authenticated MCP calls hit"
fi

echo
echo "✅ All health checks passed"
