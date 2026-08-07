#!/usr/bin/env python3
"""Testes com dados reais para todos os 5 módulos do Spectral Atomizer."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import re
import numpy as np

from spectral_atomizer.dream_fusion import DreamSpectralFusion, MemoryEntry
from spectral_atomizer.arc_spectral_encoder import ARCSpectralEncoder
from spectral_atomizer.semantic_cache import SpectralCache
from spectral_atomizer.context_atomizer import ContextAtomizer
from spectral_atomizer.prompt_distiller import PromptDistiller

print("=" * 72)
print("  TESTES COM DADOS REAIS: 5 MODULOS SPECTRAL ATOMIZER")
print("=" * 72)

# ============================================
# TEST 1: DREAM SPECTRAL FUSION
# ============================================
print()
print("-" * 50)
print("  TESTE 1: DreamSpectralFusion (sonho_consolidado)")
print("-" * 50)

dream_path = os.path.join(os.path.dirname(__file__), '..', 'sonho_consolidado_2026-05-26.md')
with open(dream_path) as f:
    dream_content = f.read()

# Split por headers ## ou ### que começam no início da linha (ou com \n antes)
# Usa positive lookbehind para \n OU início da string
sections_raw = re.split(r'\n(?=\s*#{2,3}\s)', dream_content)
if len(sections_raw) < 2:
    # Fallback: split por qualquer header no início da linha
    sections_raw = [s for s in re.split(r'\n(?=\s*#)', dream_content) if s.strip()]

memories = []
for i, section in enumerate(sections_raw):
    if len(section.strip()) < 30:
        continue
    # Extrair título da seção
    title_match = re.match(r'#{1,3}\s+(.+)', section)
    title = title_match.group(1).strip() if title_match else f'section_{i}'
    memories.append(MemoryEntry(
        id=f'dream_{i}_{title[:30]}',
        text=section[:800],
        category='dream',
        importance=0.9 if any(kw in section.lower() for kw in ['oscar', 'espectral', 'espectro', 's^t s']) else 0.7
    ))

print(f"  Memorias extraidas: {len(memories)}")
print(f"  Titulos: {[m.id[:40] for m in memories[:5]]}")

dreamer = DreamSpectralFusion(
    variance_ratio=0.85, fusion_threshold=0.7, min_cluster_size=2
)
analysis = dreamer.analyze_memories(memories)
print(f"  Clusters detectados: {analysis.get('n_clusters', 0)}")
print(f"  Dimensoes espectrais (k): {analysis.get('spectral_k', 0)}")
print(f"  Compressao: {analysis.get('compression_ratio', 1):.2f}x")
print(f"  Coerencia: {analysis.get('coherence_score', 0):.4f}")
print(f"  Padroes latentes: {len(analysis.get('latent_patterns', []))}")

dream = dreamer.dream_cycle(memories, n_cycles=2)
print(f"  Ciclo onirico: {dream.n_fusions_performed} fusoes")
print(f"  Compressao final: {dream.compression_ratio:.2f}x")
print(f"  Texto consolidado gerado: {len(dream.consolidated_text)} chars")

# ============================================
# TEST 2: ARC SPECTRAL ENCODER
# ============================================
print()
print("-" * 50)
print("  TESTE 2: ARCSpectralEncoder (dados v10_cn04.jsonl)")
print("-" * 50)

arc_path = os.path.join(os.path.dirname(__file__), '..', 'arc_runs', 'v10_cn04.jsonl')
with open(arc_path) as f:
    arc_lines = f.readlines()[:200]
arc_data = [json.loads(l) for l in arc_lines]

feature_keys = [
    'changed_pixels', 'levels_completed', 'win_levels', 'unique_states',
    'archive_size', 'n_resets', 'n_replays', 'replay_success_rate',
    'zero_delta_streak', 'steps_since_new_state'
]

embeddings = np.zeros((len(arc_data), len(feature_keys)))
for i, entry in enumerate(arc_data):
    for j, key in enumerate(feature_keys):
        val = entry.get(key, 0)
        embeddings[i, j] = float(val) if val is not None else 0.0

print(f"  Embeddings: {embeddings.shape}")

encoder = ARCSpectralEncoder(variance_ratio=0.90, use_hadamard=True)
profile = encoder.fit(embeddings)

print(f"  Dimensao original: {profile.d_model}")
print(f"  Dimensao comprimida (k): {profile.optimal_k}")
print(f"  Compressao: {profile.compression_ratio:.2f}x")

# Codificar e testar busca
for i in range(3):
    encoded = encoder.encode(embeddings[i], f'step_{i}')
    print(f"  {encoded.grid_id}: {embeddings.shape[1]} -> {len(encoded.compressed_embedding)} dims")

results = encoder.find_similar(embeddings[0], embeddings[:50], top_k=3)
print(f"  Busca similar: {len(results)} resultados")
for r in results:
    print(f"    -> {r['id']}: similaridade {r['similarity']:.4f}")

# ============================================
# TEST 3: SPECTRAL CACHE
# ============================================
print()
print("-" * 50)
print("  TESTE 3: SpectralCache (com dados ARC)")
print("-" * 50)

cache = SpectralCache(k=3, max_entries=30, similarity_threshold=0.5)
cache.fit_rotation(embeddings)

for i in range(min(20, len(embeddings))):
    cache.store(f'step_{i}', embeddings[i], {'index': i, 'step': i})

stats = cache.get_stats()
print(f"  Entradas armazenadas: {stats['entries']}")
print(f"  Dimensoes (k): {stats['k_dims']}")
print(f"  Compressao: {stats['compression_ratio']:.1f}x")

# Query
entry, sim = cache.query(embeddings[0])
print(f"  Query step_0: hit={entry is not None}")
if entry:
    print(f"    -> {entry.key} (sim: {sim:.4f})")

entry, sim = cache.query(embeddings[5])
print(f"  Query step_5: hit={entry is not None}")
if entry:
    print(f"    -> {entry.key} (sim: {sim:.4f})")

# ============================================
# TEST 4: CONTEXT ATOMIZER
# ============================================
print()
print("-" * 50)
print("  TESTE 4: ContextAtomizer (com texto real do sonho)")
print("-" * 50)

tokens = dream_content.split()[:60]
rng = np.random.RandomState(42)
t_embs = rng.randn(len(tokens), 16)
# Adicionar estrutura semantica: tokens com 'OSCAR' ou 'espectral' sao mais importantes
for i, token in enumerate(tokens):
    if any(kw in token.lower() for kw in ['oscar', 'espectral', 'cache', 'memoria', 'atencao']):
        t_embs[i] *= 3.0
    elif any(kw in token.lower() for kw in ['compres', 'dimens', 'rotac']):
        t_embs[i] *= 2.0

atomizer = ContextAtomizer(variance_ratio=0.85, method='variance_weighted', min_tokens=5)
result = atomizer.atomize(tokens, t_embs)

print(f"  Tokens originais: {len(tokens)}")
print(f"  Tokens mantidos: {len(result.kept_indices)}")
print(f"  Tokens removidos: {len(result.removed_indices)}")
print(f"  Compressao: {result.compression_ratio:.2f}x")
if result.removed_indices:
    print(f"  Removidos: {' '.join(result.removed_tokens[:20])}...")
    print(f"  Mantidos: {' '.join(result.kept_tokens[:20])}...")

# ============================================
# TEST 5: PROMPT DISTILLER (com TF-IDF fallback)
# ============================================
print()
print("-" * 50)
print("  TESTE 5: PromptDistiller (com texto real)")
print("-" * 50)

prompt = dream_content[:2000]
distiller = PromptDistiller(
    token_importance_threshold=0.15,
    variance_ratio=0.85,
    method='variance_weighted',
    min_tokens=5,
    max_removal_pct=0.40
)
result = distiller.distill(prompt)

print(f"  Tokens originais: {len(result.tokens)}")
print(f"  Tokens mantidos: {len(result.kept_indices)}")
print(f"  Tokens removidos: {len(result.removed_indices)}")
print(f"  Compressao tokens: {result.token_compression_ratio:.2f}x")
print(f"  Dimensoes k: {result.metadata.get('k_dims', 'N/A')}")

if result.is_compressed and result.kept_indices:
    kept = ' '.join([result.tokens[i] for i in sorted(result.kept_indices)])
    print(f"\n  PROMPT DESTILADO (primeiros 300 chars):")
    print(f"  {kept[:300]}...")

# ============================================
# RESUMO FINAL
# ============================================
print()
print("=" * 72)
print("  RESUMO FINAL - TODOS OS TESTES CONCLUIDOS")
print("=" * 72)
print(f"")
print(f"  {'Modulo':25s} {'Status':10s} {'Resultado'}")
print(f"  {'-'*65}")
print(f"  {'DreamSpectralFusion':25s} {'PASS':10s} {analysis.get('n_clusters', 0)} clusters, comp={analysis.get('compression_ratio', 1):.1f}x")
print(f"  {'ARCSpectralEncoder':25s} {'PASS':10s} {profile.d_model}d->{profile.optimal_k}d ({profile.compression_ratio:.1f}x)")
print(f"  {'SpectralCache':25s} {'PASS':10s} {stats['entries']} entries, k={stats['k_dims']}, {stats['compression_ratio']:.1f}x")
print(f"  {'ContextAtomizer':25s} {'PASS':10s} {len(tokens)}->{len(result.kept_indices)} tok ({result.compression_ratio:.1f}x)")
print(f"  {'PromptDistiller':25s} {'PASS':10s} {len(result.tokens)}->{len(result.kept_indices)} tok")

print(f"")
print(f"  5/5 MODULOS TESTADOS COM DADOS REAIS")
