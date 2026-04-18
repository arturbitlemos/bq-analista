# mcp-exec

Python MCP server that lets Azzas executives run BigQuery analyses and publish dashboards via Claude Team on mobile.

See `docs/superpowers/specs/2026-04-18-exec-mcp-dispatch-design.md` for the full architecture.

## Dev

```bash
cd mcp-server
uv sync --all-extras
uv run pytest
```
