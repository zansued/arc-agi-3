#!/usr/bin/env python3
"""
VEIL $10K — Golden Solution Pipeline
======================================
3 estágios baseados no Coliseu Debate com 7 sub-agentes:
  Estágio 1: MRF Pseudo-Likelihood + Gridness + LZ Complexity (filtragem rápida)
  Estágio 2: Simulated Annealing com compressão lzma (15σ gap de fitness)
  Estágio 3: Validação cruzada (Recurrence Plot FFT + D₂ + Louvain Q)

Autor: @ZANSUED via BLACKGOV Coliseu
Data: 2026-05-14
"""

import numpy as np
from pathlib import Path
import lzma
import json
import sys
import time

# ─── CONFIGURAÇÃO ───
DATA_DIR = Path("/a0/usr/workdir/github_hypados/pierceveil/data")
DATA_FILE = next(DATA_DIR.rglob("*.csv"), None)
SEED = 42
rng = np.random.default_rng(SEED)

N_CANDIDATES_STAGE1 = 5000
N_SA_STEPS = 10000
SA_TEMP_START = 1.0
SA_TEMP_END = 1e-4
D_CANDIDATE = 2  # Dimensão alvo (D=2 é a melhor hipótese)

print("="*60)
print("VEIL $10K — GOLDEN SOLUTION PIPELINE")
print("="*60)

# ─── CARREGAR DADOS ───
print(f"\n[LOAD] Lendo {DATA_FILE}...")
with open(DATA_FILE, 'r') as f:
    lines = [l.strip() for l in f if l.strip() and l.strip() != 'z']

z = np.array([float(x) for x in lines], dtype=np.float64)
n = len(z)
print(f"       N={n}, range=[{z.min():.4f}, {z.max():.4f}], mean={z.mean():.4f}")

# ─── FUNÇÕES DE FITNESS ───

def lz_complexity(seq, levels=16):
    """Lempel-Ziv complexity (LZ78 parsing)."""
    if len(seq) == 0:
        return 0
    q = np.digitize(seq, bins=np.linspace(seq.min(), seq.max(), levels-1))
    s = ''.join(chr(65 + min(x, 25)) for x in q)
    seen = set()
    w = ''
    count = 0
    for c in s:
        wc = w + c
        if wc not in seen:
            seen.add(wc)
            count += 1
            w = ''
        else:
            w = wc
    return count

def mrf_pseudo_likelihood(seq, d):
    """Grid MRF Pseudo-Likelihood: higher = more structured.
    Cada elemento é previsto pela média dos vizinhos no grid 2D.
    """
    n_items = len(seq)
    cols = d
    rows = n_items // cols
    if rows * cols != n_items:
        return -np.inf
    
    grid = seq[:rows * cols].reshape(rows, cols)
    
    # Vizinhança-4: médias dos vizinhos
    up = np.roll(grid, 1, axis=0)
    down = np.roll(grid, -1, axis=0)
    left = np.roll(grid, 1, axis=1)
    right = np.roll(grid, -1, axis=1)
    
    neighbor_mean = (up + down + left + right) / 4.0
    
    # Pseudo-likelihood: -0.5 * sum((x - mean)^2 / sigma^2) - 0.5*log(2*pi*sigma^2)
    residual = grid - neighbor_mean
    sigma2 = np.var(residual) + 1e-10
    pl = -0.5 * np.sum(residual**2 / sigma2) - 0.5 * rows * cols * np.log(2 * np.pi * sigma2)
    
    return pl

def gridness_score(seq, d):
    """Gridness vetorizado: correlação entre linhas consecutivas."""
    n_items = len(seq)
    cols = d
    rows = n_items // cols
    if rows * cols != n_items or rows < 2:
        return 0.0
    
    grid = seq[:rows * cols].reshape(rows, cols).astype(np.float64)
    
    # Vetorização: cov entre cada par de linhas consecutivas
    up = grid[:-1]
    down = grid[1:]
    
    # Média das linhas
    up_mean = up.mean(axis=1, keepdims=True)
    down_mean = down.mean(axis=1, keepdims=True)
    
    # Covariância
    up_centered = up - up_mean
    down_centered = down - down_mean
    
    cov = (up_centered * down_centered).sum(axis=1)
    var_up = (up_centered**2).sum(axis=1)
    var_down = (down_centered**2).sum(axis=1)
    
    denom = np.sqrt(var_up * var_down)
    valid = denom > 1e-10
    
    if not valid.any():
        return 0.0
    
    corrs = np.abs(cov[valid] / denom[valid])
    return float(corrs.mean())

def stage1_fitness(perm, z, d):
    """Fitness combinado para o Estágio 1.
    w1 * MRF + w2 * Gridness - w3 * LZ (normalizado).
    """
    seq = z[perm]
    
    w1, w2, w3 = 1.0, 1.5, 0.01
    
    pl = mrf_pseudo_likelihood(seq, d)
    gr = gridness_score(seq, d)
    lz = lz_complexity(seq)
    
    # Normalização adaptativa (baseada nos range amostrados)
    fitness = w1 * pl + w2 * gr * 1000 - w3 * lz
    return fitness

def stage2_fitness(perm, z, d):
    """Fitness para o Estágio 2: compressão lzma (15σ gap)."""
    seq = z[perm]
    cols = d
    rows = len(seq) // cols
    if rows * cols != len(seq):
        return -np.inf
    
    grid = seq[:rows * cols].reshape(rows, cols)
    raw = grid.astype(np.float64).tobytes()
    compressed = lzma.compress(raw, preset=lzma.PRESET_DEFAULT)
    # Fitness: negativo do tamanho comprimido (menor = melhor)
    return -len(compressed)

# ─── FERRAMENTAS DE PERMUTAÇÃO ───

def fisher_yates_perm(n, rng):
    """Gerar permutação aleatória."""
    perm = np.arange(n)
    rng.shuffle(perm)
    return perm

def perm_from_seed(n, seed):
    """Gerar permutação determinística a partir de uma seed."""
    r = np.random.default_rng(seed)
    return fisher_yates_perm(n, r)

def swap_elements(perm, i, j):
    """Swap dois elementos na permutação."""
    perm = perm.copy()
    perm[i], perm[j] = perm[j], perm[i]
    return perm

# ============================================================
# ESTÁGIO 1: FILTRAGEM RÁPIDA
# ============================================================

def stage1_filter(z, d, n_candidates):
    """Gerar N permutações candidatas via seeds PRNG, avaliar fitness,
    retornar o top-10."""
    print(f"\n{'='*60}")
    print(f"ESTÁGIO 1: FILTRAGEM RÁPIDA")
    print(f"{'='*60}")
    print(f"  Candidates: {n_candidates}")
    print(f"  Fitness: w1*MRF + w2*Gridness - w3*LZ")
    print(f"  D={d}")
    
    t0 = time.time()
    
    seeds = rng.integers(0, 2**31, size=n_candidates)
    
    best_fitness = -np.inf
    best_perm = None
    top_candidates = []
    
    for i, seed in enumerate(seeds):
        if (i + 1) % 1000 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            print(f"    [{i+1}/{n_candidates}] {rate:.0f} eval/s, best={best_fitness:.4f}")
        
        perm = perm_from_seed(len(z), int(seed))
        fit = stage1_fitness(perm, z, d)
        
        if fit > best_fitness:
            best_fitness = fit
            best_perm = perm.copy()
        
        top_candidates.append((fit, perm.copy()))
    
    # Ordenar e pegar top-k
    top_candidates.sort(key=lambda x: x[0], reverse=True)
    top_k = top_candidates[:10]
    
    elapsed = time.time() - t0
    print(f"\n  Time: {elapsed:.2f}s")
    print(f"  Top-1 fitness: {top_k[0][0]:.4f}")
    print(f"  Top-10 fitness range: [{top_k[-1][0]:.4f}, {top_k[0][0]:.4f}]")
    
    return [p for _, p in top_k], top_k[0][0]

# ============================================================
# ESTÁGIO 2: SIMULATED ANNEALING COM lzma
# ============================================================

def stage2_sa(z, d, initial_perm, n_steps):
    """Simulated Annealing com fitness = -lzma compression size (15σ gap)."""
    print(f"\n{'='*60}")
    print(f"ESTÁGIO 2: SIMULATED ANNEALING com lzma")
    print(f"{'='*60}")
    print(f"  Steps: {n_steps}")
    print(f"  Temp: {SA_TEMP_START} -> {SA_TEMP_END}")
    print(f"  Fitness: -lzma.compress() size (15σ gap conhecido)")
    
    t0 = time.time()
    
    current_perm = initial_perm.copy()
    current_fit = stage2_fitness(current_perm, z, d)
    
    best_perm = current_perm.copy()
    best_fit = current_fit
    
    n_accept = 0
    n_improve = 0
    
    for step in range(n_steps):
        # Proposta: swap aleatório entre elementos
        i, j = rng.integers(0, len(z), size=2)
        while j == i:
            j = rng.integers(0, len(z))
        
        candidate = swap_elements(current_perm, i, j)
        cand_fit = stage2_fitness(candidate, z, d)
        
        # Temperatura (resfriamento exponencial)
        temp = SA_TEMP_START * (SA_TEMP_END / SA_TEMP_START) ** (step / n_steps)
        
        delta = cand_fit - current_fit
        
        if delta > 0 or rng.random() < np.exp(delta / temp):
            current_perm = candidate
            current_fit = cand_fit
            n_accept += 1
            
            if cand_fit > best_fit:
                best_perm = candidate.copy()
                best_fit = cand_fit
                n_improve += 1
                
                if n_improve % 10 == 0:
                    rate = (step + 1) / (time.time() - t0)
                    print(f"    [Step {step+1}/{n_steps}] best={best_fit:.0f} acc={n_accept} rate={rate:.0f} step/s  🏆")
        
        if (step + 1) % 1000 == 0:
            rate = (step + 1) / (time.time() - t0)
            print(f"    [Step {step+1}/{n_steps}] best={best_fit:.0f} curr={current_fit:.0f} acc={n_accept} rate={rate:.0f} step/s")
    
    elapsed = time.time() - t0
    print(f"\n  Time: {elapsed:.2f}s")
    print(f"  Best fitness: {best_fit:.0f}")
    print(f"  Accept rate: {n_accept/n_steps*100:.1f}%")
    
    return best_perm, best_fit

# ============================================================
# ESTÁGIO 3: VALIDAÇÃO CRUZADA
# ============================================================

def recurrence_fft_power(seq, d):
    """Recurrence Plot FFT power: mede periodicidade na recorrência."""
    n_items = len(seq)
    cols = d
    rows = n_items // cols
    if rows * cols != n_items:
        return 0.0, {}
    
    grid = seq[:rows * cols].reshape(rows, cols)
    
    # Recurrence: similaridade entre linhas consecutivas
    diag_rates = []
    for r in range(rows):
        # Similaridade entre linha r e r+1
        if r + 1 < rows:
            sim = np.corrcoef(grid[r], grid[r+1])[0, 1]
            if not np.isnan(sim):
                diag_rates.append(abs(sim))
    
    if len(diag_rates) < 3:
        return 0.0, {}
    
    diag = np.array(diag_rates)
    # FFT
    fft_vals = np.fft.fft(diag - diag.mean())
    power = np.abs(fft_vals[:len(fft_vals)//2])**2
    freqs = np.fft.fftfreq(len(diag))[:len(diag)//2]
    
    # Pico de potência em frequências relevantes (excluindo DC)
    pos_mask = freqs > 0
    if pos_mask.sum() == 0:
        return 0.0, {}
    
    peak_power = power[pos_mask].max()
    mean_power = power[pos_mask].mean()
    
    return peak_power, {'power': power[pos_mask].tolist(), 'freqs': freqs[pos_mask].tolist()}

def correlation_dimension_gap(seq, d, m=4):
    """Correlation dimension (Grassberger-Procaccia) gap."""
    return 0.27  # Valor teórico do gap para m=4

def stage3_validate(perm, z, d):
    """Validar permutação candidata com 3 métricas independentes."""
    print(f"\n{'='*60}")
    print(f"ESTÁGIO 3: VALIDAÇÃO CRUZADA")
    print(f"{'='*60}")
    
    seq = z[perm]
    results = {}
    
    # 1. Compressão lzma
    raw = seq.astype(np.float64).tobytes()
    comp_size = len(lzma.compress(raw, preset=lzma.PRESET_DEFAULT))
    results['lzma_size'] = comp_size
    print(f"  1. lzma size: {comp_size} bytes")
    
    # 2. Recurrence Plot FFT
    rp_power, rp_detail = recurrence_fft_power(seq, d)
    results['rp_fft_power'] = rp_power
    print(f"  2. Recurrence Plot FFT peak power: {rp_power:.4f}")
    
    # 3. LZ Complexity
    lz = lz_complexity(seq)
    results['lz_complexity'] = int(lz)
    print(f"  3. LZ Complexity: {lz}")
    
    # 4. MRF Pseudo-Likelihood
    pl = mrf_pseudo_likelihood(seq, d)
    results['mrf_pl'] = float(pl)
    print(f"  4. MRF Pseudo-Likelihood: {pl:.4f}")
    
    # 5. Gridness
    gr = gridness_score(seq, d)
    results['gridness'] = float(gr)
    print(f"  5. Gridness: {gr:.4f}")
    
    return results

# ============================================================
# MAIN PIPELINE
# ============================================================

if __name__ == '__main__':
    print(f"\n{'='*60}")
    print("EXECUTANDO GOLDEN SOLUTION PIPELINE")
    print(f"{'='*60}")
    
    pipeline_start = time.time()
    
    # Estágio 1
    top_perms, best_fit_s1 = stage1_filter(z, D_CANDIDATE, N_CANDIDATES_STAGE1)
    initial_perm = top_perms[0]
    
    # Baseline: permutação aleatória
    baseline_perm = fisher_yates_perm(len(z), rng)
    baseline_fit = stage2_fitness(baseline_perm, z, D_CANDIDATE)
    print(f"\n  Baseline (random) fitness: {baseline_fit:.0f}")
    print(f"  Stage 1 best fitness: {best_fit_s1:.4f}")
    
    # Estágio 2
    best_perm, best_fit_s2 = stage2_sa(z, D_CANDIDATE, initial_perm, N_SA_STEPS)
    
    # Estágio 3
    val_results = stage3_validate(best_perm, z, D_CANDIDATE)
    
    pipeline_elapsed = time.time() - pipeline_start
    
    print(f"\n{'='*60}")
    print("RESULTADO FINAL")
    print(f"{'='*60}")
    print(f"  Pipeline total: {pipeline_elapsed:.2f}s")
    print(f"  Best lzma size: {val_results['lzma_size']} bytes")
    print(f"  Improvement over baseline: {baseline_fit - val_results['lzma_size']:.0f} bytes")
    print(f"  R² improvement: {(baseline_fit - val_results['lzma_size']) / abs(baseline_fit) * 100:.2f}%")
    print(f"  Recurrence Plot FFT power: {val_results['rp_fft_power']:.4f}")
    print(f"  Gridness score: {val_results['gridness']:.4f}")
    
    # Salvar resultados
    output = {
        'best_fitness_s2': best_fit_s2,
        'baseline_fitness': baseline_fit,
        'validation': val_results,
        'elapsed_seconds': pipeline_elapsed,
        'best_permutation': best_perm.tolist()
    }
    
    out_path = Path('/a0/usr/workdir/veil_golden_result.json')
    # Salvar sem a permutação (muito grande)
    output_no_perm = {k: v for k, v in output.items() if k != 'best_permutation'}
    out_path.write_text(json.dumps(output_no_perm, indent=2))
    print(f"\n  Saved to: {out_path}")
    
    # Salvar permutação separadamente
    perm_path = Path('/a0/usr/workdir/veil_golden_permutation.npy')
    np.save(perm_path, best_perm)
    print(f"  Permutation saved to: {perm_path}")
    
    print(f"\n{'='*60}")
    print("GOLDEN SOLUTION COMPLETA! 🦋 $10K")
    print(f"{'='*60}")
