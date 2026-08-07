# 📘 TechStore Brasil — Plano Estratégico de Growth Brand

> **Gerado em:** 2026-05-07 22:28 BRT
> **Baseado em:** DNA da TechStore Brasil (SENHOR @ZANSUED) + Stack VPS Real + Decisões Estratégicas + Debate Multi-Agente (10 agentes A2A)
> **Agência Autônoma 24/7:** Ghost → Typebot → Documenso → Asaas/Stripe → A2A Agents → n8n

---

## 1. 🧬 DNA da Marca (Resumo Executivo)

| Atributo | Definição |
|:---------|:----------|
| **Missão** | Democratizar o acesso à automação e IA, transformando pequenos negócios em sistemas organizados, produtivos e consistentes |
| **Produto** | Sistema Presença Inteligente™ — conteúdo inteligente que mantém presença digital ativa todos os dias sem esforço manual |
| **UVP** | Instalamos um sistema de conteúdo inteligente no seu negócio que mantém sua presença digital ativa e consistente todos os dias, sem depender do seu tempo ou esforço manual |
| **Público** | Pequenos empresários e profissionais autônomos, 23-50 anos, que não conseguem manter consistência digital |
| **Tom de Voz** | Prático, direto, inteligente, orientado a resultado. "Se dá pra automatizar, não deveria ser manual." |
| **Avatar** | Empreendedor que sabe que precisa aparecer na internet, mas não consegue manter constância. Já tentou postar sozinho, contratar alguém barato, usar ferramentas complicadas — nada se mantém. |

---

## 2. 🏗️ Stack Tecnológico (Mapeamento Real da VPS)

```
┌──────────────────────────────────────────────────────────┐
│              STACK TECHSOTRE BRASIL                       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │               ORQUESTRADOR CENTRAL                │   │
│  │         n8n (n8n.techstorebrasil.com) ✅          │   │
│  │         MCP configurado com token Bearer          │   │
│  └──────────────────────────────────────────────────┘   │
│        │            │           │            │           │
│        ▼            ▼           ▼            ▼           │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │  GHOST  │ │ TYPEBOT  │ │DOCUMENSO │ │ A2A      │    │
│  │ Blog +  │ │ Atendi-  │ │ Contratos│ │ BRIDGE   │    │
│  │Conteúdo │ │ mento +  │ │ Digitais │ │ 10 Agents│    │
│  │ Orgânico│ │Qualifica-│ │          │ │ Rodando  │    │
│  │         │ │ção       │ │          │ │ 24/7     │    │
│  └─────────┘ └──────────┘ └──────────┘ └──────────┘    │
│        │            │           │                        │
│        ▼            ▼           ▼                        │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐                 │
│  │  ASAAS  │ │  STRIPE  │ │SQUAD A2A │                 │
│  │ 🇧🇷 PIX  │ │ 🌍 Cartão│ │Orchestra-│                 │
│  │Boleto NF│ │  USD/EUR │ │tor       │                 │
│  │ Produção│ │ Produção │ │Funcional │                 │
│  └─────────┘ └──────────┘ └──────────┘                 │
└──────────────────────────────────────────────────────────┘
```

| Serviço | Subdomínio | Status | Função |
|:--------|:-----------|:------:|:-------|
| **Ghost** | ghost.techstorebrasil.com | ✅ 200 OK | Blog + conteúdo orgânico + SEO |
| **Typebot** | typebot.techstorebrasil.com | ✅ 307 | Chatbot + qualificação de leads |
| **Documenso** | documenso.techstorebrasil.com | ✅ 302 | Contratos digitais + propostas |
| **n8n** | n8n.techstorebrasil.com | ✅ **EIXO** | Automação de fluxos + MCP configurado |
| **Asaas** | API externa | ✅ Produção | Pagamentos BR (PIX, cartão, boleto, NF) |
| **Stripe** | MCP Stripe | ✅ Produção | Pagamentos internacionais (USD/EUR) |
| **A2A Bridge** | localhost:9999 | ✅ Funcional | 10 agentes A2A especialistas |
| **SQUAD Orchestrator** | squad_a2a_orchestrator.py | ✅ Funcional | Orquestração multi-agente (Handoff + SoM) |

---

## 3. 🎯 Estratégia de Aquisição — Funil Autônomo 24/7

### Topo de Funil (Atração)

| Canal | Estratégia | Ferramenta | Custo |
|:------|:-----------|:-----------|:-----:|
| **Ghost Blog** | Conteúdo SEO: "Como automatizar posts", "Sistema de conteúdo para pequenos negócios" | Ghost + n8n | 🟢 Grátis |
| **LinkedIn** | Posts diários sobre automação + cases | n8n + A2A Agents | 🟢 Grátis |
| **Instagram** | Reels educativos sobre presença digital | n8n + A2A Agents | 🟢 Grátis |
| **Indicação** | Lead ganha 1 mês grátis para cada indicação fechada | Typebot + n8n | 🟢 Comissionável |

### Meio de Funil (Qualificação)

```
Lead chega via Ghost/LinkedIn/Indicação
    → Typebot: "Como está sua presença digital hoje?"
    → Typebot qualifica: tamanho do negócio, rede social principal, frequência de posts
    → Se qualificado (pequeno negócio, 23-50 anos, sem consistência):
        → Typebot agenda call ou envia proposta automatizada
    → Se não qualificado:
        → Nutrição via Ghost (newsletter automática)
```

### Fundo de Funil (Conversão)

```
Lead qualificado
    → SQUAD A2A Agents geram proposta personalizada (baseada no diagnóstico)
    → Documenso envia contrato de assinatura
    → Lead escolhe forma de pagamento:
        ├── 🇧🇷 Brasileiro → Asaas (PIX: 70%, Cartão: 20%, Boleto: 10%)
        └── 🌍 Internacional → Stripe (cartão USD/EUR)
    → Webhook confirma pagamento
    → A2A Agents iniciam Sistema Presença Inteligente™
    → Ghost publica case de sucesso (feedback loop)
```

---

## 4. 💰 Modelo de Precificação

| Plano | Preço | O que inclui |
|:------|:-----:|:-------------|
| **Sistema Presença Inteligente™** 🚀 | **R$ 197/mês** ou **US$ 37/mês** | 12 posts/mês, 12 legendas, 4 ideias de Reels, calendário, agendamento automático |
| **Sistema Presença Inteligente™ PRO** ⚡ | **R$ 397/mês** ou **US$ 74/mês** | Tudo do básico + blog automatizado + chatbot básico + relatório mensal |
| **Sistema Personalizado** 🏆 | **R$ 997/mês** ou **US$ 187/mês** | Tudo do PRO + automações customizadas + prioridade no suporte + integrações |

### Estrutura de Custos

| Item | Custo Mensal |
|:-----|:------------:|
| Ghost (self-hosted) | 🟢 Grátis (já pago na VPS) |
| Typebot (self-hosted) | 🟢 Grátis |
| Documenso (self-hosted) | 🟢 Grátis |
| n8n (self-hosted) | 🟢 Grátis |
| A2A Agents | 🟢 Grátis (DeepSeek API ~$0.001/req) |
| Asaas | 🟢 Grátis (taxa por transação: PIX 0.99%, cartão 3.99%) |
| Stripe | 🟢 Grátis (taxa 2.9% + R$0.50) |
| DeepSeek API | ~$2/mês (para geração de conteúdo dos agentes) |
| **Total** | **~R$ 50/mês** (custo fixo) |

**Margem estimada por cliente:**
- Plano Básico (R$ 197): **~75% margem** (custo ~R$ 50)
- Plano PRO (R$ 397): **~87% margem** (custo ~R$ 50)
- Plano Personalizado (R$ 997): **~95% margem** (custo ~R$ 50)

---

## 5. 🗺️ Roadmap 90 Dias

### Mês 1 — Fundação (Dias 1-30)

| Semana | Ação | Responsável |
|:-------|:-----|:------------|
| **1** | ✅ **Plano de Growth Brand** (este documento) | SENHOR + Agent Zero |
| **1** | Configurar Typebot com fluxo de qualificação de leads | n8n |
| **1** | Conectar Ghost + Typebot (formulário → lead) | n8n |
| **2** | Configurar Asaas: webhook de PIX/cartão/boleto | n8n |
| **2** | Configurar Stripe: webhook de cartão internacional | n8n |
| **2** | Conectar Documenso + Asaas (contrato assinado → cobrança) | n8n |
| **3** | Publicar 3 artigos no Ghost sobre automação para pequenos negócios | A2A Agents |
| **3** | Criar 3 templates de proposta no Documenso | SENHOR |
| **4** | **PRIMEIRO CLIENTE PAGO** 🎯 | Fluxo completo |
| **4** | Publicar case de sucesso no Ghost | A2A Agents |

### Mês 2 — Escala (Dias 31-60)

| Semana | Ação |
|:-------|:------|
| **5** | Automatizar distribuição de conteúdo: Ghost → LinkedIn → Instagram via n8n |
| **6** | Criar programa de indicação (lead indica, ganha 1 mês grátis) |
| **7** | Publicar 4 artigos no Ghost + 8 posts em rede social |
| **8** | Avaliar métricas: leads gerados, taxa de conversão, CAC, ticket médio |

### Mês 3 — Otimização (Dias 61-90)

| Semana | Ação |
|:-------|:------|
| **9** | Otimizar fluxo Typebot baseado nos dados de conversão |
| **10** | Criar blog automatizado para clientes (Ghost multi-tenant) |
| **11** | Publicar 4 artigos + 8 posts + 1 case de sucesso |
| **12** | Revisão trimestral: o que funcionou, o que melhorar, próximos 90 dias |

---

## 6. 📊 Métricas de Sucesso (KPIs)

| Métrica | Meta Mês 1 | Meta Mês 2 | Meta Mês 3 |
|:--------|:----------:|:----------:|:----------:|
| **Leads gerados** | 10 | 30 | 50 |
| **Leads qualificados** | 5 | 15 | 25 |
| **Clientes fechados** | **1** 🎯 | 5 | 10 |
| **Taxa de conversão** | 10% | 16% | 20% |
| **Ticket médio** | R$ 197 | R$ 250 | R$ 300 |
| **MRR** | R$ 197 | R$ 1.250 | R$ 3.000 |
| **CAC** | R$ 50 | R$ 40 | R$ 30 |
| **Churn** | — | < 10% | < 5% |
| **NPS** | — | > 50 | > 70 |

---

## 7. 🚀 Plano de Expansão

### Fase 1 — MVP (Mês 1)
- **Cliente #1:** TechStore Brasil é a primeira cliente do próprio sistema
- **Prova de conceito:** Sistema Presença Inteligente™ rodando na própria marca
- **Validação:** "Se funciona na TechStore, funciona para qualquer pequeno negócio"

### Fase 2 — Escala (Meses 2-3)
- **De 1 para 10 clientes:** Usar cases de sucesso da TechStore como prova social
- **Automação total:** Pipeline lead → venda → entrega 100% automatizado via n8n
- **Conteúdo em massa:** Ghost + A2A Agents geram conteúdo para múltiplos clientes

### Fase 3 — Plataforma (Meses 4-6)
- **Ghost multi-tenant:** Cada cliente tem seu próprio blog gerenciado pela TechStore
- **Split de receita:** Asaas permite split automático (parceiros, afiliados, revendedores)
- **Expansão internacional:** Stripe ativa para clientes fora do Brasil

### Fase 4 — Agência Autônoma (Mês 6+)
- **Zero interferência humana no operacional:** Agentes A2A + n8n gerenciam tudo
- **Foco do SENHOR:** Estratégia, parcerias, produto — não operação
- **Escala ilimitada:** Cada novo cliente = custo marginal próximo de zero

---

## 8. 🔑 Próximas Ações Imediatas

| # | Ação | Ferramenta | Prioridade |
|:-:|:-----|:-----------|:---------:|
| 1 | Configurar Typebot com fluxo de qualificação de leads | Typebot + n8n | 🔴 Alta |
| 2 | Conectar Asaas webhook no n8n | n8n | 🔴 Alta |
| 3 | Conectar Stripe webhook no n8n | n8n | 🔴 Alta |
| 4 | Conectar Documenso + Asaas (contrato → cobrança) | n8n | 🔴 Alta |
| 5 | Publicar 1º artigo no Ghost | Ghost | 🟡 Média |
| 6 | Criar template de proposta no Documenso | Documenso | 🟡 Média |
| 7 | Gerar 1º lead via Ghost | Ghost | 🟢 Baixa |

---

> **Gerado por:** Agent Zero + SQUAD A2A Orchestrator (10 agentes especialistas)
> **Para:** SENHOR @ZANSUED — TechStore Brasil
> **Data:** 2026-05-07 22:28 BRT
> **Ciclo:** @BLACKGOV — Growth Brand Strategy Engine