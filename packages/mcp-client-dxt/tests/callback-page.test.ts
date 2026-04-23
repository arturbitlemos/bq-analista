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

  it('success sem email: renderiza sem quebrar', () => {
    const html = renderCallbackPage({ access: 'tok' });
    expect(html).toContain('Login concluído');
    // Sem email, mostra só o placeholder vazio — sem lançar
    expect(html).not.toContain('undefined');
    expect(html).not.toContain('null');
  });

  it('escapa HTML em error_description', () => {
    const html = renderCallbackPage({
      error: 'x',
      error_description: '<img src=x onerror=alert(1)>',
    });
    expect(html).not.toContain('<img src=x');
    expect(html).toContain('&lt;img');
  });
});
