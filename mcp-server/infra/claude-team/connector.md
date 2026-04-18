# Registering the MCP server in Claude Team (Azzas workspace)

## Owner action (admin)

1. Claude Team admin → Settings → Connectors → Add custom connector.
2. Name: `Azzas Analytics (BigQuery)`.
3. URL: `https://mcp-azzas.<corp-domain>/mcp` (SSE endpoint).
4. Auth: Custom — header `Authorization: Bearer ${MCP_TOKEN}`. The connector substitutes per-user tokens from each exec's `~/.mcp/credentials.json` via the MCP client extension. (If Claude Team doesn't support per-user bearer from connectors at rollout time, fall back to OAuth-2.0 client credentials path using the `/auth/start` redirect.)
5. System prompt (workspace-scoped):
   ```
   You have access to Azzas BigQuery analytics via 4 tools (get_context, consultar_bq, listar_analises, publicar_dashboard).
   On every session start: call get_context once to prime yourself with schema + business rules.
   Never invent numbers — if a field is missing, say so.
   After a successful consultar_bq, suggest publicar_dashboard if the exec may want a saved dashboard.
   ```
6. Scope: publish to the Execs group only (not entire workspace).

## Exec onboarding (per person)

Give them a one-page PDF with:
- `brew install` or direct binary for `mcp-login`.
- Run `mcp-login`, click through Azure AD SSO.
- Mention: token expires every 30 min; rerun `mcp-login` if you see "token expired".
- Sample queries they can paste into Claude:
  - "me dá venda da FARM ontem"
  - "resumo YTD por canal"
  - "lista minhas análises salvas"
