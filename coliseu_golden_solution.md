---
created: 2026-06-18 10:37 BRT
protocol: 🏛️ Coliseu Exponencial — ARC-AGI-3
ciclo: @BLACKGOV
deadline: 30 Jun 2026 (12 dias restantes)
---

# 🏆 ARC-HYBRID-12: Golden Solution

## Síntese do Protocolo Coliseu

| Sub-Agente | Proposta Central | Status |
|:-----------|:-----------------|:-------|
| 🏗️ Winston (Arquiteto) | ARC-PBE-lite: CEGIS loop + DSL 30 primitivas + Invariant Verification | ✅ Revisado com dados reais V58 |
| 👩‍💻 Amelia (Dev) | Análise de viabilidade: parser.py 95% reúso, invariants.py 90%, VSA NÃO serve para equivalence | ✅ Correção crítica incorporada |
| 🧠 Creative Problem Solver | Transformation Archetypes: 50 arquétipos, match por assinatura, TRIZ Principles | ✅ Adotado como Fase 1 |
| 🎯 Brainstorming Coach | Facilitação: fusão Archetypes + CEGIS, Portfolio Strategy, Cross-Examination | ✅ Estrutura do plano |

### Correção Crucial (Cross-Examination)

- ❌ **Alegação original:** "V55/V56/V57 encontraram 0 níveis"
- ✅ **Realidade:** V58 já resolveu **12 níveis** (sp80: 6, cn04: 6) via playtest manual
- ✅ **Dataset:** 25 jogos (não 400). Submissão Kaggle: 100 testes. Gap: 25 → 100.
- ❌ **Alegação original:** "VSA serve para equivalence checking de programas"
- ✅ **Realidade:** gc_vsa.py codifica posições espaciais, não programas. Usar caching por hash.

---

## 🏗️ Arquitetura ARC-HYBRID-12

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARC-HYBRID-12 FINAL                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Fase 0: Percepção (parser.py + invariants.py)                 │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ Para CADA puzzle: extrai objetos, invariantes,       │       │
│  │ assinatura de transformação → catalog/{game}.json    │       │
│  └─────────────────────────────────────────────────────┘       │
│         ↓                                                        │
│  Fase 1: Archetype Matcher (50+ assinaturas)                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ Match assinatura vs biblioteca conhecida             │       │
│  │ 3 existentes (paint, tangram, navigation) + novas    │       │
│  │ >80% → Fase 2 Quick | <80% → Fase 3 Deep            │       │
│  │ TRIZ: #10 Preliminary Action (pré-computar)          │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  Fase 2: Quick Synthesis (5s timeout)                          │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ Template pré-preenchido pelo archetype match         │       │
│  │ Enumera parâmetros, testa 3 exemplos, invariants     │       │
│  │ TRIZ: #35 Parameter Change (resolução reduzida)     │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  Fase 3: Deep Synthesis (30-120s adaptativo)                   │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ CEGIS loop: enumerative + type pruning + hash cache  │       │
│  │ Early stopping por comprimento de Kolmogorov         │       │
│  │ Se sucesso → ADICIONA à biblioteca (aprendizado!)    │       │
│  │ TRIZ: #13 Other Way Around (output→input)           │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                 │
│  Fase 4: Fallback (BFS Guiado V58)                             │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ Se Deep Synthesis falha: roda BFS com priors V58     │       │
│  │ Reaproveita pattern_memory.json (12 níveis já)       │       │
│  └─────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Plano de 12 Dias

| Dia | Foco | Tarefas | Entregável | Risco |
|:---:|:-----|:--------|:-----------|:------|
| **1** | Catalogação | Rodar parser.py + invariants.py nos 25 jogos. Extrair assinaturas de transformação. | 25 catalog files em `/arc_hybrid/catalog/` | ✅ parser.py funciona |
| **2** | Archetype Matcher | Implementar match engine. 3 arquétipos existentes (V58) + 10 novos. | `archetype_matcher.py` + biblioteca 13 assinaturas | ⚠️ Novos precisam assinatura manual |
| **3** | Quick Synthesis | Conectar archetype → template DSL. Enumeração paramétrica. | 5s/puzzle quick solve funcional | ⚠️ Interface nova |
| **4** | Deep Synthesis | CEGIS loop: enumerative + type pruning + hash cache + early stopping | 30-120s/puzzle full solve | 🔴 Core novo sem testes |
| **5** | Integração | Conectar Fases 0→1→2→3→4 pipeline fim-a-fim | Pipeline rodando em 1 jogo | 🔴 Pontos de quebra |
| **6** | Benchmark | Rodar 25 jogos. Medir: níveis encontrados, tempo, falsos positivos. | Baseline métricas (`benchmark_25.csv`) | — |
| **7** | Expansão Arquétipos | +20 arquétipos baseados nos fails do benchmark | Biblioteca 33+ assinaturas | 🟡 Depende análise dos fails |
| **8** | Validação Cruzada | Adversarial testing. Verificar falsos positivos. | Relatório de robustez | 🟡 Overfitting |
| **9** | Integração Kaggle | Formatar saída para submissão. Dockerizar. Testar em 100 testes. | Notebook de submissão | 🟡 Formato Kaggle |
| **10** | Portfolio Strategy | Executar 3 solvers independentes. Combinar resultados. | Pipeline de portfolio | 🟢 Já funciona |
| **11** | Otimização Final | Ajustar timeouts, pruning thresholds, archetype confidence. | Parâmetros otimizados | 🟡 Últimos ajustes |
| **12** | ✅ Submissão | Rodar ensemble final. Submeter. | **25+ níveis esperados** | 🏆 |

---

## 🧠 Princípios TRIZ Aplicados

| # | Princípio | Aplicação |
|:-:|:----------|:----------|
| 2 | **Taking Out** | Isolar deepcopy do loop principal. Archetype match NÃO copia grids. |
| 10 | **Preliminary Action** | Pré-computar transformações e assinaturas ANTES da busca. |
| 13 | **The Other Way Around** | Match output→input (inverso) como alternativa ao forward synthesis. |
| 35 | **Parameter Change** | Downsample 3× para match rápido, refine na resolução original. |
| 24 | **Mediator** | BFS V58 como intermediário barato antes de CEGIS caro. |
| 1 | **Segmentation** | Segmentar puzzles por tipo de transformação (cromático, geométrico, etc.). |

---

## 🛠️ Código Novo (Estimativa ~800 linhas)

| Arquivo | Linhas | Descrição |
|:--------|:------:|:----------|
| `arc_hybrid/archetype_matcher.py` | 150 | Match engine + biblioteca de assinaturas |
| `arc_hybrid/quick_synthesis.py` | 150 | Template DSL + enumeração paramétrica |
| `arc_hybrid/deep_synthesis.py` | 250 | CEGIS loop + type pruning + hash cache |
| `arc_hybrid/pipeline.py` | 100 | Orquestração Fases 0→1→2→3→4 |
| `arc_hybrid/catalog.py` | 80 | Catalogação: parser.py wrapper + assinaturas |
| `arc_hybrid/benchmark.py` | 70 | Runner de benchmark + métricas |

**Reúso massivo de código existente:**
| Componente | Origem | Reúso |
|:-----------|:-------|:-----:|
| parser.py | arc_dsr/ | 95% (adicionar extract_mapping) |
| invariants.py | arc_dsr/ | 90% (invariant verification) |
| gc_vsa.py | arc_dsr/ | Opcional (clustering de puzzles, não equivalence) |
| PatternMemory + BFS | v58_playtest/ | Integração como fallback (Fase 4) |

---

## 📈 Estratégia de Portfolio (Kaggle)

Submeter 3 solvers independentes para maximizar cobertura:

| Solver | Abordagem | Níveis Esperados | Risco |
|:-------|:----------|:----------------:|:------|
| **ARC-HYBRID** | Archetype + CEGIS + BFS | 15-25 (target) | 🔴 Pipeline novo |
| **V58-PLUS** | BFS guiado + priors + pattern memory | 12 (já funciona) | 🟢 Testado |
| **ARC-DSR-PURE** | Parser + invariants + search puro | 3-5 (baseline) | 🟡 Teórico |

Kaggle aceita múltiplas submissões. **Total combinado: 30+ níveis possíveis.**

---

## 🚨 Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|:------|:-------------:|:-------:|:----------|
| DSL incompleta (30 primitivas insuficientes) | Média | Alto | Design incremental: day 7 adiciona 20 baseado nos fails reais |
| CEGIS explosion para puzzles complexos | Média | Alto | Type pruning + early stopping (Kolmogorov) + timeout adaptativo |
| Archetype match cria falsos positivos | Baixa | Médio | Invariant verification (D4, massa cromática) rejeita |
| parser.py falha em grids complexos | Baixa | Médio | Flood fill fallback + decomposição por cor |
| Tempo insuficiente (12 dias) | — | Crítico | Portfolio Strategy: 3 solvers independentes |

---

## ✅ Conclusão

| Métrica | Target |
|:--------|:------:|
| Níveis Phase 1 (test set) | **15+** |
| Submissões Kaggle | **3 solvers independentes** |
| Cobertura de puzzles | **80%+ dos 25 jogos catalogados** |
| Tempo por puzzle (médio) | **<30s** |
| Reúso de código existente | **~70%** (parser, invariants, V58) |

**A mensagem central:** Não tentamos explorar um espaço menor (Go-Explore com archive) nem um espaço diferente (CEGIS puro) — **eliminamos o espaço de busca inteiro** na Fase 1 via reconhecimento de padrão, e reservamos CEGIS + BFS como fallbacks para o que o match não capturar.

> *"O solver que reconhece padrão primeiro, busca por último, é o solver que ganha ARC-AGI-3."* — 🧙 BMad Master, 18 Jun 2026

---

## 📋 Próximos Passos Imediatos

1. **Agora:** Salvar Golden Solution e reportar ao usuário
2. **Dia 1:** Iniciar catalogação dos 25 jogos (parser.py + invariants.py)
3. **Dia 2:** Implementar archetype_matcher.py com 3+10 assinaturas
4. **Dia 3:** Quick Synthesis funcional

*Protocolo Coliseu concluído. @BLACKGOV.*
