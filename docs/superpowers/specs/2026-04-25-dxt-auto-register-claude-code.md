# DXT Auto-Register Claude Code MCP

**Data:** 2026-04-25  
**Escopo:** `packages/mcp-client-dxt/src/index.ts`  
**Objetivo:** Quando o usuário instala o DXT no Claude Desktop, o cowork (agente background) ganha automaticamente acesso aos tools do Azzas MCP — sem terminal, sem passos extras.

---

## Contexto

O cowork do Claude Desktop roda sessions Claude Code (bundled no Desktop) como agente background. Claude Code lê MCP servers de `~/.claude.json`. Hoje esse arquivo não tem `azzas-mcp`, então o cowork não tem acesso aos tools.

O DXT roda como processo Node via o Node bundled do Claude Desktop (`process.execPath`). Esse mesmo binário pode ser referenciado no `~/.claude.json` — eliminando a necessidade de Node instalado separadamente no sistema.

---

## Solução

Adicionar `selfRegisterClaudeCode()` ao `main()` do DXT. Na primeira execução após instalação, o DXT escreve sua própria entrada em `~/.claude.json`. Nenhuma ação do usuário necessária.

---

## Comportamento

### Fluxo principal

```
main() inicia
  └─ selfRegisterClaudeCode()
       ├─ lê ~/.claude.json (ou {} se não existir)
       ├─ verifica mcpServers["azzas-mcp"]:
       │    command === process.execPath  AND  args[0] === process.argv[1]
       ├─ igual → log "skipped" → retorna
       └─ diferente/ausente → escreve entrada → log "registered" → retorna
```

### Entrada escrita em `~/.claude.json`

```json
"azzas-mcp": {
  "type": "stdio",
  "command": "<process.execPath>",
  "args":    ["<process.argv[1]>"],
  "env":     {}
}
```

- `process.execPath` = Node bundled do Claude Desktop (sem depender do PATH do sistema)
- `process.argv[1]` = path absoluto do `dist/index.js` instalado

### Idempotência

A função compara `command` e `args[0]` antes de escrever. Se já estiver correto, não toca no arquivo. Isso garante zero re-escritas em cada startup normal.

### Atualização de versão

O path do `dist/index.js` não muda entre versões do DXT (a extensão sempre instala no mesmo diretório). O que pode mudar é `process.execPath` quando o **Claude Desktop atualiza** seu Node bundled — nesse caso a comparação detecta diferença e reescreve automaticamente.

---

## Logging

Arquivo: `~/.mcp/logs/claude-code-setup.log`  
Diretório já definido em `paths.ts` → `logsDir()`.

Eventos logados (com timestamp ISO):

| Evento | Linha de log |
|--------|-------------|
| Entrada escrita/atualizada | `registered: command=<path> args=<path>` |
| Já estava correto | `skipped: already registered with correct path` |
| Erro ao ler `~/.claude.json` (JSON inválido) | `warn: invalid ~/.claude.json, reinitializing` |
| Erro ao escrever | `error writing ~/.claude.json: <mensagem>` |
| Erro ao criar diretório de log | silencioso (não pode logar o erro de log) |

O DXT **nunca lança exceção** para o processo principal por causa desta função.

---

## Casos-limite

| Situação | Comportamento |
|----------|---------------|
| `~/.claude.json` não existe | Cria com `{ mcpServers: { "azzas-mcp": ... } }` |
| `~/.claude.json` tem JSON inválido | Reinicia do `{}`, loga warn |
| Sem permissão de escrita | Loga erro, DXT continua funcionando normalmente |
| Windows | Funciona igual — `process.execPath` e `process.argv[1]` são cross-platform |
| Outros servers no `~/.claude.json` | Preservados — a função só toca na chave `azzas-mcp` |
| Entrada `azzas-mcp` existe mas aponta para worktree/path antigo | Sobrescreve com path correto |

---

## Fora do escopo

- Nenhuma mudança no portal, onboarding ou pipeline de release
- Não valida se cowork está ativo
- Não remove outras entradas do `~/.claude.json`
- Não desfaz o registro ao desinstalar o DXT

---

## Arquivos alterados

| Arquivo | Mudança |
|---------|---------|
| `packages/mcp-client-dxt/src/index.ts` | Adiciona `selfRegisterClaudeCode()` + call em `main()` |

Nenhum outro arquivo alterado. O `paths.ts` já expõe `logsDir()` — sem modificação necessária.
