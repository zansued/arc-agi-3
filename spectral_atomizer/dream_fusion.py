# dream_fusion.py — Módulo 5: Fusão Espectral de Memórias (Dream Consolidation)
#
# Aplica análise espectral (inspirada no S^T S do OSCAR) para:
#   1. Encontrar estruturas latentes comuns entre memórias
#   2. Fusão de memórias similares via projeção ortogonal
#   3. Identificar padrões de consolidação via decomposição espectral
#   4. Compactar memórias de longo prazo no subespaço espectral
#
# Conexão com o OSCAR:
#   - compute_sst() descobre quais dimensões do KV cache são críticas
#   - dream_fusion descobre quais dimensões das memórias são críticas
#     para o processo de consolidação onírica
#
# Integração com sonho_consolidado:
#   - Lê memórias do formato sonho_consolidado_YYYY-MM-DD.md
#   - Aplica análise espectral para encontrar padrões latentes
#   - Gera novas consolidações enriquecidas com insight espectral

import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Callable
import re
from datetime import datetime
from .core import (
    spectral_importance_ranking, spectral_covariance,
    spectral_rotation, compress_via_projection, spectral_distance
)


@dataclass
class MemoryEntry:
    """Uma memória para análise espectral."""
    id: str                              # identificador
    text: str                            # conteúdo textual
    embedding: Optional[np.ndarray] = None  # (d_model,) — embedding (opcional)
    timestamp: Optional[datetime] = None # quando foi criada
    category: str = "general"            # categoria
    importance: float = 1.0              # importância (0-1)
    access_count: int = 0                # quantas vezes acessada


@dataclass
class MemoryFusion:
    """Resultado da fusão espectral de memórias."""
    fused_id: str                        # ID da fusão
    source_ids: List[str]                # memórias de origem
    fused_embedding: np.ndarray           # embedding fundido
    compression_ratio: float              # compressão
    variance_explained: float             # variância explicada
    shared_dims: int                     # dimensões compartilhadas
    residual_dims: int                   # dimensões únicas
    cluster_label: int = 0               # cluster espectral


@dataclass
class SpectralDream:
    """Resultado de uma sessão de 'sonho espectral'."""
    timestamp: datetime
    n_memories_processed: int
    n_fusions_performed: int
    compression_ratio: float
    top_latent_patterns: List[Dict[str, Any]]
    memory_clusters: Dict[int, List[str]]
    consolidated_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DreamSpectralFusion:
    """
    Fusão espectral de memórias via análise S^T S.

    O processo:
      1. Coleta embeddings de memórias armazenadas
      2. Calcula S^T S = matriz de covariância espectral
      3. Decompõe em autovalores → encontra padrões latentes
      4. Clusteriza memórias por projeção no top-k
      5. Funde memórias do mesmo cluster via centroide espectral
      6. Compacta representação (projeção top-k)

    O nome 'Dream' vem da analogia com o sono:
      - Durante o dia: memórias são armazenadas em alta dimensão
      - Durante o sonho: o cérebro encontra padrões latentes
        (via S^T S) e consolida (funde) o que é redundante
      - Resultado: memória compacta, eficiente, sem perda semântica
    """

    def __init__(
        self,
        variance_ratio: float = 0.90,
        fusion_threshold: float = 0.85,
        min_cluster_size: int = 2,
        use_hadamard: bool = True
    ):
        """
        Args:
            variance_ratio: variância espectral a preservar na fusão
            fusion_threshold: similaridade mínima para fundir memórias
            min_cluster_size: mínimo de memórias para formar um cluster
            use_hadamard: usar rotação Hadamard + bit-reversal
        """
        self.variance_ratio = variance_ratio
        self.fusion_threshold = fusion_threshold
        self.min_cluster_size = min_cluster_size
        self.use_hadamard = use_hadamard
        self._rotation: Optional[np.ndarray] = None
        self._eigenvalues: Optional[np.ndarray] = None
        self._cluster_model: Optional[Any] = None

    def _embed_text(self, text: str, d_model: int = 64) -> np.ndarray:
        """
        Gera embedding simples para texto.
        Usa bag-of-characters + projeção aleatória.
        (Substitua por sentence-transformers para produção)
        """
        # Bag of characters (simplificado)
        chars = sorted(set(text.lower()))
        n_chars = len(chars)
        if n_chars == 0:
            return np.zeros(d_model)

        # One-hot encoding dos caracteres mais frequentes
        char_counts = {}
        for c in text.lower():
            char_counts[c] = char_counts.get(c, 0) + 1

        vec = np.array([char_counts.get(c, 0) for c in chars], dtype=np.float64)
        vec = vec / (np.linalg.norm(vec) + 1e-12)

        # Projetar para d_model via matriz aleatória fixa
        if not hasattr(self, '_random_proj'):
            self._random_proj = np.random.RandomState(42).randn(len(chars), d_model)
            self._random_proj /= np.linalg.norm(self._random_proj, axis=0, keepdims=True) + 1e-12

        # Ajustar projeção se n_chars mudou
        if self._random_proj.shape[0] != n_chars:
            self._random_proj = np.random.RandomState(42).randn(n_chars, d_model)
            self._random_proj /= np.linalg.norm(self._random_proj, axis=0, keepdims=True) + 1e-12

        return vec @ self._random_proj

    def analyze_memories(
        self,
        memories: List[MemoryEntry],
        embedding_fn: Optional[Callable[[str], np.ndarray]] = None
    ) -> Dict[str, Any]:
        """
        Analisa um conjunto de memórias via espectro.

        Args:
            memories: lista de MemoryEntry
            embedding_fn: função para gerar embeddings

        Returns:
            dict com análise espectral completa
        """
        if not memories:
            return {"error": "No memories provided"}

        embed_fn = embedding_fn or self._embed_text
        d_model = embed_fn("test").shape[0]

        # Gerar embeddings
        embeddings = np.zeros((len(memories), d_model))
        for i, mem in enumerate(memories):
            embeddings[i] = embed_fn(mem.text)

        # Análise espectral
        ranking = spectral_importance_ranking(
            embeddings,
            method="variance_weighted",
            variance_ratio=self.variance_ratio
        )

        # Projetar no subespaço top-k
        k = int(ranking["k"])
        proj = embeddings @ ranking["eigenvectors"][:, :k]

        # Detectar clusters via projeção espectral
        from sklearn.cluster import DBSCAN
        clustering = DBSCAN(eps=0.3, min_samples=min(2, len(memories)))
        labels = clustering.fit_predict(proj)

        # Organizar clusters
        clusters: Dict[int, List[str]] = {}
        for i, label in enumerate(labels):
            label = int(label)
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(memories[i].id)

        # Pontuação de coerência espectral
        explained = ranking["explained_variance_ratio"]
        coherence = float(
            np.sum(explained[:k]) / np.sum(explained)
            if np.sum(explained) > 0 else 0
        )

        # Salvar estado para fusão
        self._rotation = ranking["eigenvectors"][:, :k]
        self._eigenvalues = ranking["eigenvalues"]
        self._cluster_model = clustering

        return {
            "n_memories": len(memories),
            "d_model": d_model,
            "spectral_k": k,
            "compression_ratio": d_model / max(k, 1),
            "explained_variance": float(np.sum(explained[:k])),
            "coherence_score": coherence,
            "n_clusters": len(set(labels)) - (1 if -1 in labels else 0),
            "noise_points": int((labels == -1).sum()),
            "clusters": clusters,
            "cluster_labels": labels.tolist(),
            "projection": proj,
            "eigenvalues": ranking["eigenvalues"],
            "top_pattern": {
                "dimension": 0,
                "variance_ratio": float(explained[0]),
                "description": "Primary latent pattern (most variance)"
            },
            "latent_patterns": [
                {
                    "rank": i,
                    "variance_ratio": float(explained[i]),
                    "cumulative": float(np.sum(explained[:i+1]))
                }
                for i in range(min(10, len(explained)))
            ]
        }

    def fuse_memories(
        self,
        memories: List[MemoryEntry]
    ) -> List[MemoryFusion]:
        """
        Funde memórias similares via centroide espectral.

        Memórias no mesmo cluster espectral são fundidas em uma
        representação compacta (centroide no espaço top-k).

        Returns:
            List[MemoryFusion]
        """
        if not memories:
            return []

        # Analisar
        analysis = self.analyze_memories(memories)

        if "error" in analysis:
            return []

        # Agrupar por cluster (exceto ruído = -1)
        clusters = {int(k): v for k, v in analysis["clusters"].items() if int(k) >= 0}

        fusions = []
        embed_fn = getattr(self, '_embed_text', lambda x: np.zeros(64))
        d_model = embed_fn("test").shape[0]

        for label, mem_ids in clusters.items():
            if len(mem_ids) < self.min_cluster_size:
                continue

            # Embeddings das memórias no cluster
            cluster_mems = [m for m in memories if m.id in mem_ids]
            cluster_embs = np.array([
                (getattr(m, 'embedding', None) if hasattr(m, 'embedding') and m.embedding is not None
                 else self._embed_text(m.text))
                for m in cluster_mems
            ])

            # Centroide espectral (média no espaço original)
            centroid = cluster_embs.mean(axis=0)

            # Projetar no subespaço rotacionado (se disponível)
            if self._rotation is not None:
                k = self._rotation.shape[1]
                centroid_proj = centroid @ self._rotation
                compression_ratio = d_model / max(k, 1)
            else:
                centroid_proj = centroid
                compression_ratio = 1.0

            # Variância explicada pelo cluster
            if self._eigenvalues is not None:
                var_explained = float(
                    np.sum(self._eigenvalues[:min(len(self._eigenvalues), d_model)]) /
                    np.sum(self._eigenvalues)
                ) if np.sum(self._eigenvalues) > 0 else 0
            else:
                var_explained = 0.0

            fusions.append(MemoryFusion(
                fused_id=f"fusion_{label}_{datetime.now().strftime('%H%M%S')}",
                source_ids=mem_ids,
                fused_embedding=centroid_proj,
                compression_ratio=compression_ratio,
                variance_explained=var_explained,
                shared_dims=centroid_proj.shape[-1],
                residual_dims=d_model - centroid_proj.shape[-1],
                cluster_label=label
            ))

        return fusions

    def dream_cycle(
        self,
        memories: List[MemoryEntry],
        n_cycles: int = 1
    ) -> SpectralDream:
        """
        Ciclo completo de 'sonho': analisa, funde, compacta.

        Cada ciclo:
          1. Análise espectral das memórias atuais
          2. Detecção de clusters latentes
          3. Fusão intra-cluster
          4. Compactação (projeção top-k)
          5. Geração de texto consolidado

        Args:
            memories: lista de memórias
            n_cycles: número de ciclos (re-aplica fusão)

        Returns:
            SpectralDream
        """
        current_memories = list(memories)
        all_fusions = []

        for cycle in range(n_cycles):
            if len(current_memories) < self.min_cluster_size:
                break

            fusions = self.fuse_memories(current_memories)
            all_fusions.extend(fusions)

            if not fusions:
                break

            # Preparar para próximo ciclo: memórias não fundidas + fusões
            fused_ids = set()
            for fus in fusions:
                fused_ids.update(fus.source_ids)

            remaining = [m for m in current_memories if m.id not in fused_ids]
            current_memories = remaining

        # Estatísticas
        n_original = len(memories)
        n_after = len(current_memories)
        compression = n_original / max(n_after, 1)

        # Gerar texto consolidado
        analysis = self.analyze_memories(memories)
        latent_patterns = []
        if "latent_patterns" in analysis:
            for p in analysis["latent_patterns"][:5]:
                latent_patterns.append(p)

        consolidated_text = self._generate_consolidated_text(
            memories, all_fusions, analysis
        )

        return SpectralDream(
            timestamp=datetime.now(),
            n_memories_processed=n_original,
            n_fusions_performed=len(all_fusions),
            compression_ratio=compression,
            top_latent_patterns=latent_patterns[:5],
            memory_clusters=analysis.get("clusters", {}),
            consolidated_text=consolidated_text,
            metadata={
                "n_cycles": n_cycles,
                "variance_ratio": self.variance_ratio,
                "fusion_threshold": self.fusion_threshold,
                "spectral_k": analysis.get("spectral_k", 0),
                "coherence": analysis.get("coherence_score", 0)
            }
        )

    def _generate_consolidated_text(
        self,
        memories: List[MemoryEntry],
        fusions: List[MemoryFusion],
        analysis: Dict[str, Any]
    ) -> str:
        """Gera texto de consolidação a partir da análise espectral."""
        lines = []
        lines.append(f"# 🌙 Sonho Espectral - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        lines.append(f"**Memórias processadas:** {len(memories)}")
        lines.append(f"**Fusões realizadas:** {len(fusions)}")
        lines.append(f"**Compressão:** {analysis.get('compression_ratio', 1):.2f}x")
        lines.append(f"**Dimensões espectrais (k):** {analysis.get('spectral_k', 0)}")
        lines.append(f"**Coerência espectral:** {analysis.get('coherence_score', 0):.3f}")
        lines.append(f"**Clusters detectados:** {analysis.get('n_clusters', 0)}")
        lines.append("")

        lines.append("## 🔮 Padrões Latentes")
        for i, p in enumerate(analysis.get("latent_patterns", [])[:5]):
            lines.append(f"- Dimensão {i+1}: {p.get('variance_ratio', 0)*100:.1f}% da variância (acumulado: {p.get('cumulative', 0)*100:.1f}%)")
        lines.append("")

        lines.append("## 🧬 Fusões")
        for fus in fusions:
            lines.append(f"- Cluster {fus.cluster_label}: {len(fus.source_ids)} memórias fundidas")
            lines.append(f"  - IDs: {', '.join(fus.source_ids[:5])}{'...' if len(fus.source_ids) > 5 else ''}")
            lines.append(f"  - Compressão: {fus.compression_ratio:.2f}x, Variância: {fus.variance_explained:.1%}")
        lines.append("")

        lines.append("## 📊 Distribuição de Clusters")
        for label, ids in analysis.get("clusters", {}).items():
            label_name = f"Cluster {label}" if label >= 0 else "Ruído"
            lines.append(f"- {label_name}: {len(ids)} memórias")

        return '\n'.join(lines)

    def dream_from_file(
        self,
        filepath: str
    ) -> SpectralDream:
        """
        Lê memórias de um arquivo de sonho consolidado
        e aplica o ciclo espectral.

        Args:
            filepath: path para o arquivo .md de sonho consolidado
        """
        with open(filepath, 'r') as f:
            content = f.read()

        # Extrair seções do arquivo de sonho
        sections = re.split(r'\n## ', content)
        memories = []

        for i, section in enumerate(sections):
            if len(section.strip()) < 20:
                continue

            # Extrair nome da seção como ID
            section_id = f"dream_section_{i}"
            lines = section.strip().split('\n')
            if lines:
                section_id = lines[0].strip().replace('#', '').strip()[:30]

            mem = MemoryEntry(
                id=section_id,
                text=section[:500],  # limitar tamanho
                embedding=np.array([]),  # preenchido abaixo
                timestamp=datetime.now()
            )
            memories.append(mem)

        if not memories:
            return SpectralDream(
                timestamp=datetime.now(),
                n_memories_processed=0,
                n_fusions_performed=0,
                compression_ratio=1.0,
                top_latent_patterns=[],
                memory_clusters={},
                consolidated_text="# Nenhuma memória encontrada no arquivo."
            )

        return self.dream_cycle(memories)
