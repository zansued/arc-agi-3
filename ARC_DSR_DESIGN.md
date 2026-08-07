# ARC-DSR: Deductive Symbolic Reasoner
## Arquitetura Neuro-Matemática para Solução Dedutiva do ARC-AGI-3

---

## 1. Resumo Executivo

O ARC-DSR (Deductive Symbolic Reasoner) é uma arquitetura que substitui a busca exaustiva (BFS/DFS/MCTS) por raciocínio dedutivo simbólico, inspirada nos fundamentos neurocomputacionais da cognição humana. O sistema observa 3 pares de demonstração (input→output), infere a regra de transformação subjacente e a aplica ao grid de teste sem busca adicional.

**Objetivo:** Resolver 25/25 jogos do ARC-AGI-3, superando o teto de 35 níveis (V51) através de raciocínio simbólico em vez de exploração exaustiva.

---

## 2. Fundamentos Teóricos (18 Teorias)

### 2.1 Neurociência Cognitiva

| # | Teoria | Autor | Aplicação no ARC-DSR |
|:-:|:-------|:------|:---------------------|
| 1 | **Structure Mapping Theory** | Gentner (1983) | Alinhamento relacional fonte→alvo para analogia; ignora atributos superficiais (cor, posição absoluta) |
| 2 | **Grid Cells + Place Cells** | Moser & Moser (2005) | Codificação hiperdimensional de posições; translações/rotações como operações algébricas nativas |
| 3 | **Predictive Coding** | Friston (2010) | Minimização de erro preditivo; erro residual guia correção abdutiva |
| 4 | **Cognitive Chunking** | Botvinick (2012) | Compactação recursiva de sequências bem-sucedidas em operações atômicas |
| 5 | **PFC Rostrolateral (BA10)** | Urbanski et al. (2016) | Módulo dedutivo central para integração relacional e inferência analógica |
| 6 | **Rápido e Devagar (S1/S2)** | Kahneman (2011) | VSA geram intuições (S1) → DSL verifica deduções (S2) |
| 7 | **Tolman-Eichenbaum Machine** | Whittington et al. (2020) | Separação algébrica entre estrutura representacional (entorrinal) e conteúdo visual (hipocampo) |
| 8 | **Hierarchical RL** | Botvinick et al. (2009) | Encadeamento hierárquico de subtarefas no processo de indução |

### 2.2 Matemática e Lógica

| # | Teoria | Aplicação no ARC-DSR |
|:-:|:-------|:---------------------|
| 9 | **Teoria dos Grupos D₄** | Invariantes de simetria diédrica do grid (rotações 90°, espelhamentos) |
| 10 | **Teorema de Noether Discreto** | Conservação de invariantes cromáticos e topológicos antes/depois da transformação |
| 11 | **Teoria das Categorias** | Funtores que preservam estrutura entre grids; Extensões de Kan para generalização |
| 12 | **Teorema de Gold (Finite Thickness)** | DSL não-Turing-completo garante identificabilidade em tempo polinomial |
| 13 | **WLKS Subgraph Kernels** | Assinatura estrutural Weisfeiler-Lehman para isomorfismo de sub-grades |

### 2.3 Algoritmos de Síntese Simbólica

| # | Algoritmo | Aplicação no ARC-DSR |
|:-:|:----------|:---------------------|
| 14 | **DreamCoder** | Wake/sleep cycles: wake (resolver com DSL) → sleep (abstrair novas primitivas via chunking) |
| 15 | **BPL (Bayesian Program Learning)** | Priors causais dedutivos para modelagem de conceitos (Lake et al.) |
| 16 | **NPI (Neural Programmer-Interpreter)** | REPL loop: proposta → execução → verificação → iteração |
| 17 | **Inverse Planning / IRR** | Engenharia reversa da intenção do design do grid |
| 18 | **Soft TPR Autoencoder** | Role-filler binding flexível para representações composicionais contínuas |

---

## 3. Arquitetura ARC-DSR (4 Camadas)

```
╔══════════════════════════════════════════════════════════════╗
║                     ARC-DSR ARCHITECTURE                      ║
╚══════════════════════════════════════════════════════════════╝

                    ┌──────────────────────────┐
                    │     GRID DE TESTE         │
                    │     (30×30 máximo)        │
                    └───────────┬──────────────┘
                                │
                                ▼
╔══════════════════════════════════════════════════════════════╗
║  LAYER 1: PERCEPTION & PATTERN PRIMITIVES                    ║
╠══════════════════════════════════════════════════════════════╣
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ PARSER VISUAL (GC-VSA + Soft TPR)                      │ ║
║  │                                                         │ ║
║  │  1. Extrai objetos (blobs de mesma cor adjacentes)     │ ║
║  │  2. Codifica posições em hipervetores (GC-VSA)         │ ║
║  │  3. Cria grafo de cena G(V,E) com relações espaciais  │ ║
║  │  4. Calcula invariantes Noether (massa cromática,     │ ║
║  │     números de Betti, simetrias D₄)                   │ ║
║  │  5. Gera assinatura WLKS do grid                      │ ║
║  └─────────────────────────────────────────────────────────┘ ║
╚══════════════════════════════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════╗
║  LAYER 2: ANALOGICAL REASONING                               ║
╠══════════════════════════════════════════════════════════════╣
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ ALIGNER (Structure Mapping + BA10)                      │ ║
║  │                                                         │ ║
║  │  1. Alinha estruturalmente os 3 pares fonte→alvo       │ ║
║  │  2. Identifica invariantes entre input→output          │ ║
║  │  3. Descarta atributos superficiais (cor, pos.absoluta)│ ║
║  │  4. Isola a transformação relacional de alta ordem     │ ║
║  │  5. Gera hipótese: "objeto_A se move para direita"     │ ║
║  └─────────────────────────────────────────────────────────┘ ║
╚══════════════════════════════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════╗
║  LAYER 3: PROGRAM SYNTHESIS & INDUCTION                      ║
╠══════════════════════════════════════════════════════════════╣
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ COMPILER (DreamCoder + BPL + NPI)                       │ ║
║  │                                                         │ ║
║  │  1. Traduz hipótese para programa DSL                  │ ║
║  │  2. Aplica prior bayesiano causal                       │ ║
║  │  3. Executa programa no grid de teste (NPI REPL)        │ ║
║  │  4. Verifica resultado contra exemplos                  │ ║
║  │  5. Se falha, refina via MCMC sobre AST                │ ║
║  └─────────────────────────────────────────────────────────┘ ║
╚══════════════════════════════════════════════════════════════╝
                                │
                                ▼
╔══════════════════════════════════════════════════════════════╗
║  LAYER 4: VERIFICATION & GENERALIZATION                      ║
╠══════════════════════════════════════════════════════════════╣
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ VERIFIER (Gold + Categorias + Fallback)                 │ ║
║  │                                                         │ ║
║  │  1. Valida comutatividade (Funtores Categóricos)        │ ║
║  │  2. Verifica finite thickness (Gold)                    │ ║
║  │  3. Score de confiança (>0.8 aceita)                    │ ║
║  │  4. Se confiança <0.5, fallback para V51 (S1)          │ ║
║  │  5. Gera explicação da regra em linguagem natural       │ ║
║  └─────────────────────────────────────────────────────────┘ ║
╚══════════════════════════════════════════════════════════════╝
                                │
                                ▼
                    ┌──────────────────────────┐
                    │     GRID DE SAÍDA         │
                    └──────────────────────────┘
```

### 3.1 Fluxo de Decisão por Camada

```
Para cada jogo com 3 pares (train_0..2) + grid de teste:

LAYER 1:
  1. Parsear 4 grids de input → lista de objetos
     if grid vazio: return grid vazio
     if grid < 2×2: return grid original
  2. Criar grafo G(V,E) para cada grid
  3. Calcular invariantes Noether D₄
  4. Gera assinatura WLKS

LAYER 2:
  1. Para cada par (input_i, output_i), i ∈ {0,1,2}:
     a. Encontrar mapeamento entre nós de input_i e output_i
     b. Identificar transformação t_i que leva input_i → output_i
     c. Verificar consistência de t_0, t_1, t_2
  2. Se consistente: t = t_0 = t_1 = t_2
     Se inconsistente: t = composição das transformações comuns

LAYER 3:
  1. Traduzir t para programa DSL:
     Program ::= Seq(Transform, Transform)*
     Transform ::= Move(obj, dx, dy)
                 | Rotate(obj, angle)
                 | Scale(obj, factor)
                 | Copy(obj, dest_x, dest_y)
                 | Delete(obj)
                 | Fill(region, color)
                 | MapColor(mapping)
                 | Mirror(axis)
                 | Crop(bbox)
                 | Expand(bbox, padding)
                 | Symmetry(type)
                 | Conditional(predicate, Transform)
  2. Prior: shorter programs have higher probability (BPL)
  3. Executar programa no grid de teste
  4. Se output válido: aceitar

LAYER 4:
  1. Score de confiança:
     - >0.8: aceitar output
     - 0.5-0.8: tentar próxima melhor hipótese (top-3)
     - <0.5: fallback para V51 (exploração exaustiva)
  2. Se saída validada: gerar explicação
```

### 3.2 DSL Formal (CompDSL)

```bnf
Program     ::= 'Seq(' Transform (',' Transform)* ')'
              | Transform

Transform   ::= 'Move(' Obj ',' Int ',' Int ')'
              | 'Rotate(' Obj ',' Int ')'           -- angle ∈ {90, 180, 270}
              | 'Scale(' Obj ',' Float ')'          -- factor ∈ {0.5, 1.0, 2.0}
              | 'Copy(' Obj ',' Int ',' Int ')'
              | 'Delete(' Obj ')'
              | 'Fill(' Region ',' Color ')'
              | 'MapColor(' Palette ')'
              | 'Mirror(' Axis ')'
              | 'Crop(' BBox ')'
              | 'Expand(' BBox ',' Int ')'
              | 'Symmetry(' SymType ')'
              | 'If(' Predicate ',' Transform ',' Transform ')'

Obj         ::= ObjectId | 'Color(' Int ')' | 'Largest' | 'Smallest'
Region      ::= 'Box(' Int ',' Int ',' Int ',' Int ')'
              | 'Contour(' Obj ')'
              | 'All'
Axis        ::= 'X' | 'Y' | 'Diagonal'
SymType     ::= 'Rotational' | 'Reflective' | 'Glide'
Predicate   ::= 'Inside(' Obj ',' Obj ')'
              | 'Above(' Obj ',' Obj ')'
              | 'SameColor(' Obj ',' Obj ')'
              | 'Count(' Obj ',' Int ')'
              | 'Size(' Obj ',' Comparator ',' Int ')'
```

---

## 4. Plano de Implementação (3 Fases)

### Fase 1: Parser & Visual Primitives (3-5 dias)

**Objetivo:** Converter grids ARC-AGI em representações simbólicas estruturadas.

**Entregáveis:**
- [x] Módulo de extração de objetos (blobs de mesma cor adjacentes)
- [ ] Codificação GC-VSA (hipervetores de posição)
- [ ] Grafo de cena G(V,E) com relações espaciais
- [ ] Cálculo de invariantes Noether D₄
- [ ] Assinatura WLKS do grid
- [ ] Teste nos 25 jogos

**Módulos:**
- `arc_dsr/parser.py` — Extração de objetos e grafo de cena
- `arc_dsr/gc_vsa.py` — Grid-Cell Vector Symbolic Architecture
- `arc_dsr/invariants.py` — Invariantes Noether + WLKS
- `arc_dsr/visual_primitives.py` — Primitivas visuais (contornos, bounding boxes)

### Fase 2: Rule Induction Engine (3-5 dias)

**Objetivo:** Inferir regras de transformação a partir de exemplos.

**Entregáveis:**
- [ ] Alinhamento estrutural (Structure Mapping)
- [ ] Compilador DSL (CompDSL)
- [ ] Módulo abdutivo (erro residual → correção direcional)
- [ ] Prior bayesiano (programas curtos)
- [ ] Teste nos 13 jogos não resolvidos pelo V51

**Módulos:**
- `arc_dsr/aligner.py` — Alinhamento relacional fonte→alvo
- `arc_dsr/dsl.py` — Definição e execução da DSL
- `arc_dsr/abductor.py` — Correção abdutiva guiada por erro residual

### Fase 3: Program Synthesis Loop (3-5 dias)

**Objetivo:** Ciclo completo dedutivo com sleep/wake e fallback.

**Entregáveis:**
- [ ] DreamCoder-style wake/sleep cycles
- [ ] Cognitive chunking de ASTs bem-sucedidas
- [ ] REPL loop com verificação passo a passo
- [ ] Fallback integrado ao V51
- [ ] Benchmark completo (25 jogos)

**Módulos:**
- `arc_dsr/dreamcoder.py` — Wake/sleep abstraction learning
- `arc_dsr/repl.py` — REPL loop: proposta → execução → verificação
- `arc_dsr/verifier.py` — Verificador categórico + finite thickness
- `arc_dsr/orchestrator.py` — Orquestrador entre módulos

---

## 5. Integração com V51

O V51 (250K estados, 35 níveis) não é descartado — integrado como:

| Função | Descrição |
|:-------|:----------|
| **Fallback S1** | Quando ARC-DSR tem confiança <0.5, delega para V51 |
| **Gerador de dados** | Os 12 jogos resolvidos geram exemplos de treino para sleep phase |
| **Verificador** | V51 confirma se saída simbólica é alcançável via exploração |
| **Métrica de complexidade** | Estados necessários para resolver indica complexidade do jogo |

---

## 6. Métricas de Sucesso

| Métrica | Baseline (V51) | ARC-DSR (Meta) |
|:--------|:-------------:|:--------------:|
| Jogos resolvidos | 12/25 | 25/25 |
| Níveis totais | 35 | 75+ |
| Estados/jogo | ~20.000 | <100 (dedução) |
| Tempo/jogo | Segundos-minutos | Milissegundos |
| Capacidade de explicação | ❌ | ✅ Regras legíveis |
| Generalização para ARC-AGI-4 | ❌ (re-treina) | ✅ (abstração) |

---

## 7. Status do Projeto

**Versão atual:** V51 (baseline de exploração exaustiva)
**Próxima versão:** ARC-DSR Alpha (Fase 1: Parser & Primitives)
**Data de início:** 2026-06-16
**Framework:** Python 3.13, arc_agi 0.9.8, arcengine 0.9.3

---

## 8. Referências

| # | Referência | Identificador |
|:-:|:-----------|:-------------:|
| 1 | Structure-mapping: A theoretical framework for analogy (Gentner, 1983) | DOI: 10.1207/s15516709cog0702_3 |
| 2 | Reasoning by analogy requires the left frontal pole (Urbanski et al., 2016) | DOI: 10.1093/brain/aww072 |
| 3 | The LISA Model (Hummel & Holyoak, 1997) | DOI: 10.1207/s15516709cog2104_1 |
| 4 | The Tolman-Eichenbaum Machine (Whittington et al., 2020) | arXiv: 1910.04322 |
| 5 | Human-level concept learning through BPL (Lake et al., 2015) | DOI: 10.1126/science.aab3050 |
| 6 | Measuring Compositional Generalization (Keysers et al., 2020) | arXiv: 1912.09713 |
| 7 | Soft Tensor Product Representations (Gomboc et al., 2024) | arXiv: 2412.04671 |
| 8 | DreamCoder: Growing generalizable skills with wake/sleep (Ellis et al., 2021) | arXiv: 2006.08381 |
| 9 | Neural Programmer-Interpreter (Reed & de Freitas, 2015) | arXiv: 1511.06279 |
| 10 | ARC-AGI: Abstraction and Reasoning Corpus (Chollet, 2019) | arXiv: 1911.01547 |

---

*Documento criado em 2026-06-16 10:58 BRT*
*Ciclo: @ARC-DSR*
*Fundamentação: Senhor @zansued*
