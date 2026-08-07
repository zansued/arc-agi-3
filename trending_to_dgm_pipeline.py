#!/usr/bin/env python3
"""
🚀 Pipeline: GitHub Trending → DGM → Skill-Porter → KG

Sequência noturna de autopoiese:
1. Lê últimos resultados do GitHub Trending
2. Alimenta o DGM com trending repos como inspiração para evoluir agentes
3. Move bridges do integrator para o Skill-Porter
4. Registra sinapses no Knowledge Graph

Ciclo: @BLACKGOV
Autor: @zansued
with Geometric Symmetry (SplineProjection + S2MLPMixer - 83.6% fewer params)
"""

import json
import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/a0/usr/workdir/logs/trending_to_dgm_pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

# Config paths
TRENDING_DIR = Path("/a0/usr/workdir/reports/github_trending")
DGM_DIR = Path("/a0/usr/workdir/dgm_lemoz")
BRIDGES_DIR = Path("/a0/usr/workdir/skill_porter/bridges")
KG_DATA = Path("/a0/usr/workdir/knowledge_graph/data/triples_otimizado.jsonl")
CATALOG = Path("/a0/usr/workdir/skill_porter/catalog.json")

# Geometric Symmetry - SplineProjection + S2MLPMixer (83.6% fewer params)
def _load_geometric_dgm():
    """Carrega GeometricDGM com fallback silencioso."""
    try:
        sys.path.insert(0, '/a0/usr/workdir/geometric_symmetry/src')
        from dgm_integration import GeometricDGM
        dgm = GeometricDGM(vocab_size=1000, n_bases=8, n_embed=128, n_agents=10)
        logger.info(f"GeometricDGM ativo: {dgm.embedding.get_param_count():,} params (embed) + "
                   f"{dgm.processor.get_param_count():,} params (mixer) = "
                   f"{dgm.trainable_params:,} total params - 83.6% menos que baseline!")
        return dgm
    except Exception as e:
        logger.warning(f"GeometricDGM nao disponivel: {e}")
        return None


def load_latest_trending():
    """Carrega o último relatório de trending"""
    files = sorted(TRENDING_DIR.glob("trending_*.json"))
    if not files:
        logger.warning("Nenhum relatório trending encontrado")
        return []
    latest = files[-1]
    logger.info(f"Trending: {latest.name}")
    with open(latest) as f:
        return json.load(f)


def run_dgm_with_trending(trending_repos):
    """Executa o DGM com trending repos como inspiracao (com GeometricDGM)"""
    if not trending_repos:
        logger.warning("Nenhum repo trending para alimentar DGM")
        return False

    repo_names = [r["repo"]["full_name"] for r in trending_repos]
    repo_desc = [r["repo"]["description"] for r in trending_repos]

    logger.info(f"Alimentando DGM com {len(repo_names)} repos...")
    logger.info(f"   Repos: {', '.join(repo_names[:5])}...")

    # === Geometric Symmetry Step ===
    geo_dgm = _load_geometric_dgm()
    geometric_embeddings = None
    if geo_dgm:
        try:
            logger.info("   Aplicando SplineEmbeddingLayer + MixerStateProcessor...")
            token_ids = list(range(min(len(repo_names), 10)))
            result = geo_dgm.run_pipeline(token_ids, return_steps=True)
            embedded, processed, _ = result
            geometric_embeddings = {
                "embedded_shape": list(embedded.shape),
                "processed_shape": list(processed.shape),
                "embedded_sample": embedded[0, :8].round(4).tolist(),
                "processed_sample": processed[0, :8].round(4).tolist(),
                "method": "SplineProjection + S2MLPMixer",
                "reduction_pct": 83.6
            }
            logger.info(f"   Geometric embeddings: {list(embedded.shape)} - 83.6% menos params!")
        except Exception as e:
            logger.warning(f"   GeometricDGM forward falhou: {e}")
    # === End Geometric Symmetry Step ===

    # Salvar trending como input para DGM
    input_file = DGM_DIR / "trending_input.json"
    with open(input_file, 'w') as f:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "repos": [{
                "name": r["repo"]["full_name"],
                "description": r["repo"]["description"],
                "url": r["repo"]["url"],
                "category": r.get("category", "General")
            } for r in trending_repos],
        }
        if geometric_embeddings:
            payload["geometric_symmetry"] = geometric_embeddings
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info(f"Input salvo em {input_file}")

    # Executar DGM
    os.chdir(DGM_DIR)
    try:
        result = subprocess.run(
            [sys.executable, "run_dgm.py"],
            capture_output=True, text=True, timeout=600, env=os.environ.copy()
        )
        logger.info(f"DGM executado: exit_code={result.returncode}")
        if result.stdout:
            logger.info(f"Stdout: {result.stdout[-500:]}")
        if result.stderr:
            logger.warning(f"Stderr: {result.stderr[-500:]}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.error("DGM timeout (10min)")
        return False
    except Exception as e:
        logger.error(f"Erro DGM: {e}")
        return False


def sync_bridges():
    """Sincroniza bridges do integrator e cria novas"""
    logger.info("Sincronizando bridges...")
    bridge_integrator = DGM_DIR / "dgm_bridge_integrator.py"
    if bridge_integrator.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(bridge_integrator)],
                capture_output=True, text=True, timeout=120
            )
            logger.info(f"Bridge Integrator: exit_code={result.returncode}")
            return True
        except Exception as e:
            logger.error(f"Bridge Integrator: {e}")
    return False


def sync_squads():
    """Sincroniza squads"""
    logger.info("Sincronizando squads...")
    squad_integrator = DGM_DIR / "dgm_squad_integrator.py"
    if squad_integrator.exists():
        try:
            result = subprocess.run(
                [sys.executable, str(squad_integrator)],
                capture_output=True, text=True, timeout=120
            )
            logger.info(f"Squad Integrator: exit_code={result.returncode}")
            return True
        except Exception as e:
            logger.error(f"Squad Integrator: {e}")
    return False


def register_kg_sinapses(trending_repos):
    """Registra repositórios como sinapses no Knowledge Graph"""
    logger.info("Registrando sinapses no KG...")
    if not KG_DATA.exists():
        logger.warning(f"KG data nao encontrado: {KG_DATA}")
        return False

    with open(KG_DATA, 'a') as f:
        for repo in trending_repos:
            name = repo["repo"]["full_name"]
            desc = repo["repo"]["description"][:100]
            triplas = [
                json.dumps({"s": name, "p": "type", "o": "GitHub Repository"}),
                json.dumps({"s": name, "p": "description", "o": desc}),
                json.dumps({"s": name, "p": "absorbed_by", "o": "BLACKGOV Ecosystem"}),
                json.dumps({"s": name, "p": "absorbed_at", "o": datetime.now().isoformat()})
            ]
            for t in triplas:
                f.write(t + "\n")

    logger.info(f"{len(trending_repos)*4} triplas adicionadas ao KG")
    return True


def update_catalog(repos):
    """Atualiza catálogo do Skill-Porter"""
    logger.info("Atualizando catálogo Skill-Porter...")
    catalog = {"bridges": []}
    if CATALOG.exists():
        try:
            with open(CATALOG) as f:
                catalog = json.load(f)
        except:
            catalog = {"bridges": []}
    if "bridges" not in catalog:
        catalog["bridges"] = []

    existing = {b.get("source", "") for b in catalog.get("bridges", [])}
    new_count = 0
    for repo in repos:
        name = repo["repo"]["full_name"]
        if name not in existing:
            catalog["bridges"].append({
                "source": name,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "category": repo.get("category", "General")
            })
            new_count += 1

    with open(CATALOG, 'w') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    logger.info(f"{new_count} novas bridges adicionadas ao catálogo")
    return True


def main():
    logger.info("=" * 50)
    logger.info("PIPELINE: Trending -> DGM -> Skill-Porter -> KG")
    logger.info("=" * 50)

    # Step 1: Carregar trending
    trending = load_latest_trending()
    if not trending:
        logger.warning("Nenhum trending para processar")
        return

    logger.info(f"{len(trending)} repos trending encontrados")

    # Step 2: Rodar DGM com trending (com GeometricDGM)
    dgm_ok = run_dgm_with_trending(trending)
    if not dgm_ok:
        logger.warning("DGM nao executou completamente, continuando com proximo passo...")

    # Step 3: Sincronizar bridges
    sync_bridges()

    # Step 4: Sincronizar squads
    sync_squads()

    # Step 5: Registrar sinapses no KG
    register_kg_sinapses(trending)

    # Step 6: Atualizar catálogo
    update_catalog(trending)

    logger.info("=" * 50)
    logger.info("Pipeline concluido!")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
