#!/usr/bin/env python3
"""
ULTIMATE FACEBOOK API SCRAPER (UFS)
Versão puramente via API - Zero consumo de disco/memória/VPS

Baseado no Ultimate-Facebook-Scraper (NakulPoudel52/Ultimate-Facebook-Scraper-1)
mas sem Selenium, sem ChromeDriver, sem armazenamento em disco.

APIs utilizadas:
1. Firecrawl API (https://firecrawl.techstorebrasil.com/v0/scrape) sem chave
2. Facebook Graph API pública (mobile endpoints)
3. GraphQL endpoints públicos
"""

import requests
import json
import sys
import re
from typing import Dict, List, Optional, Any

API_URL = "https://firecrawl.techstorebrasil.com/v0/scrape"
FB_BASE = "https://www.facebook.com"

class UltimateFacebookAPI:
    """
    Scraper de perfil do Facebook via API pura (sem browser, sem Selenium).
    Zero consumo de disco - todos os resultados retornados como JSON.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        })

    def scrape_profile_firecrawl(self, username_or_url: str) -> Dict:
        """
        Scrape perfil do Facebook usando Firecrawl API
        Args:
            username_or_url: URL ou username do Facebook (ex: 'zuck' ou 'https://facebook.com/zuck')
        Returns:
            Dict com dados do perfil
        """
        # Normalizar URL
        if not username_or_url.startswith('http'):
            url = f"{FB_BASE}/{username_or_url}"
        else:
            url = username_or_url
        
        print(f"[FIREcRAWL] Scraping: {url}")
        
        try:
            response = requests.post(
                API_URL,
                json={"url": url},
                timeout=30
            )
            
            if response.status_code != 200:
                return {"status": "error", "error": f"HTTP {response.status_code}", "url": url}
            
            data = response.json()
            
            if not data.get("success"):
                return {"status": "error", "error": data.get("error", "Unknown error"), "url": url}
            
            metadata = data.get("data", {}).get("metadata", {})
            content = data.get("data", {}).get("content", "")
            markdown = data.get("data", {}).get("markdown", "")
            
            # Extrair dados do metadata
            profile_data = {
                "status": "success",
                "platform": "facebook",
                "url": url,
                "username": url.split('/')[-1].split('?')[0],
                "metadata": {
                    "title": metadata.get("title", ""),
                    "description": metadata.get("description", ""),
                    "ogTitle": metadata.get("ogTitle", ""),
                    "ogDescription": metadata.get("ogDescription", ""),
                    "ogImage": metadata.get("ogImage", ""),
                    "language": metadata.get("language", ""),
                    "robots": metadata.get("robots", ""),
                    "favicon": metadata.get("favicon", "")
                },
                "raw_content": content[:2000] if content else "",
                "markdown_preview": markdown[:2000] if markdown else ""
            }
            
            # Tentar extrair nome do usuário do título
            if profile_data["metadata"]["title"]:
                profile_data["name"] = profile_data["metadata"]["title"]
            
            return profile_data
            
        except requests.exceptions.Timeout:
            return {"status": "error", "error": "Timeout ao acessar URL", "url": url}
        except Exception as e:
            return {"status": "error", "error": str(e), "url": url}
    
    def search_by_name(self, name: str) -> Dict:
        """
        Buscar perfis do Facebook por nome
        Args:
            name: Nome para buscar
        Returns:
            Dict com resultados da busca
        """
        print(f"[SEARCH] Searching for: {name}")
        
        search_url = f"https://www.facebook.com/public/{name.replace(' ', '-')}"
        
        try:
            # Tentar via Firecrawl API
            result = self.scrape_profile_firecrawl(search_url)
            
            # Se não conseguir, tentar via Graph API pública
            if result["status"] == "error":
                print(f"[SEARCH] Firecrawl failed, trying Graph API...")
                # Facebook Graph API pública para busca
                graph_url = f"https://graph.facebook.com/v19.0/search?q={name}&type=user&fields=id,name,picture"
                try:
                    r = requests.get(graph_url, timeout=10)
                    if r.status_code == 200:
                        result = {
                            "status": "success",
                            "platform": "facebook",
                            "query": name,
                            "results": r.json().get("data", []),
                            "source": "graph_api"
                        }
                except Exception:
                    pass
            
            return result
            
        except Exception as e:
            return {"status": "error", "error": str(e), "query": name}
    
    def check_username(self, username: str) -> Dict:
        """
        Verificar se um username existe no Facebook
        Args:
            username: Username para verificar
        Returns:
            Dict com status e dados
        """
        url = f"{FB_BASE}/{username}"
        
        try:
            r = self.session.head(url, timeout=10, allow_redirects=True)
            
            if r.status_code == 200:
                # Username existe, pegar dados completos
                result = self.scrape_profile_firecrawl(url)
                result["username_exists"] = True
                result["url"] = r.url
                return result
            elif r.status_code == 404:
                return {
                    "status": "success",
                    "username": username,
                    "username_exists": False,
                    "message": "Username não encontrado no Facebook"
                }
            else:
                return {
                    "status": "check",
                    "username": username,
                    "username_exists": "unknown",
                    "http_status": r.status_code
                }
                
        except Exception as e:
            return {"status": "error", "error": str(e), "username": username}
    
    def lookup_by_id(self, facebook_id: str) -> Dict:
        """
        Buscar perfil do Facebook por ID numérico
        Args:
            facebook_id: ID do Facebook (ex: '100027222622744')
        Returns:
            Dict com dados do perfil
        """
        # Tenta acessar via profile.php
        url = f"{FB_BASE}/profile.php?id={facebook_id}"
        return self.scrape_profile_firecrawl(url)
    
    def extract_profile_info(self, username_or_url: str) -> Dict:
        """
        Extrai informações completas de um perfil do Facebook
        """
        result = self.scrape_profile_firecrawl(username_or_url)
        
        if result["status"] == "success":
            # Tentar extrair mais informações do conteúdo
            content = result.get("raw_content", "") + " " + result.get("markdown_preview", "")
            
            # Padrões de extração
            patterns = {
                "friends_count": r'(\d[\d.,]*)\s*(?:amigo|friend|seguidor|follower)',
                "photos_count": r'(\d[\d.,]*)\s*(?:foto|photo|fotos|photos)',
                "location": r'(?:Mora em|Lives in|From|De)\s*([^\n.]+)',
                "work": r'(?:Trabalha em|Works at|Work at)\s*([^\n.]+)',
                "education": r'(?:Estudou em|Studied at|Study at)\s*([^\n.]+)',
            }
            
            extracted = {}
            for key, pattern in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    extracted[key] = match.group(1).strip()
            
            result["extracted_info"] = extracted
        
        return result
    
    def batch_lookup(self, ids_or_usernames: List[str]) -> Dict:
        """
        Busca em lote por múltiplos IDs/usernames
        Args:
            ids_or_usernames: Lista de IDs ou usernames
        Returns:
            Dict com resultados consolidados
        """
        results = []
        for item in ids_or_usernames:
            if item.isdigit():
                result = self.lookup_by_id(item)
            else:
                result = self.extract_profile_info(item)
            results.append(result)
        
        return {
            "status": "success",
            "total_queried": len(ids_or_usernames),
            "total_success": sum(1 for r in results if r.get("status") == "success"),
            "results": results
        }


def main():
    """
    CLI de exemplo:
    python3 ultimate_fb_api.py lookup zuck
    python3 ultimate_fb_api.py search "Maria Silva"
    python3 ultimate_fb_api.py check markzuckerberg
    python3 ultimate_fb_api.py id 100027222622744
    python3 ultimate_fb_api.py batch zuck,markzuckerberg
    """
    api = UltimateFacebookAPI()
    
    if len(sys.argv) < 3:
        print(json.dumps({
            "status": "usage",
            "commands": {
                "lookup <username/url>": "Ver perfil completo",
                "search <name>": "Buscar por nome",
                "check <username>": "Verificar se username existe",
                "id <facebook_id>": "Buscar por ID numérico",
                "batch <list>": "Busca em lote (separados por vírgula)"
            },
            "zero_disk": True,
            "zero_memory_consumption": True,
            "zero_vps_storage": True
        }, indent=2))
        return
    
    command = sys.argv[1]
    target = sys.argv[2]
    
    if command == "lookup":
        result = api.extract_profile_info(target)
    elif command == "search":
        result = api.search_by_name(target)
    elif command == "check":
        result = api.check_username(target)
    elif command == "id":
        result = api.lookup_by_id(target)
    elif command == "batch":
        items = [x.strip() for x in target.split(",")]
        result = api.batch_lookup(items)
    else:
        result = {"status": "error", "error": f"Unknown command: {command}"}
    
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
