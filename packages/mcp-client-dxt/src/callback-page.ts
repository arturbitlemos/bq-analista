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
