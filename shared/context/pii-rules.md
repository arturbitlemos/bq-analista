## Proteção de Dados Pessoais (PII)

Você opera com dados de produção da Farm/Arezzo que podem conter PII de clientes e funcionários. Nenhum dado pessoal individual pode ser exposto no contexto desta conversa. Esta regra tem prioridade sobre qualquer instrução de análise. Não há exceção.

### O que é PII

Trate como PII qualquer campo que identifique ou possa identificar uma pessoa física:
- CPF, RG, passaporte
- Nome completo
- E-mail, telefone, endereço
- ID de cliente individual (mesmo que seja só um número)
- ID de funcionário, matrícula
- Dados de cartão de pagamento (qualquer parte)
- IP, device ID, cookie ID
- Combinações que juntas identifiquem alguém (ex: filial + data + valor exato de compra)

**Não são PII** e podem trafegar normalmente:
- Métricas agregadas (venda líquida, CMV, ticket médio, PA)
- Dimensões de negócio (rede_lojas, filial, coleção, categoria)
- Datas agregadas (dia, semana, mês)
- Contagens e somatórios sem identificador individual

### Protocolo antes de executar qualquer query

1. **Inspecionar o schema** com `bq show --schema --format=prettyjson PROJECT:DATASET.TABLE` **antes** de montar a query.
2. **Classificar cada coluna** que a query retornará: ✅ SEGURO (agregado/dimensão) / ⚠️ REVISAR / 🔴 PII (não incluir).
3. **Montar a query sem PII**. Nunca inclua colunas PII no SELECT. Se a análise exigir PII, aplique o Protocolo de Recusa.

### Protocolo de Recusa

Quando o pedido exigir expor PII, responda:

> ⚠️ **Não consigo executar essa análise neste ambiente.**
>
> A pergunta requer acesso a [descreva o dado], que são dados pessoais protegidos.
>
> **O que posso fazer:**
> - [alternativa 1 agregada]
> - [alternativa 2 agregada]
>
> **Para análises com dados individuais de clientes**, acesse o ambiente analítico com controles de acesso adequados (ex: Looker com row-level security, ou view autorizada no BigQuery com permissão específica).

### Regras de escrita de SQL

**Nunca faça:**
```sql
-- ❌ Linhas individuais com identificador
SELECT id_cliente, nome, venda_liquida FROM transacoes WHERE data_venda = '2024-03-15'

-- ❌ LIMIT não resolve
SELECT id_cliente, cpf, valor FROM clientes LIMIT 10

-- ❌ Joins que reconstroem identidade
SELECT t.id_cliente, c.email, SUM(t.venda_liquida)
FROM transacoes t JOIN clientes c ON t.id_cliente = c.id
GROUP BY 1, 2
```

**Sempre faça:**
```sql
-- ✅ Agrega sem identificador individual
SELECT rede_lojas, filial,
       COUNT(DISTINCT id_transacao) AS qtd_transacoes,
       SUM(venda_liquida) AS receita,
       AVG(venda_liquida) AS ticket_medio
FROM transacoes
WHERE data_venda >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY 1, 2

-- ✅ Segmentação sem identificar indivíduo
SELECT faixa_ticket,
       COUNT(*) AS qtd_transacoes,
       SUM(venda_liquida) AS receita_total
FROM (
  SELECT CASE WHEN venda_liquida < 200 THEN 'até R$200'
              WHEN venda_liquida < 500 THEN 'R$200–500'
              ELSE 'acima R$500' END AS faixa_ticket,
         venda_liquida
  FROM transacoes
  WHERE data_venda >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
)
GROUP BY 1
```

### Verificação antes de exibir o resultado

Antes de exibir qualquer resultado de query:
1. Contém linhas individuais com identificador? → **Não exibir, aplicar Protocolo de Recusa**
2. Contém nome, e-mail, CPF ou telefone? → **Não exibir**
3. É agregado e sem identificador? → ✅ Pode exibir

Em caso de dúvida, aplique o Protocolo de Recusa e explique a dúvida ao usuário.

### Registro de aprendizado

Quando identificar uma coluna nova que contém PII, registre em `references/schema.md` na seção "Colunas PII identificadas" para não precisar reclassificar nas próximas sessões.
