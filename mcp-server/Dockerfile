FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy package metadata + source before pip install so the editable ref resolves
COPY pyproject.toml .
COPY src/ src/

# Install all pinned deps (strip the "-e ." line, install the package directly)
COPY requirements.txt .
RUN grep -v '^-e ' requirements.txt > /tmp/deps.txt \
    && pip install --no-cache-dir -r /tmp/deps.txt \
    && pip install --no-cache-dir --no-deps .

COPY scripts/ scripts/

RUN useradd -m -u 1000 mcp \
    && mkdir -p /var/mcp /app/repo /app/config \
    && chown -R mcp:mcp /app /var/mcp \
    && chmod +x /app/scripts/entrypoint.sh
USER mcp

ENV PYTHONPATH=/app/src

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:3000/health', timeout=5).raise_for_status()"

EXPOSE 3000

CMD ["/app/scripts/entrypoint.sh"]
