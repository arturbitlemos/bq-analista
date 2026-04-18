# End-to-end integration test (manual, run once before production rollout)

## Prereqs
- Mac mini has Docker running.
- Keychain has all 6 secrets set (see `infra/deploy.sh`).
- `/etc/mcp/settings.toml` and `/etc/mcp/allowed_execs.json` exist and contain `artur.lemos@somagrupo.com.br`.
- Cloudflare tunnel running, hostname resolves.

## Steps

1. **Deploy**: `bash mcp-server/infra/deploy.sh`
2. **Verify service up**: `curl https://mcp-azzas.<corp>/health` → `{"status":"ok"}`
3. **Login from analyst laptop**: `uv run --directory mcp-server mcp-login --server https://mcp-azzas.<corp>`
   - Browser opens → Azure AD login → "You can close this tab."
   - `~/.mcp/credentials.json` appears with `access_token`, `refresh_token`, `email`.
4. **Call `get_context`**: use `mcp-cli` or curl against `/mcp/tools/get_context` with `Authorization: Bearer <token>`. Expect concatenated docs.
5. **Call `consultar_bq`** with:
   ```sql
   SELECT COUNT(*) AS n FROM `soma_online_refined.refined_captacao` WHERE data_venda >= CURRENT_DATE()
   ```
   Expect `row_count: 1`, `bytes_billed > 0`.
6. **Call `publicar_dashboard`** with a small HTML blob. Expect commit on `main` and a file under `analyses/artur.lemos@somagrupo.com.br/`.
7. **Check BQ audit**: `SELECT labels FROM \`region-us\`.INFORMATION_SCHEMA.JOBS_BY_PROJECT WHERE creation_time >= CURRENT_TIMESTAMP() - INTERVAL 1 HOUR AND labels.source = 'mcp_dispatch'` → email present.
8. **Check SQLite audit**: `sqlite3 /var/mcp/audit.db "SELECT * FROM audit ORDER BY ts DESC LIMIT 5"` → three rows for the 3 tool calls.
9. **Invalid exec**: temporarily remove your email from allowlist → call `/auth/callback` → expect 403.
10. **Token expiry**: set `access_token_ttl_s=5`, log in, wait 10s, call tool → expect 401 with "run: mcp-login".

## Pass criteria
All 10 steps complete without manual intervention from outside the flow. Failure at any step blocks rollout.
