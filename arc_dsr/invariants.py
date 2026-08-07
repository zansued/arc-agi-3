"""
Invariants Module - Noether Invariants & WLKS Graph Kernels

Computes topological and algebraic invariants of ARC-AGI grids:
1. Noether invariants (discrete conservation laws)
2. D4 symmetry group analysis
3. Weisfeiler-Lehman Kernel Signature (WLKS) for graph isomorphism
4. Chromatic and geometric invariants

Based on:
- Noether's Theorem (discrete): conservation of chromatic mass, topological features
- D4: Dihedral group of the square (rotations 0/90/180/270, reflections H/V/2 diagonals)
- WL: Weisfeiler-Lehman graph isomorphism test kernel
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.ndimage import label, find_objects


class NoetherInvariants:
    """
    Computes discrete Noether invariants for ARC-AGI grids.

    These are quantities that should be conserved under valid transformations,
    analogous to conservation laws in physics (Noether's theorem).
    """

    def __init__(self, grid: np.ndarray):
        self.grid = grid
        self.height, self.width = grid.shape

    def compute_all(self) -> Dict[str, Any]:
        """Compute all invariants for the grid."""
        return {
            "chromatic_mass": self.chromatic_mass(),
            "color_palette": self.color_palette(),
            "color_histogram": self.color_histogram(),
            "connected_components": self.connected_component_invariants(),
            "topological_features": self.topological_features(),
            "d4_signature": self.d4_signature(),
            "betti_numbers": self.betti_numbers(),
            "boundary_features": self.boundary_features(),
        }

    def chromatic_mass(self) -> Dict[int, int]:
        """Count pixels of each color (chromatic mass).
        Conserved under spatial transformations (move, rotate, mirror).
        """
        mass = {}
        for c in range(1, 10):  # colors 1-9 (0 is background)
            count = int(np.sum(self.grid == c))
            if count > 0:
                mass[c] = count
        return mass

    def color_palette(self) -> List[int]:
        """Sorted list of colors present.
        Conserved under all spatial transformations.
        """
        return sorted([int(c) for c in np.unique(self.grid) if c != 0])

    def color_histogram(self) -> np.ndarray:
        """Normalized color histogram (10 bins)."""
        hist = np.zeros(10, dtype=float)
        for c in range(10):
            hist[c] = np.sum(self.grid == c)
        total = hist.sum()
        if total > 0:
            hist = hist / total
        return hist

    def connected_component_invariants(self) -> Dict[str, Any]:
        """Invariants of connected components (ignoring color)."""
        binary = (self.grid > 0).astype(int)
        labeled, n_features = label(binary)

        sizes = []
        for i in range(1, n_features + 1):
            sizes.append(int(np.sum(labeled == i)))

        return {
            "n_components": int(n_features),
            "component_sizes": sorted(sizes, reverse=True),
            "mean_component_size": float(np.mean(sizes)) if sizes else 0.0,
            "component_size_variance": float(np.var(sizes)) if sizes else 0.0,
        }

    def topological_features(self) -> Dict[str, int]:
        """Topological features of the grid.
        - Number of holes (regions of background fully enclosed by foreground)
        - Number of isolated pixels
        """
        binary = (self.grid > 0).astype(int)

        # Count holes: invert and count connected components of background
        # that don't touch the border
        inverted = 1 - binary
        labeled_inv, n_inv_features = label(inverted)

        holes = 0
        for i in range(1, n_inv_features + 1):
            mask = (labeled_inv == i)
            coords = np.argwhere(mask)
            # Check if touches border
            touches_border = any(
                r == 0 or r == self.height - 1 or c == 0 or c == self.width - 1
                for r, c in coords
            )
            if not touches_border:
                holes += 1

        # Isolated single-pixel objects
        binary_minus_border = binary.copy()
        binary_minus_border[0, :] = 0
        binary_minus_border[-1, :] = 0
        binary_minus_border[:, 0] = 0
        binary_minus_border[:, -1] = 0
        labeled_iso, _ = label(binary_minus_border)
        component_sizes = [int(np.sum(labeled_iso == i))
                          for i in range(1, labeled_iso.max() + 1)]
        isolated = sum(1 for s in component_sizes if s == 1)

        return {
            "n_holes": holes,
            "n_isolated_pixels": isolated,
        }

    def d4_signature(self) -> Dict[str, bool]:
        """
        Compute D4 (dihedral group of square) symmetry signature.
        Tests all 8 symmetries of the square.
        """
        signatures = {}

        # Identity
        signatures["identity"] = True

        # Rotations
        r90 = np.rot90(self.grid, k=1)
        r180 = np.rot90(self.grid, k=2)
        r270 = np.rot90(self.grid, k=3)

        signatures["rotate_90"] = np.array_equal(self.grid, r90)
        signatures["rotate_180"] = np.array_equal(self.grid, r180)
        signatures["rotate_270"] = np.array_equal(self.grid, r270)

        # Reflections
        flip_h = np.fliplr(self.grid)
        flip_v = np.flipud(self.grid)
        flip_main_diag = self.grid.T  # Transpose = reflect over main diagonal
        flip_anti_diag = np.rot90(self.grid, k=1).T  # Reflect over anti-diagonal

        signatures["reflect_h"] = np.array_equal(self.grid, flip_h)
        signatures["reflect_v"] = np.array_equal(self.grid, flip_v)
        signatures["reflect_main_diag"] = np.array_equal(self.grid, flip_main_diag)
        signatures["reflect_anti_diag"] = np.array_equal(self.grid, flip_anti_diag)

        # Symmetry group order (how many symmetries does the grid have?)
        n_symmetries = sum(1 for v in signatures.values() if v)
        signatures["symmetry_order"] = n_symmetries

        return signatures

    def betti_numbers(self) -> Dict[str, int]:
        """
        Compute discrete Betti numbers (topological features):
        - b0: number of connected components
        - b1: number of holes (1-dimensional cycles)
        """
        binary = (self.grid > 0).astype(int)
        labeled, b0 = label(binary)

        # Count holes (1-cycles)
        inverted = 1 - binary
        labeled_inv, _ = label(inverted)
        b1 = 0
        for i in range(1, labeled_inv.max() + 1):
            mask = (labeled_inv == i)
            coords = np.argwhere(mask)
            touches_border = any(
                r == 0 or r == self.height - 1 or c == 0 or c == self.width - 1
                for r, c in coords
            )
            if not touches_border:
                b1 += 1

        return {
            "b0_components": int(b0),
            "b1_holes": b1,
        }

    def boundary_features(self) -> Dict[str, Any]:
        """Features related to the grid boundary."""
        top = self.grid[0, :]
        bottom = self.grid[-1, :]
        left = self.grid[:, 0]
        right = self.grid[:, -1]

        return {
            "border_colors": sorted(set(
                int(c) for c in
                list(top) + list(bottom) + list(left) + list(right)
                if c != 0
            )),
            "border_density": float(np.mean(self.grid > 0) *
                                     (self.height * 2 + self.width * 2) /
                                     max(self.height * self.width, 1)),
            "corners_match": int(self.grid[0, 0]) == int(self.grid[0, -1]) ==
                             int(self.grid[-1, 0]) == int(self.grid[-1, -1])
                             and int(self.grid[0, 0]) == 0,
        }

    def invariant_distance(
        self, other: NoetherInvariants
    ) -> float:
        """Compute distance between invariants of two grids.
        Lower = more likely to be related by a valid transformation.
        """
        dist = 0.0

        # Compare chromatic mass
        m1 = self.chromatic_mass()
        m2 = other.chromatic_mass()
        all_colors = set(m1.keys()) | set(m2.keys())
        for c in all_colors:
            v1 = m1.get(c, 0)
            v2 = m2.get(c, 0)
            dist += abs(v1 - v2) / (max(v1, v2, 1))

        # Compare component invariants
        c1 = self.connected_component_invariants()
        c2 = other.connected_component_invariants()
        dist += abs(c1["n_components"] - c2["n_components"]) * 0.5

        # Compare topological features
        t1 = self.topological_features()
        t2 = other.topological_features()
        dist += abs(t1["n_holes"] - t2["n_holes"]) * 0.5
        dist += abs(t1["n_isolated_pixels"] - t2["n_isolated_pixels"]) * 0.2

        return dist


class WLKSKernel:
    """
    Weisfeiler-Lehman Kernel Signature for ARC-AGI grids.

    Converts each grid into a graph G(V,E) and computes the
    WL color refinement signature up to h iterations.
    The signature is a multiset of colors at each iteration.
    """

    def __init__(self, n_iterations: int = 3):
        self.n_iterations = n_iterations

    def grid_to_graph(self, grid: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Convert grid to graph: nodes = pixels, edges = 4-connectivity."""
        h, w = grid.shape
        n_pixels = h * w

        # Node indexing: node_id = r * w + c
        edges = []
        for r in range(h):
            for c in range(w):
                idx = r * w + c
                # Right neighbor
                if c + 1 < w:
                    edges.append((idx, r * w + c + 1))
                # Bottom neighbor
                if r + 1 < h:
                    edges.append((idx, (r + 1) * w + c))

        node_features = grid.flatten()

        return node_features, np.array(edges) if edges else np.zeros((0, 2), dtype=int)

    def compute_signature(self, grid: np.ndarray) -> Dict[str, Any]:
        """
        Compute WL color refinement signature of the grid.

        Returns a dictionary of color multisets at each iteration,
        plus the final canonical color histogram.
        """
        h, w = grid.shape
        n_pixels = h * w

        # Initial coloring: pixel color value (0-9)
        # Plus structural features (is_border, position)
        colors = np.zeros(n_pixels, dtype=int)
        for r in range(h):
            for c in range(w):
                idx = r * w + c
                pixel_color = int(grid[r, c])

                # Encode: color * 1000 + position features
                is_border = (r == 0 or r == h - 1 or c == 0 or c == w - 1)
                quad = (r // (max(h // 3, 1))) * 3 + (c // (max(w // 3, 1)))

                colors[idx] = pixel_color * 10000 + int(is_border) * 100 + quad

        # Build adjacency: for each node, list of neighbor indices
        adj = [[] for _ in range(n_pixels)]
        for r in range(h):
            for c in range(w):
                idx = r * w + c
                if c + 1 < w:
                    adj[idx].append(r * w + c + 1)
                    adj[r * w + c + 1].append(idx)
                if r + 1 < h:
                    adj[idx].append((r + 1) * w + c)
                    adj[(r + 1) * w + c].append(idx)

        # WL refinement iterations
        iteration_colors = {}
        iteration_colors[0] = self._color_multiset(colors)

        for iteration in range(1, self.n_iterations + 1):
            # Compute new colors based on neighbors
            new_colors = np.zeros(n_pixels, dtype=int)
            for i in range(n_pixels):
                # Hash: current color + sorted multiset of neighbor colors
                neighbor_colors = tuple(sorted(colors[n] for n in adj[i] if n < n_pixels))
                new_colors[i] = hash((colors[i], neighbor_colors)) % (2 ** 31 - 1)

            colors = new_colors
            iteration_colors[iteration] = self._color_multiset(colors)

        # Final canonical histogram
        final_hist = np.zeros(max(colors) + 1 if len(colors) > 0 else 1)
        for c in colors:
            final_hist[c] += 1
        # Normalize
        if np.sum(final_hist) > 0:
            final_hist = final_hist / np.sum(final_hist)

        return {
            "multisets": iteration_colors,
            "histogram": final_hist.tolist(),
            "n_nodes": n_pixels,
        }

    def _color_multiset(self, colors: np.ndarray) -> Dict[int, int]:
        """Return multiset of colors as {color: count}."""
        unique, counts = np.unique(colors, return_counts=True)
        return {int(u): int(c) for u, c in zip(unique, counts)}

    def signature_similarity(
        self, sig_a: Dict[str, Any], sig_b: Dict[str, Any]
    ) -> float:
        """Compute similarity between two WL signatures."""
        # Compare histograms (cosine similarity)
        h_a = np.array(sig_a["histogram"])
        h_b = np.array(sig_b["histogram"])

        # Pad to same length
        max_len = max(len(h_a), len(h_b))
        if len(h_a) < max_len:
            h_a = np.pad(h_a, (0, max_len - len(h_a)))
        if len(h_b) < max_len:
            h_b = np.pad(h_b, (0, max_len - len(h_b)))

        dot = np.dot(h_a, h_b)
        norm_a = np.linalg.norm(h_a)
        norm_b = np.linalg.norm(h_b)

        if norm_a > 0 and norm_b > 0:
            return float(dot / (norm_a * norm_b))
        return 0.0

    def kernels_gallery(
        self, grids: List[np.ndarray]
    ) -> np.ndarray:
        """Compute pairwise WL kernel matrix for a list of grids."""
        n = len(grids)
        matrix = np.eye(n, dtype=float)

        signatures = [self.compute_signature(g) for g in grids]

        for i in range(n):
            for j in range(i + 1, n):
                sim = self.signature_similarity(signatures[i], signatures[j])
                matrix[i, j] = sim
                matrix[j, i] = sim

        return matrix


class D4Transformer:
    """
    Applies D4 group transformations to grids.
    Used to test hypotheses about symmetry operations.
    """

    @staticmethod
    def rotate_90(grid: np.ndarray) -> np.ndarray:
        return np.rot90(grid, k=1)

    @staticmethod
    def rotate_180(grid: np.ndarray) -> np.ndarray:
        return np.rot90(grid, k=2)

    @staticmethod
    def rotate_270(grid: np.ndarray) -> np.ndarray:
        return np.rot90(grid, k=3)

    @staticmethod
    def flip_horizontal(grid: np.ndarray) -> np.ndarray:
        return np.fliplr(grid)

    @staticmethod
    def flip_vertical(grid: np.ndarray) -> np.ndarray:
        return np.flipud(grid)

    @staticmethod
    def transpose(grid: np.ndarray) -> np.ndarray:
        return grid.T

    @staticmethod
    def anti_transpose(grid: np.ndarray) -> np.ndarray:
        """Reflect over anti-diagonal."""
        return np.rot90(np.fliplr(grid))

    @classmethod
    def all_transforms(cls, grid: np.ndarray) -> List[Tuple[str, np.ndarray]]:
        """Apply all 8 D4 transformations and return labeled results."""
        return [
            ("identity", grid),
            ("rotate_90", cls.rotate_90(grid)),
            ("rotate_180", cls.rotate_180(grid)),
            ("rotate_270", cls.rotate_270(grid)),
            ("flip_h", cls.flip_horizontal(grid)),
            ("flip_v", cls.flip_vertical(grid)),
            ("transpose", cls.transpose(grid)),
            ("anti_transpose", cls.anti_transpose(grid)),
        ]

    @classmethod
    def find_best_transform(
        cls, source: np.ndarray, target: np.ndarray
    ) -> Tuple[str, float]:
        """Find which D4 transformation best maps source to target."""
        best_name = "identity"
        best_score = 0.0

        for name, transformed in cls.all_transforms(source):
            if transformed.shape == target.shape:
                match = np.mean((transformed == target).astype(float))
                if match > best_score:
                    best_score = match
                    best_name = name

        return best_name, best_score


# ════════════════════════════════════════════════════════
# V55 Compatibility Adapters (bare function interface)
# ════════════════════════════════════════════════════════


def compute_invariants(grid: np.ndarray) -> Dict[str, Any]:
    """Compute all invariants for a grid."""
    inv = NoetherInvariants(grid)
    result = inv.compute_all()
    # Add 'dimensions' key required by V55 deduct_rule
    result['dimensions'] = grid.shape
    # Ensure d4_signature is a list of names (not a dict with counts)
    d4 = D4Transformer()
    if isinstance(result.get('d4_signature'), dict):
        sig_transforms = d4.all_transforms(grid)
        result['d4_signature'] = [name for name, _ in sig_transforms]
    return result


def compute_chromatic_mass(grid: np.ndarray) -> Dict[int, int]:
    """Count pixels per color in grid."""
    inv = NoetherInvariants(grid)
    return inv.chromatic_mass()


def compute_betti_numbers(grid: np.ndarray) -> Dict[str, int]:
    """Compute connectivity-based invariants (Betti-like)."""
    inv = NoetherInvariants(grid)
    return inv.connected_component_invariants()


def compute_d4_signature(grid: np.ndarray) -> List[str]:
    """Compute D4 symmetry signature."""
    d4 = D4Transformer()
    sig = d4.all_transforms(grid)
    return [name for name, _ in sig]
