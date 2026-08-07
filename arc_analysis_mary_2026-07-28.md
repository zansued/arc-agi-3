# 📊 Mary's Strategic Analysis: ARC-AGI-3 Roadmap

**Date:** 2026-07-28 21:46 BRT
**Analyst:** Mary (BMAD Business Analyst)
**Context:** 25 games, 1 level solved (sp80 L1), stuck on sp80 L2

---

## 1. VOTES ON THE 7 PROPOSED ITEMS

| # | Item | Voto | Urgência (1-10) | Risco | Justificativa |
|:-:|:-----|:----:|:---------------:|:-----:|:-------------|
| 1 | **DEEPCOPY** — serializar/restaurar estado para BFS | ✅ A FAVOR | **10** | 🟡 Médio | Fundação do pipeline BFS. Direção arquitetural já confirmada pelas memórias. Porém, bloqueado pelo bug de win detection — arcengine retorna `NOT_FINISHED` mesmo em vitória. Sem deepcopy funcional, qualquer BFS é cego. **Prioridade máxima, mas não é o primeiro passo.** |
| 2 | **GRID SEGMENTATION** — extrair objetos, posições, cores | ❌ CONTRA | **3** | 🟢 Baixo | O arcengine já fornece `get_sprites()` com tags, posições, cores e rotação. Implementar isso é reinventar a roda. Útil apenas se precisarmos de reconhecimento visual via browser (visão computacional), mas para o pipeline arcengine é redundante. |
| 3 | **DEBUG HOOK** — injetar hooks no step() para ler variáveis ofuscadas | ✅ A FAVOR | **9** | 🔴 Alto | **A chave do cofre.** Os jogos usam variáveis ofuscadas (`plzwjbfyfli`, `yqejjfwwh`). Um hook no `step()` revela: estado interno, flag de vitória real, pontuação, contadores. Sem isso, o deepcopy BFS nunca saberá quando um nível foi vencido. Risco: injetar hooks em código compilado/ofuscado exige engenharia reversa cuidadosa. |
| 4 | **CODE DECOMPILER** — tradutor automático de variáveis ofuscadas para 25 jogos | ✅ A FAVOR | **7** | 🔴 Alto | Valor imenso para generalização — mapear `cevwbinfgl → buckets_filled`, `yqejjfwwh → success` para todos os 25 jogos. Porém, complexidade alta: cada jogo tem obfuscação diferente. Pode ser um projeto dentro do projeto. Recomendo começar com um "dicionário manual" dos 5 jogos prioritários primeiro, depois automatizar. |
| 5 | **GAME ENUMERATOR** — scanner que extrai níveis, sprites, ações, rotação | ✅ A FAVOR | **6** | 🟡 Médio | O `v58_game_analyzer` já faz parte disso. Um scanner sistemático é útil para catalogar todos os 25 jogos automaticamente. Porém, não desbloqueia sp80 Level 2 agora. Risco: confiabilidade — alguns jogos podem ter estruturas atípicas que o scanner não capta. |
| 6 | **PATTERN LEARNER** — aprender padrões entre jogos similares | ❌ CONTRA | **2** | 🟡 Médio | **Prematuro.** Temos exatamente 1 nível resolvido. Não há dados suficientes para aprender padrões significativos. Padrões extraídos de 1 data point = overfitting garantido. Revisitar quando tivermos ≥5 jogos com ≥2 níveis cada. |
| 7 | **ARCHIVE REPLAY** — arquivar estados, detectar loops, replay do melhor estado | ✅ A FAVOR | **8** | 🟡 Médio | Componente crítico do BFS. O V28 provou que archive replay funciona (cn04, 4/6 replays). Endereça o Bug #2 (plano executa reset em vez de replay). Risco: explosão de estados — o archive precisa de keys compostas e dedup eficiente. Mas o V30 já demonstrou 5.601 estados, então escalabilidade é viável. |

---

## 2. O QUE ESTÁ FALTANDO NA LISTA? 🎯

### 🚨 ITEM CRÍTICO AUSENTE #1: WIN DETECTION FIX
**Não listado, mas é o verdadeiro gargalo.**

O arcengine retorna `GameState.NOT_FINISHED` mesmo quando o nível é completado. O deepcopy BFS não encontra caminho de vitória (`model_plan_successes=0`).

**Solução proposta:**
1. Usar DEBUG HOOK para descobrir qual variável interna armazena a flag de vitória
2. Implementar `vmstep()` ou método alternativo que retorne win state real
3. Ou usar `ymzfopzgbq()` (método de verificação interna descoberto no WA30) como oracle de vitória universal

**Urgência:** 10/10 — sem isso, nenhum dos outros itens resolve o problema.

### 🚨 ITEM CRÍTICO AUSENTE #2: STOCHASTIC HANDLING
**sp80 é estocástico.** BFS determinístico clássico falha quando a mesma ação produz resultados diferentes.

**Solução proposta:**
- Rollouts múltiplos para cada transição de estado
- Uso de médias/probabilidades em vez de estados determinísticos
- Ou confirmação visual via browser + visão computacional para verificar resultados

**Urgência:** 9/10 — sem isso, sp80 L2 permanece insolúvel via BFS puro.

### 🚨 ITEM CRÍTICO AUSENTE #3: COMPOSITE STATE KEYS
Bug #1 documentado: deepcopy BFS precisa de chaves compostas para dedup de estado.

**Solução:**
- Chave = `(level_index, sorted_sprite_positions, sprite_tags, rotation, steps_remaining)`
- Não apenas coordenadas do jogador — incluir estado de todos os objetos interativos

**Urgência:** 8/10 — sem dedup correto, BFS explode ou entra em loop.

### 📌 ITEM AUSENTE #4: VISUAL/VERIFICATION BRIDGE
Preferência documentada do usuário: usar browser + visão quando arcengine difere do comportamento real.

**Solução proposta:**
- Sistema de "double-check" automático: arcengine simula → browser verifica → discrepância registrada
- Para jogos estocásticos, browser é a ground truth

**Urgência:** 7/10 — relevante para sp80 imediatamente.

---

## 3. ORDEM DE IMPLEMENTAÇÃO RECOMENDADA

```
FASE 1 — DESBLOQUEIO IMEDIATO (sp80 L2)
├── 1. DEBUG HOOK (Urgência 9) — Descobrir flag de vitória real
├── 2. WIN DETECTION FIX (Não listado, Urgência 10) — Corrigir deepcopy
├── 3. DEEPCOPY (Item 1, Urgência 10) — BFS funcional com win detection
├── 4. COMPOSITE STATE KEYS (Não listado, Urgência 8) — Dedup + evitar loops
└── 5. ARCHIVE REPLAY (Item 7, Urgência 8) — Replay correto do melhor estado

FASE 2 — GENERALIZAÇÃO (próximos 10 jogos)
├── 6. STOCHASTIC HANDLING (Não listado, Urgência 9) — Múltiplos rollouts
├── 7. CODE DECOMPILER PARCIAL (Item 4, Urgência 7) — Dicionário manual 5 jogos
├── 8. VISUAL VERIFICATION BRIDGE (Não listado, Urgência 7) — Browser como oracle
└── 9. GAME ENUMERATOR (Item 5, Urgência 6) — Catalogação automática

FASE 3 — ESCALA (demais 15 jogos)
├── 10. CODE DECOMPILER COMPLETO (Item 4, continuação)
├── 11. GRID SEGMENTATION (Item 2, Urgência 3) — Se necessário
└── 12. PATTERN LEARNER (Item 6, Urgência 2) — Quando houver dados
```

---

## 4. MATRIZ DE RISCOS

| Item | Risco | Mitigação |
|:-----|:-----:|:----------|
| DEBUG HOOK | 🔴 Alto — Código ofuscado pode quebrar com atualizações | Começar com sp80 (mais familiar), depois generalizar. Usar monkey patching do método `step` original. |
| DEEPCOPY | 🟡 Médio — Win detection depende do hook | Só implementar APÓS o hook funcionar. Testar com sp80 L1 primeiro (já sabemos vencer). |
| CODE DECOMPILER | 🔴 Alto — 25 padrões diferentes de ofuscação | Abordagem incremental: dicionário manual para 5 jogos prioritários (sp80, wa30, m0r0, cn04, cd82), depois automatizar. |
| ARCHIVE REPLAY | 🟡 Médio — Explosão de estados em jogos complexos | Limitar archive a N estados por nível. Usar LRU eviction. V30 mostrou que 5k estados é viável. |
| PATTERN LEARNER | 🟡 Médio — Overfitting em dados escassos | Simplesmente não implementar agora. Aguardar mínimo 5 jogos com multiplos níveis. |

---

## 5. RECOMENDAÇÃO ESTRATÉGICA

**"O mapa não é o território"** — Alfred Korzybski

A lista original tem 7 itens, mas o **verdadeiro colapso** não está nela: está no fato de que **deepcopy sem win detection é uma Ferrari sem volante**. O item ausente #1 (Win Detection Fix) é o degrau que sustenta todos os outros.

**Prioridade absoluta agora:**
1. ✅ DEBUG HOOK no SP80 — ler variável de vitória interna
2. ✅ WIN DETECTION FIX — corrigir deepcopy
3. ✅ Validar com sp80 L1 (já sabemos a sequência vencedora)
4. ✅ Então aplicar BFS no sp80 L2

Depois disso, o resto da lista se desenrola naturalmente. Sem isso, continuamos trocando pneus de um carro que não tem motor.

---

*Mary 📊 — "A brief that saves hours of rework starts with asking why. Por que o deepcopy não detecta vitória? Descubra isso primeiro."*
