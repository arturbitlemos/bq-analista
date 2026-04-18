# CLAUDE.md

## Análise de dados de varejo — SEMPRE carregar os princípios antes

Antes de responder qualquer pedido que envolva **análise de dados, KPIs, consulta ao BigQuery, leitura de métricas de negócio, interpretação de resultados ou recomendação baseada em números**, você **DEVE**:

1. Ler o arquivo `analyst principles.md` na raiz deste projeto usando o Read tool.
2. Aplicar o framework descrito lá — especialmente:
   - A **Prime Directive**: nunca inventar número, nunca preencher gap com estimativa plausível.
   - A hierarquia analítica (Contexto → Volume → Eficiência → Rentabilidade → Diagnóstico → Recomendação).
   - Os **4 labels de tier de dado** em todo número citado: ✅ Dado real / 📊 Benchmark de mercado / 🔶 Estimativa / ❓ Dado indisponível.
   - O padrão de resposta (resposta direta → número com tier → contexto comparativo → alerta/oportunidade → próximo passo).

Esta leitura é obrigatória mesmo que você "ache que lembra" dos princípios — o arquivo é a fonte canônica e pode ter sido atualizado.

### Quando NÃO é necessário

Não precisa carregar o arquivo para tarefas puramente técnicas/operacionais que não envolvem interpretar dados — edição de código, setup de infra, commits, debugging de scripts, configuração de frontend, etc.

### Regra de ouro

Se a resposta contém qualquer número que será usado para tomar uma decisão de negócio, o arquivo de princípios **já deve ter sido lido** nesta sessão.
