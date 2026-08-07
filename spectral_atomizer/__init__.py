"""
OSCAR-inspired Spectral Atomizer Package

Adaptação do algoritmo de rotação espectral ciente de covariância (S^T S)
do OSCAR (FutureMLS-Lab) para:
  1. Atomização de Contexto
  2. Cache Semântico Compacto
  3. Destilação de Prompt (S^T S)
  4. Embedding Compacto para ARC
  5. Fusão Espectral de Memórias (Dream)

Fonte original: github.com/FutureMLS-Lab/OSCAR
Paper: arXiv 2605.17757
"""

from .core import (
    build_hadamard, bit_reversal_perm, make_br_perm_matrix,
    spectral_covariance, spectral_rotation, lstsq_threshold,
    spectral_importance_ranking, compress_via_projection,
    SparseRotation
)

from .context_atomizer import ContextAtomizer, AtomizedContext
from .semantic_cache import SpectralCache, CachedEntry
from .prompt_distiller import PromptDistiller, DistilledPrompt
from .arc_spectral_encoder import ARCSpectralEncoder
from .dream_fusion import DreamSpectralFusion, MemoryFusion

__version__ = "1.0.0"
__all__ = [
    "build_hadamard", "bit_reversal_perm", "make_br_perm_matrix",
    "spectral_covariance", "spectral_rotation", "lstsq_threshold",
    "spectral_importance_ranking", "compress_via_projection",
    "SparseRotation", "ContextAtomizer", "AtomizedContext",
    "SpectralCache", "CachedEntry", "PromptDistiller", "DistilledPrompt",
    "ARCSpectralEncoder", "DreamSpectralFusion", "MemoryFusion",
]
