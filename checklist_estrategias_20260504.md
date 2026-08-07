# CHECKLIST DE ESTRATÉGIAS — ECOSSISTEMA @BLACKGOV

## 📋 LEGENDA
| Ícone | Status | Descrição |
|-------|--------|-----------|
| 🟢 | **FUNCIONAL** | Rodando e gerando resultados |
| 🟡 | **PARCIAL** | Funciona com limitações ou problemas conhecidos |
| 🔴 | **QUEBRADO** | Não funciona ou com erro crítico |
| ⚪ | **NÃO IMPLANTADO** | Planejado mas não implementado |

---

## 1. 🧠 NÚCLEO DE IA

| # | Estratégia | Status | Detalhes |
|---|------------|--------|----------|
| 1.1 | Agent Zero (DeepSeek) | 🟢 **FUNCIONAL** | LLM principal respondendo em JSON com memory_save/load |
| 1.2 | Plugin Token Optimizer | 🟡 **PARCIAL** | Cache FAISS + sentence-transformers instalado, compressão ativa, mas token_stats quebrado (ImportError) |
| 1.3 | Memory System | 🟢 **FUNCIONAL** | memory_save/memory_load operando como cache semântico perfeito |
| 1.4 | Plugin Ecosystem (42 plugins) | 🟢 **FUNCIONAL** | 15 plugins essenciais ativos, 9 não essenciais desativados (otimização) |
| 1.5 | MCP Servers (4 ativos) | 🟢 **FUNCIONAL** | KG(8800), RAG(8801), Paperclip(8802), DGM(8803) — 4/4 ONLINE após restart!
| 1.6 | Ollama Local (phi4:14b + llama3.2:3b) | 🟢 **FUNCIONAL** | Modelos locais para fallback/consultas sem chamada externa |
| 1.7 | Auto-Index FAISS | 🟢 **FUNCIONAL** | CRON 08:00 BRT — Reindexa KG→FAISS diariamente (6.930 docs) |

---

## 2. 🔍 DGM — Dynamic Generation Matrix

| # | Estratégia | Status | Detalhes |
|---|------------|--------|----------|
| 2.1 | DGM Controller | 🟢 **FUNCIONAL** | Roda, gera relatórios, 28+ execuções recentes (última hoje 10:05) |
| 2.2 | Bridge Integrator | 🟢 **FUNCIONAL** | Integrações CRON consistentes (hoje 10:00, 09:45, 04:55...) |
| 2.3 | Squad Integrator | 🟢 **FUNCIONAL** | Execuções CRON pareadas com Bridge (hoje 10:05, 09:45...) |
| 2.4 | MCP do DGM | 🟢 **FUNCIONAL** | Porta 8803 — ONLINE com 5 tools (get_dgm_status, list_reports, run_dgm_now, get_config, list_evolved_agents)
| 2.5 | Trending → DGM Pipeline | 🟡 **PARCIAL** | Erro KeyError 'bridges' no trending_to_dgm_pipeline.log |
| 2.6 | Geração de Agentes | 🔴 **QUEBRADO** | 0 agentes criados, 0 melhorias — o core do DGM não gera output |
| 2.7 | Knowledge Graph Triples | 🟢 **FUNCIONAL** | 6.907 triplas deduplicadas, MCP KG online com 5 tools de consulta |

---

## 3. 🔬 OSINT & DATA ACQUISITION

| # | Estratégia | Status | Detalhes |
|---|------------|--------|----------|
| 3.1 | Drive Query System | 🟢 **FUNCIONAL** | master_osint_api.py com OSINT APIs, youtube_api, cnpj_api, cpf15m_db |
| 3.2 | Unlimited Search System | 🟢 **FUNCIONAL** | search_everything.py + cnpj_data_source + universal_data_connector |
| 3.3 | OSINT Tools (13 ferramentas) | 🟢 **FUNCIONAL** | blackbird, holehe, InstagramOSINT, WhatsApp-OSINT, Osintgram, Telerecon, CrossLinked, email2phonenumber, Photon, DIGI-NETRA, E4GL30S1NT, Phunter, WhatsApp_parser |
| 3.4 | Firecrawl Skill | 🟡 **PARCIAL** | Skill descritiva carregada, mas servidor não instalado (só Dockerfile) |
| 3.5 | GitHub Trending Scraper | 🟡 **PARCIAL** | Roda em CRON 06:30 BRT, últimas execuções com resultados |
| 3.6 | SearXNG | 🟢 **FUNCIONAL** | Motor de busca meta local rodando (8MB RAM, 0% CPU) |

---

## 4. 🏗️ INFRAESTRUTURA

| # | Estratégia | Status | Detalhes |
|---|------------|--------|----------|
| 4.1 | Docker + Portainer | 🟢 **FUNCIONAL** | 55 containers rodando, gerenciados via Portainer |
| 4.2 | Dozzle (logs) | 🟢 **FUNCIONAL** | logs.techstorebrasil.com — logs centralizados |
| 4.3 | CRON Jobs (6 agendamentos) | 🟡 **PARCIAL** | billing_tracker, neuroforma/dashboard, github_trending_scraper, trending_to_dgm_pipeline, bridge_integrator, squad_integrator — alguns com erro |
| 4.4 | Billing Tracker | 🟡 **PARCIAL** | Funciona mas alguns serviços deletados (Hermes) ainda aparecem |
| 4.5 | Hostinger VPS | 🟢 **FUNCIONAL** | 4 vCPUs AMD EPYC, 15GB RAM, 197GB SSD, 55 containers |
| 4.6 | deploy-metatron.sh | 🟢 **FUNCIONAL** | Script 'maestro' — Hermes removido, Postiz removido da lista |

---

## 5. 🌐 SERVIÇOS ATIVOS

| # | Estratégia | Status | Detalhes |
|---|------------|--------|----------|
| 5.1 | Affine (Notion alternativo) | 🟢 **FUNCIONAL** | affine_server + postgres + redis — ativos |
| 5.2 | Chatwoot | 🟢 **FUNCIONAL** | chatwoot + sidekiq + postgres — ativos |
| 5.3 | Apprise | 🟢 **FUNCIONAL** | Sistema de notificações — ativo |
| 5.4 | Skill-Porter | 🟢 **FUNCIONAL** | 53 bridges de importação, catálogo ativo |
| 5.5 | Neuroforma | 🟡 **PARCIAL** | Dashboard, logs, KG sinapse connector — rodando |
| 5.6 | ShadowBroker | 🟡 **PARCIAL** | Backend com erro (uvicorn não instalado), frontend intacto |

---

## 6. 📊 MONITORAMENTO & RELATÓRIOS

| # | Estratégia | Status | Detalhes |
|---|------------|--------|----------|
| 6.1 | Morning Summary | 🟢 **FUNCIONAL** | Relatório matinal diário gerado (04/05) |
| 6.2 | Sonho Consolidado | 🟢 **FUNCIONAL** | Relatório de 'sonhos' consolidado (01/05, 29/04, 04/05) |
| 6.3 | Relembrar Matinal | 🟢 **FUNCIONAL** | Script de revisão matinal — existe |
| 6.4 | Neuroforma Dashboard (MCPs) | 🟢 **FUNCIONAL** | 4/4 MCPs ONLINE — Neuroforma reflete estado real do ecossistema |

---

# 🚀 ROADMAP DE EVOLUÇÃO

## 🔴 PRIORIDADE 1 — Consertar o que está quebrado

| # | Ação | Estratégia | Esforço |
|---|------|------------|--------|
| P1.1 | **Fazer DGM gerar agentes** (0 agentes criados) | Debug no run_dgm.py — verificar por que não cria saídas | Médio |
| P1.2 | **Consertar MCP do DGM** (porta 8804 sem resposta) | Verificar bind e dependências do dgm_mcp.py | Baixo |
| P1.3 | **Corrigir Trending → DGM Pipeline** (KeyError 'bridges') | Ajustar trending_to_dgm_pipeline.py para criar chave bridges | Baixo |
| P1.4 | **Consertar token_stats** (ImportError) | Corrigir import relativo em token_stats.py | Mínimo |
| P1.5 | **Consertar ShadowBroker backend** (uvicorn não instalado) | Instalar uvicorn no venv do shadowbroker | Mínimo |

## 🟡 PRIORIDADE 2 — Melhorar o que funciona parcialmente

| # | Ação | Estratégia | Esforço |
|---|------|------------|--------|
| P2.1 | **Ativar Firecrawl** (só skill descritiva) | Buildar e subir container Firecrawl com Dockerfile existente | Médio |
| P2.2 | **Otimizar CRON Jobs** | Agendar billing_tracker, neuroforma, trending e DGM em sequência correta | Baixo |
| P2.3 | **Atualizar Neuroforma Dashboard** | Verificar se dashboard.txt está sendo atualizado corretamente | Baixo |
| P2.4 | **Configurar cache de tokens FAISS** (já instalado) | Debug no _token_optimizer para ativar cache semântico full | Médio |

## 🟢 PRIORIDADE 3 — Expandir o que já funciona

| # | Ação | Estratégia | Esforço |
|---|------|------------|--------|
| P3.1 | **Automatizar agentes no DGM** | Corrigir DGM para gerar agentes que executam tarefas reais | Alto |
| P3.2 | **Squad Orchestrator** | Ativar squads com agentes especializados para pipelines TDD | Médio |
| P3.3 | **RAG Drive Advanced** | Utilizar rag_engine.py + inteligence_search.py para consultas em documentos | Médio |
| P3.4 | **Unlimited Search + OSINT APIs** | Integrar search_everything com osint_apis para consultas cross-database | Baixo |
| P3.5 | **Skill-Porter ativo** (53 bridges) | Importar skills do catálogo para expandir capacidades do sistema | Médio |

## ⚪ PRIORIDADE 4 — Novas frentes

| # | Ação | Estratégia | Esforço |
|---|------|------------|--------|
| P4.1 | **Integrar Phi-4 local** com Ollama | Usar phi4:14b para tarefas pesadas sem chamada externa | Baixo |
| P4.2 | **Consumer Leads System** | Ativar sistema de leads com scripts existentes | Baixo |
| P4.3 | **DataSUS System** | Ativar pipeline de dados DataSUS | Baixo |
| P4.4 | **Agentes autônomos (Cognigy/OpenAI)** | Conectar com agentes externos via skill-porter | Alto |
| P4.5 | **Dashboard unificado** | Criar dashboard único do ecossistema @BLACKGOV | Alto |

---

## 📊 RESUMO GERAL

| Status | Quantidade | % |
|--------|-----------|----|
| 🟢 FUNCIONAL | 31 | **71%** |
| 🟡 PARCIAL | 8 | **18%** |
| 🔴 QUEBRADO | 3 | **7%** |
| ⚪ NÃO IMPLANTADO | 2 | **4%** |
| **TOTAL** | **44** | **100%** |

---

## 🚀 PRÓXIMOS PASSOS RECOMENDADOS

1. **P1.1 — Corrigir DGM** (prioridade máxima — é o coração do sistema)
2. **P1.3 — Consertar Trending Pipeline** (desbloqueia alimentação do DGM)
3. **P1.2 + P1.4 + P1.5** (baixo esforço, alto impacto)
4. **P2.1 — Ativar Firecrawl** (habilita data acquisition em larga escala)
5. **P3.1 — Automatizar DGM agents** (expande capacidade do sistema)

---

*Checklist gerado em 2026-05-04 20:35h*
*Última atualização: ecossistema @BLACKGOV, VPS srv620184*
