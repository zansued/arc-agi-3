#!/usr/bin/env python3
"""
Recon Runner — Script de execução do Pipeline de Recon Automatizado.

Fluxo:
1. Subfinder: enumeração passiva de subdomínios
2. httpx: HTTP probing (hosts ativos, tecnologias, títulos)
3. Katana: crawling de endpoints
4. Nuclei: scanning de vulnerabilidades
5. KG Ingester: integração ao Knowledge Graph

Uso:
  python3 recon_runner.py --domain example.com
  python3 recon_runner.py --domain example.com --output /tmp/recon_report.json
  python3 recon_runner.py --list-domains  # lista domínios configurados
"""

import json
import os
import subprocess
import sys
import argparse
from datetime import datetime

# Paths
WORKDIR = '/a0/usr/workdir'
KG_DIR = os.path.join(WORKDIR, 'knowledge_graph')
DATA_DIR = os.path.join(KG_DIR, 'data')

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def timestamp():
    return datetime.now().isoformat()

def run_subfinder(domain: str) -> list:
    """Etapa 1: Enumeração passiva de subdomínios."""
    print(f"[1/5] 🔍 Subfinder: enumerando subdomínios para {domain}...")
    output_file = f'/tmp/subfinder_{domain}.txt'
    try:
        result = subprocess.run(
            ['subfinder', '-d', domain, '-silent', '-o', output_file],
            capture_output=True, text=True, timeout=120
        )
        if os.path.exists(output_file):
            with open(output_file) as f:
                subdomains = [l.strip() for l in f if l.strip()]
            print(f"  ✅ {len(subdomains)} subdomínios encontrados")
            return subdomains
        return []
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ Timeout após 120s")
        return []
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return []

def run_httpx(subdomains: list) -> list:
    """Etapa 2: HTTP probing."""
    print(f"[2/5] 🌐 httpx: probe HTTP em {len(subdomains)} hosts...")
    if not subdomains:
        print("  ⏭️ Pulando (sem subdomínios)")
        return []
    try:
        input_text = '\n'.join(subdomains)
        result = subprocess.run(
            ['httpx', '-json', '-silent', '-title', '-tech-detect', '-status-code'],
            input=input_text, capture_output=True, text=True, timeout=180
        )
        hosts = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    hosts.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        print(f"  ✅ {len(hosts)} hosts ativos detectados")
        return hosts
    except subprocess.TimeoutExpired:
        print(f"  ⚠️ Timeout após 180s")
        return []
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return []

def run_katana(hosts: list) -> list:
    """Etapa 3: Crawling de endpoints."""
    print(f"[3/5] 🕸️ Katana: crawleando endpoints...")
    if not hosts:
        print("  ⏭️ Pulando (sem hosts ativos)")
        return []
    urls = []
    for h in hosts[:5]:  # Limite de 5 hosts por execução
        url = h.get('url', '')
        if url:
            urls.append(url)
    if not urls:
        print("  ⏭️ Pulando (sem URLs válidas)")
        return []
    try:
        output_file = '/tmp/katana_crawl.txt'
        for url in urls[:3]:  # Crawlear até 3 URLs
            subprocess.run(
                ['katana', '-u', url, '-d', '2', '-silent', '-o', output_file],
                capture_output=True, text=True, timeout=120
            )
        endpoints = []
        if os.path.exists(output_file):
            with open(output_file) as f:
                endpoints = [l.strip() for l in f if l.strip()]
        print(f"  ✅ {len(endpoints)} endpoints descobertos")
        return endpoints
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return []

def run_nuclei(hosts: list, severity: str = 'medium,high,critical') -> list:
    """Etapa 4: Scanning de vulnerabilidades."""
    print(f"[4/5] 🔬 Nuclei: scanneando vulnerabilidades (severity: {severity})...")
    if not hosts:
        print("  ⏭️ Pulando (sem hosts)")
        return []
    findings = []
    for h in hosts[:5]:  # Limite de 5 hosts
        url = h.get('url', '')
        if not url:
            continue
        try:
            result = subprocess.run(
                ['nuclei', '-u', url, '-severity', severity, '-json', '-silent'],
                capture_output=True, text=True, timeout=300
            )
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        findings.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except subprocess.TimeoutExpired:
            print(f"  ⚠️ Timeout ao scanear {url}")
        except Exception as e:
            print(f"  ❌ Erro ao scanear {url}: {e}")
    print(f"  ✅ {len(findings)} vulnerabilidades/encontros encontrados")
    return findings

def ingest_to_kg(domain: str, subdomains: list, hosts: list, findings: list) -> int:
    """Etapa 5: Integração ao Knowledge Graph."""
    print(f"[5/5] 🧠 KG Integrator: inserindo descobertas no Knowledge Graph...")
    sys.path.insert(0, os.path.join(KG_DIR, 'engine'))
    try:
        from spo_engine import SPOModel
        engine = SPOModel(data_dir=DATA_DIR)
        triples_added = 0

        # Tipo 1: dominio → subdominio
        if subdomains:
            for sub in subdomains:
                triple = {
                    "subject": f"domain:{domain}",
                    "predicate": "has_subdomain",
                    "object": f"subdomain:{sub}",
                    "confidence": 1.0,
                    "source": "subfinder",
                    "timestamp": timestamp()
                }
                engine.add_triple(triple)
                triples_added += 1

        # Tipo 2: subdominio → IP
        if hosts:
            for host in hosts:
                sub = host.get('url', '')
                ips = host.get('ip', '')
                if sub and ips:
                    triple = {
                        "subject": f"subdomain:{sub}",
                        "predicate": "resolves_to",
                        "object": f"ip:{ips.split(',')[0].strip()}",
                        "confidence": 1.0,
                        "source": "httpx",
                        "timestamp": timestamp()
                    }
                    engine.add_triple(triple)
                    triples_added += 1

        # Tipo 3: IP → porta (via Nuclei findings e portas do httpx)
        if hosts:
            for host in hosts:
                ips = host.get('ip', '')
                port = host.get('port', '')
                if ips and port:
                    triple = {
                        "subject": f"ip:{ips.split(',')[0].strip()}",
                        "predicate": "has_open_port",
                        "object": f"port:{port}",
                        "confidence": 1.0,
                        "source": "httpx",
                        "timestamp": timestamp()
                    }
                    engine.add_triple(triple)
                    triples_added += 1

        if findings:
            for finding in findings:
                fip = finding.get('ip', '')
                fport = finding.get('port', '')
                if fip and fport:
                    triple = {
                        "subject": f"ip:{fip}",
                        "predicate": "has_open_port",
                        "object": f"port:{fport}",
                        "confidence": 1.0,
                        "source": "nuclei",
                        "timestamp": timestamp()
                    }
                    engine.add_triple(triple)
                    triples_added += 1

        print(f"  ✅ {triples_added} triplas inseridas no KG")
        return triples_added
    except ImportError as e:
        print(f"  ❌ Erro ao importar SPOModel: {e}")
        return 0
    except Exception as e:
        print(f"  ❌ Erro na integração KG: {e}")
        return 0


def run_pipeline(domain: str, output: str = None) -> dict:
    """Executa o pipeline completo de recon."""
    print(f"\n{'='*60}")
    print(f"🚀 RECON PIPELINE — {domain}")
    print(f"📅 {timestamp()}")
    print(f"{'='*60}\n")

    start = datetime.now()

    # Etapas
    subdomains = run_subfinder(domain)
    hosts = run_httpx(subdomains)
    endpoints = run_katana(hosts)
    findings = run_nuclei(hosts)
    kg_count = ingest_to_kg(domain, subdomains, hosts, findings)

    elapsed = (datetime.now() - start).total_seconds()

    report = {
        "domain": domain,
        "timestamp": timestamp(),
        "duration_seconds": elapsed,
        "summary": {
            "subdomains": len(subdomains),
            "hosts_ativos": len(hosts),
            "endpoints": len(endpoints),
            "vulnerabilities": len(findings),
            "kg_triples": kg_count
        },
        "subdomains": subdomains,
        "hosts": hosts,
        "endpoints": endpoints,
        "findings": findings
    }

    # Salvar relatório
    if output:
        with open(output, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n📄 Relatório salvo em: {output}")

    print(f"\n{'='*60}")
    print(f"✅ RECON COMPLETO — {domain}")
    print(f"⏱️ Duração: {elapsed:.1f}s")
    print(f"📊 Subdomínios: {len(subdomains)} | Hosts ativos: {len(hosts)} | Endpoints: {len(endpoints)} | Vulnerabilidades: {len(findings)} | KG: {kg_count} triplas")
    print(f"{'='*60}\n")

    return report


# Domínios configurados para scan recorrente
DOMINIOS_PADRAO = [
    # Adicione aqui os domínios alvo
    # Exemplo: "example.com", "meudominio.com.br"
]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Recon Pipeline Automatizado')
    parser.add_argument('--domain', help='Domínio alvo para recon')
    parser.add_argument('--output', help='Caminho para salvar relatório JSON')
    parser.add_argument('--list-domains', action='store_true', help='Listar domínios configurados')
    parser.add_argument('--add-domain', help='Adicionar domínio à lista padrão')

    args = parser.parse_args()

    if args.list_domains:
        print("Domínios configurados para scan recorrente:")
        if DOMINIOS_PADRAO:
            for d in DOMINIOS_PADRAO:
                print(f"  - {d}")
        else:
            print("  (Nenhum domínio configurado ainda — use --add-domain ou edite DOMINIOS_PADRAO)")
        sys.exit(0)

    if args.add_domain:
        # Adiciona domínio editando o próprio script
        import re
        script_path = os.path.abspath(__file__)
        with open(script_path) as f:
            content = f.read()
        # Verificar se já existe
        if args.add_domain in content:
            print(f"Domínio {args.add_domain} já está na lista.")
        else:
            content = content.replace(
                'DOMINIOS_PADRAO = [',
                f'DOMINIOS_PADRAO = [\n    "{args.add_domain}",'
            )
            with open(script_path, 'w') as f:
                f.write(content)
            print(f"✅ Domínio {args.add_domain} adicionado à lista padrão!")
        sys.exit(0)

    if args.domain:
        run_pipeline(args.domain, args.output)
    else:
        print("❌ Use --domain para especificar o alvo ou --list-domains para ver configurados")
        parser.print_help()
        sys.exit(1)
