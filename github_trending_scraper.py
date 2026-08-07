#!/usr/bin/env python3
"""
GitHub Trending Repository Scanner
====================================
Escaneia repositórios em alta no GitHub Trending, analisa com Deep-Wiki
quando disponível, e gera relatório matinal de absorção.

Autor: @zansued
Ciclo: @BLACKGOV
Cron: 06:30 BRT (daily)
"""

import requests
import json
import os
import sys
import re
from datetime import datetime, date, timezone, timedelta
from bs4 import BeautifulSoup
from pathlib import Path

# ============================================================
# CONFIGURAÇÃO
# ============================================================

REPORT_DIR = Path("/a0/usr/workdir/reports/github_trending")
DEEPWIKI_URL = "https://mcp.deepwiki.com/mcp"
BRIDGES_DIR = Path("/a0/usr/workdir/skill_porter/bridges")
CATALOG_PATH = Path("/a0/usr/workdir/skill_porter/catalog.json")

# Repositórios já absorvidos (mapeados por nome do repositório)
# Bridge Skill-Porter mapeia por nome
ABSORVED_REPOS = {
    "AutoGPT": "autogpt",
    "Significant-Gravitas/AutoGPT": "autogpt",
    "LangChain": "langchain",
    "langchain-ai/langchain": "langchain",
    "langchain": "langchain",
    "crewAI": "crewai",
    "crewAIInc/crewAI": "crewai",
    "crewai": "crewai",
    "autogen": "autogen",
    "microsoft/autogen": "autogen",
    "mem0": "mem0",
    "mem0ai/mem0": "mem0",
    "Dify": "dify",
    "langgenius/dify": "dify",
    "graphrag": "graphrag",
    "microsoft/graphrag": "graphrag",
    "graphiti": "graphiti",
    "getzep/graphiti": "graphiti",
    "ragflow": "ragflow",
    "infiniflow/ragflow": "ragflow",
    "swe-agent": "swe_agent",
    "swe-agent/swe-agent": "swe_agent",
    "swe_agent": "swe_agent",
    "aider": "aider",
    "Aider-AI/aider": "aider",
}

# Palavras-chave de interesse para o ecossistema @BLACKGOV
INTEREST_KEYWORDS = [
    # Agentes e frameworks
    "agent", "ai agent", "multi-agent", "autonomous",
    # OSINT e segurança
    "osint", "recon", "security", "threat", "intelligence",
    # Automação
    "automation", "workflow", "pipeline", "orchestrator",
    # Linguagem natural e conhecimento
    "rag", "knowledge graph", "llm", "nlp", "embedding",
    # Ferramentas do ecossistema
    "mcp", "n8n", "tool", "bridge", "plugin",
    # Dados
    "data", "scraper", "crawler", "extraction",
]


class GitHubTrendingScanner:
    """Escaneia repositórios em alta no GitHub Trending."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        self.bridges = self._load_bridges()
        os.makedirs(REPORT_DIR, exist_ok=True)
    
    def _load_bridges(self):
        """Carrega bridges existentes do catálogo."""
        bridgenames = set()
        if CATALOG_PATH.exists():
            try:
                data = json.loads(CATALOG_PATH.read_text())
                for entry in data:
                    name = entry.get("name", "").lower().strip()
                    bridgenames.add(name)
            except:
                pass
        # Também escaneia diretório de bridges
        if BRIDGES_DIR.exists():
            for f in BRIDGES_DIR.iterdir():
                if f.suffix == ".py" and not f.name.startswith("__"):
                    name = f.stem.lower().strip()
                    bridgenames.add(name)
        return bridgenames
    
    def scrape_trending(self, language="python", since="daily"):
        """
        Raspa a página de trending do GitHub.
        Retorna lista de dicionários com repositórios.
        """
        url = f"https://github.com/trending/{language}?since={since}"
        print(f"[*] Raspando: {url}")
        
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            print(f"[!] Erro ao acessar GitHub Trending: {e}")
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = soup.select("article.Box-row")
        repos = []
        
        for article in articles:
            try:
                # Nome do repositório
                h2 = article.select_one("h2")
                if not h2:
                    continue
                a = h2.select_one("a")
                if not a:
                    continue
                full_name = a.get_text(strip=True).replace(" ", "")
                repo_url = f"https://github.com{full_name}"
                
                # Descrição
                desc_p = article.select_one("p.col-9")
                description = desc_p.get_text(strip=True) if desc_p else ""
                
                # Linguagem
                lang_span = article.select_one("span[itemprop='programmingLanguage']")
                language_used = lang_span.get_text(strip=True) if lang_span else ""
                
                # Estrelas
                stars = 0
                stars_links = article.select("a.Link--muted")
                for link in stars_links:
                    text = link.get_text(strip=True)
                    if "stars" in link.get("href", ""):
                        stars = self._parse_number(text)
                        break
                
                # Forks
                forks = 0
                for link in stars_links:
                    text = link.get_text(strip=True)
                    if "forks" in link.get("href", ""):
                        forks = self._parse_number(text)
                        break
                
                # Estrelas hoje
                stars_today = 0
                today_span = article.select_one("span.d-inline-block.float-sm-right")
                if today_span:
                    today_text = today_span.get_text(strip=True)
                    match = re.search(r"(\d[\d,.]*)", today_text.replace(",", ""))
                    if match:
                        stars_today = int(match.group(1).replace(",", ""))
                
                repo = {
                    "name": f"{full_name.split('/')[-1]}",
                    "full_name": full_name.lstrip("/"),
                    "url": f"https://github.com{full_name}",
                    "description": description,
                    "language": language_used,
                    "stars": stars,
                    "forks": forks,
                    "stars_today": stars_today,
                    "topics": [],
                }
                repos.append(repo)
            except Exception as e:
                print(f"[!] Erro ao extrair repositório: {e}")
                continue
        
        return repos
    
    def _parse_number(self, text):
        """Parse k/m numbers like '1.2k' or '3.4m'"""
        text = text.strip().replace(",", "")
        if not text:
            return 0
        if text.endswith("k"):
            return int(float(text[:-1]) * 1000)
        elif text.endswith("m"):
            return int(float(text[:-1]) * 1000000)
        else:
            try:
                return int(text)
            except:
                return 0
    
    def analyze_with_deepwiki(self, repo):
        """
        Tenta analisar repositório com Deep-Wiki MCP.
        Retorna análise aprofundada ou None.
        """
        try:
            # Testar conexão com Deep-Wiki via JSON-RPC
            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "analyze_repository",
                    "arguments": {
                        "repo_url": repo["url"]
                    }
                },
                "id": 1
            }
            resp = requests.post(
                DEEPWIKI_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if "result" in data:
                    return data["result"]
        except Exception as e:
            print(f"[!] Deep-Wiki não disponível para {repo['name']}: {e}")
        return None
    
    def classify_repo(self, repo):
        """
        Classifica repositório quanto ao interesse para o ecossistema.
        Retorna: categoria, score, já absorvido?
        """
        name = repo["name"].lower().strip()
        full_name = repo["full_name"].lower().strip()
        desc = repo["description"].lower().strip()
        
        # Verificar se já foi absorvido
        already_absorbed = (
            name in ABSORVED_REPOS or
            full_name in ABSORVED_REPOS or
            name in self.bridges or
            name.replace("-", "_").replace(".", "_") in self.bridges
        )
        
        # Calcular score de interesse
        score = 0
        matched_keywords = []
        search_text = f"{name} {full_name} {desc}"
        
        for kw in INTEREST_KEYWORDS:
            if kw in search_text:
                score += 1
                if kw not in matched_keywords:
                    matched_keywords.append(kw)
        
        # Bônus por popularidade
        if repo["stars"] >= 10000:
            score += 3
        elif repo["stars"] >= 5000:
            score += 2
        elif repo["stars"] >= 1000:
            score += 1
        
        # Bônus por crescimento recente
        if repo["stars_today"] >= 500:
            score += 2
        elif repo["stars_today"] >= 100:
            score += 1
        
        return {
            "already_absorbed": already_absorbed,
            "score": score,
            "matched_keywords": matched_keywords,
            "category": self._categorize(search_text),
        }
    
    def _categorize(self, text):
        """Categoriza repositório por tipo."""
        if any(w in text for w in ["agent", "multi-agent", "autonomous"]):
            return "🤖 AI Agent"
        elif any(w in text for w in ["rag", "knowledge graph", "embedding"]):
            return "🧠 RAG/Knowledge"
        elif any(w in text for w in ["osint", "recon", "threat", "security"]):
            return "🕵️ OSINT/Security"
        elif any(w in text for w in ["scraper", "crawler", "extraction", "data"]):
            return "📊 Data"
        elif any(w in text for w in ["automation", "workflow", "orchestrator"]):
            return "⚙️ Automation"
        elif any(w in text for w in ["mcp", "tool", "bridge", "plugin"]):
            return "🔧 Tool/Plugin"
        elif any(w in text for w in ["llm", "nlp", "language model"]):
            return "🧠 LLM"
        else:
            return "📦 General"
    
    def generate_report(self, repos, language="python"):
        """Gera relatório markdown com recomendações."""
        today = date.today().isoformat()
        
        # Classificar todos
        classified = []
        for r in repos:
            c = self.classify_repo(r)
            c["repo"] = r
            classified.append(c)
        
        # Ordenar por score (decrescente)
        classified.sort(key=lambda x: x["score"], reverse=True)
        
        # Separar recomendados vs já absorvidos
        recommended = [c for c in classified if not c["already_absorbed"] and c["score"] > 0]
        absorbed = [c for c in classified if c["already_absorbed"]]
        observed = [c for c in classified if not c["already_absorbed"] and c["score"] == 0]
        
        markdown = f"""# 🔥 GitHub Trending — {today}

> Gerado automaticamente pelo ecossistema @BLACKGOV
> Linguagem: {language} | Período: daily

---

## 🏆 Recomendados para Absorção ({len(recommended)})

"""
        
        for i, c in enumerate(recommended[:10], 1):
            r = c["repo"]
            bridge_name = r["name"].lower().replace("-", "_").replace(".", "_")
            markdown += f"""### {i}. [{r['name']}]({r['url']})
| ★ Total | ⭐ Hoje | 🍴 Forks | 🏷️ Categoria |
|---------|--------|---------|------------|
| {r['stars']:,} | +{r['stars_today']} | {r['forks']:,} | {c['category']} |

**Descrição:** {r['description']}

**Score de interesse:** {c['score']} | **Keywords:** {', '.join(c['matched_keywords'])}

**Sugestão bridge:** `{bridge_name}`

---

"""
        
        markdown += f"\n## ✅ Já Absorvidos ({len(absorbed)})\n\n"
        for c in absorbed[:5]:
            r = c["repo"]
            bridge_name = ABSORVED_REPOS.get(r["name"], ABSORVED_REPOS.get(r["full_name"], "?"))
            markdown += f"- [{r['name']}]({r['url']}) ({r['stars']:,}★) → ✅ `{bridge_name}` ativa\n"
        
        markdown += f"\n## 👀 Observar ({len(observed)})\n\n"
        for c in observed[:5]:
            r = c["repo"]
            if r["stars"] > 100:  # Só mostrar se tiver alguma estrela
                markdown += f"- [{r['name']}]({r['url']}) ({r['stars']:,}★) — {r['description'][:80]}...\n"
        
        markdown += f"\n---\n*Relatório gerado em {datetime.now().strftime('%Y-%m-%d %H:%M BRT')}*\n"
        
        return markdown, classified
    
    def save_report(self, markdown, json_data):
        """Salva relatório e dados JSON."""
        today = date.today().isoformat()
        
        # Markdown
        md_path = REPORT_DIR / f"trending_{today}.md"
        md_path.write_text(markdown)
        print(f"[✓] Relatório salvo: {md_path}")
        
        # JSON
        json_path = REPORT_DIR / f"trending_{today}.json"
        with open(json_path, "w") as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
        print(f"[✓] Dados salvos: {json_path}")
        
        # Symlink para último
        latest_md = REPORT_DIR / "trending_latest.md"
        if latest_md.exists():
            latest_md.unlink()
        os.symlink(md_path, latest_md)
        
        return md_path, json_path


def main():
    """Execução principal."""
    print("=" * 50)
    print("  🔥 GitHub Trending Scanner - @BLACKGOV")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # Suporta argumento de linguagem
    language = "python"
    if len(sys.argv) > 1:
        language = sys.argv[1]
    
    scanner = GitHubTrendingScanner()
    
    # Raspagem
    print(f"\n[+] Raspando GitHub Trending ({language})...")
    repos = scanner.scrape_trending(language=language, since="daily")
    
    if not repos:
        print("[!] Nenhum repositório encontrado.")
        print("\n[!] Possível bloqueio do GitHub. Tentando com headers diferentes...")
        # Fallback: pesquisa no GitHub API
        try:
            print("[+] Usando GitHub API como fallback...")
            api_url = f"https://api.github.com/search/repositories?q=created:>{datetime.now() - timedelta(days=7):%Y-%m-%d}&sort=stars&order=desc&per_page=25&language={language}"
            resp = requests.get(api_url, headers={"Accept": "application/vnd.github.v3+json"}, timeout=15)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items[:25]:
                    repos.append({
                        "name": item["name"],
                        "full_name": item["full_name"],
                        "url": item["html_url"],
                        "description": item.get("description", "") or "",
                        "language": item.get("language", "") or "",
                        "stars": item["stargazers_count"],
                        "forks": item["forks_count"],
                        "stars_today": 0,
                        "topics": item.get("topics", []),
                    })
                print(f"[✓] GitHub API retornou {len(repos)} repositórios!")
            else:
                print(f"[!] GitHub API falhou: {resp.status_code}")
        except Exception as e:
            print(f"[!] Erro no fallback GitHub API: {e}")
    
    if not repos:
        print("[!] Nenhum repositório encontrado. Gerando relatório vazio.")
        empty_report = f"# 🔥 GitHub Trending — {date.today().isoformat()}\n\nNenhum repositório encontrado. Possível bloqueio do GitHub ou erro de conexão.\n"
        scanner.save_report(empty_report, [])
        return
    
    # Gerar relatório
    print(f"\n[+] Gerando relatório com {len(repos)} repositórios...")
    report, classified = scanner.generate_report(repos, language)
    
    # Salvar
    md_path, json_path = scanner.save_report(report, classified)
    
    # Tentar Deep-Wiki (se disponível)
    print(f"\n[+] Tentando Deep-Wiki para análise aprofundada...")
    deepwiki_results = {}
    for c in classified[:3]:  # Top 3 apenas
        if not c["already_absorbed"] and c["score"] >= 2:
            result = scanner.analyze_with_deepwiki(c["repo"])
            if result:
                deepwiki_results[c["repo"]["name"]] = result
                print(f"  ✓ Deep-Wiki: {c['repo']['name']}")
    
    if deepwiki_results:
        deepwiki_path = REPORT_DIR / f"deepwiki_{date.today().isoformat()}.json"
        with open(deepwiki_path, "w") as f:
            json.dump(deepwiki_results, f, indent=2, ensure_ascii=False, default=str)
        print(f"[✓] Análises Deep-Wiki salvas: {deepwiki_path}")
    else:
        print("[!] Deep-Wiki não disponível ou sem resultados")
    
    # Resumo
    recommended = [c for c in classified if not c["already_absorbed"] and c["score"] > 0]
    absorbed = [c for c in classified if c["already_absorbed"]]
    
    print("\n" + "=" * 50)
    print("  📊 RESUMO")
    print("=" * 50)
    print(f"  Total de repositórios: {len(repos)}")
    print(f"  🏆 Recomendados: {len(recommended)}")
    print(f"  ✅ Já absorvidos: {len(absorbed)}")
    print(f"  📄 Relatório: {md_path}")
    print("=" * 50)
    
    if recommended:
        print("\n  Top recomendados:")
        for c in recommended[:5]:
            r = c["repo"]
            print(f"    {r['name']} ({r['stars']:,}★) - {r['description'][:60]}...")


if __name__ == "__main__":
    main()
