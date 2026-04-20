#!/bin/bash
set -e

# Clone or update the bq-analista repo into /app/repo
if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPO" ]; then
    if [ ! -d "/app/repo/.git" ]; then
        git clone "https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" /app/repo
    else
        git -C /app/repo pull --ff-only
    fi
fi

exec python -m mcp_exec.server
