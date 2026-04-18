# Local Development Guide — MCP Exec Server

Run the MCP server locally for development and testing. No Docker, Cloudflare, or Azure AD required.

## Quick Start

```bash
cd mcp-server
uv sync --all-extras
export MCP_REPO_ROOT=/Users/arturlemos/Documents/bq-analista
export MCP_SETTINGS=$(pwd)/config/settings.toml
uv run mcp-exec-server
```

Server listens on `http://localhost:3000` (FastAPI).

## Setup

### 1. Create Local Config

```bash
cp config/settings.example.toml config/settings.toml
cp config/allowed_execs.example.json config/allowed_execs.json
```

Edit `config/settings.toml`:
```toml
[server]
host = "127.0.0.1"
port = 3000

[bigquery]
project_id = "soma-online-refined"
max_bytes_billed = 5000000000
query_timeout_s = 60
max_rows = 100000
allowed_datasets = ["soma_online_refined"]

[github]
repo_path = "/Users/arturlemos/Documents/bq-analista"
branch = "main"
author_name = "mcp-local-test"
author_email = "test@local"

[auth]
jwt_secret = "local-dev-secret-1234567890"
access_token_ttl_s = 3600
refresh_token_ttl_s = 86400

[audit]
db_path = "./audit.db"
retention_days = 90
```

Edit `config/allowed_execs.json`:
```json
{
  "allowed_emails": [
    "artur.lemos@somagrupo.com.br",
    "test@local"
  ]
}
```

### 2. Set BigQuery Credentials (optional)

For actual BQ queries:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
```

Without credentials, BQ calls return sandbox errors (safe).

### 3. Start Server (Development Mode)

```bash
export MCP_REPO_ROOT=/Users/arturlemos/Documents/bq-analista
export MCP_SETTINGS=$(pwd)/config/settings.toml
uv run mcp-exec-dev
```

**Note:** `mcp-exec-dev` is a development server that doesn't require Azure AD env vars. Use `mcp-exec-server` for production (requires `MCP_AZURE_*` env vars).

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:3000
```

## Testing

### Test 1: Health check

```bash
curl http://localhost:3000/health
# Output: {"status":"ok"}
```

### Test 2: Get Bearer Token

Dev server provides a simple endpoint to issue tokens:

```bash
curl "http://localhost:3000/auth/issue-token?email=artur.lemos@somagrupo.com.br"
# Output: {"access_token":"eyJ...","email":"artur.lemos@somagrupo.com.br"}

TOKEN=$(curl -s "http://localhost:3000/auth/issue-token?email=artur.lemos@somagrupo.com.br" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
echo $TOKEN
```

Use `$TOKEN` in subsequent requests.

### Test 3: Call `get_context`

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:3000/mcp/tools/get_context
```

Expected: JSON with `text` (concatenated docs) and `allowed_tables`.

### Test 4: Call `consultar_bq` (no credentials)

```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sql":"SELECT 1 AS n"}' \
  http://localhost:3000/mcp/tools/consultar_bq
```

Expected (no BQ creds): `{"error":"no credentials..."}` or query results if BQ_SA is set.

### Test 5: Call `publicar_dashboard`

Generate HTML using the template:

```bash
python3 << 'EOF'
import sys
sys.path.insert(0, '/Users/arturlemos/Documents/bq-analista')

from exec_template import generate_dashboard_html, KPICard, Insight

html = generate_dashboard_html(
    title="Test Dashboard",
    brand="FARM",
    period="Test",
    hero_label="Test KPI",
    hero_value="R$100",
    kpis=[KPICard("Label", "Value")],
    insights=[Insight("Test insight", type="positive")],
)

print(html[:200])
EOF
```

Save HTML to `test.html`, then:

```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test",
    "brand": "FARM",
    "period": "Test",
    "description": "Test dashboard",
    "html_content": "<html><body>Test</body></html>",
    "tags": ["test"]
  }' \
  http://localhost:3000/mcp/tools/publicar_dashboard
```

Expected: `{"link": "/analyses/artur.lemos@somagrupo.com.br/...", "published_at": "..."}` and new commit on main.

Verify:
```bash
git log --oneline -n 1
# Should show commit from mcp-local-test
ls analyses/artur.lemos@somagrupo.com.br/
# Should show HTML file
```

### Test 6: Call `listar_analises`

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "http://localhost:3000/mcp/tools/listar_analises?escopo=mine"
```

Expected: array of analyses with `{id, title, brand, date, link}`.

### Test 7: Auth rejection

Use invalid token:

```bash
curl -H "Authorization: Bearer invalid" \
  http://localhost:3000/mcp/tools/get_context
```

Expected: `401 Unauthorized`.

## Status

✓ Local dev server running (mcp-exec-dev)
✓ Token issuance working
✓ Config files created
✓ Tests passing (57/57)
✓ MCP tools mounted at /mcp/

## Next Steps

- [ ] Test MCP tools (`get_context`, `consultar_bq`, `publicar_dashboard`, `listar_analises`)
- [ ] Wire template generator to report-generator skill
- [ ] Test end-to-end flow: token → get_context → generate HTML → publicar_dashboard → verify commit
- [ ] Add mock BQ client for testing without real credentials
- [ ] Document how Claude calls template generator

## Cleanup

```bash
# Remove local config
rm config/settings.toml config/allowed_execs.json audit.db
```
