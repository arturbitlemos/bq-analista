#!/bin/bash
set -e

# Clone or sync the monorepo using GitHub App auth (mutable /app/repo, used
# by publicar_dashboard for commits/pushes). Silent no-op if env vars unset.
uv run python -m mcp_core.clone_repo

exec uv run python -m agent.server
