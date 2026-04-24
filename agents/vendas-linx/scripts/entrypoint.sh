#!/bin/bash
set -e

# Clone or sync the monorepo using GitHub App auth (mutable /app/repo, used
# by publicar_dashboard for commits/pushes). Non-fatal: if the clone fails
# the server still boots; only publicar_dashboard will be affected.
uv run python -m mcp_core.clone_repo || echo "[entrypoint] clone_repo failed; continuing"

exec uv run python -m agent.server
