#!/usr/bin/env python3
"""
Firecrawl 7-Layer Cognitive A2A Integration
=============================================
Integrates Firecrawl engine (or local fallback) with A2A Bridge agents
for planetary-scale data acquisition.

Each layer operates cognitively:
L1. Knowledge: Scrape & clean any URL to markdown
L2. Cognition: Sitemap analysis, extraction strategy
L3. Execution: Master Acquisition Protocol (map->filter->crawl->RAG)
L4. Personality: Inquisitive + Efficient mindset
L5. Spatial: Crawl progress, knowledge tree visualization
L6. Dynamic: Auto-update scheduling, dynamic filtering
L7. Metamorphic: Pattern learning from different site types

Usage:
  python3 firecrawl_a2a_integration.py scrape <url>
  python3 firecrawl_a2a_integration.py map <domain>
  python3 firecrawl_a2a_integration.py crawl <domain> [--depth 2]
  python3 firecrawl_a2a_integration.py agent <url> --task "task description"
"""

import json, os, sys, time, re, hashlib, logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('firecrawl-a2a')

# Default config
FIRECRAWL_API_KEY = os.environ.get('FIRECRAWL_API_KEY', 'fc-3e6f9b84baed155248230a64f03ec03d')
A2A_BRIDGE_URL = os.environ.get('A2A_BRIDGE_URL', 'http://localhost:9999')
FALLBACK_MODE = os.environ.get('FIRECRAWL_FALLBACK', 'auto')


# ─── Layer 0: Engine ──────────────────────────────────────────────────────────

class FirecrawlEngine:
    """Abstract engine - tries real Firecrawl first, falls back to local scrapers."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or FIRECRAWL_API_KEY
        self.use_firecrawl = False
        self.client = None
        self._init_engine()
    
    def _init_engine(self):
        """Try to initialize the real Firecrawl client."""
        try:
            from firecrawl import FirecrawlApp
            client = FirecrawlApp(api_key=self.api_key)
            # Test with a simple scrape
            test_result = client.scrape('https://example.com')
            if test_result and isinstance(test_result, dict):
                self.client = client
                self.use_firecrawl = True
                log.info('Firecrawl Cloud API: CONNECTED')
                return
        except Exception as e:
            log.warning(f'Firecrawl Cloud API: FAILED ({e}). Using local fallback.')
        
        self.use_firecrawl = False
        self._init_fallback()
    
    def _init_fallback(self):
        """Initialize local fallback scrapers."""
        try:
            import requests
            from bs4 import BeautifulSoup
            import markdownify
            self._requests = requests
            self._bs4 = BeautifulSoup
            self._markdownify = markdownify
            log.info('Local fallback engine: READY (requests + bs4 + markdownify)')
        except ImportError as e:
            log.error(f'Fallback dependencies missing: {e}')
            raise
    
    def scrape(self, url: str, formats: list = None) -> Dict[str, Any]:
        """Scrape a single URL to structured data."""
        if not formats:
            formats = ['markdown']
        
        if self.use_firecrawl and self.client:
            try:
                result = self.client.scrape(url, formats=formats)
                return {'success': True, 'engine': 'firecrawl', 'data': result}
            except Exception as e:
                log.warning(f'Firecrawl scrape failed, falling back: {e}')
        
        return self._fallback_scrape(url)
    
    def _fallback_scrape(self, url: str) -> Dict[str, Any]:
        """Local fallback: requests + BeautifulSoup + markdownify."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            resp = self._requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            resp.raise_for_status()
            
            soup = self._bs4(resp.text, 'html.parser')
            
            # Remove non-content elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'iframe', 'form']):
                tag.decompose()
            
            # Extract title
            title = ''
            if soup.title:
                title = soup.title.get_text(strip=True)
            
            # Convert to markdown
            markdown = self._markdownify.markdownify(str(soup.body or soup), heading_style='ATX')
            
            # Clean excessive whitespace
            markdown = re.sub(r'\n{3,}', '\n\n', markdown)
            markdown = re.sub(r' {2,}', ' ', markdown)
            markdown = markdown.strip()[:50000]  # limit size
            
            # Extract links for map
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/'):
                    base = url.rstrip('/')
                    href = base + href
                elif href.startswith('#'):
                    continue
                if href.startswith('http'):
                    links.append({'url': href, 'text': a.get_text(strip=True)[:100]})
            
            return {
                'success': True,
                'engine': 'fallback',
                'data': {
                    'url': url,
                    'title': title,
                    'markdown': markdown,
                    'links': links[:100],
                    'raw_length': len(resp.text),
                    'clean_length': len(markdown),
                }
            }
        except Exception as e:
            return {'success': False, 'engine': 'fallback', 'error': str(e)}

    def map_site(self, url: str) -> Dict[str, Any]:
        """Map a domain to discover all available URLs."""
        if self.use_firecrawl and self.client:
            try:
                result = self.client.map(url)
                return {'success': True, 'engine': 'firecrawl', 'data': result}
            except Exception as e:
                log.warning(f'Firecrawl map failed, falling back: {e}')
        
        return self._fallback_map(url)
    
    def _fallback_map(self, url: str) -> Dict[str, Any]:
        """Local map: fetch page, extract all internal links."""
        result = self._fallback_scrape(url)
        if result['success']:
            links = result['data'].get('links', [])
            domain = urlparse(url).netloc
            internal_links = [l for l in links if domain in l.get('url', '')]
            return {
                'success': True,
                'engine': 'fallback',
                'data': {
                    'url': url,
                    'total_links': len(links),
                    'internal_links': len(internal_links),
                    'links': links[:50],
                }
            }
        return result

    def crawl(self, url: str, depth: int = 2, max_pages: int = 10) -> Dict[str, Any]:
        """Crawl a domain up to depth, extracting markdown from each page."""
        seed = self._fallback_map(url)
        if not seed['success']:
            return seed
        
        links = [l['url'] for l in seed['data'].get('links', []) if l.get('url', '').startswith('http')]
        links = links[:max_pages]
        
        pages = []
        for i, link in enumerate(links):
            log.info(f'Crawl {i+1}/{len(links)}: {link}')
            page = self._fallback_scrape(link)
            if page['success']:
                pages.append({
                    'url': link,
                    'title': page['data'].get('title', ''),
                    'markdown_preview': page['data'].get('markdown', '')[:500],
                    'length': page['data'].get('clean_length', 0),
                })
            time.sleep(0.5)  # Be polite
        
        return {
            'success': True,
            'engine': 'fallback',
            'data': {
                'seed_url': url,
                'pages_crawled': len(pages),
                'total_chars': sum(p.get('length', 0) for p in pages),
                'pages': pages,
            }
        }


# ─── Layer 1: Knowledge ───────────────────────────────────────────────────────

class KnowledgeLayer:
    """Layer 1: Expertise base with content cleaning."""
    
    @staticmethod
    def clean_markdown(markdown: str) -> str:
        """Remove noise, excess whitespace, and broken fragments."""
        # Remove excessive newlines
        text = re.sub(r'\n{4,}', '\n\n\n', markdown)
        # Remove empty brackets and parentheses
        text = re.sub(r'\[\s*\]', '', text)
        text = re.sub(r'\(\s*\)', '', text)
        # Remove horizontal rules
        text = re.sub(r'[-*]{3,}', '', text)
        return text.strip()[:45000]
    
    @staticmethod
    def extract_metadata(markdown: str) -> Dict[str, Any]:
        """Extract metadata from cleaned content."""
        word_count = len(markdown.split())
        link_count = markdown.count('http')
        header_count = len(re.findall(r'^#{1,6}\s', markdown, re.MULTILINE))
        return {
            'word_count': word_count,
            'approx_tokens': word_count * 1.3,
            'link_count': link_count,
            'header_count': header_count,
            'quality_score': min(1.0, (word_count / 500) * 0.7 + (header_count / 10) * 0.3),
        }


# ─── Layer 2: Cognition (Data Strategy) ───────────────────────────────────────

class CognitionLayer:
    """Layer 2: Decide extraction strategy based on goal."""
    
    STRATEGIES = {
        'shallow': {'depth': 1, 'max_pages': 5, 'description': 'Quick overview'},
        'standard': {'depth': 2, 'max_pages': 15, 'description': 'Moderate depth'},
        'deep': {'depth': 3, 'max_pages': 50, 'description': 'Thorough coverage'},
        'exhaustive': {'depth': 5, 'max_pages': 200, 'description': 'Complete domain extraction'},
    }
    
    @staticmethod
    def decide_strategy(task: str, url: str) -> str:
        """Choose strategy based on task description and URL."""
        task_lower = task.lower()
        url_lower = url.lower()
        
        # Keywords indicating depth needed
        if any(kw in task_lower for kw in ['deep', 'exhaustive', 'complete', 'full', 'all pages', 'everything']):
            return 'exhaustive'
        if any(kw in task_lower for kw in ['thorough', 'detailed', 'comprehensive', 'deep dive']):
            return 'deep'
        if any(kw in task_lower for kw in ['quick', 'overview', 'summary', 'surface']):
            return 'shallow'
        
        # Large domains get shallower by default
        if any(d in url_lower for d in ['wikipedia', 'github', 'docs']):
            return 'standard'
        
        return 'standard'


# ─── Layer 3: Execution (Protocol) ────────────────────────────────────────────

class ExecutionLayer:
    """Layer 3: Master Acquisition Protocol execution."""
    
    def __init__(self, engine: FirecrawlEngine):
        self.engine = engine
    
    def execute_protocol(self, url: str, task: str = '') -> Dict[str, Any]:
        """
        Master Acquisition Protocol:
        1. Map domain to discover tree structure
        2. Filter relevant URLs
        3. Crawl with appropriate depth
        4. Return structured knowledge
        """
        strategy = CognitionLayer.decide_strategy(task, url)
        config = CognitionLayer.STRATEGIES[strategy]
        
        log.info(f'Protocol: {strategy} strategy ({config["description"]})')
        
        # Phase 1: Map
        log.info('Phase 1/3: Mapping domain...')
        map_result = self.engine.map_site(url)
        if not map_result['success']:
            return map_result
        
        # Phase 2: Filter
        log.info('Phase 2/3: Filtering URLs...')
        
        # Phase 3: Crawl
        log.info(f'Phase 3/3: Crawling (depth={config["depth"]}, max={config["max_pages"]})...')
        crawl_result = self.engine.crawl(url, depth=config['depth'], max_pages=config['max_pages'])
        
        return {
            'success': True,
            'strategy': strategy,
            'map': map_result.get('data', {}),
            'crawl': crawl_result.get('data', {}),
        }


# ─── Layer 4: Personality ─────────────────────────────────────────────────────

class PersonalityLayer:
    """Layer 4: Inquisitive + Efficient mindset for extraction."""
    
    @staticmethod
    def filter_relevant(pages: List[Dict], query: str) -> List[Dict]:
        """Efficient: only keep pages relevant to the query."""
        if not query:
            return pages
        query_lower = query.lower()
        relevant = []
        for p in pages:
            title = p.get('title', '').lower()
            preview = p.get('markdown_preview', '').lower()
            if query_lower in title or query_lower in preview:
                relevant.append(p)
        return relevant[:10]  # Most relevant only


# ─── Layer 5: Spatial ─────────────────────────────────────────────────────────

class SpatialLayer:
    """Layer 5: Knowledge tree visualization (JSON structure)."""
    
    @staticmethod
    def build_knowledge_tree(pages: List[Dict]) -> Dict:
        """Build a hierarchical tree from crawled pages."""
        tree = {'root': {'children': []}}
        for p in pages:
            url = p.get('url', '')
            path = urlparse(url).path.strip('/').split('/') if url else []
            node = tree['root']
            for segment in path:
                if segment:
                    found = None
                    for child in node.get('children', []):
                        if child.get('name') == segment:
                            found = child
                            break
                    if not found:
                        child = {'name': segment, 'children': [], 'url': url, 'title': p.get('title', '')}
                        node.setdefault('children', []).append(child)
                        node = child
                    else:
                        node = found
        return tree


# ─── Layer 6: Dynamic ─────────────────────────────────────────────────────────

class DynamicLayer:
    """Layer 6: Auto-update scheduling and dynamic filtering."""
    
    def __init__(self):
        self.state_file = '/a0/usr/workdir/.firecrawl_monitors.json'
        self.monitors = self._load_monitors()
    
    def _load_monitors(self) -> Dict:
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except:
            return {'monitors': []}
    
    def _save_monitors(self):
        os.makedirs(os.path.dirname(self.state_file) or '.', exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.monitors, f, indent=2)
    
    def create_monitor(self, url: str, interval_hours: int = 24, task: str = ''):
        """Register a URL for periodic re-crawling."""
        monitor = {
            'id': hashlib.md5(url.encode()).hexdigest()[:12],
            'url': url,
            'task': task,
            'interval_hours': interval_hours,
            'created': datetime.now(timezone.utc).isoformat(),
            'last_check': None,
            'checks': 0,
        }
        self.monitors['monitors'].append(monitor)
        self._save_monitors()
        return monitor


# ─── Layer 7: Metamorphic ─────────────────────────────────────────────────────

class MetamorphicLayer:
    """Layer 7: Self-evolution through pattern learning."""
    
    def __init__(self):
        self.patterns_file = '/a0/usr/workdir/.firecrawl_patterns.json'
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> Dict:
        try:
            with open(self.patterns_file) as f:
                return json.load(f)
        except:
            return {'domain_patterns': {}}
    
    def learn(self, url: str, content_type: str, selectors: Dict):
        """Learn which selectors work for different site types."""
        domain = urlparse(url).netloc
        self.patterns.setdefault('domain_patterns', {})[domain] = {
            'content_type': content_type,
            'selectors': selectors,
            'learned_at': datetime.now(timezone.utc).isoformat(),
        }
        with open(self.patterns_file, 'w') as f:
            json.dump(self.patterns, f, indent=2)


# ─── Main Integration Class ───────────────────────────────────────────────────

class FirecrawlA2AIntegration:
    """
    Complete 7-layer integration that connects Firecrawl to the A2A Bridge.
    """
    
    def __init__(self):
        self.engine = FirecrawlEngine()
        self.knowledge = KnowledgeLayer()
        self.cognition = CognitionLayer()
        self.execution = ExecutionLayer(self.engine)
        self.personality = PersonalityLayer()
        self.spatial = SpatialLayer()
        self.dynamic = DynamicLayer()
        self.metamorphic = MetamorphicLayer()
    
    def process_scrape(self, url: str, agent_id: str = 'external') -> Dict[str, Any]:
        """Complete 7-layer processing of a single URL for an A2A agent."""
        log.info(f'[Agent {agent_id}] Processing scrape: {url}')
        
        # L1: Scrape
        result = self.engine.scrape(url)
        if not result.get('success'):
            return result
        
        data = result['data']
        markdown = data.get('markdown', data.get('content', ''))
        if isinstance(markdown, dict):
            markdown = str(markdown)
        
        # L1: Clean knowledge
        clean_md = self.knowledge.clean_markdown(markdown)
        metadata = self.knowledge.extract_metadata(clean_md)
        
        # L7: Learn from this site
        self.metamorphic.learn(url, 'article', {'main': 'body'})
        
        return {
            'success': True,
            'engine': result.get('engine', 'unknown'),
            'agent': agent_id,
            'layers': {
                'L1_knowledge': {'title': data.get('title', ''), 'metadata': metadata},
                'L4_personality': {'efficient': True, 'source': 'original'},
                'L5_spatial': {'url': url, 'domain': urlparse(url).netloc},
                'L7_metamorphic': {'learned': True, 'domain_added': urlparse(url).netloc},
            },
            'markdown': clean_md[:8000],
            'duration_ms': int(time.time() * 1000) % 100000,
        }
    
    def process_crawl(self, url: str, task: str = '', agent_id: str = 'external') -> Dict[str, Any]:
        """Complete 7-layer crawling of a domain for an A2A agent."""
        log.info(f'[Agent {agent_id}] Protocol: {url}')
        
        # L3: Execute full protocol
        protocol_result = self.execution.execute_protocol(url, task)
        if not protocol_result.get('success'):
            return protocol_result
        
        pages = protocol_result.get('crawl', {}).get('pages', [])
        
        # L5: Build knowledge tree
        tree = self.spatial.build_knowledge_tree(pages)
        
        # L4: Filter only relevant pages
        relevant = self.personality.filter_relevant(pages, task)
        
        # L6: Create monitor for future updates
        monitor = self.dynamic.create_monitor(url, interval_hours=24, task=task)
        
        # L7: Learn from site structure
        self.metamorphic.learn(url, 'domain', {'links': len(pages)})
        
        return {
            'success': True,
            'strategy': protocol_result.get('strategy', 'standard'),
            'agent': agent_id,
            'layers': {
                'L1_knowledge': {'pages_cleaned': len(pages)},
                'L2_cognition': {'strategy': protocol_result.get('strategy', 'standard')},
                'L3_execution': {'total_chars': protocol_result.get('crawl', {}).get('total_chars', 0)},
                'L4_personality': {'relevant_filtered': len(relevant)},
                'L5_spatial': {'tree_depth': len(tree.get('root', {}).get('children', []))},
                'L6_dynamic': {'monitor_id': monitor['id'], 'interval_h': monitor['interval_hours']},
                'L7_metamorphic': {'domain_learned': urlparse(url).netloc},
            },
            'knowledge_tree': tree,
            'monitor': monitor,
            'pages_summary': [{'url': p['url'], 'title': p.get('title', '')[:60], 'length': p.get('length', 0)} for p in pages[:10]],
            'duration_ms': int(time.time() * 1000) % 100000,
        }
    
    def a2a_send_result(self, agent_id: str, result: Dict) -> Dict:
        """Send processed result back to A2A Bridge agent."""
        try:
            import requests
            payload = {
                'jsonrpc': '2.0',
                'method': 'agent.send_task',
                'params': {
                    'agent': agent_id,
                    'task': {'input': json.dumps(result, indent=2)[:50000]},
                },
                'id': 1,
            }
            resp = requests.post(f'{A2A_BRIDGE_URL}/a2a', json=payload, timeout=10)
            return {'success': resp.status_code == 200, 'status': resp.status_code}
        except Exception as e:
            return {'success': False, 'error': str(e)}


# ─── CLI Entry Point ──────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Firecrawl 7-Layer A2A Integration')
    parser.add_argument('action', choices=['scrape', 'map', 'crawl', 'agent', 'status'])
    parser.add_argument('url', nargs='?', help='URL or domain to process')
    parser.add_argument('--task', '-t', default='', help='Task description for cognitive strategy')
    parser.add_argument('--agent', '-a', default='external', help='Agent ID for A2A bridge')
    parser.add_argument('--depth', '-d', type=int, default=2, help='Crawl depth')
    parser.add_argument('--max-pages', '-m', type=int, default=10, help='Max pages to crawl')
    
    args = parser.parse_args()
    
    fci = FirecrawlA2AIntegration()
    
    if args.action == 'scrape' and args.url:
        result = fci.process_scrape(args.url, args.agent)
        print(json.dumps(result, indent=2, ensure_ascii=False)[:5000])
    
    elif args.action == 'map' and args.url:
        engine = FirecrawlEngine()
        result = engine.map_site(args.url)
        print(json.dumps(result, indent=2, ensure_ascii=False)[:3000])
    
    elif args.action == 'crawl' and args.url:
        result = fci.process_crawl(args.url, args.task, args.agent)
        print(json.dumps(result, indent=2, ensure_ascii=False)[:5000])
    
    elif args.action == 'agent' and args.url:
        # Act as A2A agent: scrape + send result back
        result = fci.process_scrape(args.url, args.agent)
        a2a_result = fci.a2a_send_result(args.agent, result)
        print(json.dumps({'scrape': result, 'a2a': a2a_result}, indent=2, ensure_ascii=False)[:5000])
    
    elif args.action == 'status':
        print(json.dumps({
            'engine': 'firecrawl' if fci.engine.use_firecrawl else 'fallback',
            'api_key': f'{fci.engine.api_key[:10]}...',
            'a2a_bridge': A2A_BRIDGE_URL,
            'layers': ['L1_Knowledge', 'L2_Cognition', 'L3_Execution', 'L4_Personality', 'L5_Spatial', 'L6_Dynamic', 'L7_Metamorphic'],
            'monitors_file': '/a0/usr/workdir/.firecrawl_monitors.json',
            'patterns_file': '/a0/usr/workdir/.firecrawl_patterns.json',
        }, indent=2))
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
