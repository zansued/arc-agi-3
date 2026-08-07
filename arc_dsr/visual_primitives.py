"""
Visual Primitives Module

Extracts geometric and visual features from ARC-AGI objects:
- Hu moments (translation/rotation/scale invariant shape descriptors)
- Contour features (perimeter, convex hull, solidity)
- Shape descriptors (compactness, elongation, eccentricity)
- Bounding box analysis

These primitives are used by Layer 2 (Analogical Reasoning) to match
objects across input/output pairs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class ShapeDescriptor:
    """
    Computes geometric descriptors for ARC-AGI objects.

    These descriptors are used to:
    1. Match objects across input/output pairs
    2. Classify shape types beyond simple categories
    3. Detect transformations (rotation, scaling, shearing)
    """

    @staticmethod
    def from_binary_mask(mask: np.ndarray) -> Dict[str, Any]:
        """Compute shape descriptors from a binary mask."""
        h, w = mask.shape
        ys, xs = np.where(mask > 0)

        if len(xs) == 0:
            return {}

        descriptors = {}

        # Basic properties
        descriptors["area"] = int(len(xs))
        descriptors["perimeter"] = ShapeDescriptor._compute_perimeter(mask)
        descriptors["centroid_y"] = float(np.mean(ys))
        descriptors["centroid_x"] = float(np.mean(xs))

        # Bounding box
        min_y, max_y = int(ys.min()), int(ys.max())
        min_x, max_x = int(xs.min()), int(xs.max())
        descriptors["bbox"] = (min_y, min_x, max_y, max_x)
        descriptors["bbox_width"] = max_x - min_x + 1
        descriptors["bbox_height"] = max_y - min_y + 1
        descriptors["aspect_ratio"] = (max_x - min_x + 1) / max(max_y - min_y + 1, 1)

        # Shape metrics
        if descriptors["perimeter"] > 0:
            descriptors["compactness"] = (4 * np.pi * descriptors["area"]) / (descriptors["perimeter"] ** 2)
        else:
            descriptors["compactness"] = 0.0

        # Elongation: ratio of major to minor axis
        cov = np.cov(xs, ys)
        if cov.size > 0:
            eigvals = np.linalg.eigvalsh(cov)
            major = max(eigvals)
            minor = min(eigvals)
            if minor > 1e-6:
                descriptors["elongation"] = float(np.sqrt(major / minor))
            else:
                descriptors["elongation"] = 1.0

        # Hu moments (translation, rotation, and scale invariant)
        hu = ShapeDescriptor._compute_hu_moments(mask)
        for i, moment in enumerate(hu):
            descriptors[f"hu_{i+1}"] = float(moment)

        # Fill ratio
        bbox_area = descriptors["bbox_width"] * descriptors["bbox_height"]
        if bbox_area > 0:
            descriptors["fill_ratio"] = descriptors["area"] / bbox_area
        else:
            descriptors["fill_ratio"] = 0.0

        # Convex hull features
        hull_area = ShapeDescriptor._convex_hull_area(xs, ys)
        descriptors["convex_hull_area"] = hull_area
        if hull_area > 0:
            descriptors["solidity"] = descriptors["area"] / hull_area
        else:
            descriptors["solidity"] = 0.0

        return descriptors

    @staticmethod
    def _compute_perimeter(mask: np.ndarray) -> float:
        """Compute perimeter using 4-connectivity."""
        from scipy.ndimage import binary_dilation
        struct = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=bool)
        dilated = binary_dilation(mask, structure=struct)
        border = dilated & ~mask
        return float(np.sum(border))

    @staticmethod
    def _compute_hu_moments(mask: np.ndarray) -> np.ndarray:
        """
        Compute Hu moments (7 invariant moments).

        Hu moments are invariant to:
        - Translation (μ moments)
        - Scale (η moments)
        - Rotation (specific combinations)

        Returns array of 7 moment values.
        """
        h, w = mask.shape
        ys, xs = np.where(mask > 0)

        if len(xs) == 0:
            return np.zeros(7)

        area = float(len(xs))

        # Centroid
        m00 = area
        m10 = float(np.sum(xs))
        m01 = float(np.sum(ys))
        cx = m10 / m00 if m00 > 0 else 0
        cy = m01 / m00 if m00 > 0 else 0

        # Central moments
        mu00 = m00
        mu11 = np.sum((xs - cx) * (ys - cy))
        mu20 = np.sum((xs - cx) ** 2)
        mu02 = np.sum((ys - cy) ** 2)
        mu30 = np.sum((xs - cx) ** 3)
        mu12 = np.sum((xs - cx) * (ys - cy) ** 2)
        mu21 = np.sum((xs - cx) ** 2 * (ys - cy))
        mu03 = np.sum((ys - cy) ** 3)

        # Normalize for scale invariance
        inv_mu00 = mu00 ** 2 if mu00 > 0 else 1
        nu11 = mu11 / inv_mu00
        nu20 = mu20 / inv_mu00
        nu02 = mu02 / inv_mu00
        nu30 = mu30 / (mu00 ** 2.5) if mu00 > 0 else 0
        nu12 = mu12 / (mu00 ** 2.5) if mu00 > 0 else 0
        nu21 = mu21 / (mu00 ** 2.5) if mu00 > 0 else 0
        nu03 = mu03 / (mu00 ** 2.5) if mu00 > 0 else 0

        # Hu moments (7)
        hu = np.zeros(7)
        hu[0] = nu20 + nu02
        hu[1] = (nu20 - nu02) ** 2 + 4 * nu11 ** 2
        hu[2] = (nu30 - 3 * nu12) ** 2 + (3 * nu21 - nu03) ** 2
        hu[3] = (nu30 + nu12) ** 2 + (nu21 + nu03) ** 2
        hu[4] = (nu30 - 3 * nu12) * (nu30 + nu12) * ((nu30 + nu12) ** 2 - 3 * (nu21 + nu03) ** 2) + \
                (3 * nu21 - nu03) * (nu21 + nu03) * (3 * (nu30 + nu12) ** 2 - (nu21 + nu03) ** 2)
        hu[5] = (nu20 - nu02) * ((nu30 + nu12) ** 2 - (nu21 + nu03) ** 2) + \
                4 * nu11 * (nu30 + nu12) * (nu21 + nu03)
        hu[6] = (3 * nu21 - nu03) * (nu30 + nu12) * ((nu30 + nu12) ** 2 - 3 * (nu21 + nu03) ** 2) - \
                (nu30 - 3 * nu12) * (nu21 + nu03) * (3 * (nu30 + nu12) ** 2 - (nu21 + nu03) ** 2)

        return hu

    @staticmethod
    def _convex_hull_area(xs: np.ndarray, ys: np.ndarray) -> float:
        """Compute area of convex hull using monotone chain algorithm."""
        if len(xs) < 3:
            return float(len(xs))

        points = np.column_stack((xs, ys))

        # Sort by x, then y
        idx = np.lexsort((ys, xs))
        points = points[idx]

        # Build lower hull
        lower = []
        for p in points:
            while len(lower) >= 2:
                cross = (lower[-1][0] - lower[-2][0]) * (p[1] - lower[-2][1]) - \
                        (lower[-1][1] - lower[-2][1]) * (p[0] - lower[-2][0])
                if cross > 0:
                    break
                lower.pop()
            lower.append(p)

        # Build upper hull
        upper = []
        for p in reversed(points):
            while len(upper) >= 2:
                cross = (upper[-1][0] - upper[-2][0]) * (p[1] - upper[-2][1]) - \
                        (upper[-1][1] - upper[-2][1]) * (p[0] - upper[-2][0])
                if cross > 0:
                    break
                upper.pop()
            upper.append(p)

        # Concatenate hull (remove last point of each because it's repeated)
        hull = np.array(lower[:-1] + upper[:-1])

        if len(hull) < 3:
            return 0.0

        # Shoelace formula for area
        x = hull[:, 0]
        y = hull[:, 1]
        area = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

        return float(area)

    @staticmethod
    def hu_distance(desc_a: Dict[str, Any], desc_b: Dict[str, Any]) -> float:
        """Compute distance between two sets of Hu moments.
        Lower = more similar in shape.
        """
        dist = 0.0
        for i in range(1, 8):
            key = f"hu_{i}"
            if key in desc_a and key in desc_b:
                # Log transformation for better discrimination
                m_a = np.sign(desc_a[key]) * np.log10(np.abs(desc_a[key]) + 1)
                m_b = np.sign(desc_b[key]) * np.log10(np.abs(desc_b[key]) + 1)
                dist += abs(m_a - m_b)
        return dist


class GridVisualizer:
    """Utility class for analyzing and visualizing ARC-AGI grids."""

    @staticmethod
    def extract_color_layers(grid: np.ndarray) -> Dict[int, np.ndarray]:
        """Extract binary mask for each color present."""
        layers = {}
        for c in range(1, 10):
            mask = (grid == c)
            if np.any(mask):
                layers[c] = mask.astype(np.uint8)
        return layers

    @staticmethod
    def color_positions(grid: np.ndarray) -> Dict[int, List[Tuple[int, int]]]:
        """Get pixel positions for each color."""
        positions: Dict[int, List[Tuple[int, int]]] = {}
        h, w = grid.shape
        for r in range(h):
            for c in range(w):
                color = int(grid[r, c])
                if color > 0:
                    if color not in positions:
                        positions[color] = []
                    positions[color].append((r, c))
        return positions

    @staticmethod
    def compute_symmetry_score(grid: np.ndarray) -> Dict[str, float]:
        """Compute symmetry scores [0,1] for different symmetry types."""
        h, w = grid.shape
        scores = {}

        # Horizontal symmetry
        hpairs = 0
        hmatches = 0
        for r in range(h):
            for c in range(w // 2):
                hpairs += 1
                if grid[r, c] == grid[r, w - 1 - c]:
                    hmatches += 1
        scores["horizontal"] = hmatches / max(hpairs, 1)

        # Vertical symmetry
        vpairs = 0
        vmatches = 0
        for r in range(h // 2):
            for c in range(w):
                vpairs += 1
                if grid[r, c] == grid[h - 1 - r, c]:
                    vmatches += 1
        scores["vertical"] = vmatches / max(vpairs, 1)

        # Diagonal (main diagonal)
        dpairs = 0
        dmatches = 0
        for r in range(h):
            for c in range(w):
                if r != c and r < h and c < w:
                    dpairs += 1
                    if r < h and c < w:
                        if grid[r, c] == grid[c, r]:
                            dmatches += 1
        scores["diagonal"] = dmatches / max(dpairs, 1)

        return scores

    @staticmethod
    def grid_hash(grid: np.ndarray) -> str:
        """Compute a structural hash of the grid for quick comparison."""
        h, w = grid.shape
        # Encode shape and color distribution
        signature = f"{h}x{w}:"
        colors, counts = np.unique(grid, return_counts=True)
        for c, cnt in zip(colors, counts):
            if int(c) > 0:
                signature += f"{int(c)}:{int(cnt)}_"
        return signature.rstrip("_")

    @staticmethod
    def describe_grid(grid: np.ndarray) -> Dict[str, Any]:
        """Generate a comprehensive description of the grid."""
        h, w = grid.shape
        colors_present = sorted([int(c) for c in np.unique(grid) if c != 0])

        # Compute density
        foreground_pixels = np.sum(grid > 0)
        total_pixels = h * w
        density = foreground_pixels / max(total_pixels, 1)

        # Object count (connected components regardless of color)
        from scipy.ndimage import label
        labeled, n_objects = label((grid > 0).astype(int))

        return {
            "shape": (h, w),
            "n_colors": len(colors_present),
            "colors": colors_present,
            "foreground_pixels": int(foreground_pixels),
            "density": float(density),
            "n_objects": int(n_objects),
        }
# V55 Compatibility Adapters (bare function interface)
def compute_shape_descriptors(grid: np.ndarray) -> Dict[str, Any]:
    return GridVisualizer.describe_grid(grid)
def compute_hog(grid: np.ndarray) -> np.ndarray:
    from arc_dsr.visual_primitives import ShapeDescriptor
    return ShapeDescriptor._compute_hu_moments((grid > 0).astype(float))
def compute_convex_hull_ratio(grid: np.ndarray) -> float:
    h, w = grid.shape
    fg = float(np.sum(grid > 0))
    total = float(h * w)
    return fg / total if total > 0 else 0.0
