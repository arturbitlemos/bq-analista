# Install MCP Server with Claude Team — Complete Plan

**Goal:** Register the exec-mcp-dispatch server as a custom MCP connector in Azzas Claude Team workspace so executives can access it from mobile/desktop Claude.

**Timeline:** 2–3 hours (one-time setup)
**Complexity:** Medium (Docker, Cloudflare, Claude Team connector registration)

---

## Phase 1: Infrastructure Setup (Mac Mini)

### 1.1 Prerequisites

- [ ] Mac mini in office with 24/7 power + network
- [ ] macOS 13+ with Docker Desktop installed + running
- [ ] Cloudflare account (free tier OK) with corp domain access
- [ ] Azure AD tenant admin credentials (to set up OAuth app)
- [ ] GitHub PAT with repo access (for Git commits)
- [ ] BigQuery service account key (JSON, saved securely)

### 1.2 Clone Repo & Install

On Mac mini:

```bash
# Clone repo (or pull if exists)
cd /opt/azzas  # or your chosen app directory
git clone https://github.com/azzas/bq-analista.git
cd bq-analista/mcp-server

# Install Python dependencies
uv sync --all-extras
```

**Verify:** `uv run pytest` should show 57/57 passing.

### 1.3 Create Production Config

```bash
# Create config directory
sudo mkdir -p /etc/mcp
sudo chown $(whoami) /etc/mcp

# Copy templates
cp config/settings.example.toml /etc/mcp/settings.toml
cp config/allowed_execs.example.json /etc/mcp/allowed_execs.json

# Edit settings
nano /etc/mcp/settings.toml
```

**Key edits in `/etc/mcp/settings.toml`:**

```toml
[server]
host = "0.0.0.0"  # Listen on all interfaces (Cloudflare tunnel will proxy)
port = 3000

[bigquery]
project_id = "soma-online-refined"
max_bytes_billed = 5000000000
query_timeout_s = 60
max_rows = 100000
allowed_datasets = ["soma_online_refined"]

[github]
repo_path = "/opt/azzas/bq-analista"  # Adjust path
branch = "main"
author_name = "mcp-exec-bot"
author_email = "mcp@azzas.com.br"

[auth]
jwt_secret = "$(openssl rand -base64 32)"  # Generate 32-byte secret
jwt_issuer = "azzas-mcp"
access_token_ttl_s = 1800    # 30 min
refresh_token_ttl_s = 604800 # 7 days

[audit]
db_path = "/var/mcp/audit.db"
retention_days = 90
```

**Edit `/etc/mcp/allowed_execs.json`:**

```json
{
  "allowed_emails": [
    "artur.lemos@somagrupo.com.br",
    "exec1@somagrupo.com.br",
    "exec2@somagrupo.com.br"
  ]
}
```

---

## Phase 2: Azure AD OAuth Registration

### 2.1 Create OAuth App in Azure

1. Go to **Azure Portal** → **App registrations** → **New registration**
2. **Name:** `azzas-mcp-dispatch`
3. **Supported account types:** Accounts in this organizational directory only (single tenant)
4. **Redirect URI:** `https://mcp-azzas.<corp-domain>/auth/callback` (exact match required)
5. Click **Register**

### 2.2 Configure Credentials

1. Go to **Certificates & secrets** → **New client secret**
   - Description: `mcp-exec-prod`
   - Expiry: 24 months
   - **Copy:** `Client secret value` → save securely
2. Go to **Overview**
   - **Copy:** `Application (client) ID` 
   - **Copy:** `Directory (tenant) ID`

### 2.3 Configure Permissions

1. Go to **API permissions** → **Add a permission**
2. Select **Microsoft Graph** → **Delegated permissions**
3. Search + add: `User.Read`, `email`, `profile`, `openid`
4. Click **Grant admin consent**

---

## Phase 3: Environment & Secrets

### 3.1 Store Secrets Securely

On Mac mini, use Keychain:

```bash
# Store Azure AD credentials
security add-generic-password -a mcp -s MCP_AZURE_TENANT_ID \
  -w "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
security add-generic-password -a mcp -s MCP_AZURE_CLIENT_ID \
  -w "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy"
security add-generic-password -a mcp -s MCP_AZURE_CLIENT_SECRET \
  -w "secret-value-here"

# Store BigQuery SA key
security add-generic-password -a mcp -s MCP_BQ_SA_KEY \
  -w "$(cat /path/to/sa-key.json)"

# Store JWT secret (already in /etc/mcp/settings.toml, but also in Keychain for backup)
security add-generic-password -a mcp -s MCP_JWT_SECRET \
  -w "base64-encoded-secret-from-settings"

# GitHub PAT
security add-generic-password -a mcp -s MCP_GITHUB_PAT \
  -w "github_pat_..."
```

### 3.2 Create .env File (for Docker)

```bash
cat > /etc/mcp/.env << 'EOF'
MCP_SETTINGS=/app/config/settings.toml
MCP_ALLOWLIST=/app/config/allowed_execs.json
MCP_AZURE_TENANT_ID=$(security find-generic-password -a mcp -s MCP_AZURE_TENANT_ID -w)
MCP_AZURE_CLIENT_ID=$(security find-generic-password -a mcp -s MCP_AZURE_CLIENT_ID -w)
MCP_AZURE_CLIENT_SECRET=$(security find-generic-password -a mcp -s MCP_AZURE_CLIENT_SECRET -w)
MCP_BQ_SA_KEY=$(security find-generic-password -a mcp -s MCP_BQ_SA_KEY -w)
MCP_JWT_SECRET=$(security find-generic-password -a mcp -s MCP_JWT_SECRET -w)
MCP_GITHUB_PAT=$(security find-generic-password -a mcp -s MCP_GITHUB_PAT -w)
EOF
chmod 600 /etc/mcp/.env
```

---

## Phase 4: Docker Build & Deploy

### 4.1 Build Image

```bash
cd /opt/azzas/bq-analista/mcp-server
docker build -t azzas-mcp:latest .
```

**Verify:** `docker images | grep azzas-mcp`

### 4.2 Run Container

```bash
docker run -d \
  --name mcp-exec \
  --restart unless-stopped \
  --env-file /etc/mcp/.env \
  -v /etc/mcp:/app/config \
  -v /opt/azzas/bq-analista:/app/repo \
  -v /var/mcp:/var/mcp \
  -p 3000:3000 \
  azzas-mcp:latest
```

**Verify:** 
```bash
docker logs mcp-exec
# Should show: "Uvicorn running on http://0.0.0.0:3000"

curl http://localhost:3000/health
# Should return: {"status":"ok"}
```

---

## Phase 5: Cloudflare Tunnel Setup

### 5.1 Install Cloudflare Tunnel

```bash
# Download cloudflared
cd /usr/local/bin
sudo curl -L --output cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64
sudo chmod +x cloudflared

# Verify
cloudflared --version
```

### 5.2 Authenticate Cloudflare

```bash
cloudflared tunnel login
# Opens browser → sign in to Cloudflare → returns auth token
```

### 5.3 Create Tunnel

```bash
# Create persistent tunnel
cloudflared tunnel create azzas-mcp

# Create config file
mkdir -p ~/.cloudflare-warp
cat > ~/.cloudflare-warp/config.yml << 'EOF'
tunnel: azzas-mcp
credentials-file: /Users/$(whoami)/.cloudflare/cloudflared/$(cloudflared tunnel list | grep azzas-mcp | awk '{print $1}').json

ingress:
  - hostname: mcp-azzas.soma-group.com.br
    service: http://localhost:3000
  - service: http_status:404
EOF
```

### 5.4 Route DNS

In Cloudflare Dashboard:

1. Go to **DNS** → **Records**
2. Add **CNAME record:**
   - Name: `mcp-azzas`
   - Target: `<tunnel-id>.cfargotunnel.com`
   - Proxy status: Proxied
3. Go to **SSL/TLS** → **Overview** → ensure "Full" or "Full (strict)"

### 5.5 Run Tunnel (Manual Test)

```bash
cloudflared tunnel run azzas-mcp
# Should show: "Tunnel registered successfully"
# Ctrl+C to stop
```

**Test from browser:** `https://mcp-azzas.soma-group.com.br/health`
Should return JSON.

### 5.6 Run Tunnel as launchd Service

```bash
# Create launchd plist
sudo tee /Library/LaunchDaemons/com.cloudflare.tunnel.plist > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.tunnel</string>
    <key>Program</key>
    <string>/usr/local/bin/cloudflared</string>
    <key>ProgramArguments</key>
    <array>
        <string>cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>azzas-mcp</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/cloudflared.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/cloudflared.err</string>
</dict>
</plist>
EOF

sudo launchctl load /Library/LaunchDaemons/com.cloudflare.tunnel.plist
sudo launchctl start com.cloudflare.tunnel
```

**Verify:**
```bash
sudo launchctl list | grep cloudflare
curl https://mcp-azzas.soma-group.com.br/health
```

---

## Phase 6: Claude Team Connector Registration

### 6.1 Prepare Connector JSON

Create `/etc/mcp/connector.json`:

```json
{
  "type": "mcp_server",
  "name": "Azzas MCP Dispatch",
  "description": "Executive BigQuery analytics & dashboard publishing via Claude Team mobile",
  "display_name": "Azzas Analytics (MCP)",
  "server_url": "https://mcp-azzas.soma-group.com.br",
  "auth_type": "bearer_token",
  "tools": [
    {
      "name": "get_context",
      "description": "Get schema, business rules, and allowed tables",
      "parameters": {}
    },
    {
      "name": "consultar_bq",
      "description": "Query BigQuery with full audit logging",
      "parameters": {
        "sql": {
          "type": "string",
          "description": "SELECT-only SQL (no DDL/DML)"
        }
      }
    },
    {
      "name": "publicar_dashboard",
      "description": "Publish HTML dashboard to Vercel via Git commit",
      "parameters": {
        "title": {"type": "string"},
        "brand": {"type": "string"},
        "period": {"type": "string"},
        "description": {"type": "string"},
        "html_content": {"type": "string", "description": "Complete HTML (use exec_template.py)"},
        "tags": {"type": "array", "items": {"type": "string"}}
      }
    },
    {
      "name": "listar_analises",
      "description": "List published analyses (mine or public)",
      "parameters": {
        "escopo": {
          "type": "string",
          "enum": ["mine", "public"]
        }
      }
    }
  ]
}
```

### 6.2 Register in Claude Team

1. Go to **Claude Team workspace** (https://claude.ai/team/azzas)
2. Navigate to **Settings** → **Connected apps/integrations** → **Add MCP server**
3. Fill in:
   - **Name:** `Azzas MCP Dispatch`
   - **Server URL:** `https://mcp-azzas.soma-group.com.br`
   - **Auth Type:** Bearer token (JWT)
   - **Token endpoint:** `https://mcp-azzas.soma-group.com.br/auth/start`
   - **Redirect URI:** `https://claude.ai/auth/callback` (provide by Claude)
4. Click **Save**

Claude Team will redirect to the server's `/auth/start` endpoint.

### 6.3 Test Connection

1. Open Claude (mobile or web)
2. Start a new conversation
3. In the chat, you should see **"Azzas MCP Dispatch"** available as a tool
4. Try: `@Azzas Get me the schema for the refined_captacao table`
5. Claude should call `get_context`, get the docs, and return them

---

## Phase 7: First Executive User

### 7.1 Add to Allowlist

```bash
# Edit allowed_execs.json
nano /etc/mcp/allowed_execs.json
# Add the executive's email (must match Azure AD upn)

# Reload config (or restart container)
docker restart mcp-exec
```

### 7.2 First Login

Executive opens **Claude mobile/web** → starts conversation:
- Claude prompts them to authenticate
- They're redirected to Azure AD login
- On success, token is stored locally (`~/.mcp/credentials.json` with 30-min TTL + 7-day refresh)
- They can immediately use MCP tools

### 7.3 Test End-to-End

Executive: `"Show me FARM ecommerce sales for yesterday"`
- Claude calls `get_context` → gets schema
- Claude generates SQL → calls `consultar_bq`
- Claude generates HTML (using `exec_template.py` structure) → calls `publicar_dashboard`
- MCP server:
  - Validates SQL (read-only, <5GB, <60s)
  - Runs query, tags with exec email in BigQuery
  - Commits HTML to `analyses/<email>/` on main branch
  - Vercel auto-deploys
  - Returns link to Claude
- Executive gets: **"Analysis complete: https://bq-analista.vercel.app/#analyses/..."** with link

---

## Phase 8: Operations & Monitoring

### 8.1 Log Locations

```bash
# Docker logs
docker logs -f mcp-exec

# Cloudflare tunnel logs
tail -f /var/log/cloudflared.log

# SQLite audit log (on Mac mini)
sqlite3 /var/mcp/audit.db "SELECT * FROM audit ORDER BY ts DESC LIMIT 10"

# BigQuery audit
bq query --project_id=soma-online-refined "
  SELECT labels.value AS exec_email, 
         query, creation_time 
  FROM \`region-us\`.INFORMATION_SCHEMA.JOBS_BY_PROJECT 
  WHERE labels.key = 'exec_email'
  ORDER BY creation_time DESC 
  LIMIT 10"
```

### 8.2 Cron Jobs

Set up daily audit cleanup + hourly anomaly checks:

```bash
# Create cron jobs in launchd (see ROLLOUT.md for plist templates)
```

### 8.3 Monitoring

Monitor:
- Container health: `docker ps | grep mcp-exec`
- Tunnel status: `cloudflared tunnel info azzas-mcp`
- Token issuance errors: `grep -i error /var/log/cloudflared.log`
- BQ job latency: Query BigQuery `INFORMATION_SCHEMA.JOBS_BY_PROJECT` with `exec_email` label

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 404 on `/health` | Check Docker is running: `docker ps`. Check Cloudflare tunnel is running. |
| Azure AD login fails | Verify tenant ID, client ID, client secret in env. Check redirect URI matches exactly. |
| SQL validation rejects valid query | Check comment stripping works. Use `uv run pytest tests/test_sql_validator.py -v`. |
| Token expires mid-query | Design: tokens TTL 30 min. If query >30 min, exec needs to re-login. (Cloud for long queries later.) |
| Commit to main fails | Check GitHub PAT has `repo` scope. Check Mac mini clock is correct (JWT validation strict). |
| BQ query is slow | Check query cost (monitor `bytes_scanned`). Increase `query_timeout_s` in settings if needed. |

---

## Rollback Plan

If issues arise:

1. **Immediate:** Unregister connector from Claude Team (users can't access)
2. **Container:** `docker stop mcp-exec` (tunnel still up, 404 returned)
3. **Tunnel:** `sudo launchctl stop com.cloudflare.tunnel` (DNS still resolves, but no response)
4. **Full:** Remove from Cloudflare DNS + stop tunnel + stop Docker
5. **Restore:** Can always redeploy from version control; no data loss (read-only)

---

## Success Criteria

✓ Container healthy (`docker logs` shows "Uvicorn running")
✓ Tunnel registered + active (`cloudflared tunnel info azzas-mcp`)
✓ HTTPS resolves (`curl https://mcp-azzas.soma-group.com.br/health → {"status":"ok"}`)
✓ Azure AD app created + tokens issuing
✓ Connector registered in Claude Team
✓ First executive logs in + runs `get_context` successfully
✓ End-to-end test: schema → SQL → query → dashboard → commit → link
✓ Audit logs appear in SQLite + BigQuery

---

## Next Steps

1. **This week:** Complete Phases 1–4 (infrastructure + OAuth)
2. **Next week:** Complete Phases 5–6 (Cloudflare + Claude Team registration)
3. **Week 3:** Onboard first executive + monitor for 1 week
4. **Week 4:** Scale to full allowlist
