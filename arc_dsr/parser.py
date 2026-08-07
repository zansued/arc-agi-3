"""
ARC-DSR Parser Module
Extracts objects, properties, and scene graph from ARC-AGI grids.
Layer 1: Perception & Pattern Primitives
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Types
Grid = np.ndarray  # 2D numpy array of ints (0-black/background, 1-9 colors)
Coord = Tuple[int, int]  # (row, col)


@dataclass
class Object:
    """A contiguous object/blob extracted from the grid."""
    id: int
    color: int
    pixels: List[Coord]
    bbox: Tuple[int, int, int, int]  # (min_row, min_col, max_row, max_col)
    centroid: Tuple[float, float]  # (row_center, col_center)
    area: int
    shape: str = "unknown"  # rectangle, L-shape, line, dot, complex
    aspect_ratio: float = 1.0
    is_background: bool = False
    properties: Dict[str, Any] = field(default_factory=dict)

    @property
    def width(self) -> int:
        return self.bbox[3] - self.bbox[1] + 1

    @property
    def height(self) -> int:
        return self.bbox[2] - self.bbox[0] + 1


@dataclass
class SceneGraph:
    """A graph representing the spatial and semantic structure of a grid."""
    objects: List[Object]
    edges: List[Tuple[int, int, str]] = field(default_factory=list)  # (obj_a_id, obj_b_id, relation)
    grid_shape: Tuple[int, int] = (0, 0)
    global_properties: Dict[str, Any] = field(default_factory=dict)


class Parser:
    """
    Parses ARC-AGI grids into structured symbolic representations.

    Core capabilities:
    - Object extraction via flood-fill connected components
    - Property computation (position, size, color, shape)
    - Spatial relation detection
    - Scene graph construction
    """

    def __init__(self, grid: Grid):
        self.grid = grid
        self.height, self.width = grid.shape
        self._objects: List[Object] = []
        self._labels: np.ndarray = np.zeros_like(grid, dtype=int)
        self._scene_graph: Optional[SceneGraph] = None

    def parse(self) -> SceneGraph:
        """Full parse pipeline: extract objects → compute properties → build scene graph."""
        self._extract_objects()
        self._compute_properties()
        self._build_scene_graph()
        return self._scene_graph

    def _extract_objects(self) -> None:
        """Extract all non-background connected components via flood fill."""
        label_id = 1
        self._labels = np.zeros_like(self.grid, dtype=int)

        for r in range(self.height):
            for c in range(self.width):
                if self._labels[r, c] == 0 and self.grid[r, c] != 0:
                    color = int(self.grid[r, c])
                    pixels = self._flood_fill(r, c, color)
                    if pixels:
                        self._assign_object(label_id, color, pixels)
                        label_id += 1

    def _flood_fill(self, start_r: int, start_c: int, target_color: int) -> List[Coord]:
        """Non-recursive flood fill using stack (4-directional connectivity)."""
        pixels = []
        stack = [(start_r, start_c)]
        visited = set()

        while stack:
            r, c = stack.pop()
            if (r, c) in visited:
                continue
            if not (0 <= r < self.height and 0 <= c < self.width):
                continue
            if int(self.grid[r, c]) != target_color:
                continue
            if self._labels[r, c] != 0:
                continue

            visited.add((r, c))
            self._labels[r, c] = len(self._objects) + 1  # temporary label
            pixels.append((r, c))

            # 4-directional connectivity
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (nr, nc) not in visited:
                    stack.append((nr, nc))

        return pixels

    def _assign_object(self, label_id: int, color: int, pixels: List[Coord]) -> None:
        """Create an Object from a set of pixels."""
        rows = [p[0] for p in pixels]
        cols = [p[1] for p in pixels]

        min_r, max_r = min(rows), max(rows)
        min_c, max_c = min(cols), max(cols)
        centroid_r = sum(rows) / len(pixels)
        centroid_c = sum(cols) / len(pixels)

        area = len(pixels)
        bbox_width = max_c - min_c + 1
        bbox_height = max_r - min_r + 1
        aspect_ratio = bbox_width / max(bbox_height, 1)

        # Classify shape
        shape = self._classify_shape(pixels, bbox_width, bbox_height, area)

        obj = Object(
            id=label_id,
            color=color,
            pixels=pixels,
            bbox=(min_r, min_c, max_r, max_c),
            centroid=(centroid_r, centroid_c),
            area=area,
            shape=shape,
            aspect_ratio=aspect_ratio,
            is_background=False,
        )
        self._objects.append(obj)

    def _classify_shape(self, pixels: List[Coord], bw: int, bh: int, area: int) -> str:
        """Classify shape type based on pixel geometry."""
        if area == 1:
            return "dot"
        if area == max(bw, bh):
            return "line"
        if area == bw * bh:
            return "rectangle"
        # Check if L-shape (approx fill = 2*n - 1 for L of size n)
        if area >= bw + bh - 2 and area <= bw * bh - 2:
            return "L-shape"
        if area > bw * bh * 0.8:
            return "almost_rectangle"
        return "complex"

    def _compute_properties(self) -> None:
        """Compute additional properties for each object."""
        for obj in self._objects:
            obj.properties["pixel_density"] = obj.area / max(obj.width * obj.height, 1)
            obj.properties["is_symmetric_h"] = self._check_horizontal_symmetry(obj)
            obj.properties["is_symmetric_v"] = self._check_vertical_symmetry(obj)
            obj.properties["hollow"] = self._check_hollow(obj)

    def _check_horizontal_symmetry(self, obj: Object) -> bool:
        """Check if object pixels are symmetric horizontally within its bbox."""
        min_r, min_c, max_r, max_c = obj.bbox
        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                mirrored_c = min_c + (max_c - c)
                has_pixel = int(self.grid[r, c]) == obj.color
                has_mirror = int(self.grid[r, mirrored_c]) == obj.color
                if has_pixel != has_mirror:
                    return False
        return True

    def _check_vertical_symmetry(self, obj: Object) -> bool:
        """Check if object pixels are symmetric vertically within its bbox."""
        min_r, min_c, max_r, max_c = obj.bbox
        for r in range(min_r, max_r + 1):
            mirrored_r = min_r + (max_r - r)
            for c in range(min_c, max_c + 1):
                has_pixel = int(self.grid[r, c]) == obj.color
                has_mirror = int(self.grid[mirrored_r, c]) == obj.color
                if has_pixel != has_mirror:
                    return False
        return True

    def _check_hollow(self, obj: Object) -> bool:
        """Check if an object is hollow (border-only, empty interior)."""
        min_r, min_c, max_r, max_c = obj.bbox
        if obj.width <= 2 or obj.height <= 2:
            return False

        # Count non-object pixels inside bbox
        exterior = 0
        interior_total = 0
        for r in range(min_r, max_r + 1):
            for c in range(min_c, max_c + 1):
                if int(self.grid[r, c]) != obj.color:
                    exterior += 1
                interior_total += 1

        # If > 20% of bbox is empty, likely hollow
        return exterior / max(interior_total, 1) > 0.2

    def _build_scene_graph(self) -> None:
        """Build the scene graph: nodes = objects, edges = spatial relations."""
        edges: List[Tuple[int, int, str]] = []

        for i, obj_a in enumerate(self._objects):
            for j, obj_b in enumerate(self._objects):
                if i >= j:
                    continue

                # Detect spatial relations
                relations = self._detect_relations(obj_a, obj_b)
                for rel in relations:
                    edges.append((obj_a.id, obj_b.id, rel))

        self._scene_graph = SceneGraph(
            objects=self._objects,
            edges=edges,
            grid_shape=(self.height, self.width),
            global_properties={
                "n_objects": len(self._objects),
                "colors_present": sorted(set(o.color for o in self._objects)),
                "total_pixels": sum(o.area for o in self._objects),
                "fill_ratio": sum(o.area for o in self._objects) / max(self.height * self.width, 1),
            },
        )

    def _detect_relations(self, a: Object, b: Object) -> List[str]:
        """Detect spatial relations between two objects."""
        relations = []

        # Relative position (centroid-based)
        ar, ac = a.centroid
        br, bc = b.centroid

        if abs(ar - br) < 1.0 and bc > ac + 2:
            relations.append("right_of")
        elif abs(ar - br) < 1.0 and ac > bc + 2:
            relations.append("left_of")
        if abs(ac - bc) < 1.0 and br > ar + 2:
            relations.append("below")
        elif abs(ac - bc) < 1.0 and ar > br + 2:
            relations.append("above")

        # Containment
        a_contains_b = (
            a.bbox[0] <= b.bbox[0] and a.bbox[1] <= b.bbox[1]
            and a.bbox[2] >= b.bbox[2] and a.bbox[3] >= b.bbox[3]
        )
        b_contains_a = (
            b.bbox[0] <= a.bbox[0] and b.bbox[1] <= a.bbox[1]
            and b.bbox[2] >= a.bbox[2] and b.bbox[3] >= a.bbox[3]
        )
        if a_contains_b:
            relations.append("contains")
        if b_contains_a:
            relations.append("inside")

        # Adjacency (touching at edges)
        if self._are_adjacent(a, b):
            relations.append("adjacent")

        # Same color
        if a.color == b.color:
            relations.append("same_color")

        # Same shape
        if a.shape == b.shape:
            relations.append("same_shape")

        return relations

    def _are_adjacent(self, a: Object, b: Object) -> bool:
        """Check if two objects are adjacent (touching at border, not overlapping)."""
        for pa in a.pixels:
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = pa[0] + dr, pa[1] + dc
                if (nr, nc) in b.pixels:
                    return True
        return False

    @staticmethod
    def grid_from_arc(raw_grid: List[List[int]]) -> Grid:
        """Convert ARC-AGI format (list of lists) to numpy array."""
        return np.array(raw_grid, dtype=int)

    @staticmethod
    def grid_to_arc(grid: Grid) -> List[List[int]]:
        """Convert numpy array to ARC-AGI format (list of lists)."""
        return grid.tolist()


class ObjectComparator:
    """
    Compare two scene graphs to find correspondences and transformations.
    Used by Layer 2 (Analogical Reasoning) to align source→target.
    """

    @staticmethod
    def find_correspondence(
        source_graph: SceneGraph,
        target_graph: SceneGraph
    ) -> Dict[int, int]:
        """Find best matching between source objects and target objects.
        Returns {source_id: target_id} mapping."""
        mapping: Dict[int, int] = {}
        used_targets = set()

        # Score matrix: similarity between each source-target pair
        for src_obj in source_graph.objects:
            best_score = -1.0
            best_target = None

            for tgt_obj in target_graph.objects:
                if tgt_obj.id in used_targets:
                    continue

                score = ObjectComparator._similarity(src_obj, tgt_obj)
                if score > best_score:
                    best_score = score
                    best_target = tgt_obj.id

            if best_target is not None and best_score > 0.4:
                mapping[src_obj.id] = best_target
                used_targets.add(best_target)

        return mapping

    @staticmethod
    def _similarity(a: Object, b: Object) -> float:
        """Compute similarity score [0, 1] between two objects."""
        score = 0.0
        weights = {
            "color_match": 0.20,
            "size_match": 0.20,
            "shape_match": 0.25,
            "aspect_match": 0.15,
            "area_ratio": 0.20,
        }

        # Color match
        if a.color == b.color:
            score += weights["color_match"]

        # Size similarity (smaller/larger ratio)
        min_area = min(a.area, b.area)
        max_area = max(a.area, b.area)
        if max_area > 0:
            score += weights["area_ratio"] * (min_area / max_area)

        # Shape match
        if a.shape == b.shape:
            score += weights["shape_match"]

        # Aspect ratio similarity
        min_ar = min(a.aspect_ratio, b.aspect_ratio)
        max_ar = max(a.aspect_ratio, b.aspect_ratio)
        if max_ar > 0:
            score += weights["aspect_match"] * (min_ar / max_ar)

        # Centroid proximity (normalized by grid size)
        delta_r = abs(a.centroid[0] - b.centroid[0])
        delta_c = abs(a.centroid[1] - b.centroid[1])
        proximity = 1.0 - min(1.0, (delta_r + delta_c) / 20.0)
        score += weights["size_match"] * proximity

        return score


# ════════════════════════════════════════════════════════
# V55 Compatibility Adapters (bare function interface)
# ════════════════════════════════════════════════════════


def parse_grid(grid: Grid) -> SceneGraph:
    """Adapter: parse grid and return SceneGraph."""
    p = Parser(grid)
    return p.parse()


def flood_fill(grid: Grid, start_r: int, start_c: int, target_color: int) -> List[Coord]:
    """Adapter: flood fill from a starting coordinate."""
    p = Parser(grid)
    return p._flood_fill(start_r, start_c, target_color)


def classify_shape(pixels: List[Coord], bw: int, bh: int, area: int) -> str:
    """Adapter: classify shape of a blob."""
    p = Parser.__new__(Parser)
    return p._classify_shape(pixels, bw, bh, area)
