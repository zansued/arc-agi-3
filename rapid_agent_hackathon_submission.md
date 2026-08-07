# 🚀 Rapid Agent Hackathon — Submissão

**Evento:** Devpost Rapid Agent — Google Cloud Agent Builder + Gemini + Partner MCPs
**Prazo:** 11 de Junho de 2026
**Projeto:** TechStore Brasil (`techstore-brasil-472121`)
**Ciclo:** @BLACKGOV
**Autor:** Guilherme Zanini de Sá (@zansued)
**Criado:** 2026-05-27 20:30 BRT

---

## 🏆 Visão Geral

O **TechStore Brasil** é um ecossistema de agentes autônomos que:
- **Explora** grids ARC-AGI usando Go-Explore com análise espectral (OSCAR)
- **Comprime** embeddings via S^T S spectral rotation
- **Evolui** agentes via DGM-lite (Darwin Gödel Machine)
- **Orquestra** via Google Cloud Agent Builder + Gemini 2.5 Flash

## 🧬 Stack Técnica

| Camada | Tecnologia | Função |
|:-------|:-----------|:-------|
| ☁️ **Cloud** | Google Cloud (techstore-brasil-472121) | Infraestrutura e deployments |
| 🤖 **LLM** | Gemini 2.5 Flash | Agente principal |
| 🔗 **MCP** | 5 servidores (KG, RAG, PC, DGM, Spectral) | Comunicação entre agentes |
| 🧮 **Spectral** | OSCAR S^T S rotation (arXiv 2605.17757) | Compressão espectral de embeddings |
| 🧬 **ARC** | DGM-lite v10b2 (Go-Explore + Coliseu) | Engine de exploração autônoma |
| 📊 **Partners** | Arize, Elastic, Fivetran, GitLab, MongoDB, Dynatrace | Observabilidade e dados |

## 🔧 Arquitetura de Agentes (Google Cloud Agent Builder)

```
┌─────────────────────────────────────────────────────┐
│              Google Cloud Agent Builder              │
├──────────┬──────────┬──────────┬──────────┬─────────┤
│   KG     │   RAG    │    PC    │   DGM    │Spectral │
│  MCP     │   MCP    │   MCP    │   MCP    │  MCP    │
│ (8800)   │  (8801)  │  (8802)  │  (8803)  │ (8804)  │
├──────────┴──────────┴──────────┴──────────┴─────────┤
│                    Gemini 2.5 Flash                   │
├─────────────────────────────────────────────────────┤
│            TechStore Brasil (Case de Uso)             │
└─────────────────────────────────────────────────────┘
```

## 🛠️ Ferramentas MCP

| MCP | Porta | Tools | Dados |
|:----|:----:|:------|:------|
| **Knowledge Graph** | 8800 | search, entity relations, stats | 7.343 triplas SPO |
| **RAG Drive** | 8801 | semantic search, query | Documentos Google Drive |
| **PaperClip** | 8802 | governança, gestão | PaperClip Zero |
| **DGM Agent** | 8803 | spawn, list, kill, evolve | ARC DGM-lite v10b2 |
| **Spectral** | 8804 | compress, rank, distance | OSCAR S^T S |

## 📋 Diferenciais Competitivos

1. **Spectral Engine**: Compressão de embeddings via S^T S (OSCAR) — nenhum concorrente usa
2. **ARC Go-Explore**: DGM-lite com 10 gerações de evolução (v9 → v10b2)
3. **MCP Ecosystem**: 5 servidores integrados com persistência de estado
4. **Auto-Evolução**: Agentes que spawnam e evoluem autonomamente
5. **OSINT Stack**: 5 frameworks integrados para coleta de dados
6. **Ensemble Strategy**: 20+ seeds de exploração com voting

## 🗓️ Timeline até 11/06

| Data | Marco |
|:----:|:------|
| 27/05 | ✅ MCP Ecosystem restartado (5/5 servidores UP) |
| 27/05 | ✅ DGM Agent MCP v2 criado |
| 27/05 | ✅ Spectral MCP criado (OSCAR) |
| 28/05 | 🔄 Configurar Google Cloud Agent Builder |
| 29/05 | 🔄 Integrar Partner MCPs (Arize, Elastic, MongoDB) |
| 30/05 | 🔄 Deploy da demo funcional |
| 01/06 | 🔄 Testes de integração |
| 05/06 | 🔄 Preparar vídeo de submissão |
| 08/06 | 🔄 Revisão final |
| 11/06 | 🚀 SUBMISSÃO |

## 📦 Demonstração

```python
# 1. Spawnar agente ARC
curl -X POST http://localhost:8803/jsonrpc -d '{
  "method": "spawn_agent",
  "params": {"arguments": {"seed": "sp80", "version": "v10b2"}}
}'

# 2. Comprimir embeddings
curl -X POST http://localhost:8804/jsonrpc -d '{
  "method": "compress_embeddings",
  "params": {"arguments": {"embeddings": [[1,2,3],[4,5,6]], "variance_ratio": 0.90}}
}'

# 3. Consultar Knowledge Graph
curl -X POST http://localhost:8800/jsonrpc -d '{
  "method": "search_entities",
  "params": {"arguments": {"query": "TechStore"}}
}'
```

## 📈 Métricas de Impacto

- **Compressão espectral**: 256→44 dimensões (5.82×), 95.7% variância preservada
- **Agentes evolutivos**: v9 → v10b2 (10 gerações)
- **Knowledge Graph**: 7.343 triplas, 21 predicados, 57 sujeitos
- **Ensemble**: 20+ seeds, 244+ runs
- **MCP Ecosystem**: 5 servidores integrados

## 🔗 Referências

- **[OSCAR]** arXiv 2605.17757 — FutureMLS-Lab (github.com/FutureMLS-Lab/OSCAR)
- **[ARC-AGI]** Kaggle PierceTheVeil ($10K competition)
- **[Google ADC]** techstore-brasil-472121 (Gemini 2.5 Flash)
- **[MCP]** Model Context Protocol 2025-03-26
