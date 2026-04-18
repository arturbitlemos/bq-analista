# mcp-exec

Python MCP server that lets Azzas executives run BigQuery analyses and publish dashboards via Claude Team on mobile.

See `docs/superpowers/specs/2026-04-18-exec-mcp-dispatch-design.md` for the full architecture.

## Dev

```bash
cd mcp-server
uv sync --all-extras
uv run pytest
```

## Cron jobs

Host runs two cron jobs (via launchd `StartCalendarInterval` — plists land in Phase 7):

- **Hourly anomaly check**: `python -m mcp_exec.alerts`. Exit code 1 on alert.
- **Daily audit purge**: `python scripts/purge_audit.py`.
