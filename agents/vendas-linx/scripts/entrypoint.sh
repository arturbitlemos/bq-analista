#!/bin/bash
set -e

# Clone or update the monorepo (provides shared/context + agents/*/context + analyses + library)
if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPO" ]; then
    if [ ! -d "/app/repo/.git" ]; then
        git clone "https://${GITHUB_TOKEN}@github.com/${GITHUB_REPO}.git" /app/repo
    else
        git -C /app/repo fetch origin main && git -C /app/repo reset --hard origin/main
    fi
fi

exec uv run python -m agent.server
