import json, os

SQUADS_DIR = '/a0/usr/workdir/squad_orchestrator/squads'
PIPELINES_DIR = '/a0/usr/workdir/squad_orchestrator/pipelines'
os.makedirs(SQUADS_DIR, exist_ok=True)
os.makedirs(PIPELINES_DIR, exist_ok=True)

# ======== SQUAD DE RECON AUTOMATIZADO ========
recon_squad = {
    "name": "Recon Automatizado",
    "description": "Squad especializado em reconhecimento de superfície de ataque com ProjectDiscovery stack",
    "agents": [
        {
            "name": "Subfinder",
            "role": "subdomain_enum",
            "description": "Enumeração passiva de subdomínios usando Subfinder (ProjectDiscovery)",
            "tools": ["subfinder_bridge"],
            "model": "default",
            "created_at": "2026-04-29T16:43:00"
        },
        {
            "name": "HTTP Prober",
            "role": "http_probe",
            "description": "Probe HTTP para detectar hosts ativos, títulos e tecnologias usando httpx",
            "tools": ["httpx_bridge"],
            "model": "default",
            "created_at": "2026-04-29T16:43:00"
        },
        {
            "name": "Crawler",
            "role": "crawler",
            "description": "Crawling de endpoints e URLs usando Katana",
            "tools": ["katana_bridge"],
            "model": "default",
            "created_at": "2026-04-29T16:43:00"
        },
        {
            "name": "Scanner",
            "role": "scanner",
            "description": "Scan de vulnerabilidades usando Nuclei (YAML templates)",
            "tools": ["nuclei_bridge"],
            "model": "default",
            "created_at": "2026-04-29T16:43:00"
        },
        {
            "name": "KG Integrator",
            "role": "knowledge",
            "description": "Integra descobertas ao Knowledge Graph (domínios → subdomínios → IPs → portas)",
            "tools": ["spo_engine", "ingestion_bridge"],
            "model": "default",
            "created_at": "2026-04-29T16:43:00"
        },
        {
            "name": "Analista",
            "role": "analyst",
            "description": "Consolida resultados e gera relatório final de recon",
            "tools": ["code_execution_tool", "memory_save"],
            "model": "default",
            "created_at": "2026-04-29T16:43:00"
        }
    ],
    "goal": "Mapear superfície de ataque completa: subdomínios → HTTP probing → crawling → scanning → Knowledge Graph",
    "tags": ["recon", "bugbounty", "pentest", "security", "automated"],
    "created_at": "2026-04-29T16:43:00",
    "pipeline_count": 1
}

with open(os.path.join(SQUADS_DIR, 'Recon_Automatizado.json'), 'w') as f:
    json.dump(recon_squad, f, ensure_ascii=False, indent=2)
print('✅ Squad Recon Automatizado criado!')

# ======== PIPELINE DE RECON ========
recon_pipeline = {
    "name": "Pipeline Recon Automatizado",
    "squad_name": "Recon Automatizado",
    "steps": [
        {
            "step_number": 1,
            "agent_name": "Subfinder",
            "instruction": "Enumerar subdomínios passivamente para o domínio alvo usando Subfinder",
            "input_from": None,
            "checkpoints": [
                {
                    "name": "subdominios_encontrados",
                    "type": "validation",
                    "agent": "Subfinder",
                    "description": "Validar que subdomínios foram encontrados",
                    "status": "pending",
                    "result": None,
                    "timestamp": None
                }
            ],
            "timeout_minutes": 15,
            "output": None,
            "status": "pending"
        },
        {
            "step_number": 2,
            "agent_name": "HTTP Prober",
            "instruction": "Probe HTTP nos subdomínios encontrados — detectar hosts ativos, títulos, tecnologias",
            "input_from": "Subfinder",
            "checkpoints": [],
            "timeout_minutes": 15,
            "output": None,
            "status": "pending"
        },
        {
            "step_number": 3,
            "agent_name": "Crawler",
            "instruction": "Crawlear hosts ativos para descobrir endpoints e URLs",
            "input_from": "HTTP Prober",
            "checkpoints": [],
            "timeout_minutes": 30,
            "output": None,
            "status": "pending"
        },
        {
            "step_number": 4,
            "agent_name": "Scanner",
            "instruction": "Executar Nuclei nos hosts ativos — scan de vulnerabilidades (critical, high, medium)",
            "input_from": "HTTP Prober",
            "checkpoints": [
                {
                    "name": "scan_concluido",
                    "type": "transition",
                    "agent": "Scanner",
                    "description": "Scan de vulnerabilidades concluído",
                    "status": "pending",
                    "result": None,
                    "timestamp": None
                }
            ],
            "timeout_minutes": 60,
            "output": None,
            "status": "pending"
        },
        {
            "step_number": 5,
            "agent_name": "KG Integrator",
            "instruction": "Inserir todas as descobertas no Knowledge Graph como triplas SPO",
            "input_from": None,
            "checkpoints": [
                {
                    "name": "kg_atualizado",
                    "type": "validation",
                    "agent": "KG Integrator",
                    "description": "Knowledge Graph atualizado com descobertas",
                    "status": "pending",
                    "result": None,
                    "timestamp": None
                }
            ],
            "timeout_minutes": 10,
            "output": None,
            "status": "pending"
        },
        {
            "step_number": 6,
            "agent_name": "Analista",
            "instruction": "Gerar relatório consolidado de recon e salvar em memória",
            "input_from": "Scanner",
            "checkpoints": [
                {
                    "name": "relatorio_gerado",
                    "type": "approval",
                    "agent": "Analista",
                    "description": "Relatório de recon gerado e revisado",
                    "status": "pending",
                    "result": None,
                    "timestamp": None
                }
            ],
            "timeout_minutes": 10,
            "output": None,
            "status": "pending"
        }
    ],
    "created_at": "2026-04-29T16:43:00"
}

with open(os.path.join(PIPELINES_DIR, 'Pipeline_Recon_Automatizado.json'), 'w') as f:
    json.dump(recon_pipeline, f, ensure_ascii=False, indent=2)
print('✅ Pipeline Recon Automatizado criado!')

# ======== SCRIPT DE INTEGRAÇÃO KG ========
kgingest_script = '''#!/usr/bin/env python3
"""
KG Recon Ingester — Integra descobertas de recon ao Knowledge Graph automaticamente.
Converte subdomínios, IPs e portas em triplas SPO (Subject-Predicate-Object).
"""
import json, os, sys
from datetime import datetime

KG_DIR = '/a0/usr/workdir/knowledge_graph'
sys.path.insert(0, KG_DIR)

from engine.spo_engine import SPOEngine

def ingest_recon_findings(domain: str, subdomains: list = None,
                          hosts: list = None, findings: list = None):
    """Ingere descobertas de recon no Knowledge Graph como triplas SPO"""
    engine = SPOEngine()
    triples = []
    domain_id = f"domain:{domain}"

    # Tipo 1: domínio → subdomínio
    if subdomains:
        for sub in subdomains:
            triples.append({
                "subject": domain_id,
                "predicate": "has_subdomain",
                "object": f"subdomain:{sub}",
                "confidence": 1.0,
                "source": "subfinder",
                "timestamp": datetime.now().isoformat()
            })

    # Tipo 2: subdomínio → IP
    if hosts:
        for host in hosts:
            sub = host.get("url", "")
            ips = host.get("ip", "")
            if sub and ips:
                triples.append({
                    "subject": f"subdomain:{sub}",
                    "predicate": "resolves_to",
                    "object": f"ip:{ips.split(',')[0].strip()}",
                    "confidence": 1.0,
                    "source": "httpx",
                    "timestamp": datetime.now().isoformat()
                })

    # Tipo 3: IP → portas (via Nuclei findings)
    if findings:
        for finding in findings:
            fip = finding.get("ip", "")
            fport = finding.get("port", "")
            if fip and fport:
                triples.append({
                    "subject": f"ip:{fip}",
                    "predicate": "has_open_port",
                    "object": f"port:{fport}",
                    "confidence": 1.0,
                    "source": "nuclei",
                    "timestamp": datetime.now().isoformat()
                })

    # Salvar triplas no KG
    if triples:
        count = engine.add_triples_bulk(triples)
        print(f"📊 {count} triplas inseridas no Knowledge Graph")
    else:
        print("ℹ️ Nenhuma tripla para inserir")

    return triples

if __name__ == '__main__':
    # Teste simples
    ingest_recon_findings(
        domain="example.com",
        subdomains=["www.example.com", "api.example.com"],
        hosts=[{"url": "https://www.example.com", "ip": "93.184.216.34"}],
        findings=[{"ip": "93.184.216.34", "port": "80"}]
    )
'''

with open(os.path.join(KG_DIR, 'bridges', 'recon_ingester.py'), 'w') as f:
    f.write(kgingest_script.strip())
print('✅ KG Recon Ingester criado!')

print()
print('=== RESUMO MARCO 2/3 ===')
print('✅ Squad: Recon Automatizado (6 agents)')
print('✅ Pipeline: 6 etapas encadeadas')
print('✅ KG Ingester: recon_ingester.py com engine SPO')
print('✅ Fluxo: Subfinder → httpx → Katana → Nuclei → KG → Analista')
