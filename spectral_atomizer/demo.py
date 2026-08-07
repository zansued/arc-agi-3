#!/usr/bin/env python3
"""
Demo Completo: 5 Módulos de Atomização Espectral (OSCAR-inspired)

Demonstra todas as 5 aplicações do S^T S (espectro convolutional ciente de
atenção) adaptado do OSCAR (FutureMLS-Lab) para o ecossistema BLACKGOV.

Uso:
  python demo.py              # demo completa
  python demo.py --quick      # versão rápida
  python demo.py --module 1   # módulo específico
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from datetime import datetime

# ============================================================
# Módulos do Spectral Atomizer
# ============================================================
from spectral_atomizer.core import (
    build_hadamard, bit_reversal_perm, spectral_importance_ranking,
    spectral_covariance, compress_via_projection, lstsq_threshold
)
from spectral_atomizer.context_atomizer import ContextAtomizer, AtomizedContext
from spectral_atomizer.semantic_cache import SpectralCache, SpectralCacheLayer, CachedEntry
from spectral_atomizer.prompt_distiller import PromptDistiller, DistilledPrompt
from spectral_atomizer.arc_spectral_encoder import ARCSpectralEncoder, ARCEncodingLevel
from spectral_atomizer.dream_fusion import DreamSpectralFusion, MemoryEntry, MemoryFusion, SpectralDream


def title(text: str):
    print(f"\n{'='*72}")
    print(f"  {text}")
    print(f"{'='*72}\n")


def section(text: str):
    print(f"\n{'─'*50}")
    print(f"  ▶ {text}")
    print(f"{'─'*50}")


# ============================================================
# Módulo 0: Core Matemático
# ============================================================
def demo_core():
    title("🧮 MÓDULO 0: CORE MATEMÁTICO (S^T S do OSCAR)")

    section("1. Matriz Hadamard (build_hadamard)")
    H4 = build_hadamard(4)
    print(f"Hadamard 4×4:\n{H4.round(3)}")

    section("2. Bit-Reversal Permutation")
    br = bit_reversal_perm(8)
    print(f"Bit-reversal permutation (d=8): {br.tolist()}")

    section("3. Análise Espectral S^T S")
    # Embeddings sintéticos com estrutura
    rng = np.random.RandomState(42)
    n_tokens, d_model = 20, 64
    embeddings = rng.randn(n_tokens, d_model)
    # Adicionar estrutura: tokens 0-5 são similares, 6-10 similares, etc.
    for i in range(n_tokens):
        group = i // 5
        embeddings[i] += np.ones(d_model) * (group * 0.5)

    ranking = spectral_importance_ranking(embeddings, variance_ratio=0.95)
    print(f"  Dimensões: {d_model}")
    print(f"  k para 95%% variância: {ranking['k']}")
    print(f"  Compressão possível: {ranking['compression_ratio']:.2f}x")
    print(f"  Top-5 autovalores: {ranking['eigenvalues'][:5].round(4)}")
    print(f"  Variância explicada: {ranking['cumulative_variance'][:5].round(4)}")

    section("4. Lloyd-Max Quantization (lstsq_threshold)")
    data = np.concatenate([
        np.random.randn(100) * 0.5 - 2,   # cluster 1
        np.random.randn(100) * 0.3,        # cluster 2
        np.random.randn(100) * 0.5 + 2,    # cluster 3
    ])
    levels, bounds = lstsq_threshold(data, n_levels=4)
    print(f"  Níveis ótimos (4 níveis): {levels.round(4)}")
    print(f"  Boundaries: {bounds.round(4)}")


# ============================================================
# Módulo 1: Atomização de Contexto
# ============================================================
def demo_context_atomizer():
    title("🧬 MÓDULO 1: ATOMIZAÇÃO DE CONTEXTO")

    section("Criando contexto de exemplo")
    tokens = ("O algoritmo OSCAR do FutureMLS-Lab alcançou resultados impressionantes "
              "na compressão do KV Cache. Ele usa rotação espectral offline para "
              "encontrar as dimensões que a atenção realmente consome. "
              "Isso permite comprimir o cache em ~7x sem perda significativa "
              "de precisão em benchmarks como GPQA e LiveCodeBench. "
              "Os experimentos foram realizados em Qwen3-8B e Qwen3-32B "
              "com resultados notáveis.").split()

    # Simular embeddings com estrutura
    rng = np.random.RandomState(42)
    n_tokens = len(tokens)
    d_model = 32
    embeddings = rng.randn(n_tokens, d_model)
    # Embeddings com estrutura: tokens centrais são mais informativos
    for i in range(n_tokens):
        embeddings[i] *= (1.0 + 0.5 * np.sin(i * np.pi / n_tokens))

    section("Aplicando ContextAtomizer")
    atomizer = ContextAtomizer(variance_ratio=0.90, method="variance_weighted")
    result = atomizer.atomize(tokens, embeddings)

    print(f"  Tokens originais: {len(tokens)}")
    print(f"  Tokens mantidos: {len(result.kept_indices)}")
    print(f"  Tokens removidos: {len(result.removed_indices)}")
    print(f"  Compressão: {result.compression_ratio:.2f}x")
    print(f"  Dimensões espectrais (k): {result.metadata.get('k_dims', 'N/A')}")
    print(f"  Variância explicada: {result.metadata.get('explained_variance', 0)*100:.1f}%")
    print(f"\n  Tokens mantidos: {' '.join(result.kept_tokens[:15])}...")
    print(f"  Tokens removidos: {' '.join(result.removed_tokens[:10])}...")

    section("Atomização com Sumarização")
    summary_result = atomizer.atomize_and_summarize(tokens, embeddings, n_clusters=3)
    if summary_result.get("summary"):
        for label, cluster_tokens in summary_result["summary"]["clusters"].items():
            print(f"  Cluster {label}: {' '.join(cluster_tokens[:5])}{'...' if len(cluster_tokens) > 5 else ''}")


# ============================================================
# Módulo 2: Cache Semântico Compacto
# ============================================================
def demo_semantic_cache():
    title("💾 MÓDULO 2: CACHE SEMÂNTICO COMPACTO")

    section("Criando cache com rotação espectral")
    rng = np.random.RandomState(42)
    n_samples = 100
    d_model = 128
    k = 16  # comprimir para 12.5%

    # Amostras de treino para ajustar rotação
    train_embs = rng.randn(n_samples, d_model)
    for i in range(n_samples):
        train_embs[i] += np.ones(d_model) * (i // 20)  # 5 grupos

    cache = SpectralCache(k=k, max_entries=50, similarity_threshold=0.75)
    cache.fit_rotation(train_embs)

    section("Armazenando entradas")
    entries_data = [
        ("resultado_oscar_qwen3_32b", 0),
        ("metodo_rotacao_espectral", 1),
        ("lloyd_max_quantization", 0),
        ("gpqa_benchmark_results", 2),
        ("compressao_kv_cache_7x", 1),
        ("futuro_mls_lab_paper", 2),
        ("atencao_ponderada_valor", 0),
        ("qwen3_4b_thinking", 2),
        ("hadamard_bit_reversal", 1),
        ("live_code_bench", 2),
    ]
    for key, group in entries_data:
        emb = train_embs[group * 20] + rng.randn(d_model) * 0.1
        status = cache.store(key, emb, context={"group": group, "source": group * 20})
        print(f"  [{status.upper()}] {key}")

    section("Consultando cache")
    # Query similar ao grupo "resultado_oscar_qwen3_32b"
    query = train_embs[0] + rng.randn(d_model) * 0.15
    entry, sim = cache.query(query)
    if entry:
        print(f"  ✅ HIT! Similaridade: {sim:.4f}")
        print(f"  → Entrada: {entry.key}")
        print(f"  → Contexto: {entry.context}")
    else:
        print(f"  ❌ MISS (melhor similaridade: {sim:.4f})")

    section("Estatísticas do cache")
    stats = cache.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")

    section("Teste: Cache Hierárquico (SpectralCacheLayer)")
    layer_cache = SpectralCacheLayer(d_model, levels=[d_model, d_model // 4, d_model // 16])
    layer_cache.fit_all(train_embs)
    entry_fast, sim_fast, level_used = layer_cache.query_fast(train_embs[0])
    print(f"  Query rápida: nível {level_used} usado")
    print(f"  Similaridade: {sim_fast:.4f}")


# ============================================================
# Módulo 3: Destilação de Prompt
# ============================================================
def demo_prompt_distiller():
    title("✂️ MÓDULO 3: DESTILAÇÃO DE PROMPT VIA S^T S")

    section("Prompt de exemplo (longo)")
    long_prompt = (
        "Por favor, analise o seguinte problema de compressão de KV Cache para grandes modelos de linguagem. "
        "O OSCAR é um método inovador que usa rotação espectral ciente de covariância offline para comprimir "
        "o cache de chaves e valores para apenas 2 bits por elemento. Isso resulta em aproximadamente 7 vezes "
        "de compressão comparado com o padrão BF16. Os experimentos mostram resultados impressionantes "
        "no Qwen3-32B onde a perda de precisão é de apenas 0.02 pontos percentuais. "
        "Além disso, no GLM-4.7-FP8 de 358 bilhões de parâmetros, o OSCAR supera a linha de base BF16. "
        "O método utiliza decomposição espectral das matrizes de covariância Q^T Q e V^T V ponderadas pela atenção. "
        "A rotação final é composta por autovetores, Hadamard e permutação bit-reversal. "
        "Gostaria de uma explicação detalhada do algoritmo e suas implicações para inferência de LLMs."
    )
    print(f"  Tamanho original: {len(long_prompt.split())} tokens")
    print(f"  Primeiros 80 chars: '{long_prompt[:80]}...'")

    section("Aplicando PromptDistiller")
    distiller = PromptDistiller(
        token_importance_threshold=0.15,
        variance_ratio=0.90,
        method="variance_weighted",
        min_tokens=5,
        max_removal_pct=0.50
    )
    result = distiller.distill(long_prompt)

    print(f"\n  Tokens originais: {len(result.tokens)}")
    print(f"  Tokens mantidos: {len(result.kept_indices)}")
    print(f"  Tokens removidos: {len(result.removed_indices)}")
    print(f"  Compressão de tokens: {result.token_compression_ratio:.2f}x")
    print(f"  Compressão total: {result.compression_ratio:.2f}x")
    print(f"  Dimensões espectrais (k): {result.metadata.get('k_dims', 'N/A')}")
    print(f"\n  📜 PROMPT DESTILADO:")
    print(f"  {result.distilled_prompt}")

    section("Destilação Iterativa (3 ciclos)")
    iterative = distiller.distill_iterative(long_prompt, max_iterations=3)
    print(f"  Iterações: {iterative.metadata.get('iterations', 1)}")
    print(f"  Compressão final: {iterative.compression_ratio:.2f}x")
    for r in iterative.metadata.get('iterative_results', []):
        print(f"    → compressão: {r['compression']:.2f}x, tokens: {r['tokens_kept']}")


# ============================================================
# Módulo 4: ARC Spectral Encoder
# ============================================================
def demo_arc_encoder():
    title("🧩 MÓDULO 4: EMBEDDING COMPACTO PARA ARC")

    section("Simulando embeddings de grids ARC")
    rng = np.random.RandomState(42)
    n_grids = 50
    d_model = 256  # embedding típico de encoder ARC

    # Embeddings com estrutura: grids que compartilham padrões
    embeddings = rng.randn(n_grids, d_model)
    pattern_centers = [
        np.ones(d_model) * 0.5,    # padrão 1: rotação
        np.ones(d_model) * (-0.3),  # padrão 2: flip
        np.ones(d_model) * 0.8,    # padrão 3: escala
        np.ones(d_model) * 0.0,    # padrão 4: translação
        np.ones(d_model) * 0.2,    # padrão 5: cor
    ]
    for i in range(n_grids):
        embeddings[i] += pattern_centers[i % 5] + rng.randn(d_model) * 0.1

    grid_ids = [f"train_{i}_grid" for i in range(n_grids)]

    section("Treinando ARCSpectralEncoder")
    encoder = ARCSpectralEncoder(variance_ratio=0.95, use_hadamard=True)
    profile = encoder.fit(embeddings, grid_ids)

    print(f"  Grids: {profile.n_grids}")
    print(f"  Dimensão original: {profile.d_model}")
    print(f"  Dimensão comprimida (k): {profile.optimal_k}")
    print(f"  Compressão: {profile.compression_ratio:.2f}x")

    section("Codificando grids")
    for i in range(3):
        encoded = encoder.encode(embeddings[i], grid_ids[i], ARCEncodingLevel.GRID)
        print(f"  📦 {encoded.grid_id}")
        print(f"     Original: {encoded.original_embedding.shape[0]} → Comprimido: {encoded.compressed_embedding.shape[0]}")
        print(f"     Compressão: {encoded.compression_ratio:.2f}x, Variância: {encoded.variance_preserved:.1%}")

    section("Busca de grids similares")
    query_emb = pattern_centers[0] + rng.randn(d_model) * 0.05
    similar = encoder.find_similar(query_emb, embeddings, grid_ids, top_k=3)
    for s in similar:
        print(f"  🔍 {s['id']} — similaridade: {s['similarity']:.4f}")

    section("Análise de Transformações (input → output)")
    in_embs = {}
    out_embs = {}
    for i in range(10):
        gid = f"trans_{i}"
        in_embs[gid] = embeddings[i]
        out_embs[gid] = embeddings[i] + pattern_centers[i % 5] * 0.5

    transform_analysis = encoder.analyze_transformations(in_embs, out_embs)
    print(f"  Transformações analisadas: {transform_analysis.get('n_transformations', 0)}")
    print(f"  Dimensões para 95%% da transformação: {transform_analysis.get('top_k_transform_dims', 0)}")
    print(f"  Coerência da transformação: {transform_analysis.get('transform_coherence', 0):.4f}")


# ============================================================
# Módulo 5: Dream Spectral Fusion
# ============================================================
def demo_dream_fusion():
    title("🌙 MÓDULO 5: FUSÃO ESPECTRAL DE MEMÓRIAS (DREAM)")

    section("Criando memórias de exemplo")
    memories = [
        MemoryEntry(
            id="oscar_paper_2026",
            text="OSCAR achieves 7x KV cache compression with near-lossless accuracy. Uses spectral rotation S^T S.",
            category="paper",
            importance=0.9
        ),
        MemoryEntry(
            id="qwen3_32b_results",
            text="Qwen3-32B with OSCAR: 74.17% on GPQA, only 0.02pp loss. Best INT2 method.",
            category="experiment",
            importance=0.85
        ),
        MemoryEntry(
            id="spectral_rotation_math",
            text="Rotation computed via R = U * H * P_br. Uses eigendecomposition of attention-weighted covariance.",
            category="algorithm",
            importance=0.95
        ),
        MemoryEntry(
            id="glm_47_fp8_results",
            text="GLM-4.7-FP8 (358B) with OSCAR: 78.16% vs 77.89% BF16. Surpasses baseline!",
            category="experiment",
            importance=0.88
        ),
        MemoryEntry(
            id="lloyd_max_detail",
            text="Lloyd-Max non-uniform quantization minimizes MSE for INT2. Optimized per-layer levels.",
            category="algorithm",
            importance=0.92
        ),
        MemoryEntry(
            id="qwen3_4b_thinking",
            text="Qwen3-4B-Thinking with OSCAR: 71.86% on GPQA. Small model, significant compression.",
            category="experiment",
            importance=0.75
        ),
        MemoryEntry(
            id="hadamard_bit_reversal",
            text="Hadamard matrix mixes dimensions uniformly. Bit-reversal sorts by frequency for optimal quantization.",
            category="algorithm",
            importance=0.8
        ),
        MemoryEntry(
            id="aime25_eval",
            text="AIME25 with OSCAR: 66.67% on Qwen3-8B, matching BF16. Outperforms KIVI and Kitty.",
            category="experiment",
            importance=0.82
        ),
        MemoryEntry(
            id="multimodal_ocr",
            text="OSCAR on Qwen3-VL-8B OCRBench: 854 vs 858 BF16. Best multimodal INT2 method.",
            category="experiment",
            importance=0.78
        ),
        MemoryEntry(
            id="rotation_zoo_hf",
            text="RotationZoo on HuggingFace provides pre-computed rotations for all supported models.",
            category="resource",
            importance=0.7
        ),
    ]
    print(f"  {len(memories)} memórias criadas")
    for mem in memories:
        print(f"    [{mem.category}] {mem.id}")

    section("Analisando memórias via espectro")
    dreamer = DreamSpectralFusion(
        variance_ratio=0.90,
        fusion_threshold=0.75,
        min_cluster_size=2
    )
    analysis = dreamer.analyze_memories(memories)
    print(f"  Clusters espectralmente detectados: {analysis.get('n_clusters', 0)}")
    print(f"  Dimensões espectrais (k): {analysis.get('spectral_k', 0)}")
    print(f"  Compressão possível: {analysis.get('compression_ratio', 1):.2f}x")
    print(f"  Coerência espectral: {analysis.get('coherence_score', 0):.4f}")

    print(f"\n  Padrões latentes:")
    for p in analysis.get("latent_patterns", [])[:5]:
        print(f"    Dimensão {p['rank']+1}: {p['variance_ratio']*100:.1f}% (acum: {p['cumulative']*100:.1f}%)")

    section("Fusão de memórias por cluster")
    fusions = dreamer.fuse_memories(memories)
    print(f"  Fusões realizadas: {len(fusions)}")
    for fus in fusions:
        sources = ', '.join(fus.source_ids)
        print(f"  🧬 Cluster {fus.cluster_label}: {len(fus.source_ids)} fontes")
        print(f"     Compressão: {fus.compression_ratio:.2f}x")
        print(f"     IDs: {sources[:50]}{'...' if len(sources) > 50 else ''}")

    section("Ciclo de sonho completo")
    dream = dreamer.dream_cycle(memories, n_cycles=2)
    print(f"  📊 Resultados do Sonho Espectral")
    print(f"  Memórias processadas: {dream.n_memories_processed}")
    print(f"  Fusões realizadas: {dream.n_fusions_performed}")
    print(f"  Compressão: {dream.compression_ratio:.2f}x")
    print(f"  Clusters: {len(dream.memory_clusters)}")
    print(f"\n  📝 Texto consolidado:\n")
    print(dream.consolidated_text[:300] + "..." if len(dream.consolidated_text) > 300 else dream.consolidated_text)


# ============================================================
# Sumário Final
# ============================================================
def demo_summary(all_results, quick=False):
    """Gera sumário final com resultados de todos os módulos."""
    title("📊 SUMÁRIO: SPECTRAL ATOMIZER PACKAGE")

    print(f"  Pacote: spectral_atomizer/")
    print(f"  Inspirado em: OSCAR (FutureMLS-Lab, arXiv: 2605.17757)")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Módulos implementados: 5/5")
    print()

    modules = [
        ("🧮 Core", "Matemática espectral: Hadamard, S^T S, Lloyd-Max", "core.py", "✅"),
        ("🧬 ContextAtomizer", "Atomização de contexto via ranking espectral", "context_atomizer.py", "✅"),
        ("💾 SpectralCache", "Cache semântico compacto (projeção top-k)", "semantic_cache.py", "✅"),
        ("✂️ PromptDistiller", "Destilação de prompt por S^T S", "prompt_distiller.py", "✅"),
        ("🧩 ARCSpectralEncoder", "Embedding compacto para ARC", "arc_spectral_encoder.py", "✅"),
        ("🌙 DreamSpectralFusion", "Fusão espectral de memórias (Dream)", "dream_fusion.py", "✅"),
    ]

    print(f"  {'Módulo':30s} {'Status':8s} {'Arquivo'}")
    print(f"  {'─'*70}")
    for name, desc, file_, status in modules:
        print(f"  {name:30s} {status:8s} {file_}")

    print()
    print(f"  ℹ️  Uso:")
    print(f"     from spectral_atomizer import ContextAtomizer")
    print(f"     from spectral_atomizer import SpectralCache")
    print(f"     from spectral_atomizer import PromptDistiller")
    print(f"     from spectral_atomizer import ARCSpectralEncoder")
    print(f"     from spectral_atomizer import DreamSpectralFusion")

    if not quick:
        print()
        print(f"  📖 Documentação completa:")
        print(f"     cat /a0/usr/workdir/spectral_atomizer/core.py")
        print(f"     python /a0/usr/workdir/spectral_atomizer/demo.py --help")


# ============================================================
# Main
# ============================================================
def main():
    args = sys.argv[1:]
    quick = "--quick" in args

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if "--module" in args:
        idx = args.index("--module")
        if idx + 1 < len(args):
            module_num = int(args[idx + 1])
            modules = {0: demo_core, 1: demo_context_atomizer, 2: demo_semantic_cache,
                       3: demo_prompt_distiller, 4: demo_arc_encoder, 5: demo_dream_fusion}
            if module_num in modules:
                modules[module_num]()
            else:
                print(f"Module {module_num} not found. Use 0-5.")
            return

    # Demo completa
    if not quick:
        demo_core()
        demo_context_atomizer()
        demo_semantic_cache()
        demo_prompt_distiller()
        demo_arc_encoder()
        demo_dream_fusion()
    else:
        # Quick: só módulos 3 e 5 (mais interessantes)
        demo_prompt_distiller()
        demo_arc_encoder()

    demo_summary({}, quick)


if __name__ == "__main__":
    main()
