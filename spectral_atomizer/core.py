# core.py — OSCAR-Inspired Spectral Math (Adaptado)
#
# Inspirado em: compute_kv_rotation.py (OSCAR / FutureMLS-Lab)
#   - build_hadamard, bit_reversal_perm, make_br_perm_matrix
#   - spectral_covariance (generaliza S^T S para qualquer embedding)
#   - spectral_rotation (R = U · H · P_br)
#   - lstsq_threshold (Lloyd-Max simplificado)
#   - spectral_importance_ranking (ranking de dimensões)
#   - compress_via_projection (projeção no subespaço top-k)

import numpy as np
from typing import Tuple, Optional, Dict, Any

# ---------------------------------------------------------------------------
# 1. MATRIZES AUXILIARES (Hadamard + Bit-Reversal como no OSCAR)
# ---------------------------------------------------------------------------

def build_hadamard(n: int) -> np.ndarray:
    """Matriz Hadamard recursiva (tamanho potência de 2)."""
    if n < 1 or n & (n - 1):
        raise ValueError(f"Hadamard size must be a power of two, got {n}")
    if n == 1:
        return np.ones((1, 1), dtype=np.float64)
    h = build_hadamard(n // 2)
    top = np.hstack([h, h])
    bot = np.hstack([h, -h])
    return np.vstack([top, bot]) / np.sqrt(2)


def bit_reversal_perm(d: int) -> np.ndarray:
    """Permutação bit-reversal (ordena por frequência)."""
    if d < 1 or d & (d - 1):
        raise ValueError(f"Bit-reversal size must be a power of two, got {d}")
    bits = int(np.log2(d))
    return np.array([int(bin(i)[2:].zfill(bits)[::-1], 2) for i in range(d)])


def make_br_perm_matrix(eigenvalues: np.ndarray) -> np.ndarray:
    """Matriz de permutação bit-reversal ordenada por autovalor."""
    d = len(eigenvalues)
    sorted_idx = np.argsort(eigenvalues)[::-1]
    br = bit_reversal_perm(d)
    perm = np.zeros(d, dtype=int)
    for i in range(d):
        perm[br[i]] = sorted_idx[i]
    I = np.eye(d, dtype=np.float64)
    return I[:, perm]

# ---------------------------------------------------------------------------
# 2. FUNÇÕES DE COVARIÂNCIA ESPECTRAL (Generalização do S^T S)
# ---------------------------------------------------------------------------

def spectral_covariance(
    embeddings: np.ndarray,
    weights: Optional[np.ndarray] = None,
    method: str = "unweighted"
) -> np.ndarray:
    """
    Calcula a matriz de covariância espectral dos embeddings.

    Parâmetros:
        embeddings: (n_tokens, d_model) — sequência de embeddings
        weights: (n_tokens,) — pesos opcionais (ex: scores de atenção)
        method: "unweighted" | "attention_weighted" | "variance_weighted"

    Retorna:
        cov: (d_model, d_model) — matriz de covariância

    Inspirado em compute_sst() do OSCAR:
      Σ_v = Σ_h 𝔼[ (q_h^T Q q_h)^{1/2} · v_h · v_h^T ]

    Adaptação: substitui Q/K/V por embedding único, mas mantém
    a lógica de ponderação pela importância atencional.
    """
    n_tokens, d_model = embeddings.shape
    X = embeddings.astype(np.float64)

    if method == "unweighted":
        cov = X.T @ X / n_tokens

    elif method == "attention_weighted":
        if weights is None:
            weights = np.ones(n_tokens) / n_tokens
        weights = np.asarray(weights, dtype=np.float64).flatten()
        weights = weights / weights.sum() * n_tokens
        Xw = X * np.sqrt(weights)[:, None]
        cov = Xw.T @ Xw / n_tokens

    elif method == "variance_weighted":
        # Ponderação pela norma L2 de cada token (proxy para importância)
        norms = np.linalg.norm(X, axis=1)
        weights = norms / norms.sum() * n_tokens
        Xw = X * np.sqrt(weights)[:, None]
        cov = Xw.T @ Xw / n_tokens

    else:
        raise ValueError(f"Unknown method: {method}")

    # Simetrização
    cov = (cov + cov.T) / 2
    return cov


def spectral_rotation(
    cov: np.ndarray,
    use_hadamard: bool = True,
    sparse: bool = False
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Decompõe a matriz de covariância e compõe a rotação R = U · H · P_br.

    Parâmetros:
        cov: (d, d) — matriz de covariância
        use_hadamard: se True, compõe R · H · P_br; se False, só U
        sparse: se True, retorna como SparseRotation

    Retorna:
        (rotation_matrix: (d, d), eigenvalues: (d,))
    """
    d = cov.shape[0]

    # Decomposição espectral
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Garantir ordem decrescente
    idx = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[idx]
    eigenvectors = eigenvectors[:, idx]

    # Rotação: U (eigenvectors)
    R = eigenvectors.copy()

    if use_hadamard:
        # Encontrar a menor potência de 2 >= d
        n = 1
        while n < d:
            n <<= 1
        # Verificar se n é potência de 2 (sempre será) E d também
        if d & (d - 1) == 0:  # d é potência de 2
            # Usamos Hadamard em bloco diagonal
            H = build_hadamard(n)
            if n > d:
                H = H[:d, :d]
            R = R @ H

            # Permutação bit-reversal
            P_br = make_br_perm_matrix(eigenvalues)
            R = R @ P_br
        # Se d não é potência de 2, usamos apenas os autovetores (sem Hadamard + bit-reversal)
        # Isso ainda preserva a compressão espectral via PCA
        # O Hadamard/bit-reversal é um refinamento para concentração uniforme da variância

    if sparse:
        return SparseRotation.from_dense(R), eigenvalues
    return R, eigenvalues


class SparseRotation:
    """Representação esparsa da rotação (top-k autovetores)."""

    def __init__(self, U: np.ndarray, eigenvalues: np.ndarray, k: int):
        self.U = U  # (d, k) — top-k autovetores
        self.eigenvalues = eigenvalues
        self.k = k
        self.d = U.shape[0]

    @classmethod
    def from_dense(cls, R: np.ndarray, k: Optional[int] = None):
        d = R.shape[0]
        if k is None:
            k = max(1, d // 2)
        return cls(R[:, :k], np.ones(d), k)

    def project(self, X: np.ndarray) -> np.ndarray:
        """Projeta X no subespaço rotacionado top-k."""
        return X @ self.U

    def unproject(self, Z: np.ndarray) -> np.ndarray:
        """Reconstrói X a partir da projeção."""
        return Z @ self.U.T

# ---------------------------------------------------------------------------
# 3. LLOYD-MAX SIMPLIFICADO (Threshold de Quantização)
# ---------------------------------------------------------------------------

def lstsq_threshold(
    data: np.ndarray,
    n_levels: int = 4
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Lloyd-Max simplificado para encontrar níveis ótimos de quantização.

    Parâmetros:
        data: (n,) — dados 1D para quantizar
        n_levels: número de níveis (2, 4, 8, 16)

    Retorna:
        (levels, boundaries)
    """
    data = data.flatten().astype(np.float64)
    data = data[np.isfinite(data)]
    if len(data) == 0:
        return np.linspace(-1, 1, n_levels), np.linspace(-1, 1, n_levels + 1)

    # Inicialização uniforme
    vmin, vmax = data.min(), data.max()
    boundaries = np.linspace(vmin, vmax, n_levels + 1)

    for _ in range(50):  # iterações
        # Níveis: média dos dados em cada bin
        levels = np.zeros(n_levels)
        for i in range(n_levels):
            mask = (data >= boundaries[i])
            if i < n_levels - 1:
                mask &= (data < boundaries[i + 1])
            if mask.any():
                levels[i] = data[mask].mean()
            else:
                levels[i] = (boundaries[i] + (boundaries[i + 1] if i + 1 < len(boundaries) else boundaries[i])) / 2

        # Novas boundaries: pontos médios entre níveis
        for i in range(1, n_levels):
            boundaries[i] = (levels[i - 1] + levels[i]) / 2

    return levels, boundaries

# ---------------------------------------------------------------------------
# 4. ANÁLISE DE IMPORTÂNCIA ESPECTRAL
# ---------------------------------------------------------------------------

def spectral_importance_ranking(
    embeddings: np.ndarray,
    method: str = "unweighted",
    variance_ratio: float = 0.95
) -> Dict[str, Any]:
    """
    Ranking de importância das dimensões usando análise espectral.

    Parâmetros:
        embeddings: (n_tokens, d_model)
        method: "unweighted" | "attention_weighted" | "variance_weighted"
        variance_ratio: fração da variância a preservar (0-1)

    Retorna:
        dict com:
          - eigenvalues: autovalores ordenados
          - eigenvectors: autovetores correspondentes
          - cumulative_variance: variância acumulada
          - k: número de dimensões para variance_ratio
          - importance_per_token: importância de cada token
          - compression_ratio: razão de compressão possível
    """
    d_model = embeddings.shape[1]
    cov = spectral_covariance(embeddings, method=method)
    eigvals, eigvecs = np.linalg.eigh(cov)

    # Ordenar decrescente
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]

    # Variância explicada
    total_var = eigvals.sum()
    explained_ratio = eigvals / total_var
    cumulative = np.cumsum(explained_ratio)
    k = int(np.searchsorted(cumulative, variance_ratio) + 1)

    # Importância por token (norma no subespaço top-k)
    proj = embeddings @ eigvecs[:, :k]
    importance_per_token = np.linalg.norm(proj, axis=1)

    return {
        "eigenvalues": eigvals,
        "eigenvectors": eigvecs,
        "explained_variance_ratio": explained_ratio,
        "cumulative_variance": cumulative,
        "k": k,
        "d_model": d_model,
        "compression_ratio": d_model / max(k, 1),
        "importance_per_token": importance_per_token,
        "variance_ratio": variance_ratio,
        "method": method
    }


def compress_via_projection(
    embeddings: np.ndarray,
    k: Optional[int] = None,
    variance_ratio: float = 0.95
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Comprime embeddings via projeção no subespaço espectral.

    Parâmetros:
        embeddings: (n_tokens, d_model)
        k: número de dimensões alvo (se None, calculado de variance_ratio)
        variance_ratio: fração da variância a preservar

    Retorna:
        (embeddings_comprimidos: (n_tokens, k), metadata)
    """
    ranking = spectral_importance_ranking(embeddings, variance_ratio=variance_ratio)
    if k is None:
        k = ranking["k"]

    eigvecs = ranking["eigenvectors"]
    proj = embeddings @ eigvecs[:, :k]

    metadata = {
        "k": k,
        "original_dim": embeddings.shape[1],
        "compression_ratio": embeddings.shape[1] / max(k, 1),
        "variance_preserved": ranking["cumulative_variance"][k - 1] if k > 0 else 0,
        "eigenvectors": eigvecs[:, :k]
    }
    return proj, metadata


# ---------------------------------------------------------------------------
# 5. DISTÂNCIA ESPECTRAL (Similaridade no Espaço Rotacionado)
# ---------------------------------------------------------------------------

def spectral_distance(
    x: np.ndarray,
    y: np.ndarray,
    rotation_matrix: Optional[np.ndarray] = None
) -> float:
    """
    Distância cosseno no espaço espectral rotacionado.
    Se rotation_matrix é None, usa PCA simples.
    """
    if rotation_matrix is not None:
        x_r = x @ rotation_matrix[:, :min(rotation_matrix.shape[1], x.shape[-1])]
        y_r = y @ rotation_matrix[:, :min(rotation_matrix.shape[1], y.shape[-1])]
    else:
        x_r = x
        y_r = y
    cos_sim = np.dot(x_r, y_r) / (np.linalg.norm(x_r) * np.linalg.norm(y_r) + 1e-12)
    return 1.0 - cos_sim
