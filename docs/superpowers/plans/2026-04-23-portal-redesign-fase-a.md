# Portal Redesign Fase A — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesenhar o portal `bq-analista.vercel.app` — dar visibilidade ao onboarding, alinhar visualmente à marca Azzas 2154, reorganizar a library de análises pra escalar até 100-300 items/analista, e rebrandar a tela de sucesso de auth do DXT.

**Architecture:** Três vetores: (1) backend Python (`mcp-core`) ganha campo `author_email` no `LibraryEntry` pra distinguir autoria; (2) DXT client ganha função `renderCallbackPage` com marca aplicada; (3) portal Vercel reescreve `index.html` e `onboarding.html` com tabs (Minhas/Time/Arquivadas), busca cross-domain via `/api/mcp/agents`, facets, arquivamento via localStorage, e header com link permanente pro onboarding. Sem mudança de schema de `library.json` além do campo novo (retrocompatível). Sem novos endpoints, sem mudança de auth.

**Tech Stack:** Python 3.13 + pytest (mcp-core), TypeScript + vitest (mcp-client-dxt), HTML/CSS/vanilla JS (portal), Vercel functions + middleware Web Crypto. Google Fonts (Red Hat Display + Playfair Display). Sem framework frontend.

**Spec:** [`docs/superpowers/specs/2026-04-23-portal-redesign-fase-a-design.md`](../specs/2026-04-23-portal-redesign-fase-a-design.md)

---

## File Structure

**Backend (Python, editar):**
- `packages/mcp-core/src/mcp_core/library.py` — `LibraryEntry` ganha `author_email: str`
- `packages/mcp-core/src/mcp_core/server_factory.py` — `publicar_dashboard` passa `author_email=exec_email`
- `packages/mcp-core/tests/test_library.py` — cobre o campo novo

**DXT client (TypeScript, editar/criar):**
- `packages/mcp-client-dxt/src/callback-page.ts` — **novo**, exporta `renderCallbackPage(params)` → HTML string rebrandado (sucesso/erro)
- `packages/mcp-client-dxt/src/auth.ts` — substitui string inline `<h1>Pronto!</h1>...` por `renderCallbackPage(params)`
- `packages/mcp-client-dxt/tests/callback-page.test.ts` — **novo**, vitest
- `packages/mcp-client-dxt/manifest.json` — bump `1.0.0` → `1.0.1`

**Portal (HTML/CSS/JS, editar):**
- `portal/onboarding.html` — rebrand completo (hero navy, passos em grid, agentes editorial)
- `portal/index.html` — reescrita: header com link onboarding, tabs, cross-domain fetch, facets, archive localStorage, card menu, mobile bottom sheet. Preserva iframe viewer e MSAL flow.

**Sem mudança:** `portal/vercel.json`, `portal/middleware.js`, `portal/api/*.js`.

---

## Task 1: Backend — `author_email` em `LibraryEntry`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/library.py`
- Modify: `packages/mcp-core/tests/test_library.py`

- [ ] **Step 1.1: Ler o estado atual**

Abra `packages/mcp-core/src/mcp_core/library.py` e confirme que `LibraryEntry` é um `@dataclass` com os campos: `id, title, brand, date, link, description, tags, filename`. `prepend_entry` converte via `asdict(entry)` e adiciona `record["file"] = entry.link.lstrip("/")` pra compat.

- [ ] **Step 1.2: Escrever teste que falha — campo `author_email` persiste no JSON**

Adicione ao final de `packages/mcp-core/tests/test_library.py`:

```python
def test_author_email_is_persisted(tmp_path: Path) -> None:
    lib = tmp_path / "lib.json"
    entry = LibraryEntry(
        id="abc", title="T", brand="FARM", date="2026-04-23",
        link="/analyses/vendas-linx/public/abc.html",
        description="d", tags=[], filename="abc.html",
        author_email="artur.lemos@somagrupo.com.br",
    )
    prepend_entry(lib, entry)
    saved = json.loads(lib.read_text())
    assert saved[0]["author_email"] == "artur.lemos@somagrupo.com.br"
```

- [ ] **Step 1.3: Rodar teste pra ver falhar**

```bash
cd packages/mcp-core && uv run pytest tests/test_library.py::test_author_email_is_persisted -v
```
Expected: FAIL com `TypeError: LibraryEntry.__init__() got an unexpected keyword argument 'author_email'`.

- [ ] **Step 1.4: Adicionar o campo no dataclass**

Em `packages/mcp-core/src/mcp_core/library.py`, troque:

```python
@dataclass
class LibraryEntry:
    id: str
    title: str
    brand: str
    date: str
    link: str
    description: str
    tags: list[str]
    filename: str
```

por:

```python
@dataclass
class LibraryEntry:
    id: str
    title: str
    brand: str
    date: str
    link: str
    description: str
    tags: list[str]
    filename: str
    author_email: str
```

- [ ] **Step 1.5: Rodar o teste novo — deve passar, e os antigos precisam continuar passando**

```bash
cd packages/mcp-core && uv run pytest tests/test_library.py -v
```
Expected: os dois testes antigos falham porque `LibraryEntry(...)` agora exige `author_email`. Vá pra step 1.6 pra corrigir.

- [ ] **Step 1.6: Atualizar os testes existentes pra passar `author_email`**

Em `packages/mcp-core/tests/test_library.py`, nos dois `test_creates_library_json_if_missing` e `test_prepends_to_existing_list`, adicione `author_email="x@y.com"` no construtor de `LibraryEntry`. Resultado:

```python
entry = LibraryEntry(
    id="abc", title="T", brand="FARM", date="2026-04-18",
    link="/analyses/x@y.com/abc.html", description="d", tags=["ytd"],
    filename="abc.html", author_email="x@y.com",
)
```

e

```python
entry = LibraryEntry(
    id="new", title="T", brand="B", date="2026-04-18",
    link="/x", description="d", tags=[], filename="new.html",
    author_email="x@y.com",
)
```

- [ ] **Step 1.7: Rodar todos os testes do pacote**

```bash
cd packages/mcp-core && uv run pytest -v
```
Expected: todos passam (3 em `test_library.py` + os outros testes do pacote).

- [ ] **Step 1.8: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add packages/mcp-core/src/mcp_core/library.py packages/mcp-core/tests/test_library.py
git commit -m "feat(library): adiciona author_email em LibraryEntry"
```

---

## Task 2: Backend — `publicar_dashboard` passa `author_email`

**Files:**
- Modify: `packages/mcp-core/src/mcp_core/server_factory.py:231-239`

- [ ] **Step 2.1: Localizar o bloco onde `LibraryEntry` é construído**

Em `packages/mcp-core/src/mcp_core/server_factory.py`, encontre a chamada `prepend_entry(library_path, LibraryEntry(...))` dentro de `publicar_dashboard`. Hoje passa `id`, `title`, `brand`, `date`, `link`, `description`, `tags`, `filename`. `exec_email` está disponível como variável local desde `exec_email = _current_email(ctx)`.

- [ ] **Step 2.2: Passar `author_email=exec_email` na construção**

Substitua:

```python
prepend_entry(
    library_path,
    LibraryEntry(
        id=entry_id, title=title, brand=brand, date=today,
        link=link, description=description, tags=tags, filename=entry_filename,
    ),
)
```

por:

```python
prepend_entry(
    library_path,
    LibraryEntry(
        id=entry_id, title=title, brand=brand, date=today,
        link=link, description=description, tags=tags, filename=entry_filename,
        author_email=exec_email,
    ),
)
```

- [ ] **Step 2.3: Rodar testes do pacote pra garantir nada quebrou**

```bash
cd packages/mcp-core && uv run pytest -v
```
Expected: todos passam (inclusive `test_server_factory.py` se existir, já que `LibraryEntry` agora aceita `author_email` desde Task 1).

- [ ] **Step 2.4: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add packages/mcp-core/src/mcp_core/server_factory.py
git commit -m "feat(publicar_dashboard): grava author_email no library entry"
```

---

## Task 3: DXT — módulo `callback-page.ts` com renderização rebrandada

**Files:**
- Create: `packages/mcp-client-dxt/src/callback-page.ts`
- Create: `packages/mcp-client-dxt/tests/callback-page.test.ts`

- [ ] **Step 3.1: Escrever teste que falha — sucesso produz HTML com headline e email**

Crie `packages/mcp-client-dxt/tests/callback-page.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { renderCallbackPage } from '../src/callback-page';

describe('renderCallbackPage', () => {
  it('success: inclui headline, email, e auto-close script', () => {
    const html = renderCallbackPage({
      access: 'tok',
      email: 'artur.lemos@somagrupo.com.br',
    });
    expect(html).toContain('Login concluído');
    expect(html).toContain('artur.lemos@somagrupo.com.br');
    expect(html).toContain('window.close');
    expect(html).toContain('Red Hat Display');
    expect(html).toContain('#274566'); // navy
  });

  it('error wrong_tenant: mensagem sobre tenant corporativo', () => {
    const html = renderCallbackPage({ error: 'wrong_tenant' });
    expect(html).toContain('Login não concluído');
    expect(html).toContain('tenant corporativo Azzas');
    expect(html).toContain('ai.labs@somagrupo.com.br');
  });

  it('error invalid_code: mensagem sobre autorização expirada', () => {
    const html = renderCallbackPage({ error: 'invalid_code' });
    expect(html).toContain('autorização expirou');
  });

  it('error desconhecido com description: usa a description', () => {
    const html = renderCallbackPage({
      error: 'qualquer_outro',
      error_description: 'detalhe específico do Azure',
    });
    expect(html).toContain('detalhe específico do Azure');
  });

  it('error sem description: fallback genérico', () => {
    const html = renderCallbackPage({ error: 'qualquer_outro' });
    expect(html).toContain('Algo deu errado');
  });

  it('escapa HTML em email e error_description', () => {
    const html = renderCallbackPage({
      access: 'tok',
      email: '<script>alert(1)</script>@x.com',
    });
    expect(html).not.toContain('<script>alert(1)</script>@x.com');
    expect(html).toContain('&lt;script&gt;');
  });
});
```

- [ ] **Step 3.2: Rodar teste pra ver falhar**

```bash
cd packages/mcp-client-dxt && npm test -- callback-page
```
Expected: FAIL — `Cannot find module '../src/callback-page'`.

- [ ] **Step 3.3: Implementar `callback-page.ts`**

Crie `packages/mcp-client-dxt/src/callback-page.ts`:

```typescript
import type { LoopbackParams } from './auth.js';

const ERROR_MESSAGES: Record<string, string> = {
  wrong_tenant: 'Você não está no tenant corporativo Azzas.',
  invalid_code: 'A autorização expirou ou falhou.',
  azure_error: 'Erro na comunicação com o Azure AD.',
};

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function resolveErrorMessage(params: LoopbackParams): string {
  const code = params.error ?? '';
  if (ERROR_MESSAGES[code]) return ERROR_MESSAGES[code];
  if (params.error_description) return params.error_description;
  return 'Algo deu errado.';
}

const PAGE_CSS = `
  :root {
    --ink: #000; --ink-soft: #595959; --ink-faint: #999;
    --surface: #fff; --surface-cream: #F9F6EA; --surface-warm: #E8E8E4;
    --navy: #274566; --steel: #3D5A73; --blue-soft: #A1C6ED;
    --font-primary: 'Red Hat Display', Arial, sans-serif;
    --font-editorial: 'Playfair Display', Georgia, serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--surface-cream); font-family: var(--font-primary); color: var(--ink); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 2rem; }
  .card { background: var(--surface); max-width: 480px; width: 100%; padding: 3rem 2.5rem; border-radius: 12px; text-align: center; border: 1px solid var(--surface-warm); }
  .brand { font-size: 0.8rem; letter-spacing: 0.2em; text-transform: uppercase; font-weight: 600; color: var(--navy); margin-bottom: 2rem; }
  .brand em { font-family: var(--font-editorial); font-style: italic; font-weight: 400; text-transform: none; letter-spacing: normal; color: var(--steel); font-size: 1rem; }
  .icon { width: 56px; height: 56px; margin: 0 auto 1.5rem; color: var(--navy); }
  h1 { font-weight: 400; font-size: 1.75rem; letter-spacing: -0.01em; margin-bottom: 0.5rem; line-height: 1.15; }
  .editorial { font-family: var(--font-editorial); font-style: italic; font-size: 1.1rem; color: var(--steel); margin-bottom: 1.5rem; }
  .sub { font-size: 0.9rem; color: var(--ink-soft); font-weight: 300; line-height: 1.5; }
  .countdown { font-size: 0.75rem; color: var(--ink-faint); margin-top: 2rem; letter-spacing: 0.05em; text-transform: uppercase; }
`;

function renderSuccess(email: string): string {
  const safeEmail = escapeHtml(email);
  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Login concluído — Azzas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;1,400&family=Red+Hat+Display:wght@300;400;600&display=swap" rel="stylesheet">
<style>${PAGE_CSS}</style>
</head>
<body>
<div class="card">
  <div class="brand">AZZAS <em>análises</em></div>
  <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
    <circle cx="12" cy="12" r="10"></circle>
    <path d="M8 12l3 3 5-6"></path>
  </svg>
  <h1>Login concluído</h1>
  <p class="editorial">Bem-vindo, ${safeEmail}.</p>
  <p class="sub">Você já pode fechar esta aba e voltar pro Claude Desktop.</p>
  <p class="countdown" id="countdown">Fechando em 3s...</p>
</div>
<script>
  let s = 3;
  const el = document.getElementById('countdown');
  const id = setInterval(() => {
    s--;
    if (s <= 0) { clearInterval(id); window.close(); el.textContent = 'Você pode fechar a aba.'; }
    else { el.textContent = 'Fechando em ' + s + 's...'; }
  }, 1000);
</script>
</body>
</html>`;
}

function renderError(message: string): string {
  const safeMessage = escapeHtml(message);
  return `<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Login não concluído — Azzas</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;1,400&family=Red+Hat+Display:wght@300;400;600&display=swap" rel="stylesheet">
<style>${PAGE_CSS}</style>
</head>
<body>
<div class="card">
  <div class="brand">AZZAS <em>análises</em></div>
  <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
    <path d="M12 2L2 22h20L12 2z"></path>
    <line x1="12" y1="9" x2="12" y2="14"></line>
    <circle cx="12" cy="18" r="0.5" fill="currentColor"></circle>
  </svg>
  <h1>Login não concluído</h1>
  <p class="editorial">${safeMessage}</p>
  <p class="sub">Volte pro Claude Desktop e tente novamente. Se persistir, contate ai.labs@somagrupo.com.br.</p>
</div>
</body>
</html>`;
}

export function renderCallbackPage(params: LoopbackParams): string {
  if (params.error) {
    return renderError(resolveErrorMessage(params));
  }
  return renderSuccess(params.email ?? '');
}
```

- [ ] **Step 3.4: Rodar teste pra ver passar**

```bash
cd packages/mcp-client-dxt && npm test -- callback-page
```
Expected: todos os 6 testes passam.

- [ ] **Step 3.5: Rodar typecheck**

```bash
cd packages/mcp-client-dxt && npm run typecheck
```
Expected: nenhum erro.

- [ ] **Step 3.6: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add packages/mcp-client-dxt/src/callback-page.ts packages/mcp-client-dxt/tests/callback-page.test.ts
git commit -m "feat(dxt): renderCallbackPage com marca Azzas"
```

---

## Task 4: DXT — `auth.ts` usa `renderCallbackPage` + bump versão

**Files:**
- Modify: `packages/mcp-client-dxt/src/auth.ts:86-92`
- Modify: `packages/mcp-client-dxt/manifest.json:5`

- [ ] **Step 4.1: Substituir a string inline em `auth.ts`**

Em `packages/mcp-client-dxt/src/auth.ts`, adicione o import no topo (junto aos outros imports de `./paths.js`):

```typescript
import { renderCallbackPage } from './callback-page.js';
```

Localize o bloco dentro de `runLoopbackCallback`:

```typescript
res.writeHead(200, { 'Content-Type': 'text/html' });
res.end('<h1>Pronto!</h1><p>Você pode fechar esta aba.</p>');
clearTimeout(timer);
server!.close();
resolve({ ...params, port: activePort });
```

Substitua por:

```typescript
res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
res.end(renderCallbackPage(params));
clearTimeout(timer);
server!.close();
resolve({ ...params, port: activePort });
```

- [ ] **Step 4.2: Rodar testes de auth pra garantir que nada quebrou**

```bash
cd packages/mcp-client-dxt && npm test -- auth
```
Expected: todos passam. Os testes de loopback existentes só checam que o servidor resolve os params — não checam o HTML retornado. Se algum teste assertou a string antiga "Pronto!", ajuste-o pra asserção mais genérica (ex: `expect(html).toContain('Login concluído')`).

- [ ] **Step 4.3: Bump de versão em `manifest.json`**

Em `packages/mcp-client-dxt/manifest.json`, troque:

```json
"version": "1.0.0",
```

por:

```json
"version": "1.0.1",
```

- [ ] **Step 4.4: Rodar build completo**

```bash
cd packages/mcp-client-dxt && npm run build && npm run typecheck && npm test
```
Expected: build gera `dist/index.js` sem erro, typecheck limpo, todos os testes passam.

- [ ] **Step 4.5: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add packages/mcp-client-dxt/src/auth.ts packages/mcp-client-dxt/manifest.json
git commit -m "feat(dxt): callback loopback usa página rebrandada + bump 1.0.1"
```

---

## Task 5: Portal — `onboarding.html` rebrandado

**Files:**
- Modify: `portal/onboarding.html` (reescrita completa)

- [ ] **Step 5.1: Ler o onboarding.html atual pra listar os elementos dinâmicos**

```bash
wc -l portal/onboarding.html
```
Expected: ~120 linhas. O script JS no final faz 3 coisas: (1) popula `user-info` com email da sessão via cookie; (2) `fetch('/api/mcp/version')` → popula `dxt-version` e ribbon de update; (3) `fetch('/api/mcp/agents')` → popula lista de agentes. Precisa preservar esses comportamentos no novo HTML.

- [ ] **Step 5.2: Reescrever `portal/onboarding.html` com marca aplicada**

Substitua o conteúdo inteiro de `portal/onboarding.html` por:

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Azzas MCP — Onboarding</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;1,400&family=Red+Hat+Display:wght@300;400;600&display=swap" rel="stylesheet">
  <link rel="icon" type="image/png" sizes="32x32" href="/public/assets/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="/public/assets/favicon-16x16.png">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --ink: #000; --ink-soft: #595959; --ink-faint: #999;
      --surface: #fff; --surface-cream: #F9F6EA; --surface-warm: #E8E8E4;
      --navy: #274566; --steel: #3D5A73; --blue-soft: #A1C6ED; --blue-light: #C5D9ED;
      --font-primary: 'Red Hat Display', Arial, sans-serif;
      --font-editorial: 'Playfair Display', Georgia, serif;
    }
    body { background: var(--surface); font-family: var(--font-primary); color: var(--ink); min-height: 100vh; }
    a { color: inherit; }

    /* Ribbon */
    .ribbon { background: var(--surface-cream); padding: 0.75rem 2rem; border-bottom: 1px solid var(--surface-warm); text-align: center; font-size: 0.85rem; color: var(--ink-soft); display: none; }
    .ribbon.visible { display: block; }

    /* Header */
    header { background: var(--surface); border-bottom: 1px solid var(--surface-warm); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
    .brand { font-size: 0.85rem; letter-spacing: 0.2em; text-transform: uppercase; font-weight: 600; color: var(--ink); }
    .brand em { font-family: var(--font-editorial); font-style: italic; font-weight: 400; text-transform: none; letter-spacing: normal; color: var(--steel); font-size: 1rem; margin-left: 0.25rem; }
    nav { display: flex; gap: 1.25rem; align-items: center; font-size: 0.85rem; }
    nav a { color: var(--ink-soft); text-decoration: none; border-bottom: 1px dotted transparent; padding: 0.25rem 0; }
    nav a.active { color: var(--navy); border-bottom-color: var(--navy); font-weight: 600; }
    nav a:hover { color: var(--navy); }
    .user-chip { background: var(--surface-warm); padding: 0.35rem 0.85rem; border-radius: 20px; font-size: 0.75rem; color: var(--ink-soft); }

    /* Hero */
    .hero { background: var(--navy); color: var(--surface); padding: 4rem 2rem; }
    .hero-inner { max-width: 760px; margin: 0 auto; }
    .eyebrow { font-size: 0.7rem; letter-spacing: 0.25em; text-transform: uppercase; color: var(--blue-soft); margin-bottom: 1rem; font-weight: 600; }
    h1 { font-weight: 400; font-size: clamp(2rem, 5vw, 2.75rem); letter-spacing: -0.02em; line-height: 1.08; margin-bottom: 0.5rem; }
    .editorial { font-family: var(--font-editorial); font-style: italic; font-weight: 400; font-size: clamp(1.1rem, 2.5vw, 1.4rem); color: var(--blue-light); margin-bottom: 1.75rem; line-height: 1.3; }
    .hero p { max-width: 560px; font-size: 1rem; font-weight: 300; color: #D6E2ED; line-height: 1.6; margin-bottom: 2rem; }
    .cta { display: inline-block; background: var(--surface); color: var(--navy); padding: 1rem 1.75rem; border-radius: 4px; font-weight: 600; font-size: 0.95rem; text-decoration: none; letter-spacing: 0.02em; transition: transform 0.1s; }
    .cta:hover { transform: translateY(-1px); }
    .sub-cta { font-size: 0.8rem; color: var(--blue-soft); margin-top: 0.85rem; }

    /* Sections */
    section.content { padding: 3rem 2rem; border-bottom: 1px solid var(--surface-warm); }
    section.content-inner { max-width: 760px; margin: 0 auto; }
    section.content.alt { background: var(--surface-warm); }
    .section-heading { font-size: 0.7rem; letter-spacing: 0.25em; text-transform: uppercase; color: var(--ink-faint); margin-bottom: 1.25rem; font-weight: 600; }

    /* Steps grid */
    .steps { list-style: none; padding: 0; counter-reset: step; display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; max-width: 760px; margin: 0 auto; }
    .steps li { counter-increment: step; display: flex; gap: 1rem; align-items: flex-start; }
    .steps li::before { content: counter(step, decimal-leading-zero); font-family: var(--font-editorial); font-style: italic; color: var(--navy); font-size: 1.75rem; min-width: 2rem; line-height: 1; padding-top: 0.1rem; font-weight: 400; }
    .steps .step-text { font-size: 0.95rem; color: var(--ink-soft); line-height: 1.55; font-weight: 300; }
    .steps .step-text strong { color: var(--ink); font-weight: 600; }

    /* Agents grid */
    .agents { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; max-width: 760px; margin: 0 auto; }
    .agent { background: var(--surface-cream); padding: 1.25rem 1.5rem; border-left: 3px solid var(--navy); }
    .agent h3 { font-size: 1rem; margin-bottom: 0.3rem; font-weight: 600; }
    .agent p { font-size: 0.85rem; color: var(--ink-soft); font-weight: 300; line-height: 1.5; }

    /* Troubleshooting */
    .troubleshooting { font-size: 0.95rem; color: var(--ink-soft); line-height: 1.6; max-width: 760px; margin: 0 auto; font-weight: 300; }
    .troubleshooting p { margin-bottom: 0.85rem; }
    .troubleshooting strong { color: var(--ink); font-weight: 600; display: block; margin-bottom: 0.1rem; }
    .troubleshooting a { color: var(--navy); text-decoration: underline; }

    /* Footer */
    footer { padding: 2rem; text-align: center; font-size: 0.8rem; color: var(--ink-faint); }
    footer a { color: var(--ink-soft); }

    @media (max-width: 680px) {
      header { padding: 0.85rem 1rem; flex-wrap: wrap; }
      nav { flex-wrap: wrap; gap: 0.75rem; }
      .hero { padding: 2.5rem 1.25rem; }
      section.content { padding: 2rem 1.25rem; }
      .steps, .agents { grid-template-columns: 1fr; gap: 1.25rem; }
    }
  </style>
</head>
<body>
  <div id="ribbon" class="ribbon"></div>

  <header>
    <div class="brand">AZZAS <em>análises</em></div>
    <nav>
      <a href="/">Análises</a>
      <a href="/onboarding" class="active">Instalar no Claude</a>
      <span class="user-chip" id="user-info">—</span>
    </nav>
  </header>

  <section class="hero">
    <div class="hero-inner">
      <div class="eyebrow">Azzas 2154 · Claude Desktop</div>
      <h1>Análises onde você já está conversando.</h1>
      <p class="editorial">Uma extensão. Seu BigQuery. Sua identidade corporativa.</p>
      <p>Instale a extensão Azzas no Claude Desktop e faça perguntas aos dados sem sair do chat. As respostas usam sua permissão de acesso — nada mais, nada menos.</p>
      <a id="download-btn" class="cta" href="/api/download-dxt">Baixar Azzas MCP v<span id="dxt-version">—</span> ↓</a>
      <p class="sub-cta">macOS e Windows · última atualização: <span id="last-updated">—</span></p>
    </div>
  </section>

  <section class="content">
    <div class="content-inner">
      <h2 class="section-heading">Instalação</h2>
      <ol class="steps">
        <li><div class="step-text">Baixe o arquivo <strong>.dxt</strong> acima.</div></li>
        <li><div class="step-text">No Claude Desktop, clique no seu nome (canto inferior esquerdo) → <strong>Configurações</strong> → <strong>Extensões</strong> → <strong>Configurações avançadas</strong> → <strong>Instalar extensão</strong>.</div></li>
        <li><div class="step-text">Selecione o <strong>.dxt</strong> que você baixou e confirme em <strong>Install</strong>.</div></li>
        <li><div class="step-text">No chat, peça uma análise. Na primeira vez, o Claude abre o browser pra <strong>login corporativo</strong>. Depois disso, é só conversar.</div></li>
      </ol>
    </div>
  </section>

  <section class="content alt">
    <div class="content-inner">
      <h2 class="section-heading">O que você ganha</h2>
      <ul id="agents-list" class="agents"><li class="agent"><h3>Carregando agentes…</h3></li></ul>
    </div>
  </section>

  <section class="content">
    <div class="content-inner">
      <h2 class="section-heading">Não tem Claude Desktop?</h2>
      <p style="color: var(--ink-soft); font-weight: 300; line-height: 1.6;">Baixe em <a href="https://claude.ai/download" target="_blank" rel="noopener" style="color: var(--navy);">claude.ai/download</a>. Aceita qualquer plano Pro.</p>
    </div>
  </section>

  <section class="content alt">
    <div class="content-inner">
      <h2 class="section-heading">Problemas comuns</h2>
      <div class="troubleshooting">
        <p><strong>"Pediu login de novo depois de uns dias"</strong>Normal. A sessão expira em 7 dias, basta logar.</p>
        <p><strong>"Instalei mas não vejo as ferramentas do Azzas"</strong>Reinicie o Claude Desktop uma vez.</p>
        <p><strong>"Tentei usar uma ferramenta e deu 403"</strong>Seu e-mail precisa estar liberado pro agente em questão. Contate <a href="mailto:ai.labs@somagrupo.com.br">ai.labs@somagrupo.com.br</a>.</p>
        <p><strong>"Sua versão do Azzas MCP está desatualizada"</strong>Volte aqui e baixe a versão mais nova.</p>
      </div>
    </div>
  </section>

  <footer>
    Para times técnicos, a arquitetura está em <a href="https://github.com/somalabs/bq-analista" target="_blank" rel="noopener">README do repositório</a>.
  </footer>

  <script>
    function getSessionEmail() {
      const match = document.cookie.match(/session=([^;]+)/);
      if (!match) return null;
      const raw = decodeURIComponent(match[1]);
      const parts = raw.split('~');
      return parts.length >= 3 ? parts[0] : null;
    }
    const email = getSessionEmail();
    document.getElementById('user-info').textContent = email ?? '—';

    fetch('/api/mcp/version').then(r => r.json()).then(v => {
      document.getElementById('dxt-version').textContent = v.latest;
      const lastKnown = localStorage.getItem('mcp_last_known_version');
      if (lastKnown && lastKnown !== v.latest) {
        const ribbon = document.getElementById('ribbon');
        ribbon.textContent = `Nova versão disponível: v${v.latest}. Baixe abaixo pra atualizar.`;
        ribbon.classList.add('visible');
      }
      localStorage.setItem('mcp_last_known_version', v.latest);
    }).catch(() => {
      document.getElementById('dxt-version').textContent = '?';
    });

    fetch('/api/mcp/agents').then(r => r.json()).then(m => {
      const ul = document.getElementById('agents-list');
      ul.innerHTML = '';
      for (const a of m.agents) {
        const li = document.createElement('li');
        li.className = 'agent';
        const h3 = document.createElement('h3');
        h3.textContent = a.label;
        li.appendChild(h3);
        ul.appendChild(li);
      }
    }).catch(() => {
      document.getElementById('agents-list').innerHTML = '<li class="agent"><h3>Não consegui carregar a lista.</h3></li>';
    });

    document.getElementById('last-updated').textContent = new Date().toLocaleDateString('pt-BR');
  </script>
</body>
</html>
```

- [ ] **Step 5.3: Rodar dev server local e abrir `/onboarding.html` no browser**

```bash
cd portal && npm install && npx vercel dev --listen 3000
```

Abra http://localhost:3000/onboarding.html. (Middleware vai pedir login — pode ignorar ou logar conforme sua config local. Se preferir validar só visualmente, abra o arquivo direto: `file:///Users/arturlemos/Documents/bq-analista/portal/onboarding.html`.)

Expected visual: hero navy com eyebrow "AZZAS 2154 · CLAUDE DESKTOP", headline em Red Hat, editorial em Playfair italic, botão branco, seções alternando fundo branco/bege quente, passos numerados em Playfair italic.

- [ ] **Step 5.4: Rodar os testes do portal pra confirmar que nada quebrou**

```bash
cd portal && npm test
```
Expected: todos passam (são só api handlers, página HTML não é testada).

- [ ] **Step 5.5: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add portal/onboarding.html
git commit -m "feat(portal): onboarding.html rebrandado com paleta Azzas"
```

---

## Task 6: Portal — `index.html` header + hero + tabs + grid skeleton

Reescrita estrutural do `index.html` que troca a navegação (filtros chips horizontais) por tabs Minhas/Time/Arquivadas, adiciona link pro onboarding no header, e mantém o iframe viewer, MSAL flow e data layer antigos funcionando no intermediário. Tasks 7-10 substituirão o data layer.

**Files:**
- Modify: `portal/index.html` (reescrita do HTML + CSS; mantém scripts)

- [ ] **Step 6.1: Ler o arquivo atual e listar os blocos a preservar**

```bash
wc -l portal/index.html
```

Preservar (não tocar por enquanto):
- `<script type="importmap">` com MSAL (linhas ~14-20)
- `<script type="module" src="/msal-init.js">` (linha ~295 aproximadamente)
- Bloco de `<script type="module">` no final com: `initMsal`, `init()`, `loadLibrary`, `buildFilters`, `getFiltered`, `renderGrid`, `openAnalysis`, `shareAnalysis`. **Em Task 7+ esses serão reescritos.**

Vai mudar totalmente:
- `<style>` — atualiza paleta/tipografia/layout pra incluir header, nav, hero com tabs, toolbar, grid de cards
- Estrutura `<body>`: substitui header antigo + filtros por header novo (brand + nav), hero da library, tabs, toolbar (busca + facets), grid. Iframe viewer (library-view / analysis-view) fica idêntico.

- [ ] **Step 6.2: Substituir `<body>` pelo novo layout**

Em `portal/index.html`, ache o `<body>` atual e o bloco `#loading` + `#library-view` + `#analysis-view`. Substitua tudo dentro do `<body>` (mas ANTES do primeiro `<script type="module">`) por:

```html
<body>
  <div id="loading">
    <div class="spinner"></div>
    <p>Carregando…</p>
  </div>

  <div id="library-view">
    <header>
      <div class="brand">AZZAS <em>análises</em></div>
      <nav>
        <a href="/" class="active">Análises</a>
        <a href="/onboarding">Instalar no Claude</a>
        <span class="user-chip" id="user-email">—</span>
      </nav>
    </header>

    <section class="hero">
      <div class="hero-inner">
        <h1 id="hero-title">Minhas análises</h1>
        <p class="editorial" id="hero-sub">—</p>
      </div>
    </section>

    <div class="tabs" role="tablist">
      <button class="tab active" data-tab="mine" role="tab">Minhas <span class="count" id="count-mine">0</span></button>
      <button class="tab" data-tab="team" role="tab">Time <span class="count" id="count-team">0</span></button>
      <button class="tab" data-tab="archived" role="tab">Arquivadas <span class="count" id="count-archived">0</span></button>
    </div>

    <div class="toolbar">
      <input id="search" class="search" type="search" placeholder="Buscar por título, descrição, tag, marca…" autocomplete="off">
      <select id="facet-agent" class="facet"><option value="">Agente</option></select>
      <select id="facet-brand" class="facet"><option value="">Marca</option></select>
      <select id="facet-period" class="facet">
        <option value="">Período</option>
        <option value="7d">Últimos 7 dias</option>
        <option value="30d">Últimos 30 dias</option>
        <option value="quarter">Este trimestre</option>
        <option value="year">Este ano</option>
        <option value="all">Tudo</option>
      </select>
      <select id="facet-sort" class="facet">
        <option value="recent">Mais recente</option>
        <option value="old">Mais antiga</option>
        <option value="title">Título A→Z</option>
      </select>
      <button id="mobile-filters" class="mobile-filters">Filtros ▾</button>
    </div>

    <div id="grid"></div>
  </div>

  <div id="analysis-view">
    <div id="analysis-topbar">
      <button id="back-btn">← voltar</button>
      <span id="analysis-crumb"></span>
    </div>
    <iframe id="analysis-iframe" title="Análise"></iframe>
  </div>

  <div id="toast" class="toast" aria-live="polite"></div>
```

- [ ] **Step 6.3: Substituir o bloco `<style>` (mantém tokens `:root`) pelo novo CSS**

Em `portal/index.html`, substitua TUDO dentro de `<style>...</style>` por:

```css
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --ink: #000; --ink-soft: #595959; --ink-faint: #999;
      --surface: #fff; --surface-warm: #E8E8E4; --surface-cream: #F9F6EA;
      --navy: #274566; --steel: #3D5A73; --blue-soft: #A1C6ED; --blue-light: #C5D9ED;
      --status-pending: #B5AFA8;
      --font-primary: 'Red Hat Display', Arial, sans-serif;
      --font-editorial: 'Playfair Display', Georgia, serif;
    }

    body { background: var(--surface); color: var(--ink); font-family: var(--font-primary); min-height: 100vh; }
    a { color: inherit; }
    button { font-family: inherit; cursor: pointer; }

    /* Loading */
    #loading { display: flex; align-items: center; justify-content: center; height: 100vh; flex-direction: column; gap: 16px; color: var(--ink-soft); }
    .spinner { width: 32px; height: 32px; border: 3px solid var(--surface-warm); border-top-color: var(--navy); border-radius: 50%; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Views */
    #library-view { display: none; }
    #analysis-view { display: none; flex-direction: column; position: fixed; inset: 0; background: var(--surface); z-index: 10; }

    /* Header */
    header { background: var(--surface); border-bottom: 1px solid var(--surface-warm); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
    .brand { font-size: 0.85rem; letter-spacing: 0.2em; text-transform: uppercase; font-weight: 600; color: var(--ink); }
    .brand em { font-family: var(--font-editorial); font-style: italic; font-weight: 400; text-transform: none; letter-spacing: normal; color: var(--steel); font-size: 1rem; margin-left: 0.25rem; }
    nav { display: flex; gap: 1.25rem; align-items: center; font-size: 0.85rem; }
    nav a { color: var(--ink-soft); text-decoration: none; border-bottom: 1px dotted transparent; padding: 0.25rem 0; }
    nav a.active { color: var(--navy); border-bottom-color: var(--navy); font-weight: 600; }
    nav a:hover { color: var(--navy); }
    .user-chip { background: var(--surface-warm); padding: 0.35rem 0.85rem; border-radius: 20px; font-size: 0.75rem; color: var(--ink-soft); }

    /* Hero */
    .hero { background: var(--surface-cream); padding: 2rem; border-bottom: 1px solid var(--surface-warm); }
    .hero-inner { max-width: 1200px; margin: 0 auto; }
    .hero h1 { font-weight: 400; font-size: clamp(1.5rem, 3.5vw, 2rem); letter-spacing: -0.01em; margin-bottom: 0.3rem; }
    .hero .editorial { font-family: var(--font-editorial); font-style: italic; font-size: 1.05rem; color: var(--steel); }

    /* Tabs */
    .tabs { background: var(--surface); padding: 0 2rem; display: flex; gap: 0; border-bottom: 1px solid var(--surface-warm); }
    .tab { background: transparent; border: none; padding: 0.9rem 1.25rem; font-size: 0.85rem; color: var(--ink-faint); border-bottom: 2px solid transparent; letter-spacing: 0.02em; }
    .tab.active { color: var(--navy); border-bottom-color: var(--navy); font-weight: 600; }
    .tab:hover { color: var(--ink-soft); }
    .tab .count { display: inline-block; background: var(--surface-warm); color: var(--ink-soft); font-size: 0.7rem; padding: 0.05rem 0.5rem; border-radius: 8px; margin-left: 0.4rem; font-weight: 400; }
    .tab.active .count { background: var(--blue-light); color: var(--navy); }

    /* Toolbar */
    .toolbar { background: var(--surface); padding: 1rem 2rem; display: flex; gap: 0.5rem; align-items: center; border-bottom: 1px solid var(--surface-warm); flex-wrap: wrap; }
    .search { flex: 1; min-width: 200px; border: 1px solid var(--surface-warm); padding: 0.55rem 0.85rem; border-radius: 6px; font-size: 0.9rem; color: var(--ink); font-family: inherit; background: var(--surface); }
    .search:focus { outline: none; border-color: var(--navy); }
    .facet { border: 1px solid var(--surface-warm); background: var(--surface); padding: 0.55rem 0.75rem; border-radius: 6px; font-size: 0.85rem; color: var(--ink-soft); font-family: inherit; }
    .mobile-filters { display: none; border: 1px solid var(--surface-warm); background: var(--surface); padding: 0.55rem 1rem; border-radius: 6px; font-size: 0.85rem; color: var(--ink-soft); }

    /* Grid */
    #grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; padding: 1.5rem 2rem 3rem; max-width: 1400px; margin: 0 auto; }

    /* Card */
    .card { background: var(--surface); border: 1px solid var(--surface-warm); border-radius: 8px; overflow: hidden; position: relative; display: flex; flex-direction: column; transition: border-color 0.15s, transform 0.1s; }
    .card:hover { border-color: var(--navy); transform: translateY(-2px); }
    .card-thumb { height: 88px; position: relative; cursor: pointer; }
    .card-brand-chip { position: absolute; top: 0.7rem; left: 0.7rem; background: rgba(255,255,255,0.92); padding: 0.1rem 0.5rem; border-radius: 3px; font-size: 0.65rem; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase; color: var(--navy); }
    .card-menu { position: absolute; top: 0.6rem; right: 0.6rem; background: rgba(255,255,255,0.92); border: none; width: 26px; height: 26px; border-radius: 4px; font-size: 1rem; color: var(--ink-soft); line-height: 1; padding: 0; }
    .card-menu:hover { background: var(--surface); color: var(--navy); }
    .card-body { padding: 0.85rem 1rem 1rem; cursor: pointer; flex: 1; display: flex; flex-direction: column; }
    .card-title { font-size: 0.9rem; font-weight: 600; line-height: 1.3; margin-bottom: 0.25rem; }
    .card-meta { font-size: 0.7rem; color: var(--ink-faint); margin-bottom: 0.4rem; }
    .card-meta .agent { font-size: 0.65rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--steel); margin-right: 0.35rem; }
    .card-desc { font-size: 0.8rem; color: var(--ink-soft); line-height: 1.45; font-weight: 300; margin-bottom: 0.6rem; flex: 1; }
    .card-tags { display: flex; gap: 0.3rem; flex-wrap: wrap; }
    .tag-chip { font-size: 0.6rem; padding: 0.1rem 0.45rem; background: var(--surface-warm); color: var(--ink-soft); border-radius: 10px; letter-spacing: 0.05em; text-transform: uppercase; font-weight: 600; }

    /* Card menu dropdown */
    .card-menu-dropdown { position: absolute; top: 2.3rem; right: 0.6rem; background: var(--surface); border: 1px solid var(--surface-warm); border-radius: 6px; padding: 0.3rem 0; box-shadow: 0 4px 12px rgba(0,0,0,0.06); z-index: 2; min-width: 160px; display: none; }
    .card-menu-dropdown.open { display: block; }
    .card-menu-dropdown button { display: block; width: 100%; text-align: left; background: transparent; border: none; padding: 0.5rem 0.85rem; font-size: 0.85rem; color: var(--ink-soft); cursor: pointer; }
    .card-menu-dropdown button:hover { background: var(--surface-cream); color: var(--navy); }

    /* Empty states */
    .empty { grid-column: 1 / -1; text-align: center; padding: 4rem 2rem; color: var(--ink-faint); font-family: var(--font-editorial); font-style: italic; font-size: 1.1rem; }
    .empty-hint { display: block; font-family: var(--font-primary); font-style: normal; font-size: 0.85rem; color: var(--ink-soft); margin-top: 0.5rem; }

    /* Analysis view (iframe) */
    #analysis-topbar { background: var(--ink); color: var(--surface); padding: 0.85rem 1.5rem; display: flex; align-items: center; gap: 1rem; font-size: 0.85rem; }
    #back-btn { background: transparent; border: 1px solid rgba(255,255,255,0.3); color: var(--surface); padding: 0.3rem 0.75rem; border-radius: 4px; font-size: 0.8rem; }
    #back-btn:hover { border-color: var(--surface); }
    #analysis-iframe { flex: 1; border: none; width: 100%; background: var(--surface); }

    /* Toast */
    .toast { position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%) translateY(200%); background: var(--ink); color: var(--surface); padding: 0.75rem 1.25rem; border-radius: 6px; font-size: 0.85rem; font-weight: 500; z-index: 100; transition: transform 0.25s ease-out; pointer-events: none; }
    .toast.visible { transform: translateX(-50%) translateY(0); }

    /* Responsive */
    @media (max-width: 900px) {
      #grid { grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); padding: 1.25rem; }
    }
    @media (max-width: 600px) {
      header { padding: 0.85rem 1rem; flex-wrap: wrap; gap: 0.75rem; }
      nav { flex-wrap: wrap; gap: 0.75rem; font-size: 0.8rem; }
      .hero { padding: 1.5rem 1rem; }
      .tabs { padding: 0 1rem; overflow-x: auto; }
      .tab { padding: 0.75rem 0.85rem; white-space: nowrap; }
      .toolbar { padding: 0.85rem 1rem; }
      .facet, #facet-agent, #facet-brand, #facet-period, #facet-sort { display: none; }
      .mobile-filters { display: block; }
      .search { width: 100%; min-width: 0; }
      #grid { grid-template-columns: 1fr; padding: 1rem; }
    }
```

- [ ] **Step 6.4: Verificar no browser que a nova estrutura aparece**

```bash
cd portal && npx vercel dev --listen 3000
```
Abra http://localhost:3000/. Logue (ou use o cookie da sessão atual).

Expected: header novo (AZZAS análises + nav), hero creme com "Minhas análises", tabs, toolbar com busca e facets, grade de cards. Os cards ainda renderizam via código antigo (pode ficar bagunçado porque o HTML dos cards mudou). **Não é pra funcionar 100% ainda** — o objetivo dessa task é o esqueleto visual. Tasks 7+ religam a lógica.

- [ ] **Step 6.5: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add portal/index.html
git commit -m "feat(portal): novo layout do index.html (header+hero+tabs+toolbar)"
```

---

## Task 7: Portal — data layer cross-domain

Substitui o carregamento single-domain por fetch paralelo de todos os agentes via `/api/mcp/agents`. Classifica items em mine/team. Preserva `openAnalysis`/`shareAnalysis` existentes.

**Files:**
- Modify: `portal/index.html` (só o bloco `<script type="module">` no final)

- [ ] **Step 7.1: Localizar o bloco de script do data layer atual**

Ache no fim de `portal/index.html` o `<script type="module">` que contém `let userIdentity = null`, `async function init()`, `async function loadLibrary(domain)`, `buildFilters`, `getFiltered`, `renderGrid`, `openAnalysis`, `shareAnalysis`. Esse é o bloco que vai ser reescrito.

- [ ] **Step 7.2: Substituir o bloco de script pelo novo**

Substitua todo o conteúdo entre `<script type="module">` e `</script>` no FINAL do arquivo por:

```javascript
import { initMsal } from '/msal-init.js'
import { InteractionRequiredAuthError } from '@azure/msal-browser'

// ─── Estado global ─────────────────────────────────────────────────────────
let userIdentity = null                    // slug do email (usado no middleware)
let userEmail = null                       // email completo (lowercase)
let allItems = []                          // Todos os items carregados, c/ source e agent
let activeTab = 'mine'                     // 'mine' | 'team' | 'archived'
let searchQuery = ''
let filterAgent = ''
let filterBrand = ''
let filterPeriod = ''
let sortMode = 'recent'

// ─── LocalStorage: arquivamento ────────────────────────────────────────────
const ARCHIVE_KEY = 'azzas_archived'

function getArchivedIds() {
  try {
    const raw = localStorage.getItem(ARCHIVE_KEY)
    if (!raw) return new Set()
    const arr = JSON.parse(raw)
    return new Set(arr.map(a => a.id))
  } catch { return new Set() }
}
function setArchived(ids) {
  const arr = [...ids].map(id => ({ id, archivedAt: new Date().toISOString() }))
  localStorage.setItem(ARCHIVE_KEY, JSON.stringify(arr))
}
function archiveItem(id) {
  const s = getArchivedIds(); s.add(id); setArchived(s)
}
function unarchiveItem(id) {
  const s = getArchivedIds(); s.delete(id); setArchived(s)
}

// ─── Slug de email (igual ao Python) ───────────────────────────────────────
// packages/mcp-core/src/mcp_core/server_factory.py:
//   email_slug = re.sub(r"[^a-z0-9]+", "-", exec_email.lower()).strip("-")[:24] or "user"
function emailSlug(email) {
  if (!email) return 'user'
  const s = email.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 24)
  return s || 'user'
}

// ─── Classificação mine/team ───────────────────────────────────────────────
function isMine(item) {
  if (item.source === 'private') return true
  if (item.author_email) return item.author_email.toLowerCase() === userEmail
  // Fallback pra items antigos sem author_email: checa prefixo do filename
  const slug = emailSlug(userEmail)
  return (item.filename ?? '').startsWith(slug + '-')
}

// ─── Filtros ───────────────────────────────────────────────────────────────
function matchesSearch(item, q) {
  if (!q) return true
  const hay = [item.title, item.description, (item.tags ?? []).join(' '), item.brand]
    .filter(Boolean).join(' ').toLowerCase()
  return hay.includes(q.toLowerCase())
}
function matchesAgent(item, slug) { return !slug || item.agent?.name === slug }
function matchesBrand(item, brand) { return !brand || item.brand === brand }
function matchesPeriod(item, code) {
  if (!code || code === 'all') return true
  const d = Date.parse(item.date)
  if (Number.isNaN(d)) return false
  const now = Date.now()
  const day = 86400000
  if (code === '7d') return now - d <= 7 * day
  if (code === '30d') return now - d <= 30 * day
  if (code === 'quarter') {
    const nowDate = new Date(now); const qStart = new Date(nowDate.getFullYear(), Math.floor(nowDate.getMonth() / 3) * 3, 1)
    return d >= qStart.getTime()
  }
  if (code === 'year') {
    const y = new Date(now).getFullYear()
    return d >= Date.parse(`${y}-01-01`)
  }
  return true
}

// ─── Carregamento ──────────────────────────────────────────────────────────
async function init() {
  try {
    const msalInstance = await initMsal()
    await msalInstance.initialize()
    const redirectResult = await msalInstance.handleRedirectPromise()
    let idToken = null
    if (redirectResult) { idToken = redirectResult.idToken }
    else {
      const accounts = msalInstance.getAllAccounts()
      if (accounts.length === 0) { await msalInstance.loginRedirect({ scopes: ['openid', 'profile'] }); return }
      try {
        const silent = await msalInstance.acquireTokenSilent({ account: accounts[0], scopes: ['openid', 'profile'] })
        idToken = silent.idToken
      } catch (e) {
        if (e instanceof InteractionRequiredAuthError) { await msalInstance.loginRedirect({ scopes: ['openid', 'profile'] }); return }
        throw e
      }
    }

    const authResult = await fetch('/api/auth', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idToken }), credentials: 'include' })
    if (!authResult.ok) throw new Error('Falha na autenticação com o servidor')
    const { identity } = await authResult.json()
    userIdentity = identity
    userEmail = identity.toLowerCase()

    const accounts = msalInstance.getAllAccounts()
    document.getElementById('user-email').textContent = accounts[0]?.username ?? userEmail

    await loadAllLibraries()
  } catch (err) {
    document.getElementById('loading').innerHTML =
      `<p style="color:var(--ink); font-family:var(--font-editorial); font-style:italic;">Erro: ${err.message}</p>`
  }
}

async function loadAllLibraries() {
  const agentsRes = await fetch('/api/mcp/agents')
  if (!agentsRes.ok) throw new Error('Não consegui buscar a lista de agentes')
  const { agents } = await agentsRes.json()

  const tasks = []
  for (const agent of agents) {
    tasks.push(fetchLibraryFile(agent, 'private'))
    tasks.push(fetchLibraryFile(agent, 'public'))
  }
  const results = await Promise.all(tasks)
  const merged = new Map() // dedupe by id, private wins
  for (const list of results) {
    for (const item of list) {
      if (item.source === 'private' || !merged.has(item.id)) {
        merged.set(item.id, item)
      }
    }
  }
  allItems = [...merged.values()]
  render()
  document.getElementById('loading').style.display = 'none'
  document.getElementById('library-view').style.display = 'block'
}

async function fetchLibraryFile(agent, source) {
  const path = source === 'private'
    ? `/library/${agent.name}/${encodeURIComponent(userIdentity)}.json`
    : `/library/${agent.name}/public.json`
  try {
    const r = await fetch(path)
    if (!r.ok) return []
    const arr = await r.json()
    return arr.map(item => ({ ...item, source, agent: { name: agent.name, label: agent.label } }))
  } catch { return [] }
}

// ─── Render ────────────────────────────────────────────────────────────────
function render() {
  const archivedIds = getArchivedIds()
  const visibleInTab = allItems.filter(item => {
    const archived = archivedIds.has(item.id)
    if (activeTab === 'archived') return archived
    if (archived) return false
    if (activeTab === 'mine') return isMine(item)
    if (activeTab === 'team') return !isMine(item)
    return true
  })

  // Counts (tabs sempre refletem universo antes dos facets/busca)
  const countMine = allItems.filter(i => !archivedIds.has(i.id) && isMine(i)).length
  const countTeam = allItems.filter(i => !archivedIds.has(i.id) && !isMine(i)).length
  const countArchived = [...archivedIds].filter(id => allItems.some(i => i.id === id)).length
  document.getElementById('count-mine').textContent = countMine
  document.getElementById('count-team').textContent = countTeam
  document.getElementById('count-archived').textContent = countArchived

  // Facets filtram o que é mostrado DENTRO da tab
  let filtered = visibleInTab
    .filter(i => matchesSearch(i, searchQuery))
    .filter(i => matchesAgent(i, filterAgent))
    .filter(i => matchesBrand(i, filterBrand))
    .filter(i => matchesPeriod(i, filterPeriod))

  // Sort
  if (sortMode === 'recent') filtered.sort((a, b) => (b.date ?? '').localeCompare(a.date ?? ''))
  else if (sortMode === 'old') filtered.sort((a, b) => (a.date ?? '').localeCompare(b.date ?? ''))
  else if (sortMode === 'title') filtered.sort((a, b) => (a.title ?? '').localeCompare(b.title ?? ''))

  renderHero(countMine, countTeam, countArchived)
  renderFacets(visibleInTab)
  renderGrid(filtered)
}

function renderHero(mine, team, archived) {
  const titleEl = document.getElementById('hero-title')
  const subEl = document.getElementById('hero-sub')
  if (activeTab === 'mine') {
    titleEl.textContent = 'Minhas análises'
    subEl.textContent = `${mine} publicadas · ${archived} arquivadas`
  } else if (activeTab === 'team') {
    titleEl.textContent = 'Análises do time'
    subEl.textContent = `${team} publicadas por colegas`
  } else {
    titleEl.textContent = 'Arquivadas'
    subEl.textContent = `${archived} escondidas da sua library`
  }
}

function renderFacets(items) {
  const agents = [...new Map(items.filter(i => i.agent).map(i => [i.agent.name, i.agent])).values()]
  const brands = [...new Set(items.map(i => i.brand).filter(Boolean))].sort()
  fillSelect('facet-agent', 'Agente', agents.map(a => [a.name, a.label]))
  fillSelect('facet-brand', 'Marca', brands.map(b => [b, b]))
}
function fillSelect(id, label, options) {
  const el = document.getElementById(id)
  const current = el.value
  el.innerHTML = `<option value="">${label}</option>` + options.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')
  if (options.some(([v]) => v === current)) el.value = current
}

function renderGrid(items) {
  const grid = document.getElementById('grid')
  if (items.length === 0) {
    grid.innerHTML = renderEmpty()
    return
  }
  grid.innerHTML = ''
  for (const item of items) { grid.appendChild(buildCard(item)) }
}

function renderEmpty() {
  if (activeTab === 'mine' && !searchQuery && !filterAgent && !filterBrand && !filterPeriod) {
    return `<div class="empty">Você ainda não publicou nenhuma análise.<span class="empty-hint">Peça uma análise no Claude Desktop com a extensão Azzas MCP instalada.</span></div>`
  }
  if (activeTab === 'team' && !searchQuery && !filterAgent && !filterBrand && !filterPeriod) {
    return `<div class="empty">O time ainda não publicou nada público.</div>`
  }
  if (activeTab === 'archived') {
    return `<div class="empty">Nada arquivado.</div>`
  }
  return `<div class="empty">Nenhuma análise encontrada${searchQuery ? ` pra "${searchQuery}"` : ''}.</div>`
}

function brandGradient(brand) {
  // Rotação determinística por hash simples
  const palette = [
    'linear-gradient(135deg, #C5D9ED, #A1C6ED)',       // light → powder
    'linear-gradient(135deg, #F9F6EA, #E8D9A6)',       // cream → tan
    'linear-gradient(135deg, #3D5A73, #274566)',       // steel → navy
    'linear-gradient(135deg, #E8E8E4, #B5AFA8)',       // bege → warm gray
  ]
  let h = 0
  for (const ch of (brand ?? 'default')) { h = (h * 31 + ch.charCodeAt(0)) >>> 0 }
  return palette[h % palette.length]
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const d = Date.parse(dateStr); if (Number.isNaN(d)) return ''
  const days = Math.floor((Date.now() - d) / 86400000)
  if (days < 1) return 'hoje'
  if (days === 1) return 'há 1 dia'
  if (days < 30) return `há ${days} dias`
  if (days < 365) return `há ${Math.floor(days / 30)} meses`
  return `há ${Math.floor(days / 365)} anos`
}

function buildCard(item) {
  const card = document.createElement('div')
  card.className = 'card'
  const darkThumb = /steel|navy/.test(brandGradient(item.brand))
  card.innerHTML = `
    <div class="card-thumb" style="background: ${brandGradient(item.brand)};">
      ${item.brand ? `<div class="card-brand-chip"${darkThumb ? ' style="background:#fff;"' : ''}>${escapeHtml(item.brand)}</div>` : ''}
      <button class="card-menu" aria-label="Mais ações">⋯</button>
      <div class="card-menu-dropdown"></div>
    </div>
    <div class="card-body">
      <div class="card-title">${escapeHtml(item.title ?? '—')}</div>
      <div class="card-meta">
        ${item.agent?.label ? `<span class="agent">${escapeHtml(item.agent.label)}</span>·` : ''}
        ${escapeHtml(item.period ?? item.date ?? '')} ${item.date ? `· ${timeAgo(item.date)}` : ''}
      </div>
      <div class="card-desc">${escapeHtml(item.description ?? '')}</div>
      <div class="card-tags">${(item.tags ?? []).map(t => `<span class="tag-chip">${escapeHtml(t)}</span>`).join('')}</div>
    </div>
  `
  card.querySelector('.card-thumb').addEventListener('click', ev => { if (!ev.target.closest('.card-menu')) openAnalysis(item) })
  card.querySelector('.card-body').addEventListener('click', () => openAnalysis(item))
  card.querySelector('.card-menu').addEventListener('click', ev => { ev.stopPropagation(); toggleMenu(card, item) })
  return card
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

// ─── Menu + ações do card (placeholder; Task 10 implementa) ───────────────
function toggleMenu(card, item) {
  const dropdown = card.querySelector('.card-menu-dropdown')
  // Fecha outros
  document.querySelectorAll('.card-menu-dropdown.open').forEach(d => { if (d !== dropdown) d.classList.remove('open') })
  // Conteúdo
  const archivedIds = getArchivedIds()
  const archived = archivedIds.has(item.id)
  const publicItem = item.source === 'public'
  let html = ''
  if (publicItem && !archived) html += `<button data-action="copy-link">Copiar link</button>`
  if (!publicItem && !archived) html += `<button data-action="share">Tornar pública</button>`
  html += archived ? `<button data-action="unarchive">Restaurar</button>` : `<button data-action="archive">Arquivar</button>`
  dropdown.innerHTML = html
  dropdown.classList.toggle('open')

  dropdown.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.stopPropagation()
      dropdown.classList.remove('open')
      const action = btn.dataset.action
      if (action === 'archive') { archiveItem(item.id); render() }
      else if (action === 'unarchive') { unarchiveItem(item.id); render() }
      else if (action === 'copy-link') { copyLink(item) }
      else if (action === 'share') { shareAnalysis(item) }
    })
  })
}

async function copyLink(item) {
  const url = window.location.origin + (item.link ?? `/${item.file ?? ''}`)
  try {
    await navigator.clipboard.writeText(url)
    showToast('Link copiado')
  } catch {
    showToast('Não consegui copiar — verifique permissão')
  }
}

function showToast(text) {
  const el = document.getElementById('toast')
  el.textContent = text
  el.classList.add('visible')
  clearTimeout(el._timer)
  el._timer = setTimeout(() => el.classList.remove('visible'), 2000)
}

async function shareAnalysis(item) {
  try {
    const res = await fetch('/api/share', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ analysisId: item.id }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.error ?? 'Erro desconhecido')
    await loadAllLibraries()
    showToast('Análise agora é pública')
  } catch (err) {
    showToast(`Erro ao tornar público: ${err.message}`)
  }
}

// ─── Iframe viewer ─────────────────────────────────────────────────────────
function openAnalysis(item) {
  document.getElementById('library-view').style.display = 'none'
  const view = document.getElementById('analysis-view')
  view.style.display = 'flex'
  document.getElementById('analysis-crumb').textContent = `${item.brand ?? ''} · ${item.title ?? ''}`
  document.getElementById('analysis-iframe').src = item.file ?? item.link?.replace(/^\//, '') ?? ''
}

document.getElementById('back-btn').addEventListener('click', () => {
  document.getElementById('analysis-view').style.display = 'none'
  document.getElementById('analysis-iframe').src = ''
  document.getElementById('library-view').style.display = 'block'
})

// ─── Tabs e facets ─────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'))
    t.classList.add('active')
    activeTab = t.dataset.tab
    render()
  })
})
document.getElementById('search').addEventListener('input', ev => { searchQuery = ev.target.value; render() })
document.getElementById('facet-agent').addEventListener('change', ev => { filterAgent = ev.target.value; render() })
document.getElementById('facet-brand').addEventListener('change', ev => { filterBrand = ev.target.value; render() })
document.getElementById('facet-period').addEventListener('change', ev => { filterPeriod = ev.target.value; render() })
document.getElementById('facet-sort').addEventListener('change', ev => { sortMode = ev.target.value; render() })

// Fecha menus ao clicar fora
document.addEventListener('click', () => {
  document.querySelectorAll('.card-menu-dropdown.open').forEach(d => d.classList.remove('open'))
})

// Bottom sheet mobile (Task 9 implementa)
document.getElementById('mobile-filters').addEventListener('click', openBottomSheet)

function openBottomSheet() {
  // Placeholder — implementado em Task 9
  alert('Filtros: implementação mobile em Task 9')
}

init()
```

- [ ] **Step 7.3: Verificar no browser**

```bash
cd portal && npx vercel dev --listen 3000
```

Abra http://localhost:3000/ e faça login. Expected:
- Cards aparecem distribuídos nas tabs Minhas e Time
- Busca filtra
- Facets de Agente e Marca aparecem populados
- Contagens nas tabs refletem números reais
- Clicar num card abre iframe fullscreen; voltar funciona
- "Copiar link" aparece em items públicos, "Tornar pública" em items privados
- Arquivar move pra tab Arquivadas

- [ ] **Step 7.4: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add portal/index.html
git commit -m "feat(portal): data layer cross-domain + tabs + facets + archive"
```

---

## Task 8: Portal — empty states polish + render loading skeleton

Cosmético. Hoje o loading é só um spinner; durante fetch, queremos skeleton de cards. Também polir mensagens de erro no load.

**Files:**
- Modify: `portal/index.html`

- [ ] **Step 8.1: Adicionar CSS do skeleton**

No bloco `<style>`, adicione antes do `/* Responsive */`:

```css
    /* Skeleton */
    .skeleton-card { background: var(--surface); border: 1px solid var(--surface-warm); border-radius: 8px; height: 200px; position: relative; overflow: hidden; }
    .skeleton-card::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,0.6), transparent); animation: shimmer 1.4s infinite; }
    @keyframes shimmer { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
```

- [ ] **Step 8.2: Renderizar skeleton durante o fetch inicial**

No script, logo antes de `await loadAllLibraries()` dentro de `init()`, adicione:

```javascript
document.getElementById('loading').style.display = 'none'
document.getElementById('library-view').style.display = 'block'
document.getElementById('grid').innerHTML = Array.from({length: 6}).map(() => '<div class="skeleton-card"></div>').join('')
```

E em `loadAllLibraries` remova as duas linhas finais que já ocultavam `#loading` e mostravam `#library-view` (agora são redundantes):

```javascript
allItems = [...merged.values()]
render()
```

- [ ] **Step 8.3: Verificar no browser**

Reload. Expected: durante o carregamento, aparecem 6 cards skeleton com shimmer. Depois os cards reais substituem.

- [ ] **Step 8.4: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add portal/index.html
git commit -m "feat(portal): loading skeleton em vez de spinner cheio"
```

---

## Task 9: Portal — Bottom sheet mobile pros facets

**Files:**
- Modify: `portal/index.html`

- [ ] **Step 9.1: Adicionar HTML do bottom sheet**

Em `portal/index.html`, adicione logo depois do `<div id="toast" ...>` (antes do primeiro `<script type="module">`):

```html
  <div id="sheet" class="sheet" role="dialog" aria-modal="true" aria-hidden="true">
    <div class="sheet-backdrop"></div>
    <div class="sheet-panel">
      <div class="sheet-handle"></div>
      <div class="sheet-header">Filtros</div>
      <div class="sheet-content">
        <label class="sheet-field"><span>Agente</span><select id="sheet-agent"></select></label>
        <label class="sheet-field"><span>Marca</span><select id="sheet-brand"></select></label>
        <label class="sheet-field"><span>Período</span>
          <select id="sheet-period">
            <option value="">Tudo</option>
            <option value="7d">Últimos 7 dias</option>
            <option value="30d">Últimos 30 dias</option>
            <option value="quarter">Este trimestre</option>
            <option value="year">Este ano</option>
          </select>
        </label>
        <label class="sheet-field"><span>Ordenar</span>
          <select id="sheet-sort">
            <option value="recent">Mais recente</option>
            <option value="old">Mais antiga</option>
            <option value="title">Título A→Z</option>
          </select>
        </label>
      </div>
      <div class="sheet-footer">
        <button id="sheet-apply">Aplicar</button>
      </div>
    </div>
  </div>
```

- [ ] **Step 9.2: Adicionar CSS do bottom sheet**

No `<style>`, após o bloco `.toast`, adicione:

```css
    /* Bottom sheet */
    .sheet { position: fixed; inset: 0; z-index: 200; display: none; }
    .sheet.open { display: block; }
    .sheet-backdrop { position: absolute; inset: 0; background: rgba(0,0,0,0.4); opacity: 0; transition: opacity 0.2s; }
    .sheet.open .sheet-backdrop { opacity: 1; }
    .sheet-panel { position: absolute; left: 0; right: 0; bottom: 0; background: var(--surface); border-radius: 16px 16px 0 0; padding: 0.5rem 1.5rem 1.5rem; max-height: 75vh; transform: translateY(100%); transition: transform 0.25s ease-out; display: flex; flex-direction: column; }
    .sheet.open .sheet-panel { transform: translateY(0); }
    .sheet-handle { width: 40px; height: 4px; background: var(--surface-warm); border-radius: 2px; margin: 0.5rem auto 1rem; }
    .sheet-header { font-size: 0.75rem; letter-spacing: 0.2em; text-transform: uppercase; color: var(--ink-faint); font-weight: 600; margin-bottom: 1rem; }
    .sheet-content { display: flex; flex-direction: column; gap: 1rem; overflow-y: auto; }
    .sheet-field { display: flex; flex-direction: column; gap: 0.35rem; }
    .sheet-field span { font-size: 0.8rem; color: var(--ink-soft); }
    .sheet-field select { border: 1px solid var(--surface-warm); padding: 0.65rem 0.75rem; border-radius: 6px; font-size: 0.95rem; font-family: inherit; background: var(--surface); color: var(--ink); }
    .sheet-footer { padding-top: 1rem; }
    .sheet-footer button { width: 100%; background: var(--navy); color: var(--surface); border: none; padding: 0.9rem; border-radius: 6px; font-size: 0.95rem; font-weight: 600; }
```

- [ ] **Step 9.3: Substituir a função stub `openBottomSheet` pelo handler real**

No script, substitua:

```javascript
function openBottomSheet() {
  // Placeholder — implementado em Task 9
  alert('Filtros: implementação mobile em Task 9')
}
```

por:

```javascript
function openBottomSheet() {
  const agents = [...new Map(allItems.filter(i => i.agent).map(i => [i.agent.name, i.agent])).values()]
  const brands = [...new Set(allItems.map(i => i.brand).filter(Boolean))].sort()
  fillSelect('sheet-agent', 'Agente', agents.map(a => [a.name, a.label]))
  fillSelect('sheet-brand', 'Marca', brands.map(b => [b, b]))
  document.getElementById('sheet-agent').value = filterAgent
  document.getElementById('sheet-brand').value = filterBrand
  document.getElementById('sheet-period').value = filterPeriod
  document.getElementById('sheet-sort').value = sortMode
  const sheet = document.getElementById('sheet')
  sheet.classList.add('open')
  sheet.setAttribute('aria-hidden', 'false')
}
function closeBottomSheet() {
  const sheet = document.getElementById('sheet')
  sheet.classList.remove('open')
  sheet.setAttribute('aria-hidden', 'true')
}

document.querySelector('#sheet .sheet-backdrop').addEventListener('click', closeBottomSheet)
document.getElementById('sheet-apply').addEventListener('click', () => {
  filterAgent = document.getElementById('sheet-agent').value
  filterBrand = document.getElementById('sheet-brand').value
  filterPeriod = document.getElementById('sheet-period').value
  sortMode = document.getElementById('sheet-sort').value
  // Sincroniza os selects de desktop também (caso usuário volte pro desktop sem recarregar)
  document.getElementById('facet-agent').value = filterAgent
  document.getElementById('facet-brand').value = filterBrand
  document.getElementById('facet-period').value = filterPeriod
  document.getElementById('facet-sort').value = sortMode
  closeBottomSheet()
  render()
})
```

- [ ] **Step 9.4: Verificar em viewport mobile**

Em Chrome DevTools, ative viewport mobile (iPhone SE, 375px). Verifique:
- Os selects desktop desaparecem
- Aparece o botão "Filtros ▾"
- Clicar no botão abre o bottom sheet com 4 selects
- Aplicar fecha o sheet e filtra a grid
- Clicar no backdrop fecha sem aplicar

- [ ] **Step 9.5: Commit**

```bash
cd /Users/arturlemos/Documents/bq-analista
git add portal/index.html
git commit -m "feat(portal): bottom sheet de filtros pra mobile"
```

---

## Task 10: Portal — QA manual final + favicon check

**Files:** nenhum código novo.

- [ ] **Step 10.1: Checklist de QA desktop**

Abra http://localhost:3000/ em Chrome desktop e valide:

- [ ] Login MSAL funciona (redirect Azure → portal).
- [ ] Header mostra "AZZAS *análises*", link "Análises" (ativo), "Instalar no Claude", e o email do usuário.
- [ ] Hero mostra "Minhas análises · N publicadas · M arquivadas".
- [ ] Tabs "Minhas", "Time", "Arquivadas" com contagens. Clicar troca universo.
- [ ] Busca filtra por título, descrição, tag E marca (teste digitando uma marca).
- [ ] Facets Agente e Marca populam baseado no que existe na tab ativa.
- [ ] Facet Período filtra corretamente (ex: "Últimos 7 dias" esconde items mais antigos).
- [ ] Facet Ordem funciona (recent / old / title).
- [ ] Cada card mostra: thumb com gradiente, chip de marca, menu ⋯, título, `AGENTE · período · há X dias`, descrição, tags.
- [ ] Clicar no card abre iframe fullscreen; botão "voltar" retorna à library preservando tab ativa.
- [ ] Menu ⋯ em card público: "Copiar link" + "Arquivar". Copiar mostra toast "Link copiado".
- [ ] Menu ⋯ em card privado (se houver): "Tornar pública" + "Arquivar".
- [ ] Arquivar remove da tab atual; aparece em "Arquivadas" com opção "Restaurar".
- [ ] Link "Instalar no Claude" leva pra `/onboarding` e fica com estilo ativo lá.

- [ ] **Step 10.2: Checklist de QA mobile**

Chrome DevTools → viewport iPhone SE (375 × 667):

- [ ] Header não quebra (pode empilhar, mas legível).
- [ ] Tabs rolam horizontal se necessário.
- [ ] Selects de facets somem; aparece botão "Filtros ▾".
- [ ] Clicar "Filtros ▾" abre bottom sheet com 4 dropdowns.
- [ ] "Aplicar" filtra e fecha o sheet.
- [ ] Grid fica em 1 coluna.
- [ ] Onboarding: hero pilha, passos em 1 coluna, agentes em 1 coluna.

- [ ] **Step 10.3: Checklist onboarding**

Abra http://localhost:3000/onboarding:

- [ ] Header igual ao do portal (brand + nav com "Instalar no Claude" ativo).
- [ ] Hero navy com eyebrow, h1, editorial, parágrafo, CTA branco, sub-CTA.
- [ ] Versão do DXT aparece no botão CTA.
- [ ] Lista de agentes populada (cards bege claro com left-border navy).
- [ ] Seção de troubleshooting com 4 perguntas + mailto funciona.
- [ ] Footer discreto com link pro README.

- [ ] **Step 10.4: Commit (se houver ajustes pontuais durante o QA)**

Se descobrir bugs pontuais durante o QA, corrija-os no mesmo commit:

```bash
cd /Users/arturlemos/Documents/bq-analista
git add portal/index.html portal/onboarding.html
git commit -m "chore(portal): ajustes pós-QA da Fase A"
```

Se nada precisar mudar, pule este step.

---

## Task 11: Push pra produção

**Files:** nenhum.

- [ ] **Step 11.1: Verificar estado do working tree**

```bash
cd /Users/arturlemos/Documents/bq-analista
git status
git log --oneline origin/main..HEAD
```

Expected: working tree limpo, histórico com os 10 commits (Tasks 1-10) ainda não empurrados.

- [ ] **Step 11.2: Rodar testes finais locais**

```bash
cd packages/mcp-core && uv run pytest -v
cd ../mcp-client-dxt && npm test && npm run typecheck
cd ../../portal && npm test
```

Expected: todos passam.

- [ ] **Step 11.3: Push**

```bash
cd /Users/arturlemos/Documents/bq-analista
git push origin main
```

CI vai disparar:
- **Deploy Agents to Railway** — rebuild dos dois agentes (vendas-linx, devolucoes) com o campo `author_email` novo.
- **Deploy Portal to Vercel** — redeploy com `index.html` + `onboarding.html` novos.

- [ ] **Step 11.4: Aguardar CI terminar e validar em produção**

```bash
gh run list --limit 3
```

Quando ambos "completed success":

- Abrir https://bq-analista.vercel.app/ — verifica portal novo.
- Abrir https://bq-analista.vercel.app/onboarding — verifica onboarding novo.
- Usar um agente MCP no Claude Desktop pra publicar uma nova análise — verifica que o entry no `library/<agent>/public.json` resultante tem `author_email`.

- [ ] **Step 11.5: Rebuildar e disponibilizar DXT v1.0.1**

```bash
cd packages/mcp-client-dxt
npm run build:dxt
```

Output esperado: `packages/mcp-client-dxt/azzas-mcp-1.0.1.dxt` (ou similar, conforme `scripts/build-dxt.mjs`).

Copiar o `.dxt` pra `portal/public/downloads/azzas-mcp-1.0.1.dxt`:

```bash
cp packages/mcp-client-dxt/azzas-mcp-1.0.1.dxt portal/public/downloads/azzas-mcp-1.0.1.dxt
```

Bump a versão no manifest do portal em `portal/api/mcp/_helpers/manifest.js`:

```javascript
const VERSION = {
  latest: '1.0.1',
  min: '1.0.0',
};
```

Commit e push:

```bash
git add portal/public/downloads/azzas-mcp-1.0.1.dxt portal/api/mcp/_helpers/manifest.js
git commit -m "release(dxt): v1.0.1 com callback page rebrandada"
git push
```

- [ ] **Step 11.6: Smoke test DXT v1.0.1**

Após o novo deploy do portal:

- Baixar `azzas-mcp-1.0.1.dxt` em https://bq-analista.vercel.app/onboarding
- Desinstalar o DXT v1.0.0 existente no Claude Desktop (Configurações → Extensões → Azzas MCP → remover)
- Instalar o 1.0.1 seguindo o fluxo do onboarding
- Fazer uma pergunta no chat pra disparar o fluxo de auth
- Ao completar o login no browser, verificar que a tela nova aparece (check navy + "Login concluído" + email)

---

## Self-Review

Ran the self-review checklist against the spec. Findings:

**Spec coverage — todas as requisitos do spec cobertos:**
- Tabs Minhas/Time/Arquivadas (§ Navegação) → Task 6 (HTML) + Task 7 (lógica)
- Cross-domain via `/api/mcp/agents` → Task 7
- Busca incluindo brand → Task 7 (`matchesSearch`)
- Facets Agente + Marca + Período + Ordem → Task 6 (HTML) + Task 7 (lógica)
- Arquivamento localStorage → Task 7 (`getArchivedIds`, `archiveItem`)
- Ações no card condicionais por visibilidade → Task 7 (`toggleMenu`)
- Toast pra "copiar link" → Task 7 (`showToast`)
- Entrada header pro onboarding → Task 6 (HTML)
- Layout visual (hero creme, tabs, cards com agente no meta) → Task 6 + 7
- Onboarding rebrandado → Task 5
- Página de sucesso do DXT → Tasks 3 + 4
- `author_email` no LibraryEntry → Tasks 1 + 2
- Fallback por filename slug pra items antigos → Task 7 (`isMine`)
- Responsivo mobile com bottom sheet → Task 9
- Skeleton loading → Task 8
- Empty states → Task 7 (`renderEmpty`)
- Rollout em 3 vetores → Task 11

**Placeholder scan:** Task 7 original referenciava `openBottomSheet` como stub com alert. Isso é substituído em Task 9 — ok. Nenhum TBD/TODO remanescente.

**Type consistency:** funções `renderCallbackPage`, `escapeHtml`, `archiveItem`, `getArchivedIds`, `isMine`, `matchesSearch`, `buildCard` todas definidas uma vez, usadas consistentemente. Campo `author_email` definido em Task 1, usado em Tasks 2 e 7 com mesma grafia.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-23-portal-redesign-fase-a.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
