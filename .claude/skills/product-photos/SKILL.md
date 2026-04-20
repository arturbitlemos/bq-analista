---
name: product-photos
description: >
  Sempre que o relatório envolver lista de produtos (ranking, análise por SKU, best-sellers,
  piores giros, ruptura, cobertura por produto, etc.), incluir a foto do produto via API
  `https://images.somalabs.com.br/brands/{rede}/products/reference_id/{produto}_{cor}/image`.
  Ativa automaticamente em qualquer relatório cujo grão seja produto × cor.
  Gatilhos: "relatório de produto", "top produtos", "best-sellers", "piores vendedores",
  "ranking de SKU", "produtos em ruptura", "produtos com cobertura baixa", "análise de produto",
  "matadores", "giro por produto".
---

# Fotos de produto — uso obrigatório em relatórios

## Quando ativar

Ativar **sempre** que o output tiver uma lista/tabela cujo grão é produto (ou produto × cor). Exemplos:
- "Top 20 vestidos em venda no mês"
- "Produtos com maior ruptura na Farm"
- "Best-sellers da coleção verão"
- "Piores giros de BYNV nos últimos 30 dias"
- "Relatório de SKUs com cobertura > 90 dias"

**Não ativar** em análises agregadas sem grão de produto (venda por marca, atingimento por loja, canal × marca, etc.).

## API

```
https://images.somalabs.com.br/brands/{rede}/products/reference_id/{produto}_{cor}/image
```

- `{rede}`: ID numérico da rede/marca (coluna `RL_ORIGEM` ou equivalente). Ex.: Farm = `2`.
- `{produto}`: valor da coluna `PRODUTO` (ex.: `350625`).
- `{cor}`: valor da coluna `COR_PRODUTO` (ex.: `0013`). **Obrigatório** — produto sem cor não resolve.
- Separador entre produto e cor é `_` (underscore).

Exemplo canônico: `https://images.somalabs.com.br/brands/2/products/reference_id/350625_0013/image`

A API entrega a imagem no tamanho nativo — não há parâmetros de largura/altura nem controle de dimensão via URL.

## Regras de renderização

### 1. Output HTML (dashboard, email, template executivo)

Coluna `foto` como **primeira coluna** da tabela:

```html
<td>
  <img src="https://images.somalabs.com.br/brands/2/products/reference_id/350625_0013/image"
       alt="350625 0013"
       loading="lazy"
       onerror="this.style.display='none'">
</td>
```

- `loading="lazy"` em listas com > 10 linhas.
- `onerror` esconde silenciosamente se a imagem não existir.
- Exibição é controlada via CSS (a API devolve a imagem em tamanho nativo).

### 2. Output Markdown (resposta direta no chat)

```markdown
| Foto | Produto | Cor | Descrição | Vendas |
|---|---|---|---|---|
| ![](https://images.somalabs.com.br/brands/2/products/reference_id/350625_0013/image) | 350625 | 0013 | Vestido X | R$ 1,2M |
```

### 3. SQL — montar a URL já na query

```sql
SELECT
  CONCAT('https://images.somalabs.com.br/brands/',
         CAST(v.RL_ORIGEM AS STRING),
         '/products/reference_id/',
         v.PRODUTO, '_', v.COR_PRODUTO,
         '/image') AS foto_url,
  v.PRODUTO, v.COR_PRODUTO, pc.DESC_COR_PRODUTO,
  p.DESC_PRODUTO, p.COLECAO,
  SUM(v.QTDE_PROD) AS pecas,
  SUM(SAFE_CAST(v.VALOR_PAGO_PROD AS NUMERIC)) AS venda_liquida
FROM `soma-pipeline-prd.silver_linx.TB_WANMTP_VENDAS_LOJA_CAPTADO` v
LEFT JOIN `soma-pipeline-prd.silver_linx.PRODUTOS` p USING (PRODUTO)
LEFT JOIN `soma-pipeline-prd.silver_linx.PRODUTO_CORES` pc USING (PRODUTO, COR_PRODUTO)
WHERE v.DATA_VENDA BETWEEN @data_inicio AND @data_fim
GROUP BY 1, 2, 3, 4, 5, 6
ORDER BY venda_liquida DESC
LIMIT 50
```

### 4. Template executivo (`exec_template.py`)

Passar a lista de produtos com chave `foto_url` populada; o template renderiza a `<img>` com as dimensões do §1.

## Proporção

Razão **2:3 retrato** é o default — é o formato das fotos de look da Soma. Ao aplicar CSS ou container, preservar a proporção; não usar quadrado nem paisagem, a menos que seja explicitamente solicitado.

## Edge cases

- **`COR_PRODUTO IS NULL`** → célula vazia, não renderizar (API exige cor).
- **`RL_ORIGEM` desconhecido** → não renderizar; a URL precisa do ID da rede.
- **Produto agregado por várias cores** → usar a cor com maior venda no período como representante; ou omitir.
- **Imagem 404** → o `onerror` já resolve; não tentar fallback alternativo.
- **Produtos inativos** (`PRODUTOS.INATIVO = 1`) → manter a foto (o cadastro histórico continua válido para identificação).

## Checklist antes de entregar um relatório de produto

1. Coluna `foto` / `foto_url` presente e como **primeira coluna**?
2. URL montada com `{rede}/products/reference_id/{PRODUTO}_{COR_PRODUTO}/image`?
3. HTML: `loading="lazy"` em listas longas e `onerror` para 404?
4. Markdown: sintaxe `![](...)` ou `<img>` inline?
