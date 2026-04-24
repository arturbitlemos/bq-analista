# Build context MUST be the repo root.
# Railway: Dockerfile path = agents/devolucoes/Dockerfile, Build context = .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install uv --no-cache-dir

# Copy workspace root + mcp-core + this agent (explicit paths avoid copying unnecessary dirs)
COPY pyproject.toml uv.lock ./
COPY packages/mcp-core/ packages/mcp-core/
COPY agents/devolucoes/ agents/devolucoes/
COPY shared/ shared/
COPY .claude/ .claude/

# Install agent and its mcp-core dependency via uv workspace
WORKDIR /app/agents/devolucoes
RUN uv sync --frozen

# Stage config to /app/config (default MCP_SETTINGS path)
RUN mkdir -p /app/config && cp -r /app/agents/devolucoes/config/. /app/config/

COPY agents/devolucoes/scripts/entrypoint.sh /app/scripts/entrypoint.sh

RUN useradd -m -u 1000 mcp \
    && mkdir -p /var/mcp /app/repo \
    && chown -R mcp:mcp /app /var/mcp \
    && chmod +x /app/scripts/entrypoint.sh
USER mcp

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:3000/health', timeout=5).raise_for_status()"

EXPOSE 3000

CMD ["/app/scripts/entrypoint.sh"]
