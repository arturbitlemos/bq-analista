#!/usr/bin/env bash
# Usage: scripts/new-agent.sh <domain>
# Creates a new agent from the current vendas-linx agent as reference.
# Requirements: bash, python3 (for cross-platform string substitution)

set -euo pipefail

DOMAIN="${1:?Usage: new-agent.sh <domain>}"
AGENT_DIR="agents/$DOMAIN"
REF_DIR="agents/vendas-linx"
REPO_ROOT="$(git rev-parse --show-toplevel)"

cd "$REPO_ROOT"

if [ -d "$AGENT_DIR" ]; then
  echo "ERROR: $AGENT_DIR already exists" >&2
  exit 1
fi

# Validate domain format (lowercase, hyphens ok, no spaces)
if ! echo "$DOMAIN" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
  echo "ERROR: domain must be lowercase letters, digits, or hyphens (e.g. vendas-ecomm)" >&2
  exit 1
fi

echo "Creating agent: $DOMAIN (from $REF_DIR)"
cp -r "$REF_DIR" "$AGENT_DIR"

# Cross-platform string substitution via Python
python3 - "$AGENT_DIR" "$DOMAIN" << 'PYEOF'
import sys, re
from pathlib import Path

agent_dir = Path(sys.argv[1])
domain = sys.argv[2]

def replace_in_file(path: Path, old: str, new: str):
    content = path.read_text()
    if old in content:
        path.write_text(content.replace(old, new))

# pyproject.toml: update name
replace_in_file(agent_dir / "pyproject.toml", 'name = "agent-vendas-linx"', f'name = "agent-{domain}"')

# settings.toml: update domain and clear allowed_datasets
settings = agent_dir / "config" / "settings.toml"
content = settings.read_text()
content = content.replace('domain = "vendas-linx"', f'domain = "{domain}"')
content = re.sub(
    r'allowed_datasets\s*=\s*\[.*?\]',
    'allowed_datasets = []  # REQUIRED: set the datasets for this domain',
    content,
)
settings.write_text(content)

print(f"  ✓ pyproject.toml: name updated")
print(f"  ✓ settings.toml: domain={domain}, allowed_datasets cleared")
PYEOF

# Clear sensitive/domain-specific files
echo '{"allowed_emails": []}' > "$AGENT_DIR/config/allowed_execs.json"

printf '# Schema — %s\n\nDocumente aqui as tabelas do domínio %s.\n\nSiga o protocolo PII do CLAUDE.md antes de escrever qualquer coluna.\n' \
  "$DOMAIN" "$DOMAIN" > "$AGENT_DIR/src/agent/context/schema.md"

printf '# Business Rules — %s\n\nDocumente aqui as regras de negócio do domínio %s.\n' \
  "$DOMAIN" "$DOMAIN" > "$AGENT_DIR/src/agent/context/business-rules.md"

# Clear audit db if it was copied
rm -f "$AGENT_DIR/audit.db" "$AGENT_DIR"/*.db

echo ""
echo "Agent created at $AGENT_DIR"
echo ""
echo "Next steps:"
echo "  1. config/settings.toml      — set allowed_datasets"
echo "  2. config/allowed_execs.json — add authorized emails"
echo "  3. src/agent/context/schema.md         — document tables (PII first!)"
echo "  4. src/agent/context/business-rules.md — document rules"
echo "  5. uv lock  (from repo root)"
echo "  6. See CLAUDE.md 'Como criar um novo agente' for Railway setup"
