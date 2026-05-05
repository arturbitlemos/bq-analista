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
echo "Next steps (see README § 'Criando um novo agente MCP' for full detail):"
echo ""
echo "  [Repo] Governança — checked in:"
echo "    1. $AGENT_DIR/config/settings.toml         — set allowed_datasets"
echo "    2. $AGENT_DIR/config/allowed_execs.json    — add authorized emails"
echo "    3. $AGENT_DIR/src/agent/context/schema.md          — document tables (PII first!)"
echo "    4. $AGENT_DIR/src/agent/context/business-rules.md  — document rules"
echo "    5. $AGENT_DIR/src/agent/context/SKILL.md           — agent workflow for Claude"
echo "    6. uv lock  (from repo root)"
echo ""
echo "  [Railway] Deployment — env vars no dashboard:"
echo "    Required:  MCP_DOMAIN, MCP_BQ_PROJECT_ID, MCP_BQ_BILLING_PROJECT_ID,"
echo "               MCP_BQ_SA_KEY, MCP_AZURE_TENANT_ID, MCP_AZURE_CLIENT_ID,"
echo "               MCP_AZURE_CLIENT_SECRET, MCP_JWT_SECRET, GITHUB_TOKEN, GITHUB_REPO"
echo "    Optional:  MCP_GITHUB_AUTHOR_EMAIL, MCP_GITHUB_AUTHOR_NAME, MCP_GITHUB_BRANCH"
echo ""
echo "  [Railway] Se o nome do serviço Railway diferir do diretório:"
echo "    echo '<railway-service-name>' > $AGENT_DIR/.service-name"
echo ""
echo "  [Portal] Wire up — sem isso o DXT não enxerga o agente:"
echo "    7. portal/api/mcp/_helpers/manifest.js   — add agente em MANIFEST.agents"
echo ""
echo "  [DXT] Atualizar prompt e fazer release:"
echo "    8. packages/mcp-client-dxt/manifest.json — extend prompt_for_model"
echo "    9. release do DXT — ver docs/release-dxt.md (4 passos)"
echo ""
echo "  [Validar] README § 'Validação fim-a-fim' — checklist antes do PR"
