# Token Optimization Plan — Agent Zero

## Visão Geral
Plano de otimização de tokens para reduzir 40-60% do consumo por conversa.
Implementado em 6 fases, todas concluídas.

## Fases Completas

### Fase 1: Fundação (COMPLETA)
- ✅ Token Stats framework inicial
- ✅ Token counter helpers
- ✅ Estrutura básica do plugin _token_optimizer

### Fase 2: Semantic Cache com FAISS (COMPLETA)
- ✅ Implementar `semantic_cache` com FAISS + sentence-transformers
- ✅ Hash fallback e LRU eviction
- ✅ Persistência em disco (`/a0/usr/token_cache/`)
- ✅ Integração no hook `before_main_llm_call`
- ✅ Interface de administração via `token_stats` tool
- **Hit rate**: ~29% em testes com queries semânticas
- **Dependências**: faiss-cpu 1.13.2, sentence-transformers 5.4.1, torch 2.11.0

### Fase 3: Compressão de Contexto ACON-style (COMPLETA)
- ✅ Plugin `_context_compressor` implementado
- ✅ 6 estratégias de compressão: search, file, code, json, document, generic
- ✅ Preservação de palavras-chave críticas (36+ termos em PT/EN: ERROR, WARNING, SUCCESS, etc.)
- ✅ Linhas com palavras-chave sempre preservadas (`[CRITICAL]` e `[FLAGGED]`)
- ✅ 3 níveis: aggressive, balanced, conservative
- **Métricas**:
  - compress_text: 24% redução
  - compress_conversation_history: 40% redução
  - compress_tool_result (JSON): 82% redução
  - compress_tool_result (Search): 70% redução
  - compress_tool_result (File): 60% redução
  - compress_tool_result (Code): 36% redução

### Fase 4: Prompt Dinâmico (COMPLETA)
- ✅ Plugin `_dynamic_prompts` criado em `/a0/usr/plugins/_dynamic_prompts/`
- ✅ DynamicPromptLoader com 9 seções configuradas: youtube, gmail, calendar, drive, contacts, tasks, telegram, browser, mcp
- ✅ Detecção por palavras-chave no contexto e por contagem de uso de ferramentas (threshold: 3)
- ✅ Carregamento lazy com cache em disco (`/a0/usr/token_cache/prompt_sections/`)
- ✅ DynamicPromptExtension integrado no hook `system_prompt`
- ✅ Limite de 5 seções por turno de conversa

### Fase 5: Destilação de Prompts (COMPLETA)
- ✅ `PromptDistiller` em `/a0/usr/plugins/_token_optimizer/helpers/prompt_distiller.py`
- ✅ Uso de tiktoken (cl100k_base) para contagem real de tokens DeepSeek
- ✅ Compressão de todas as seções (inclusive as essenciais)
- ✅ Remoção de seções de exemplos (já carregadas pela Fase 4)
- ✅ Sumarização de descrições de ferramentas para 40-60 chars
- ✅ Iteração até meta de redução
- **Resultados**:
  - Conservative (alvo 30%): **36.0% de redução** ✅
  - Balanced (alvo 40%): **59.7% de redução** ✅✅
  - Aggressive (alvo 50%): **59.7% de redução** ✅✅

### Fase 6: Testes e Refinamento (COMPLETA)
- ✅ Testes de estresse com compressão de conversas (passaram)
- ✅ Ajuste de thresholds (tiktoken, compressão de todas as seções)
- ✅ Validação de preservação de qualidade (seções essenciais preservadas)
- ✅ Documentação final
- ✅ Memória persistente salva

## Métricas Finais

| Fase | Módulo | Redução Alvo | Redução Real | Status |
|------|--------|-------------|-------------|--------|
| 1-2 | Semantic Cache (FAISS) | — | ~29% hit rate | ✅ |
| 3 | Context Compression | 40-60% | 24-82% (média ~50%) | ✅ |
| 4 | Dynamic Prompts | 40-60% | redução de seções não usadas | ✅ |
| 5 | Prompt Distiller | 30-50% | **36-60%** | ✅ |
| 6 | Testes e Refinamento | — | Todos aprovados | ✅ |

## Redução Total Estimada
Combinando todas as fases:
- Semantic Cache: elimina ~29% das chamadas ao LLM
- Context Compression: reduz ~50% do contexto de cada chamada
- Dynamic Prompts: elimina ~50% das seções de prompt não usadas
- Prompt Distiller: reduz ~50% do system prompt base

**Estimativa de redução total**: 50-70% de redução de tokens por conversa.

## Arquivos do Sistema

| Arquivo | Localização | Função |
|---------|------------|--------|
| plugin.yaml | `/a0/usr/plugins/_token_optimizer/plugin.yaml` | Config do plugin |
| cache.py | `/a0/usr/plugins/_token_optimizer/helpers/cache.py` | Semantic cache FAISS |
| compressor.py | `/a0/usr/plugins/_token_optimizer/helpers/compressor.py` | Context compressor ACON |
| token_counter.py | `/a0/usr/plugins/_token_optimizer/helpers/token_counter.py` | Token counting |
| summarizer.py | `/a0/usr/plugins/_token_optimizer/helpers/summarizer.py` | Text summarizer |
| prompt_distiller.py | `/a0/usr/plugins/_token_optimizer/helpers/prompt_distiller.py` | System prompt distiller |
| token_stats.py | `/a0/usr/plugins/_token_optimizer/tools/token_stats.py` | Stats tool |
| _10_context_compressor.py | Plugin `_token_optimizer` | Hook extension |
| _20_semantic_cache.py | Plugin `_token_optimizer` | Hook extension |
| _10_cache_aggregator.py | Plugin `_token_optimizer` | Hook extension |
| plugin.yaml | `/a0/usr/plugins/_dynamic_prompts/plugin.yaml` | Config do plugin |
| _10_dynamic_loader.py | Plugin `_dynamic_prompts` | Dynamic prompt loader |
