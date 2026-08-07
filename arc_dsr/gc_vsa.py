"""
Grid-Cell Vector Symbolic Architecture (GC-VSA)

Implements hyperdimensional computing primitives inspired by grid cells,
capable of encoding spatial positions and computing transformations
(translations, rotations) as native algebraic operations.

Based on:
- Grid cells (Moser & Moser, 2005)
- FPE: Fractional Power Encoding (Frady et al., 2018)
- TEM: Tolman-Eichenbaum Machine (Whittington et al., 2020)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class VSAConfig:
    """Configuration for the VSA hyperdimensional encoding."""
    dimension: int = 1024  # Hypervector dimension (typical: 512-4096)
    n_grid_modules: int = 6  # Number of grid-cell modules (each with different scale)
    scales: List[float] = field(default_factory=lambda: None)
    orientations: List[float] = field(default_factory=lambda: None)

    def __post_init__(self):
        if self.scales is None:
            # Log-spaced scales like mammalian grid cells
            self.scales = [3.0, 6.0, 12.0, 24.0, 48.0, 96.0]
        if self.orientations is None:
            # Hexagonal: 0°, 60°, 120° (3 basis orientations per module)
            self.orientations = [0.0, math.pi / 3, 2 * math.pi / 3]


class GridCellVSA:
    """
    Grid-Cell inspired Vector Symbolic Architecture.

    Encodes positions (x, y) as hyperdimensional vectors using
    Fractional Power Encoding (FPE) with multiple spatial scales.
    Transforms (translation, rotation) become circular convolution operations.
    """

    def __init__(self, config: Optional[VSAConfig] = None):
        self.config = config or VSAConfig()
        self.dim = self.config.dimension
        self.n_modules = self.config.n_grid_modules

        # Pre-compute basis vectors for each module and orientation
        self._phi_x, self._phi_y = self._init_basis_vectors()

    def _init_basis_vectors(self) -> Tuple[np.ndarray, np.ndarray]:
        """Initialize random basis vectors for FPE encoding.

        Returns:
            phi_x: (n_modules × n_orientations × dimension)
            phi_y: (n_modules × n_orientations × dimension)
        """
        n_orient = len(self.config.orientations)

        # Random phase vectors on the complex unit circle
        # This is the standard FPE approach: v(θ) = e^{iθ}
        phi_x = np.zeros((self.n_modules, n_orient, self.dim), dtype=np.complex64)
        phi_y = np.zeros((self.n_modules, n_orient, self.dim), dtype=np.complex64)

        for m in range(self.n_modules):
            for o in range(n_orient):
                # Random phases uniformly in [0, 2π)
                theta_x = np.random.uniform(0, 2 * math.pi, self.dim)
                theta_y = np.random.uniform(0, 2 * math.pi, self.dim)

                # Encode as complex exponentials
                phi_x[m, o, :] = np.exp(1j * theta_x)
                phi_y[m, o, :] = np.exp(1j * theta_y)

        return phi_x, phi_y

    def encode_position(self, x: float, y: float) -> np.ndarray:
        """Encode a position (x, y) as a hypervector.

        Uses Fractional Power Encoding: v(x,y) = FFT^{-1}(e^{i·x·ω_x + i·y·ω_y})

        Args:
            x: x-coordinate (can be fractional)
            y: y-coordinate (can be fractional)

        Returns:
            Hypervector of dimension self.dim (real-valued)
        """
        n_orient = len(self.config.orientations)
        vec = np.zeros(self.dim, dtype=np.complex64)

        for m in range(self.n_modules):
            scale = self.config.scales[m]
            # Scale position by module's spatial frequency
            sx = x / scale
            sy = y / scale

            for o in range(n_orient):
                orientation = self.config.orientations[o]
                # Rotate coordinates according to orientation
                rx = sx * math.cos(orientation) + sy * math.sin(orientation)
                ry = -sx * math.sin(orientation) + sy * math.cos(orientation)

                # FPE: phase = rx * ω_x + ry * ω_y
                # Where ω are the pre-computed basis vectors
                phase_x = rx * np.angle(self._phi_x[m, o, :])
                phase_y = ry * np.angle(self._phi_y[m, o, :])
                total_phase = phase_x + phase_y

                vec += np.exp(1j * total_phase)

        # Normalize (important for VSA operations)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        return vec

    def translate(self, vec: np.ndarray, dx: float, dy: float) -> np.ndarray:
        """Apply a translation (dx, dy) to an encoded position vector.

        Translation in FPE-VSA is circular convolution:
        T(Δx, Δy) ⊛ v(x,y) = v(x+Δx, y+Δy)

        This is significantly faster than re-encoding:
        we just element-wise multiply with the translation vector.
        """
        trans_vec = self.encode_position(dx, dy)
        # In Fourier domain: element-wise multiplication = circular convolution
        result = vec * trans_vec
        norm = np.linalg.norm(result)
        if norm > 0:
            result = result / norm
        return result

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two hypervectors."""
        dot = np.abs(np.dot(a.conj(), b))
        return float(dot / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def position_distance(
        self, pos_a: Tuple[float, float], pos_b: Tuple[float, float]
    ) -> float:
        """
        Compute the VSA-based distance between two positions.
        This is a smooth measure of spatial similarity.
        """
        va = self.encode_position(*pos_a)
        vb = self.encode_position(*pos_b)
        return 1.0 - self.similarity(va, vb)


class ObjectVSA:
    """
    Encodes ARC-AGI objects as hyperdimensional vectors.
    Combines position, color, shape, and size into a single vector.
    """

    def __init__(self, gc_vsa: GridCellVSA):
        self.gc_vsa = gc_vsa
        self.dim = gc_vsa.dim

        # Pre-compute color basis vectors (10 colors: 0-9)
        self._color_vecs = self._init_color_vectors()

        # Pre-compute shape basis vectors
        self._shape_vecs = self._init_shape_vectors()

    def _init_color_vectors(self) -> Dict[int, np.ndarray]:
        """Initialize random basis vectors for each color."""
        rng = np.random.default_rng(42)
        colors: Dict[int, np.ndarray] = {}
        for c in range(10):
            vec = rng.uniform(-1, 1, self.dim) + 1j * rng.uniform(-1, 1, self.dim)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            colors[c] = vec
        return colors

    def _init_shape_vectors(self) -> Dict[str, np.ndarray]:
        rng = np.random.default_rng(123)
        shapes = ["dot", "line", "rectangle", "L-shape", "almost_rectangle", "complex", "unknown"]
        shape_vecs: Dict[str, np.ndarray] = {}
        for s in shapes:
            vec = rng.uniform(-1, 1, self.dim) + 1j * rng.uniform(-1, 1, self.dim)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            shape_vecs[s] = vec
        return shape_vecs

    def encode_object(self, obj) -> np.ndarray:
        """Encode a complete object as a hypervector.

        Combines: position (centroid), color, shape, size
        Uses bundling (addition) and binding (circular convolution).
        """
        # Position part
        pos_vec = self.gc_vsa.encode_position(obj.centroid[0], obj.centroid[1])

        # Color part
        color_vec = self._color_vecs.get(obj.color, self._color_vecs[0])

        # Shape part
        shape_vec = self._shape_vecs.get(obj.shape, self._shape_vecs["unknown"])

        # Size part (normalized)
        size_norm = min(1.0, obj.area / 100.0)  # Cap at 100 pixels
        size_phase = np.exp(1j * 2 * math.pi * size_norm)

        # Bundle: weighted sum of bound components
        # Using a simple additive model: v = α·v_pos + β·v_color + γ·v_shape + δ·size
        # With binding: pos ⊛ color ⊛ shape ensures compositional structure
        bound = pos_vec * color_vec * shape_vec * size_phase

        norm = np.linalg.norm(bound)
        if norm > 0:
            bound = bound / norm

        return bound

    def similarity(self, obj_a, obj_b) -> float:
        """Compute VSA similarity between two objects."""
        va = self.encode_object(obj_a)
        vb = self.encode_object(obj_b)
        return self.gc_vsa.similarity(va, vb)

    def transform_query(
        self,
        source_obj,
        target_obj,
        dx: float = 0.0,
        dy: float = 0.0
    ) -> float:
        """
        Query whether source_obj transformed by (dx, dy) matches target_obj.
        Higher score = better match.
        """
        vs = self.encode_object(source_obj)
        vt = self.encode_object(target_obj)

        # Apply translation to source
        translated = self.gc_vsa.translate(vs, dx, dy)

        # Compare with target
        similarity = self.gc_vsa.similarity(translated, vt)

        # Also check untransformed similarity (color/shape match)
        vs_color_shape = vs * np.conj(self.gc_vsa.encode_position(
            source_obj.centroid[0], source_obj.centroid[1]
        ))
        vt_color_shape = vt * np.conj(self.gc_vsa.encode_position(
            target_obj.centroid[0], target_obj.centroid[1]
        ))
        norm = np.linalg.norm(vs_color_shape)
        if norm > 0:
            vs_color_shape = vs_color_shape / norm
        norm = np.linalg.norm(vt_color_shape)
        if norm > 0:
            vt_color_shape = vt_color_shape / norm

        # Blend position-similarity with identity-similarity
        identity_score = self.gc_vsa.similarity(vs_color_shape, vt_color_shape)

        return 0.6 * similarity + 0.4 * identity_score
