#!/usr/bin/env python3
"""
ARC-AGI-3 Kaggle Submission — ARC-DSR (Deductive Symbolic Reasoner)

Submissão para a competição ARC Prize 2026 - ARC-AGI-3.

Baseado no framework ARC-DSR: parser simbólico + invariantes geométricas
+ Grid-Cell VSA + indução dedutiva de regras.

Autor: @zansued (Guilherme Zanini)
Competição: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ============================================================
# ARC-DSR PARSER: Extrai objetos e relações de grids
# ============================================================

@dataclass
class GridObject:
    """An object extracted from an ARC grid."""
    color: int
    pixels: List[Tuple[int, int]]
    centroid: Tuple[float, float]
    area: int
    bbox: Tuple[int, int, int, int]  # min_row, min_col, max_row, max_col
    shape: str = "unknown"
    symmetry_h: bool = False
    symmetry_v: bool = False
    hollow: bool = False


def flood_fill(grid: np.ndarray, start_row: int, start_col: int) -> List[Tuple[int, int]]:
    """Extract a connected component (4-directional) from the grid."""
    if grid[start_row, start_col] == 0:
        return []
    color = grid[start_row, start_col]
    rows, cols = grid.shape
    visited = set()
    stack = [(start_row, start_col)]
    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        if r < 0 or r >= rows or c < 0 or c >= cols:
            continue
        if grid[r, c] != color:
            continue
        visited.add((r, c))
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            stack.append((r + dr, c + dc))
    return list(visited)


def classify_shape(pixels: List[Tuple[int, int]], bbox: Tuple[int, int, int, int]) -> str:
    """Classify object shape based on pixel arrangement."""
    min_r, min_c, max_r, max_c = bbox
    h = max_r - min_r + 1
    w = max_c - min_c + 1
    area = len(pixels)
    bbox_area = h * w

    if area == 1:
        return "dot"
    if area == max(h, w):
        return "line"
    if area == bbox_area:
        return "rectangle"
    if area >= bbox_area * 0.85:
        return "almost_rectangle"
    # L-shape: missing exactly one quadrant
    if h >= 2 and w >= 2 and area >= bbox_area * 0.7 and area <= bbox_area * 0.85:
        return "L-shape"
    return "complex"


def parse_grid(grid: np.ndarray) -> List[GridObject]:
    """Parse an ARC grid into a list of objects."""
    rows, cols = grid.shape
    visited = np.zeros_like(grid, dtype=bool)
    objects = []

    for r in range(rows):
        for c in range(cols):
            if grid[r, c] != 0 and not visited[r, c]:
                pixels = flood_fill(grid, r, c)
                if not pixels:
                    continue
                color = grid[pixels[0]]
                for pr, pc in pixels:
                    visited[pr, pc] = True

                # Bounding box
                min_r = min(p[0] for p in pixels)
                max_r = max(p[0] for p in pixels)
                min_c = min(p[1] for p in pixels)
                max_c = max(p[1] for p in pixels)

                # Centroid
                centroid = (
                    sum(p[0] for p in pixels) / len(pixels),
                    sum(p[1] for p in pixels) / len(pixels),
                )

                # Symmetry checks
                obj_mask = np.zeros((max_r - min_r + 1, max_c - min_c + 1), dtype=bool)
                for pr, pc in pixels:
                    obj_mask[pr - min_r, pc - min_c] = True
                sym_h = bool(np.array_equal(obj_mask, obj_mask[:, ::-1]))
                sym_v = bool(np.array_equal(obj_mask, obj_mask[::-1, :]))

                objects.append(GridObject(
                    color=int(color),
                    pixels=pixels,
                    centroid=centroid,
                    area=len(pixels),
                    bbox=(min_r, min_c, max_r, max_c),
                    shape=classify_shape(pixels, (min_r, min_c, max_r, max_c)),
                    symmetry_h=sym_h,
                    symmetry_v=sym_v,
                ))

    return objects


# ============================================================
# INVARIANTES: Noether + WLKS + D4
# ============================================================

def compute_chromatic_mass(grid: np.ndarray) -> Dict[int, int]:
    """Count pixels per color (invariante Noether: conservação cromática)."""
    counts = {}
    for c in range(1, 10):
        counts[c] = int(np.sum(grid == c))
    return counts


def compute_betti_numbers(grid: np.ndarray) -> Dict[str, int]:
    """
    Compute topological features (Betti-0 and Betti-1 approximations).
    Betti-0 = number of connected components
    Betti-1 = number of holes
    """
    visited = np.zeros_like(grid, dtype=bool)
    objects = parse_grid(grid)
    # Betti-0 = number of objects
    betti_0 = len(objects)
    # Betti-1 = number of holes (hollow objects + background holes)
    holes = sum(1 for obj in objects if obj.hollow)
    return {"betti_0": betti_0, "betti_1": holes}


def compute_d4_signature(grid: np.ndarray) -> List[bool]:
    """
    Compute symmetry signature under D4 group.
    Returns [identity, rot90, rot180, rot270, reflect_h, reflect_v, reflect_d1, reflect_d2]
    """
    sig = []
    # Identity
    sig.append(True)
    # Rot90
    rot90 = np.rot90(grid)
    sig.append(bool(np.array_equal(grid, rot90)))
    # Rot180
    rot180 = np.rot90(grid, 2)
    sig.append(bool(np.array_equal(grid, rot180)))
    # Rot270
    rot270 = np.rot90(grid, 3)
    sig.append(bool(np.array_equal(grid, rot270)))
    # Reflect horizontal
    sig.append(bool(np.array_equal(grid, grid[:, ::-1])))
    # Reflect vertical
    sig.append(bool(np.array_equal(grid, grid[::-1, :])))
    # Reflect main diagonal
    sig.append(bool(np.array_equal(grid, grid.T)))
    # Reflect anti-diagonal
    anti = np.rot90(grid.T, 1)
    sig.append(bool(np.array_equal(grid, anti)))
    return sig


def compute_invariants(grid: np.ndarray) -> Dict[str, Any]:
    """Compute all invariants for a grid."""
    return {
        "chromatic_mass": compute_chromatic_mass(grid),
        "betti_numbers": compute_betti_numbers(grid),
        "d4_signature": compute_d4_signature(grid),
        "dimensions": list(grid.shape),
        "total_pixels": int(grid.shape[0] * grid.shape[1]),
    }


# ============================================================
# REGRA DE TRANSFORMAÇÃO (DSL)
# ============================================================

TRANSFORM_TYPES = [
    "identity", "move", "rotate", "reflect",
    "scale", "copy", "delete", "fill",
    "color_map", "crop", "expand", "symmetry",
]


@dataclass
class TransformRule:
    """A single transformation rule inferred from examples."""
    transform_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


def infer_transform(input_objs: List[GridObject], output_objs: List[GridObject]) -> TransformRule:
    """
    Given parsed input and output objects, infer the transformation rule.
    This is the core analogical mapping: Structure Mapping Theory.
    """
    # Count objects
    n_in = len(input_objs)
    n_out = len(output_objs)

    # Case 1: Same count → likely identity, move, reflect, or color_map
    if n_in == n_out:
        # Check color map
        color_pairs = {}
        for i, (inp, out) in enumerate(zip(input_objs, output_objs)):
            if inp.color != out.color:
                color_pairs[inp.color] = out.color
        if color_pairs and len(color_pairs) <= 3:
            return TransformRule("color_map", {"mapping": color_pairs}, 0.7)

        # Check centroid shifts
        shifts = []
        for inp, out in zip(input_objs, output_objs):
            dx = out.centroid[0] - inp.centroid[0]
            dy = out.centroid[1] - inp.centroid[1]
            shifts.append((dx, dy))
        avg_shift = (np.mean([s[0] for s in shifts]), np.mean([s[1] for s in shifts]))
        if abs(avg_shift[0]) > 0.5 or abs(avg_shift[1]) > 0.5:
            return TransformRule("move", {"dx": float(avg_shift[0]), "dy": float(avg_shift[1])}, 0.75)

        # Check size change
        area_ratios = [out.area / max(inp.area, 1) for inp, out in zip(input_objs, output_objs)]
        if all(abs(r - 1.0) > 0.1 for r in area_ratios):
            return TransformRule("scale", {"factor": float(np.mean(area_ratios))}, 0.6)

    # Case 2: Output has more objects → likely copy
    if n_out > n_in:
        return TransformRule("copy", {"delta": n_out - n_in}, 0.5)

    # Case 3: Output has fewer objects → likely delete
    if n_out < n_in:
        return TransformRule("delete", {"delta": n_in - n_out}, 0.5)

    return TransformRule("identity", {}, 0.3)


# ============================================================
# SOLVER PRINCIPAL
# ============================================================

class ARCDSR_Solver:
    """
    ARC-Deductive Symbolic Reasoner.
    
    Pipeline:
    1. Parse input/output pairs into objects
    2. Compute invariants for each grid
    3. Infer transformation rule via Structure Mapping
    4. Apply rule to test grid
    5. Return predicted output
    """

    def __init__(self):
        self.rules: List[TransformRule] = []

    def fit(self, train_pairs: List[Tuple[np.ndarray, np.ndarray]]):
        """
        Learn from training examples.
        train_pairs: list of (input_grid, output_grid) pairs
        """
        self.rules = []
        for inp, out in train_pairs:
            inp_objs = parse_grid(inp)
            out_objs = parse_grid(out)
            rule = infer_transform(inp_objs, out_objs)
            self.rules.append(rule)

        # If all rules agree, boost confidence
        types = [r.transform_type for r in self.rules]
        if len(set(types)) == 1 and len(types) > 1:
            for r in self.rules:
                r.confidence = min(1.0, r.confidence + 0.1)

    def predict(self, test_grid: np.ndarray) -> Optional[np.ndarray]:
        """Apply the inferred rule to a test grid."""
        if not self.rules:
            return test_grid.copy()

        # Take the highest-confidence rule
        best_rule = max(self.rules, key=lambda r: r.confidence)
        result = test_grid.copy()

        if best_rule.transform_type == "identity":
            return result

        if best_rule.transform_type == "color_map":
            mapping = best_rule.params.get("mapping", {})
            for old_color, new_color in mapping.items():
                result[result == old_color] = new_color
            return result

        if best_rule.transform_type == "move":
            dx = int(best_rule.params.get("dx", 0))
            dy = int(best_rule.params.get("dy", 0))
            return self._apply_translation(result, dx, dy)

        if best_rule.transform_type == "reflect":
            return result[:, ::-1].copy()

        if best_rule.transform_type == "rotate":
            return np.rot90(result, k=1).copy()

        if best_rule.transform_type == "scale":
            factor = best_rule.params.get("factor", 1.0)
            if abs(factor - 2.0) < 0.5:
                return np.repeat(np.repeat(result, 2, axis=0), 2, axis=1)
            return result

        if best_rule.transform_type == "symmetry":
            axis = best_rule.params.get("axis", "h")
            if axis == "h":
                return result[:, ::-1].copy()
            return result[::-1, :].copy()

        if best_rule.transform_type == "crop":
            bbox = best_rule.params.get("bbox", (0, 0, result.shape[0], result.shape[1]))
            min_r, min_c, max_r, max_c = bbox
            return result[min_r:max_r+1, min_c:max_c+1].copy()

        return result

    def _apply_translation(self, grid: np.ndarray, dx: int, dy: int) -> np.ndarray:
        """Apply a translation (dx, dy) to all non-zero pixels."""
        rows, cols = grid.shape
        new_grid = np.zeros_like(grid)
        for r in range(rows):
            for c in range(cols):
                if grid[r, c] != 0:
                    nr, nc = r + dx, c + dy
                    if 0 <= nr < rows and 0 <= nc < cols:
                        new_grid[nr, nc] = grid[r, c]
        return new_grid


# ============================================================
# INTERFACE KAGGLE ARC-AGI-3
# ============================================================

def solve(
    train_input: List[np.ndarray],
    train_output: List[np.ndarray],
    test_input: np.ndarray
) -> np.ndarray:
    """
    Main solve function called by Kaggle evaluation.
    
    Args:
        train_input: List of training input grids
        train_output: List of training output grids  
        test_input: The test input grid to solve
    
    Returns:
        Predicted output grid
    """
    solver = ARCDSR_Solver()
    train_pairs = list(zip(train_input, train_output))
    solver.fit(train_pairs)
    prediction = solver.predict(test_input)
    return prediction


# ============================================================
# CLI TESTING (for local debugging)
# ============================================================

if __name__ == "__main__":
    # Simple test with a 3x3 grid
    test_in = np.array([
        [0, 1, 0],
        [1, 0, 1],
        [0, 1, 0],
    ])
    test_out = np.array([
        [0, 2, 0],
        [2, 0, 2],
        [0, 2, 0],
    ])
    solver = ARCDSR_Solver()
    solver.fit([(test_in, test_out)])
    pred = solver.predict(test_in)
    print(f"Input:\n{test_in}")
    print(f"Expected:\n{test_out}")
    print(f"Predicted:\n{pred}")
    match = bool(np.array_equal(pred, test_out))
    print(f"Match: {match}")
    sys.exit(0 if match else 1)
