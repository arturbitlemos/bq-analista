import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import archiver from 'archiver';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const pkgRoot = path.resolve(__dirname, '..');
const repoRoot = path.resolve(pkgRoot, '..', '..');

const require = createRequire(import.meta.url);
const pkg = require(path.join(pkgRoot, 'package.json'));
const version = pkg.version;

const SKILL_NAME = 'azzas-analista';
const SKILL_DESCRIPTION =
  'Use esta skill em toda sessão que envolver análise de dados do grupo Azzas 2154 via BigQuery — vendas, devoluções, KPIs de varejo (venda líquida, ticket médio, PA, markup, margem, GMROI, sell-through, giro, cobertura), comparação vs LY, interpretação de números, ou recomendação de negócio. Contém a Prime Directive anti-alucinação, os 4 tiers de dado (✅ real / 📈 LY / 🔶 estimativa / ❓ indisponível), a hierarquia analítica (Contexto → Volume → Eficiência → Rentabilidade → Diagnóstico → Recomendação) e o protocolo obrigatório de PII antes de qualquer query. Triggers: "analisar vendas", "qual o ticket médio", "como está a margem", "rodar consulta no BigQuery", "comparar vs ano passado", "análise de devolução", "KPI", "BI", agentes vendas-linx/devolucoes.';

function stripFrontmatter(md) {
  if (!md.startsWith('---')) return md;
  const end = md.indexOf('\n---', 3);
  if (end === -1) return md;
  const rest = md.slice(end + 4);
  return rest.replace(/^\s*\n/, '');
}

function readSource(relPath) {
  const full = path.join(repoRoot, relPath);
  return fs.readFileSync(full, 'utf8');
}

function composeSkillMd() {
  const principles = stripFrontmatter(readSource('shared/context/analyst-principles.md')).trim();
  const piiRules = readSource('shared/context/pii-rules.md').trim();

  const frontmatter = [
    '---',
    `name: ${SKILL_NAME}`,
    `description: ${JSON.stringify(SKILL_DESCRIPTION)}`,
    `version: ${version}`,
    '---',
    '',
  ].join('\n');

  const preamble = [
    '# Azzas — Analista de Dados (Claude Desktop)',
    '',
    'Esta skill é a fonte canônica de comportamento para análises do grupo **Azzas 2154** via Claude Desktop + extensão MCP (DXT). Ela complementa a DXT: a DXT dá o *acesso* (auth corporativa + BigQuery via agentes); esta skill dá o *método* (como responder, o que nunca inventar, quando recusar).',
    '',
    'A ordem das seções é proposital: **segurança de dados primeiro** (PII), depois princípios epistêmicos, depois framework de varejo. Se PII e análise entrarem em conflito, PII vence sempre.',
    '',
    '---',
    '',
  ].join('\n');

  const body = [
    '## Parte 1 — Proteção de Dados Pessoais (prioridade máxima)',
    '',
    piiRules.replace(/^## Proteção de Dados Pessoais \(PII\)\s*\n/, '').trim(),
    '',
    '---',
    '',
    '## Parte 2 — Princípios do Analista',
    '',
    principles.replace(/^# Retail Analyst — Operating Principles\s*\n/, '').trim(),
    '',
  ].join('\n');

  return frontmatter + preamble + body + '\n';
}

function main() {
  const buildDir = path.join(pkgRoot, 'build');
  const skillDir = path.join(buildDir, SKILL_NAME);
  fs.rmSync(buildDir, { recursive: true, force: true });
  fs.mkdirSync(skillDir, { recursive: true });

  const skillMd = composeSkillMd();
  fs.writeFileSync(path.join(skillDir, 'SKILL.md'), skillMd, 'utf8');

  const outFile = path.join(pkgRoot, `azzas-analista-${version}.zip`);
  const output = fs.createWriteStream(outFile);
  const archive = archiver('zip', { zlib: { level: 9 } });

  return new Promise((resolve, reject) => {
    output.on('close', () => {
      const sizeKb = (archive.pointer() / 1024).toFixed(1);
      console.log(`✔ Built ${path.basename(outFile)} (${sizeKb} KB)`);
      resolve();
    });
    archive.on('error', reject);
    archive.pipe(output);
    archive.directory(skillDir, SKILL_NAME);
    archive.finalize();
  });
}

await main();
