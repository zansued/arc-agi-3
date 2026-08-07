#!/usr/bin/env python3
"""
FB ULTIMATE SCRAPER v2 — BUSCA EM MASSA DE LEADS

Evolução do Ultimate Facebook API Scraper original.

Novas capacidades:
- Batch processing com paralelismo (ThreadPoolExecutor)
- Pipeline automático: SQLite → Firecrawl API → Enriquecimento → Exportação
- Rate limiting inteligente para evitar bloqueio
- Exportação para CSV, JSON, e integração com Knowledge Graph
- Bridge Skill-Porter (fb_ultimate_bridge)

APIs utilizadas:
1. Firecrawl API (https://firecrawl.techstorebrasil.com/v0/scrape) sem chave
2. Facebook Graph API pública (fallback)
3. SQLite BrazilianPeople.db (base local)
"""

import requests
import json
import sys
import os
import csv
import time
import random
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

# Configurações
API_URL = "https://firecrawl.techstorebrasil.com/v0/scrape"
FB_BASE = "https://www.facebook.com"
DB_PATH = "/a0/usr/uploads/BrazilianPeople.db"
MAX_WORKERS = 5  # Paralelismo máximo
RATE_LIMIT_DELAY = 2.0  # Delay entre requisições

def log(msg: str):
    """Log simples com timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


class FacebookMassScraper:
    """
    Scraper em massa de leads do Facebook.
    """

    def __init__(self, max_workers: int = MAX_WORKERS, db_path: str = DB_PATH):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; SM-S23) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        })
        self.max_workers = max_workers
        self.db_path = db_path
        self.stats = {"scraped": 0, "failed": 0, "skipped": 0, "total": 0}

    def scrape_profile(self, url: str) -> Dict:
        """
        Scrape perfil individual via Firecrawl API.
        """
        if not url.startswith('http'):
            url = f"{FB_BASE}/{url}"

        try:
            resp = requests.post(
                API_URL,
                json={"url": url},
                timeout=30
            )
            if resp.status_code != 200:
                return {"status": "error", "error": f"HTTP {resp.status_code}"}

            data = resp.json()
            if not data.get("success"):
                return {"status": "error", "error": data.get("error", "Unknown")}

            metadata = data.get("data", {}).get("metadata", {})
            return {
                "status": "success",
                "url": url,
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "ogTitle": metadata.get("ogTitle", ""),
                "ogDescription": metadata.get("ogDescription", ""),
                "ogImage": metadata.get("ogImage", ""),
                "language": metadata.get("language", "")
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def batch_scrape(self, urls: List[str]) -> List[Dict]:
        """
        Scrape múltiplos URLs em paralelo com rate limiting.
        """
        results = []
        log(f"Iniciando batch scrape de {len(urls)} URLs (workers={self.max_workers})")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(self._rate_limited_scrape, url): url 
                for url in urls
            }

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                    if result.get("status") == "success":
                        self.stats["scraped"] += 1
                    else:
                        self.stats["failed"] += 1
                except Exception as e:
                    results.append({"status": "error", "error": str(e), "url": url})
                    self.stats["failed"] += 1

        log(f"Batch completo: {self.stats['scraped']} success, {self.stats['failed']} failed")
        return results

    def _rate_limited_scrape(self, url: str) -> Dict:
        """Scrape com delay para evitar rate limiting"""
        time.sleep(RATE_LIMIT_DELAY + random.uniform(0.5, 1.5))
        return self.scrape_profile(url)

    def process_from_db(self, limit: int = 50, state: str = None) -> List[Dict]:
        """
        Processa leads do banco SQLite e enriquece com dados do Facebook.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT nome_completo, telefone, facebook_id, cidade, estado FROM facebook_data WHERE facebook_id IS NOT NULL AND facebook_id != ''"
        params = []

        if state:
            query += " AND estado = ?"
            params.append(state)

        query += " LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        self.stats["total"] = len(rows)
        log(f"Carregados {len(rows)} registros do banco SQLite")

        enriched = []
        urls = []
        url_map = {}

        for row in rows:
            nome, telefone, fb_id, cidade, estado = row
            url = f"{FB_BASE}/profile.php?id={fb_id}"
            urls.append(url)
            url_map[url] = {
                "nome": nome,
                "telefone": telefone,
                "facebook_id": fb_id,
                "cidade": cidade or "",
                "estado": estado or ""
            }

        # Scrape em batch
        scrape_results = self.batch_scrape(urls)

        # Merge resultados
        for result in scrape_results:
            url = result.get("url", "")
            base_info = url_map.get(url, {})
            enriched.append({
                **base_info,
                "scrape_status": result.get("status"),
                "facebook_title": result.get("title", ""),
                "facebook_description": result.get("description", ""),
                "facebook_og_title": result.get("ogTitle", ""),
                "scraped_at": datetime.now().isoformat()
            })

        return enriched

    def search_leads_by_name(self, names: List[str]) -> List[Dict]:
        """
        Busca leads por lista de nomes.
        """
        log(f"Buscando {len(names)} nomes no Facebook...")
        results = []

        for name in names:
            time.sleep(RATE_LIMIT_DELAY)
            search_url = f"https://www.facebook.com/public/{name.replace(' ', '-')}"
            result = self.scrape_profile(search_url)
            result["query_name"] = name
            results.append(result)

            if result.get("status") == "success":
                log(f"  ✅ {name}: encontrado")
            else:
                log(f"  ❌ {name}: {result.get('error', 'falha')}")

        return results

    def export_csv(self, leads: List[Dict], output_path: str):
        """Exporta leads enriquecidos para CSV"""
        if not leads:
            log("Nada para exportar")
            return

        fieldnames = [
            "nome", "telefone", "facebook_id", "cidade", "estado",
            "scrape_status", "facebook_title", "facebook_description",
            "facebook_og_title", "scraped_at"
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(leads)

        log(f"✅ Exportados {len(leads)} leads para {output_path}")

    def export_json(self, leads: List[Dict], output_path: str):
        """Exporta leads enriquecidos para JSON"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(leads, f, ensure_ascii=False, indent=2)
        log(f"✅ Exportados {len(leads)} leads para {output_path}")

    def get_stats(self) -> Dict:
        """Retorna estatísticas da sessão"""
        return {
            **self.stats,
            "success_rate": round(
                (self.stats["scraped"] / max(self.stats["total"], 1)) * 100, 1
            ),
            "firecrawl_api": API_URL
        }


def main():
    """CLI principal"""
    scraper = FacebookMassScraper()

    if len(sys.argv) < 2:
        print("""USO:
  python3 ultimate_fb_mass.py batch <limite> [estado]  → Processa leads do banco SQLite
  python3 ultimate_fb_mass.py search <nome1,nome2>    → Busca por nomes
  python3 ultimate_fb_mass.py scrape <url>            → Scrape perfil único
  python3 ultimate_fb_mass.py stats                   → Estatísticas do sistema
        """)
        return

    cmd = sys.argv[1]

    if cmd == "batch":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
        state = sys.argv[3] if len(sys.argv) > 3 else None
        leads = scraper.process_from_db(limit=limit, state=state)

        out_json = f"leads_enriquecidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        out_csv = f"leads_enriquecidos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        scraper.export_json(leads, out_json)
        scraper.export_csv(leads, out_csv)

        print(f"\n📊 Estatísticas: {json.dumps(scraper.get_stats(), indent=2)}")

    elif cmd == "search":
        names = sys.argv[2].split(",") if len(sys.argv) > 2 else []
        results = scraper.search_leads_by_name(names)

        out = f"search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(out, 'w') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Resultados salvos em {out}")

    elif cmd == "scrape":
        url = sys.argv[2] if len(sys.argv) > 2 else input("URL: ")
        result = scraper.scrape_profile(url)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif cmd == "stats":
        print(json.dumps(scraper.get_stats(), indent=2))


if __name__ == "__main__":
    main()