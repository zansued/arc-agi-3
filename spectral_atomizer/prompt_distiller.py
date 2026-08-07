# prompt_distiller.py — Módulo 3: Destilador de Prompt via S^T S (OSCAR-inspired)
#
# Aplica análise espectral (S^T S do OSCAR) para rankear cada token
# do prompt por importância atencional, comprimindo prompts longos
# em versões destiladas que preservam o núcleo semântico.
#
# Inspirado em compute_sst() do OSCAR:
#   Σ_v = Σ_h 𝔼[ (q_h^T Q q_h)^{1/2} · v_h · v_h^T ]
# 
# Adaptação: em vez de Q/K/V de atenção multi-head, usamos
# embeddings de token (ex: sentence-transformers) e calculamos
# a matriz de covariância S^T S para encontrar as dimensões
# que mais contribuem para a estrutura semântica do prompt.

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Callable
from .core import spectral_importance_ranking, compress_via_projection


@dataclass
class DistilledPrompt:
    """Resultado da destilação de prompt."""
    original_prompt: str                        # prompt original
    distilled_prompt: str                       # prompt destilado
    tokens: List[str]                           # tokens do original
    importance_scores: np.ndarray               # (n_tokens,) — scores
    kept_indices: List[int]                     # índices preservados
    removed_indices: List[int]                  # índices removidos
    compression_ratio: float = 1.0              # razão de compressão
    token_compression_ratio: float = 1.0        # compressão de tokens
    dim_compression_ratio: float = 1.0          # compressão de dimensões
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_compressed(self) -> bool:
        return self.compression_ratio > 1.1


class PromptDistiller:
    """
    Destilador de prompts via análise espectral S^T S.

    Pipeline:
      1. Tokeniza o prompt
      2. Gera embeddings (token-level ou sentencas)
      3. Aplica S^T S → ranking espectral de importância
      4. Remove tokens de baixa importância (abaixo do threshold)
      5. Reconstrói o prompt destilado

    A novidade é que o ranking usa a ESTRUTURA ESPECTRAL (autovetores
    da covariância), não apenas TF-IDF ou atenção superficial. Dimensões
    que explicam mais variância dos embeddings são as que carregam
    mais informação semântica para o downstream.
    """

    def __init__(
        self,
        token_importance_threshold: float = 0.15,
        variance_ratio: float = 0.90,
        dim_compression: Optional[int] = None,
        method: str = "variance_weighted",
        min_tokens: int = 5,
        max_removal_pct: float = 0.60
    ):
        """
        Args:
            token_importance_threshold: fração do max importance para manter (0-1)
            variance_ratio: fração da variância espectral a preservar
            dim_compression: se definido, comprime dimensões para este valor
            method: "unweighted" | "attention_weighted" | "variance_weighted"
            min_tokens: mínimo de tokens após destilação
            max_removal_pct: máximo % de tokens removíveis (0-1)
        """
        self.token_importance_threshold = token_importance_threshold
        self.variance_ratio = variance_ratio
        self.dim_compression = dim_compression
        self.method = method
        self.min_tokens = min_tokens
        self.max_removal_pct = max_removal_pct

    def _simple_tokenizer(self, text: str) -> List[str]:
        """Tokenização simples por palavras."""
        return text.split()

    def _simple_reconstruct(self, original: str, tokens: List[str], kept_indices: List[int]) -> str:
        """Reconstrói o prompt a partir dos tokens preservados."""
        kept_tokens = [tokens[i] for i in sorted(kept_indices)]
        return ' '.join(kept_tokens)

    def _tfidf_embeddings(self, tokens: List[str]) -> np.ndarray:
        """Gera embeddings TF-IDF para um conjunto de tokens."""
        from collections import Counter
        n_tokens = len(tokens)
        # Calcular TF (term frequency) para cada token
        total_terms = len(tokens)
        tf = Counter(tokens)
        # IDF aproximado: log(N / df) onde df = contagem de documentos
        # Aqui cada token é um 'documento', e df = frequência nos vizinhos
        vocab = list(set(tokens))
        n_vocab = len(vocab)
        # Embedding: para cada token, vetor de co-ocorrência com janela 2
        d_model = min(64, n_vocab)
        if d_model < 2:
            d_model = 2
        emb = np.zeros((n_tokens, d_model))
        for i in range(n_tokens):
            # Contexto local: tokens antes e depois
            ctx = []
            if i > 0:
                ctx.append(tokens[i-1])
            if i < n_tokens - 1:
                ctx.append(tokens[i+1])
            # Frequência do token no contexto local
            for j, v in enumerate(vocab[:d_model]):
                tf_val = tokens.count(v) / max(total_terms, 1)
                idf_val = np.log(n_tokens / max(ctx.count(v), 1) + 1)
                emb[i, j] = tf_val * idf_val
        # Normalizar
        norms = np.linalg.norm(emb, axis=1, keepdims=True) + 1e-12
        emb = emb / norms
        return emb

    def distill(
        self,
        prompt: str,
        embeddings: Optional[np.ndarray] = None,
        embedding_fn: Optional[Callable[[List[str]], np.ndarray]] = None,
        tokenizer: Optional[Callable[[str], List[str]]] = None
    ) -> DistilledPrompt:
        """
        Destila um prompt via análise espectral.

        Args:
            prompt: texto a ser destilado
            embeddings: (n_tokens, d_model) — opcional (pré-computado)
            embedding_fn: função para gerar embeddings (se embeddings é None)
            tokenizer: função de tokenização customizada

        Returns:
            DistilledPrompt
        """
        tok = tokenizer or self._simple_tokenizer
        tokens = tok(prompt)
        n_tokens = len(tokens)

        if n_tokens <= self.min_tokens:
            return DistilledPrompt(
                original_prompt=prompt,
                distilled_prompt=prompt,
                tokens=tokens,
                importance_scores=np.ones(n_tokens),
                kept_indices=list(range(n_tokens)),
                removed_indices=[],
                compression_ratio=1.0,
                metadata={"reason": "too_short"}
            )

        # Gerar embeddings se necessário
        if embeddings is None:
            if embedding_fn is not None:
                embeddings = embedding_fn(tokens)
            else:
                # Fallback TF-IDF para gerar embeddings reais a partir do texto
                embeddings = self._tfidf_embeddings(tokens)

        # Análise espectral S^T S
        dim_analysis = spectral_importance_ranking(
            embeddings,
            method=self.method,
            variance_ratio=self.variance_ratio
        )

        # Compressão de dimensões (opcional)
        if self.dim_compression is not None:
            compressed_embs, meta = compress_via_projection(
                embeddings, k=self.dim_compression
            )
            dim_compression_ratio = meta["compression_ratio"]
        else:
            compressed_embs = embeddings
            dim_compression_ratio = 1.0

        # Importância por token: norma no subespaço top-k
        importance = dim_analysis["importance_per_token"]
        importance_norm = importance / (importance.max() + 1e-12)

        # Threshold adaptativo para token removal
        max_removable = int(n_tokens * self.max_removal_pct)
        threshold = self.token_importance_threshold

        kept = np.where(importance_norm >= threshold)[0]
        removed = np.where(importance_norm < threshold)[0]

        # Ajustar para respeitar limites
        if len(kept) < self.min_tokens:
            sorted_idx = np.argsort(importance_norm)[::-1]
            kept = sorted(sorted_idx[:self.min_tokens])
            removed = sorted(sorted_idx[self.min_tokens:])

        if len(removed) > max_removable:
            # Ordenar removidos por importância (menos importante primeiro)
            removed_scores = [(i, importance_norm[i]) for i in removed]
            removed_scores.sort(key=lambda x: x[1])
            # Manter apenas os mais removíveis
            removed = [r[0] for r in removed_scores[:max_removable]]
            kept_mask = np.ones(n_tokens, dtype=bool)
            kept_mask[removed] = False
            kept = np.where(kept_mask)[0].tolist()

        kept = sorted(kept)
        removed = sorted(removed)

        # Reconstruir prompt
        distilled = self._simple_reconstruct(prompt, tokens, kept)

        token_compression = n_tokens / max(len(kept), 1)
        total_compression = token_compression * dim_compression_ratio

        return DistilledPrompt(
            original_prompt=prompt,
            distilled_prompt=distilled,
            tokens=tokens,
            importance_scores=importance_norm,
            kept_indices=kept,
            removed_indices=removed,
            compression_ratio=total_compression,
            token_compression_ratio=token_compression,
            dim_compression_ratio=dim_compression_ratio,
            metadata={
                "k_dims": int(dim_analysis["k"]),
                "d_model": int(dim_analysis["d_model"]),
                "explained_variance": float(
                    dim_analysis["cumulative_variance"][
                        min(int(dim_analysis["k"]) - 1, len(dim_analysis["cumulative_variance"]) - 1)
                    ]
                ),
                "method": self.method,
                "threshold": self.token_importance_threshold,
                "n_kept": len(kept),
                "n_removed": len(removed),
                "token_compression": token_compression,
                "dim_compression": dim_compression_ratio
            }
        )

    def distill_iterative(
        self,
        prompt: str,
        max_iterations: int = 3,
        convergence_ratio: float = 0.95,
        **kwargs
    ) -> DistilledPrompt:
        """
        Destilação iterativa: aplica o processo várias vezes,
        cada iteração usando o resultado da anterior.
        """
        current_prompt = prompt
        all_results = []

        for i in range(max_iterations):
            result = self.distill(current_prompt, **kwargs)
            all_results.append(result)

            if not result.is_compressed:
                break

            current_prompt = result.distilled_prompt

            # Verificar convergência
            if i > 0:
                prev_ratio = all_results[i - 1].compression_ratio
                if abs(result.compression_ratio - 1.0) < 0.05:
                    break
                if result.compression_ratio >= prev_ratio * convergence_ratio:
                    break

        final = all_results[-1]
        final.metadata["iterations"] = len(all_results)
        final.metadata["iterative_results"] = [
            {"compression": r.compression_ratio, "tokens_kept": len(r.kept_indices)}
            for r in all_results
        ]
        return final

    def batch_distill(
        self,
        prompts: List[str],
        **kwargs
    ) -> List[DistilledPrompt]:
        """Destila múltiplos prompts."""
        return [self.distill(p, **kwargs) for p in prompts]
