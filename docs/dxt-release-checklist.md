# DXT Release Checklist

Rodar antes de cada release. Preencher com data e versão.

## Data: ___________ | Versão: ___________

### macOS (Apple Silicon + Intel)

- [ ] `.dxt` arrastado pra Claude Desktop aparece no menu de extensões
- [ ] Tool `vendas_linx__get_context` aparece na lista do Claude
- [ ] Primeiro tool call: mensagem "🔐 Autenticação necessária" aparece
- [ ] Browser abre em `bq-analista.vercel.app/api/mcp/auth/start`
- [ ] Após login Azure real, redirect pro loopback funciona, user vê "Pronto!"
- [ ] Segunda pergunta executa tool sem nova auth
- [ ] `~/.mcp/credentials.json` existe com mode 0600
- [ ] Remover `credentials.json` manualmente → próximo call dispara re-auth
- [ ] Setar `access_expires_at` no passado no arquivo → refresh silencioso
- [ ] 403 de allowlist (simular com email fora do `allowed_execs`) → mensagem correta

### Windows 10 + 11

- [ ] Install via Claude Desktop funciona
- [ ] Browser padrão abre (testar Edge e Chrome)
- [ ] SmartScreen não bloqueia (`.dxt` deve ser tratado como extensão, não executável)
- [ ] `%USERPROFILE%\.mcp\credentials.json` criado
- [ ] Mesmos testes do macOS aplicáveis

### Cenários críticos

- [ ] `min_dxt_version` no servidor bumpado acima da versão instalada → todo tool retorna erro de versão
- [ ] Vercel offline (simular com host override) → DXT degrada com mensagem "não consegui buscar ferramentas"
- [ ] Agent Railway offline → outros agents continuam ok

## Aprovação

- [ ] QA macOS: ___________ (nome, data)
- [ ] QA Windows: ___________ (nome, data)
- [ ] Go/no-go: ___________ (nome, data)
