# **VEILBreaker: Mapping Latent Shadows**

## **A deterministic 10D geometric basis for partial signal recovery in VEIL Track 1**

**Author:** @ZANSUED / BLACKGOV  
**Method:** VEILBreaker v1  
**Promoted candidate:** v5b-LITE D=10  
**Promotion date:** 2026-05-19  
**Kernel:** `veil-v5b-fixed-d10` (https://www.kaggle.com/code/guilhermezaninides/veil-v5b-fixed-d10)  

---

## **Abstract**

This write-up presents the final investigation behind **VEILBreaker**, a deterministic partial-signal recovery method developed for the **Pierce the VEIL: Hack It and Crack It Simulation** competition.

The challenge provides only **4,096 scalar observations**: Z ∈ R^(4096 × 1). The original records, dimensionality, feature names, feature types, feature semantics, ordering, encoder, decoder, model, and transformation process are hidden.

The final conclusion is intentionally cautious:

> I do not claim full reconstruction of the hidden original table. I claim that the public scalar stream is not structureless. It preserves partial geometric signal.

The final method, **VEILBreaker v1**, corresponds to the promoted **v5b-LITE D=10** candidate. It maps each scalar latent into a **10-dimensional deterministic geometric basis** designed to preserve rank order, local density, nonlinear curvature, compressed magnitude, and positive-tail asymmetry.

The final thesis is:

> **The table remains hidden. The geometry does not disappear completely.**

---

# **1. What the challenge gives us**

The competition is not a conventional supervised learning task. There are no labels, no training/test split, no known target variable, no known feature space.

Instead, we are given a scalar latent stream and asked whether the original records can be reconstructed from it.

Formally:

```text
Observed: Z ∈ R^(N × 1)
Hidden:   X ∈ R^(N × D)
Unknown:  D, encoder, decoder, feature semantics, scale, distribution, task
Goal:     produce X_hat ∈ R^(N × D_hat)
```

A valid full reconstruction would require correct row count, hidden dimensionality, row-wise alignment, finite output, input dependence, generalization, and meaningful accuracy.

Central question: *Does a single scalar value per row contain enough information to recover an unknown high-dimensional record?*

---

# **2. The central constraint: non-identifiability**

Let Z = E(X) where X is unknown, E is unknown, Z is observed. Many incompatible hidden datasets may produce the same observed scalar stream. This is a **non-identifiability problem**.

The project therefore moved from "Recover the original table" to **"Map the recoverable structure left inside the scalar representation."**

---

# **3. The first temptation: direct reconstruction**

The baseline `X_hat = np.column_stack([z, z])` is deterministic and row-aligned but conceptually weak — it repackages the only information already given. The first major pivot: **Statistical structure in Z is not the same as record-level reconstruction of X.**

---

# **4. The chaotic hypothesis**

Before the final method, I explored Takens' embedding theorem, delay-coordinate reconstruction, Lyapunov instability, and manifold unfolding. This depended on row order being meaningful — which could not be assumed. Order-dependent methods are dangerous unless row order is part of the data-generating process. The strategy shifted to **permutation-equivariant** methods.

---

# **5. The revelation: random controls and normalization discipline**

Testing against random controls, shuffled sequences, Gaussian nulls, and permutation tests revealed that some early metrics were too optimistic and a sigma issue inflated signal. The corrected standard: extract recoverable geometric signal without claiming exact inversion.

---

# **6. Final audit of the scalar latents**

```text
N = 4,096, mean = 0.1026, std = 2.1501
Data source: /kaggle/input/competitions/pierce-the-veil/intercepted_data.csv

Wasserstein-1 signature:
  Real W1: 0.8850  |  Null W1: 0.0231  |  Ratio: 38.36×
```

This is a **distributional signature** — it shows measurable structure relative to Gaussian reference. Full reconstruction is not empirically justified from the public scalar stream alone, but partial signal remains measurable.

---

# **7. Figure 1: Public latent distribution**

| Statistic | Value |
|:----------|:-----:|
| N | 4,096 |
| Mean | 0.1026 |
| Std | 2.1501 |
| Range | ≈ [-7, +10] |

*Figure available in kernel output → `fig1_latent_distribution.png`. Shows empirical distribution of the intercepted scalar latent stream — measurable center, spread, tail behavior.*

---

# **8. Reversing the compression argument**

The usual privacy defense is: dimensionality reduction destroys invertibility. But if the scalar representation remains useful for a downstream task, some task-aligned signal must survive. VEILBreaker asks: *What structural information survives in the exposed scalar stream?*

---

# **9. Synthetic SDR demonstration**

```text
Synthetic X dimension: 10
Task prediction from scalar Z: AUC ≈ 0.998, accuracy ≈ 96.8%
Full X reconstruction from Z:   R² ≈ 0.099
```

A scalar can be highly useful for prediction while still being insufficient for full reconstruction.

---

# **10. From D4 to VEILBreaker v1**

```text
D4 → D8 → v4 → v5a → v5b → v5b-LITE (promoted)
```

## **10.1 D4: the first disciplined partial extractor**

Four features: `z_norm`, `rank` (tie-aware), `logit_rank`, `density`. Key property: reconstruct(PZ) ≈ P·reconstruct(Z). Permutation-equivariant.

## **10.2 v4: stable geometric baseline**

Eight features: normalized latent, signed square curvature, sin, cos, tanh, centered rank, density proxy, clipped logistic. Combined element-wise nonlinear transforms with batch-level permutation-equivariant transforms.

## **10.3 v5b-LITE: the promoted compact candidate**

v5b-LITE = v4 core basis + `f_log_abs` + `f_exp_pos` → D_hat = 10.

---

# **11. VEILBreaker v1 pipeline**

```text
Z (N×1) → Sanitization → Z-score normalization → V4 core basis (8) → V5b-LITE additions (2) → 10D basis → Contract tests + Plots
```

Does NOT use hidden labels, row-order artifacts, random guessing, hardcoded outputs, or semantic decoding.

---

# **12. Final algorithm**

```python
def reconstruct(public_latents, hidden_latents=None, metadata=None):
    z = sanitize_latents(public_latents)
    zn = normalized_latents(z)

    f_z = zn
    f_z2 = np.sign(zn) * np.abs(zn) ** 2
    f_sin = np.sin(zn)
    f_cos = np.cos(zn)
    f_tanh = np.tanh(zn)
    f_rank = compute_centered_rank(z)
    f_density = compute_density_proxy(z)
    f_logit = 1.0 / (1.0 + np.exp(-np.clip(zn, -10.0, 10.0)))

    # V5b-LITE additions (ablation-selected)
    f_log_abs = standardize(np.log1p(np.abs(zn)))
    f_exp_pos = standardize(np.where(zn > 0, np.exp(np.clip(zn, -3.0, 3.0)), 0.0))

    return np.column_stack([
        f_z, f_z2, f_sin, f_cos, f_tanh,
        f_rank, f_density, f_logit,
        f_log_abs, f_exp_pos
    ]).astype(np.float64)
```

---

# **13. Why each feature exists**

| # | Feature | Purpose | Interpretation |
|:-:|:--------|:--------|:---------------|
| 1 | `f_z` | Normalized scalar position | Preserves standardized location |
| 2 | `f_z2` | Signed curvature | Expands nonlinear magnitude, preserves sign |
| 3 | `f_sin` | Periodic nonlinear projection | Tests curved latent geometry |
| 4 | `f_cos` | Complementary projection | Adds phase-like variation |
| 5 | `f_tanh` | Saturated response | Controls extremes, preserves direction |
| 6 | `f_rank` | Tie-aware global order | Ordinal leakage (robust to monotone transforms) |
| 7 | `f_density` | Local spacing proxy | Concentration and gaps |
| 8 | `f_logit` | Bounded score-like projection | Soft score from scalar location |
| 9 | `f_log_abs` | **Compressed magnitude** | Radial distance from center ← BEST feature |
| 10 | `f_exp_pos` | **Positive-tail asymmetry** | One-sided tail behavior |

---

# **14. Why rank and density matter**

Rank is robust to monotone transformations. If the encoder distorted scale but preserved order, rank still captures ordinal leakage. Density captures local concentration — topology reduces to order, gaps, density discontinuities, and tails in 1D.

---

# **15. The ablation study**

```text
KEEP:    f_log_abs (BEST), f_exp_pos (asymmetry)
REMOVE:  f_quantile (redundant with f_rank, r=1.0000)
         f_erf      (harmful, removal improves rank by +0.0046)
```

The D=10 compact basis (eff_rank=4.6649) outperformed D=12 (eff_rank=3.9075). More dimensions ≠ better representation. Better feature selection does.

---

# **16. Figure 2: Singular value spectrum**

| σ₁ | σ₂ | σ₃ | σ₄ | σ₅ | σ₆ | σ₇ | σ₈ | σ₉ | σ₁₀ |
|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 161.02 | 85.40 | 68.10 | 47.75 | 17.57 | 6.08 | 2.45 | 1.82 | 0.92 | 0.38 |

Effective rank: **4.6649** — the basis does not collapse, preserving multiple independent directions of variation.

*Figure available in kernel output → `fig2_singular_spectrum.png`*

---

# **17. Figure 3: Feature correlation matrix**

Correlation matrix (10×10) — all pairwise |r| < 0.85, most < 0.30. Features are predominantly non-redundant.

*Figure available in kernel output → `fig3_feature_correlation.png`. Shows low inter-feature redundancy, validating the ablation decisions.*

---

# **18. Contract tests**

```text
 1. ✅ shape check
 2. ✅ finite output
 3. ✅ determinism
 4. ✅ input dependence
 5. ✅ permutation equivariance (10/10 seeds)
 6. ✅ N=0 handling
 7. ✅ N=1 handling
 8. ✅ tie consistency (identical inputs → identical outputs)
 9. ✅ NaN/Inf handling
10. ✅ effective rank > 1 (4.6649)
11. ✅ entropy > 0 (1.5401)

Results: 11/11 PASSED | 10/10 Permutation tests
```

---

# **19. Final v5b-LITE audit results**

| Metric | Result | Δ vs v4 |
|:-------|:------:|:-------:|
| N | 4,096 (real data) | ✅ |
| Feature dimension | 10 | — |
| Contract tests | **11/11** ✅ | — |
| Permutation tests | **10/10** ✅ | — |
| Effective rank | **4.6649** | **+32%** (v4: 3.5274) |
| Entropy | 1.5401 | — |
| W1 Real | **0.8850** | — |
| W1 Null | 0.0231 | — |
| **W1 Ratio** | **38.36×** | 🔥 |
| SRMSE D=10 | 2.1461 | — |
| SRMSE D=16 | 2.1437 | — |
| SRMSE D=132 | 2.0990 | — |
| Submission CSV | 548,669 bytes | — |

**Effective rank evolution:** v4=3.5274 → v5b full=3.9075 → v5b-LITE=**4.6649**

---

# **20. Figure 4: Wasserstein-1 signature**

| Metric | Real Latents | Gaussian Null | **Ratio** |
|:-------|:------------:|:-------------:|:---------:|
| Wasserstein-1 | 0.8850 | 0.0231 | **38.36×** |

*Figure available in kernel output → `fig4_wasserstein_signature.png`. The Wasserstein-1 distance of the real latents is 38.36× greater than Gaussian noise — a strong distributional signature.*

This is not a reconstruction metric. It is evidence that the scalar stream deviates measurably from a Gaussian null.

---

# **21. Figure 5: SRMSE floor analysis**

| Dimensionality | SRMSE Floor |
|:--------------:|:----------:|
| D=10 | 2.1461 |
| D=16 | 2.1437 |
| D=132 | 2.0990 |

The small movement across D values reinforces that changing output dimension alone does not solve the inverse problem.

*Figure available in kernel output → `fig5_srmse_floor.png`*

---

# **22. Effective rank and entropy**

```python
_, s, _ = np.linalg.svd(X, full_matrices=False)
sn = s / (s.sum() + 1e-10)
entropy = -np.sum(sn * np.log(sn + 1e-10))
effective_rank = np.exp(entropy)
```

Effective rank measures whether the basis collapses — not reconstruction accuracy. VEILBreaker produces a richer representation without proving recovery of X.

---

# **23. Why D=10 is not claimed as the hidden dimensionality**

D_hat = 10 is the dimensionality of the engineered geometric basis, not a claim about the hidden source. True source dimensionality remains unknown.

---

# **24. What VEILBreaker discovered**

The scalar stream preserves measurable structure in: global order, local density, scalar spacing, nonlinear curvature, radial magnitude, positive-tail asymmetry, and spectral diversity after deterministic expansion. A representation can fail to reveal full records while still leaking partial structure.

---

# **25. What VEILBreaker did not discover**

This method does NOT claim: recovery of original records, feature names, feature semantics, true dimensionality, the encoder, the downstream task, proof of impossibility, or proof that VEIL is broken.

---

# **26. Full reconstruction vs partial signal**

| Full reconstruction | Partial signal recovery |
|:-------------------|:-----------------------|
| X_hat ≈ X with correct D, alignment, values, structure, generalization | X_hat = g(Z) extracting interpretable, row-wise, permutation-equivariant proxies |

VEILBreaker is in the second category.

---

# **27. Why this matters**

In privacy-preserving ML, the question is not only "Can the attacker reconstruct the entire dataset?" but also "What can the attacker still infer?" Even without exact inversion, a scalar latent may leak ordering, outliers, density, score-like behavior, tails, and neighborhoods.

---

# **28. The map is not the territory**

The original dataset is the object; the scalar latent stream is the shadow. VEILBreaker does not reconstruct the object — it **maps the shadow**. The generated 10D matrix is not the hidden table; it is a map of recoverable latent geometry.

---

# **29. Reproducibility**

```text
Artifacts produced:
  /kaggle/working/reconstruction_output.npy
  /kaggle/working/submission.csv
  /kaggle/working/submission_summary.json
  /kaggle/working/figures/fig1-5_latent_distribution.png

Method is fully deterministic. Null diagnostics use random sampling — fix random seed for exact reproduction.
```

---

# **30. Track positioning**

Aligned with: Attack Strategy & Analysis, Partial Signal Recovery, Best Technical Write-Up. Not primarily a Full Reconstruction Grand Prize claim.

Contribution: rejected hypotheses, empirical diagnostics, non-identifiability framing, partial signal extraction, ablation study, deterministic final algorithm, clear limitations, reproducible methodology.

---

# **31. Final conclusion**

The project began with chaotic reconstruction hopes, passed through delay embeddings and Lyapunov intuition, then corrected course: row order may not be meaningful, some metrics were inflated, distributional structure is not reconstruction.

The final result is VEILBreaker v1 — a deterministic, tie-aware, permutation-equivariant 10D geometric basis expansion.

It does not break the entire VEIL. It does not reconstruct the original table. **But it shows that the scalar stream still carries recoverable structure.**

> **VEIL may hide the table, but it does not necessarily erase its geometry.**

And in privacy analysis, geometry is already signal.

---

## **Short summary**

VEILBreaker v1 is a deterministic, tie-aware, permutation-equivariant 10D geometric basis expansion for VEIL's public 1D latent stream. It documents the full journey from chaotic reconstruction attempts to controlled partial signal recovery, including random controls, normalization correction, feature evolution, ablation, 11/11 contract tests, Wasserstein-1 signature (38.36× ratio), SRMSE floor analysis, and evidence that rank, density, curvature, magnitude, and tail asymmetry remain measurable.

---

## **Tags**

`inverse-problem` `privacy` `reconstruction-attack` `partial-signal-recovery` `latent-space` `geometric-basis` `permutation-equivariance` `ablation-study` `non-identifiability` `red-team-analysis` `wasserstein-distance` `effective-rank` `spectral-diagnostics`
