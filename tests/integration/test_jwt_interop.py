import json
import subprocess
from pathlib import Path

import pytest

from mcp_core.jwt_tokens import TokenIssuer

PORTAL_DIR = Path(__file__).resolve().parents[2] / "portal"

SECRET = "x" * 32
ISSUER = "mcp-exec-azzas"
EMAIL = "interop@azzas.com.br"
DXT_DIR = Path(__file__).resolve().parents[2] / "packages" / "mcp-client-dxt"


def _ts_mint() -> dict:
    result = subprocess.run(
        ["npm", "run", "--silent", "interop:mint", "--",
         EMAIL, SECRET, ISSUER, "1800", "604800"],
        cwd=DXT_DIR, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout.strip())


def test_ts_mints_python_verifies():
    """Portal/DXT mint access tokens that the mcp-core agents validate as Bearer
    on every tool call. Refresh interop is intentionally not tested — DXT renews
    via the portal's own /api/mcp/auth/refresh, never against mcp-core directly,
    so externally-minted refresh tokens lack mcp-core's rotation claims (fid/jti)
    by design."""
    pair = _ts_mint()
    issuer = TokenIssuer(secret=SECRET, issuer=ISSUER, access_ttl_s=1800, refresh_ttl_s=604800)
    access_claims = issuer.verify_access(pair["access"])
    assert access_claims["email"] == EMAIL
    assert access_claims["sub"] == EMAIL
    assert access_claims["iss"] == ISSUER
    assert access_claims["kind"] == "access"


def test_python_mints_ts_verifies(tmp_path):
    issuer = TokenIssuer(secret=SECRET, issuer=ISSUER, access_ttl_s=1800, refresh_ttl_s=604800)
    pair = issuer.issue(EMAIL)
    jwt_module = str(DXT_DIR / "src" / "jwt.js")
    script = f"""
import {{ decodeToken }} from {json.dumps(jwt_module)};
const claims = decodeToken({json.dumps(pair.access_token)}, {json.dumps(SECRET)}, {json.dumps(ISSUER)});
console.log(JSON.stringify(claims));
"""
    script_file = tmp_path / "verify.mjs"
    script_file.write_text(script)
    result = subprocess.run(
        ["npx", "tsx", str(script_file)],
        cwd=DXT_DIR, capture_output=True, text=True, check=True,
    )
    claims = json.loads(result.stdout.strip())
    assert claims["email"] == EMAIL
    assert claims["kind"] == "access"


def test_secret_mismatch_rejected():
    pair = _ts_mint()
    wrong_issuer = TokenIssuer(secret="y" * 32, issuer=ISSUER, access_ttl_s=1800, refresh_ttl_s=604800)
    with pytest.raises(Exception):
        wrong_issuer.verify_access(pair["access"])


def test_js_portal_mints_python_verifies(tmp_path):
    script = f"""
const {{ issueTokens }} = require({json.dumps(str(PORTAL_DIR / "api" / "mcp" / "_helpers" / "jwt.js"))});
const pair = issueTokens({{
  email: {json.dumps(EMAIL)},
  secret: {json.dumps(SECRET)},
  issuer: {json.dumps(ISSUER)},
  accessTtlS: 1800,
  refreshTtlS: 604800,
}});
console.log(JSON.stringify(pair));
"""
    script_file = tmp_path / "mint.cjs"
    script_file.write_text(script)
    result = subprocess.run(
        ["node", str(script_file)],
        cwd=PORTAL_DIR, capture_output=True, text=True, check=True,
    )
    pair = json.loads(result.stdout.strip())
    issuer = TokenIssuer(secret=SECRET, issuer=ISSUER, access_ttl_s=1800, refresh_ttl_s=604800)
    access_claims = issuer.verify_access(pair["access"])
    assert access_claims["email"] == EMAIL
    assert access_claims["kind"] == "access"
    assert access_claims["iss"] == ISSUER
    # Refresh interop intentionally not tested — see test_ts_mints_python_verifies.


def test_python_mints_js_portal_verifies(tmp_path):
    issuer = TokenIssuer(secret=SECRET, issuer=ISSUER, access_ttl_s=1800, refresh_ttl_s=604800)
    pair = issuer.issue(EMAIL)
    script = f"""
const {{ decodeToken }} = require({json.dumps(str(PORTAL_DIR / "api" / "mcp" / "_helpers" / "jwt.js"))});
const claims = decodeToken({json.dumps(pair.access_token)}, {json.dumps(SECRET)}, {json.dumps(ISSUER)});
console.log(JSON.stringify(claims));
"""
    script_file = tmp_path / "verify.cjs"
    script_file.write_text(script)
    result = subprocess.run(
        ["node", str(script_file)],
        cwd=PORTAL_DIR, capture_output=True, text=True, check=True,
    )
    claims = json.loads(result.stdout.strip())
    assert claims["email"] == EMAIL
    assert claims["kind"] == "access"
    assert claims["iss"] == ISSUER
