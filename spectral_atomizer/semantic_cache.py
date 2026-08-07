# semantic_cache.py — Módulo 2: Cache Semântico Compacto via Projeção Espectral
#
# Armazena embeddings no subespaço rotacionado (top-k dimensões)
# em vez do espaço original, economizando memória sem perder
# as dimensões que a atenção realmente usa.
#
# Inspirado em OSCAR: assim como o KV cache armazena K/V em INT2
# (~2 bits) em vez de BF16 (16 bits), aqui armazenamos projeções
# top-k em vez do embedding completo.

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple, Callable
from .core import spectral_rotation, spectral_covariance


@dataclass
class CachedEntry:
    """Entrada no cache semântico compacto."""
    key: str                       # chave de busca (texto original)
    projection: np.ndarray         # (k,) — embedding projetado
    context: Dict[str, Any]        # metadados anexos
    score: float = 0.0             # score de relevância
    access_count: int = 0          # contagem de acessos


class SpectralCache:
    """
    Cache semântico que armazena embeddings no subespaço espectral.

    Economia de memória:
      - Se d_model = 768 e k = 48 (top 6.25%)
      - Cada entrada: 768 floats → 48 floats = 16× compressão!

    A projeção é feita com a rotação espectral R = U · H · P_br
    (inspirada no OSCAR), que garante que as dimensões preservadas
    são as mais relevantes para a atenção/recuperação.
    """

    def __init__(
        self,
        k: int = 64,
        max_entries: int = 1000,
        similarity_threshold: float = 0.85,
        rotation_matrix: Optional[np.ndarray] = None
    ):
        """
        Args:
            k: número de dimensões a preservar
            max_entries: máximo de entradas no cache
            similarity_threshold: threshold para hit (cosseno)
            rotation_matrix: matriz de rotação pré-computada
        """
        self.k = k
        self.max_entries = max_entries
        self.similarity_threshold = similarity_threshold
        self.rotation_matrix = rotation_matrix
        self.entries: List[CachedEntry] = []
        self._hit_count = 0
        self._miss_count = 0

    @property
    def hit_rate(self) -> float:
        total = self._hit_count + self._miss_count
        return self._hit_count / total if total > 0 else 0.0

    @property
    def compression_ratio(self) -> float:
        """Razão de compressão do cache."""
        if not self.entries:
            return 0.0
        original_mem = len(self.entries) * 768  # d_model estimado
        compressed_mem = len(self.entries) * self.k
        return original_mem / compressed_mem if compressed_mem > 0 else 1.0

    def fit_rotation(self, embeddings: np.ndarray) -> np.ndarray:
        """
        Treina a rotação espectral a partir de um batch de embeddings.

        Args:
            embeddings: (n_samples, d_model)

        Returns:
            rotation_matrix: (d_model, k)
        """
        cov = spectral_covariance(embeddings)
        R, _ = spectral_rotation(cov, use_hadamard=True)
        self.rotation_matrix = R[:, :self.k]
        return self.rotation_matrix

    def _project(self, embedding: np.ndarray) -> np.ndarray:
        """Projeta embedding no subespaço top-k."""
        if self.rotation_matrix is not None:
            # Usar rotação espectral
            return embedding @ self.rotation_matrix
        else:
            # Fallback: PCA via SVD no embedding único
            return embedding[:self.k]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Similaridade cosseno entre vetores projetados."""
        a_norm = a / (np.linalg.norm(a) + 1e-12)
        b_norm = b / (np.linalg.norm(b) + 1e-12)
        return float(np.dot(a_norm, b_norm))

    def store(
        self,
        key: str,
        embedding: np.ndarray,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Armazena um embedding no cache (comprimido).

        Args:
            key: chave textual
            embedding: (d_model,)
            context: metadados

        Returns:
            "stored" | "updated" | "full"
        """
        # Verificar se já existe
        proj = self._project(embedding)

        for entry in self.entries:
            if entry.key == key:
                entry.projection = proj
                entry.context = context or {}
                entry.access_count += 1
                return "updated"

        # Cache cheio: remover entrada menos acessada
        if len(self.entries) >= self.max_entries:
            self.entries.sort(key=lambda e: e.access_count)
            self.entries.pop(0)

        self.entries.append(CachedEntry(
            key=key,
            projection=proj,
            context=context or {},
            access_count=1
        ))
        return "stored"

    def query(
        self,
        query_embedding: np.ndarray
    ) -> Tuple[Optional[CachedEntry], float]:
        """
        Busca entrada similar no cache.

        Args:
            query_embedding: (d_model,) — embedding de consulta

        Returns:
            (CachedEntry | None, max_similarity)
        """
        if not self.entries:
            self._miss_count += 1
            return None, 0.0

        q_proj = self._project(query_embedding)
        best_entry = None
        best_sim = 0.0

        for entry in self.entries:
            sim = self._cosine_similarity(q_proj, entry.projection)
            if sim > best_sim:
                best_sim = sim
                best_entry = entry

        if best_entry is not None and best_sim >= self.similarity_threshold:
            best_entry.access_count += 1
            best_entry.score = (best_entry.score + best_sim) / 2
            self._hit_count += 1
            return best_entry, best_sim

        self._miss_count += 1
        return None, best_sim

    def query_with_threshold(
        self,
        query_embedding: np.ndarray,
        threshold: Optional[float] = None
    ) -> List[Tuple[CachedEntry, float]]:
        """
        Retorna todas as entradas acima do threshold.
        """
        if not self.entries:
            return []

        t = threshold if threshold is not None else self.similarity_threshold
        q_proj = self._project(query_embedding)
        results = []

        for entry in self.entries:
            sim = self._cosine_similarity(q_proj, entry.projection)
            if sim >= t:
                results.append((entry, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def clear(self) -> int:
        """Limpa o cache e retorna o número de entradas removidas."""
        n = len(self.entries)
        self.entries.clear()
        return n

    def get_stats(self) -> Dict[str, Any]:
        """Estatísticas do cache."""
        return {
            "entries": len(self.entries),
            "max_entries": self.max_entries,
            "k_dims": self.k,
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "hit_rate": self.hit_rate,
            "compression_ratio": self.compression_ratio,
            "has_rotation": self.rotation_matrix is not None
        }


class SpectralCacheLayer:
    """
    Cache hierárquico com múltiplos níveis de compressão.

    Nível 0: cache original (sem compressão)
    Nível 1: top-50% dimensões
    Nível 2: top-25% dimensões
    Nível 3: top-10% dimensões
    """

    def __init__(
        self,
        d_model: int,
        levels: Optional[List[int]] = None
    ):
        if levels is None:
            levels = [d_model, d_model // 2, d_model // 4, max(1, d_model // 10)]
        self.levels = levels
        self.caches = [
            SpectralCache(k=k) for k in levels
        ]

    def fit_all(self, embeddings: np.ndarray):
        """Treina rotações para todos os níveis."""
        for cache in self.caches:
            cache.fit_rotation(embeddings)

    def store_at_level(
        self,
        key: str,
        embedding: np.ndarray,
        level: int = -1,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """Armazena em todos os níveis até o especificado."""
        if level < 0:
            level = len(self.caches) - 1
        results = []
        for i, cache in enumerate(self.caches):
            if i <= level:
                results.append(cache.store(key, embedding, context))
        return results

    def query_fast(
        self,
        query_embedding: np.ndarray,
        min_confidence: float = 0.9
    ) -> Tuple[Optional[CachedEntry], float, int]:
        """
        Busca começando pelo nível mais comprimido (mais rápido).
        Só vai para o próximo nível se a confiança for baixa.

        Returns:
            (entry, confidence, level_used)
        """
        for i, cache in enumerate(self.caches):
            entry, sim = cache.query(query_embedding)
            if entry is not None and sim >= min_confidence:
                return entry, sim, i

        return self.caches[0].query(query_embedding)[0], 0.0, 0
