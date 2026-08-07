# arc_spectral_encoder.py — Módulo 4: Embedding Compacto para ARC via Espectro
#
# Aplica rotação espectral (inspirada no OSCAR) para comprimir
# as representações internas do modelo ARC (Abstraction and Reasoning
# Corpus). Cada grid de 30x30 é codificado em um embedding de alta
# dimensionalidade; a análise espectral encontra as dimensões que
# realmente carregam informação de raciocínio.
#
# Inspirado no OSCAR:
#   - compute_sst() → encontra dimensões relevantes para atenção
#   - Adaptação: embedding_analysis() → encontra dimensões relevantes
#     para raciocínio ARC (transformações, objetos, padrões)
#
# ARC: https://github.com/fchollet/ARC-AGI
# PierceVeil: https://kaggle.com/competitions/arc-prize-2024

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Callable
from enum import Enum
from .core import (
    spectral_importance_ranking, compress_via_projection,
    spectral_covariance, spectral_rotation, SparseRotation
)


class ARCEncodingLevel(Enum):
    """Níveis de codificação ARC."""
    TOKEN = "token"           # Cada célula do grid
    PATCH = "patch"           # Patches (ex: 5x5)
    GRID = "grid"             # Grid completo
    OBJECT = "object"         # Objetos segmentados
    TRANSFORMATION = "transform"  # Transformações entre grids


@dataclass
class ARCGridEmbedding:
    """Embedding de um grid ARC."""
    grid_id: str                             # ID do grid (ex: "train_0")
    grid_shape: Tuple[int, int]              # (H, W)
    original_embedding: np.ndarray           # (d_model,) — embedding original
    compressed_embedding: np.ndarray         # (k,) — embedding comprimido
    level: ARCEncodingLevel                  # nível de codificação
    compression_ratio: float = 1.0           # d_model / k
    variance_preserved: float = 0.95         # variância preservada
    eigenvalues: Optional[np.ndarray] = None


@dataclass
class ARCDatasetProfile:
    """Perfil espectral de um conjunto de grids ARC."""
    n_grids: int
    d_model: int
    optimal_k: int
    compression_ratio: float
    explained_variance: np.ndarray           # variância acumulada
    eigenvalues: np.ndarray                  # autovalores
    eigenvectors: np.ndarray                 # autovetores (rotação)
    rotation_matrix: Optional[np.ndarray] = None


class ARCSpectralEncoder:
    """
    Encoder espectral para grids ARC.

    Pipeline:
      1. Recebe embeddings de grids ARC (token-level, patch-level, ou grid-level)
      2. Calcula matriz de covariância (S^T S inspirado no OSCAR)
      3. Decompõe em autovetores → rotação espectral
      4. Projeta no subespaço top-k
      5. Fornece reconstrução e busca

    Aplicações:
      - Comprimir embeddings do encoder neural (ex: 512 → 32 dimensões)
      - Encontrar grids similares no espaço espectral
      - Identificar transformações latentes (padrões de raciocínio)
      - Detectar anomalias/outliers no raciocínio do modelo
    """

    def __init__(
        self,
        variance_ratio: float = 0.95,
        use_hadamard: bool = True,
        k_fixed: Optional[int] = None
    ):
        """
        Args:
            variance_ratio: fração da variância a preservar
            use_hadamard: usar rotação Hadamard + bit-reversal
            k_fixed: número fixo de dimensões (anula variance_ratio)
        """
        self.variance_ratio = variance_ratio
        self.use_hadamard = use_hadamard
        self.k_fixed = k_fixed
        self.profile: Optional[ARCDatasetProfile] = None
        self._rotation_matrix: Optional[np.ndarray] = None

    def fit(
        self,
        embeddings: np.ndarray,
        grid_ids: Optional[List[str]] = None
    ) -> ARCDatasetProfile:
        """
        Treina a rotação espectral a partir de embeddings ARC.

        Args:
            embeddings: (n_grids, d_model) — embeddings dos grids
            grid_ids: IDs opcionais

        Returns:
            ARCDatasetProfile
        """
        n_grids, d_model = embeddings.shape

        # Análise espectral
        ranking = spectral_importance_ranking(
            embeddings,
            method="unweighted",
            variance_ratio=self.variance_ratio
        )

        k = self.k_fixed if self.k_fixed is not None else int(ranking["k"])

        # Rotação espectral
        cov = spectral_covariance(embeddings)
        R_full, eigvals = spectral_rotation(
            cov, use_hadamard=self.use_hadamard
        )
        self._rotation_matrix = R_full[:, :k]

        compression_ratio = d_model / max(k, 1)

        self.profile = ARCDatasetProfile(
            n_grids=n_grids,
            d_model=d_model,
            optimal_k=k,
            compression_ratio=compression_ratio,
            explained_variance=ranking["cumulative_variance"],
            eigenvalues=ranking["eigenvalues"],
            eigenvectors=ranking["eigenvectors"][:, :k],
            rotation_matrix=self._rotation_matrix
        )

        return self.profile

    def encode(
        self,
        embedding: np.ndarray,
        grid_id: str = "",
        level: ARCEncodingLevel = ARCEncodingLevel.GRID
    ) -> ARCGridEmbedding:
        """
        Codifica um embedding ARC no espaço comprimido.

        Args:
            embedding: (d_model,) — embedding original
            grid_id: identificador
            level: nível de codificação

        Returns:
            ARCGridEmbedding
        """
        d_model = embedding.shape[-1]

        if self._rotation_matrix is not None:
            compressed = embedding @ self._rotation_matrix
            k = self._rotation_matrix.shape[1]
            var_preserved = float(
                self.profile.explained_variance[min(k - 1, len(self.profile.explained_variance) - 1)]
                if self.profile is not None else self.variance_ratio
            )
        else:
            # Fallback: PCA via SVD no embedding único
            compressed = embedding[:min(32, d_model)]
            k = len(compressed)
            var_preserved = 0.0

        return ARCGridEmbedding(
            grid_id=grid_id,
            grid_shape=(0, 0),  # preenchido externamente
            original_embedding=embedding,
            compressed_embedding=compressed,
            level=level,
            compression_ratio=d_model / max(k, 1),
            variance_preserved=var_preserved
        )

    def decode(self, compressed: np.ndarray) -> np.ndarray:
        """
        Reconstrói embedding original a partir do comprimido.
        (Perda = (1 - variance_preserved) * 100%%)
        """
        if self._rotation_matrix is not None:
            return compressed @ self._rotation_matrix.T
        return compressed

    def find_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray,
        candidate_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Encontra grids similares no espaço espectral.

        Args:
            query_embedding: (d_model,)
            candidate_embeddings: (n_candidates, d_model)
            candidate_ids: identificadores
            top_k: número de resultados

        Returns:
            [{"id", "similarity", "compressed_query", "compressed_candidate"}]
        """
        q = self.encode(query_embedding, "query").compressed_embedding
        q_norm = q / (np.linalg.norm(q) + 1e-12)

        candidates_proj = np.array([
            self.encode(c, str(i)).compressed_embedding
            for i, c in enumerate(candidate_embeddings)
        ])
        cand_norms = np.linalg.norm(candidates_proj, axis=1, keepdims=True) + 1e-12
        candidates_norm = candidates_proj / cand_norms

        similarities = candidates_norm @ q_norm

        top_idx = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_idx:
            results.append({
                "id": candidate_ids[idx] if candidate_ids else str(idx),
                "similarity": float(similarities[idx]),
                "compressed_query": q,
                "compressed_candidate": candidates_proj[idx]
            })

        return results

    def analyze_transformations(
        self,
        input_embeddings: Dict[str, np.ndarray],
        output_embeddings: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Analisa transformações (input → output) no espaço espectral.

        Identifica:
          - Quais dimensões do espectro mudam mais com a transformação
          - Se a transformação é rotacional, translacional, ou de escala
          - Padrões de raciocínio consistentes

        Args:
            input_embeddings: {grid_id: embedding}
            output_embeddings: {grid_id: embedding}

        Returns:
            dict com análise
        """
        common_ids = set(input_embeddings.keys()) & set(output_embeddings.keys())
        if not common_ids:
            return {"error": "No common grid IDs"}

        deltas = []
        for gid in common_ids:
            inp = input_embeddings[gid]
            out = output_embeddings[gid]
            delta = out - inp
            deltas.append(delta)

        deltas = np.array(deltas)

        # Análise espectral dos deltas
        cov_delta = spectral_covariance(deltas)
        delta_eigvals, delta_eigvecs = np.linalg.eigh(cov_delta)
        idx = np.argsort(delta_eigvals)[::-1]
        delta_eigvals = delta_eigvals[idx]
        delta_eigvecs = delta_eigvecs[:, idx]

        explained = delta_eigvals / (delta_eigvals.sum() + 1e-12)
        cumulative = np.cumsum(explained)

        # Quais dimensões 'carregam' a transformação?
        top_k = int(np.searchsorted(cumulative, 0.95) + 1)

        return {
            "n_transformations": len(common_ids),
            "delta_eigenvalues": delta_eigvals,
            "delta_eigenvectors": delta_eigvecs,
            "top_k_transform_dims": top_k,
            "explained_variance_transform": cumulative[:10],
            "n_dims_for_95pct": top_k,
            "transform_coherence": float(np.mean(delta_eigvals[:top_k]) / (delta_eigvals.sum() / len(delta_eigvals)))
        }

    def compress_pipeline(
        self,
        encoder_model: Callable[[np.ndarray], np.ndarray],
        grid_batch: np.ndarray,
        grid_ids: Optional[List[str]] = None
    ) -> List[ARCGridEmbedding]:
        """
        Pipeline completa: codifica grids → gera embeddings → comprime.

        Args:
            encoder_model: função que transforma grid (H,W,10) em embedding (d_model,)
            grid_batch: (n_grids, H, W, 10) — batch de grids one-hot
            grid_ids: identificadores

        Returns:
            List[ARCGridEmbedding]
        """
        # 1. Gerar embeddings via modelo
        embeddings = np.array([
            encoder_model(grid) for grid in grid_batch
        ])

        # 2. Treinar rotação espectral
        self.fit(embeddings, grid_ids)

        # 3. Codificar cada grid
        results = []
        for i, (emb, gid) in enumerate(
            zip(embeddings, grid_ids or [str(i) for i in range(len(embeddings))])
        ):
            encoded = self.encode(emb, gid, ARCEncodingLevel.GRID)
            encoded.grid_shape = grid_batch[i].shape[:2]
            results.append(encoded)

        return results
