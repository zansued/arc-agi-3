# context_atomizer.py — Módulo 1: Atomização de Contexto via Espectro
#
# Aplica análise espectral (S^T S do OSCAR) para rankear tokens/dimensões
# por importância atencional e atomizar (podar) o que for redundante.

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from .core import spectral_importance_ranking


@dataclass
class AtomizedContext:
    """Resultado da atomização de contexto."""
    tokens: List[str]              # tokens originais
    embeddings: np.ndarray         # (n_tokens, d_model)
    importance_scores: np.ndarray  # (n_tokens,) — score de importância
    kept_indices: List[int]        # índices dos tokens preservados
    removed_indices: List[int]     # índices dos tokens removidos
    compressed: bool = False       # se houve compressão
    compression_ratio: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def kept_tokens(self) -> List[str]:
        return [self.tokens[i] for i in self.kept_indices]

    @property
    def removed_tokens(self) -> List[str]:
        return [self.tokens[i] for i in self.removed_indices]


class ContextAtomizer:
    """
    Atomizador de contexto via análise espectral.

    Examina as dimensões dos embeddings e identifica:
    - Dimensões de alta variância = críticas para atenção
    - Tokens com projeção significativa no top-k = núcleo semântico
    - Tokens no subespaço residual = candidatos a atomização

    Inspirado em compute_sst() do OSCAR:
      Em vez de calcular Q^T K / V para KV cache, calculamos a
      matriz de covariância S^T S dos embeddings e usamos o
      espectro para rankear a importância de cada token/dimensão.
    """

    def __init__(
        self,
        variance_ratio: float = 0.90,
        method: str = "unweighted",
        min_tokens: int = 1,
        importance_threshold: float = 0.08
    ):
        """
        Args:
            variance_ratio: fração da variância a preservar (0-1)
            method: "unweighted" | "attention_weighted" | "variance_weighted"
            min_tokens: mínimo de tokens a manter
            importance_threshold: fração do max importance para manter token (0-1)
                Quanto menor, mais tokens são removidos. Default 0.08 (8%%).
        """
        self.variance_ratio = variance_ratio
        self.method = method
        self.min_tokens = min_tokens
        self.importance_threshold = importance_threshold

    def atomize(
        self,
        tokens: List[str],
        embeddings: np.ndarray,
        attention_weights: Optional[np.ndarray] = None
    ) -> AtomizedContext:
        """
        Atomiza uma sequência de tokens via análise espectral.

        Args:
            tokens: lista de strings (tokens/words)
            embeddings: (n_tokens, d_model)
            attention_weights: (n_tokens,) pesos opcionais

        Returns:
            AtomizedContext
        """
        n_tokens = len(tokens)
        if n_tokens <= self.min_tokens:
            return AtomizedContext(
                tokens=tokens,
                embeddings=embeddings,
                importance_scores=np.ones(n_tokens),
                kept_indices=list(range(n_tokens)),
                removed_indices=[],
                compressed=False,
                compression_ratio=1.0,
                metadata={"reason": "below_minimum_tokens"}
            )

        # Análise espectral
        ranking = spectral_importance_ranking(
            embeddings,
            method=self.method if attention_weights is None else "attention_weighted",
            variance_ratio=self.variance_ratio
        )

        # Importância por token = norma no subespaço top-k
        importance = ranking["importance_per_token"]

        # Normalizar importância
        importance_norm = importance / (importance.max() + 1e-12)

        # Threshold adaptativo: manter tokens com importância > X% do máximo
        # X = importance_threshold configurável (default 8%%)
        threshold = self.importance_threshold
        kept = np.where(importance_norm >= threshold)[0]
        removed = np.where(importance_norm < threshold)[0]

        # Garantir mínimo de tokens
        if len(kept) < self.min_tokens:
            # Ordenar por importância e pegar os top-k
            sorted_idx = np.argsort(importance_norm)[::-1]
            kept = sorted_idx[:self.min_tokens]
            removed = sorted_idx[self.min_tokens:]

        kept = sorted(kept)
        removed = sorted(removed)

        compression_ratio = n_tokens / max(len(kept), 1)

        return AtomizedContext(
            tokens=tokens,
            embeddings=embeddings,
            importance_scores=importance_norm,
            kept_indices=kept,
            removed_indices=removed,
            compressed=len(removed) > 0,
            compression_ratio=compression_ratio,
            metadata={
                "method": ranking["method"],
                "variance_ratio": self.variance_ratio,
                "k_dims": int(ranking["k"]),
                "total_dims": int(ranking["d_model"]),
                "explained_variance": float(ranking["cumulative_variance"][int(ranking["k"]) - 1]),
                "threshold": threshold,
                "n_kept": len(kept),
                "n_removed": len(removed),
                "compression_ratio": compression_ratio
            }
        )

    def atomize_and_summarize(
        self,
        tokens: List[str],
        embeddings: np.ndarray,
        n_clusters: int = 3
    ) -> Dict[str, Any]:
        """
        Atomiza e sumariza tokens removidos em clusters semânticos.
        (Versão estendida que agrupa tokens removidos em temas)
        """
        result = self.atomize(tokens, embeddings)

        if not result.compressed:
            return {
                "atomized": result,
                "summary": None,
                "message": "No tokens removed"
            }

        # Clusterizar tokens removidos por similaridade espectral
        if len(result.removed_indices) > 1:
            removed_embs = embeddings[result.removed_indices]
            # Normalizar
            norms = np.linalg.norm(removed_embs, axis=1, keepdims=True)
            removed_embs_norm = removed_embs / (norms + 1e-12)

            # K-means simplificado nos embeddings
            from sklearn.cluster import KMeans
            n_clusters = min(n_clusters, len(result.removed_indices))
            kmeans = KMeans(n_clusters=n_clusters, n_init=5, random_state=42)
            labels = kmeans.fit_predict(removed_embs_norm)

            clusters = {}
            for i, label in enumerate(labels):
                label = int(label)
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(result.tokens[result.removed_indices[i]])

            return {
                "atomized": result,
                "summary": {
                    "n_clusters": n_clusters,
                    "clusters": clusters,
                    "cluster_centers": kmeans.cluster_centers_
                },
                "message": f"{len(result.removed_tokens)} tokens removed, clustered into {n_clusters} groups"
            }

        return {"atomized": result, "summary": None, "message": "Single token removed"}
