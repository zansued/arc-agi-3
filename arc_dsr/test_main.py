"""
ARC-DSR Test Suite — Fase 1: Parser & Visual Primitives

Tests the core modules with real ARC-AGI-3 data:
1. Parser: object extraction, scene graph
2. GC-VSA: spatial encoding, translation queries
3. Invariants: Noether, D4, WLKS
4. Visual Primitives: shape descriptors, Hu moments

Usage:
    python -m arc_dsr.test_main
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

# Ensure workdir is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from arc_agi import datasets
except ImportError:
    print("WARNING: arc_agi not installed. Using synthetic test grids instead.")
    datasets = None

from arc_dsr.parser import Parser, ObjectComparator, SceneGraph, Object
from arc_dsr.gc_vsa import GridCellVSA, VSAConfig, ObjectVSA
from arc_dsr.invariants import (
    NoetherInvariants, WLKSKernel, D4Transformer
)
from arc_dsr.visual_primitives import (
    ShapeDescriptor, GridVisualizer
)


def test_synthetic_grids():
    """Test with synthetic grids to verify basic functionality."""
    print("\n" + "=" * 60)
    print("🧪 TEST 1: Synthetic Grid Parser")
    print("=" * 60)

    # Grid 1: simple rectangle
    grid1 = np.array([
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ], dtype=int)

    parser1 = Parser(grid1)
    sg1 = parser1.parse()

    print(f"Grid shape: {grid1.shape}")
    print(f"Objects found: {len(sg1.objects)}")
    for obj in sg1.objects:
        print(f"  Object {obj.id}: color={obj.color}, shape={obj.shape}, "
              f"area={obj.area}, bbox={obj.bbox}, centroid=({obj.centroid[0]:.1f},{obj.centroid[1]:.1f})")
    print(f"Edges: {len(sg1.edges)}")
    print(f"Global: n_objects={sg1.global_properties['n_objects']}, "
          f"colors={sg1.global_properties['colors_present']}")

    # Grid 2: multiple objects (must be interpreted as one contiguous shape)
    # Actually let's make a grid with two separate rectangles
    grid2 = np.array([
        [0, 0, 0, 0, 0, 0, 0],
        [0, 2, 2, 0, 0, 3, 0],
        [0, 2, 2, 0, 0, 3, 0],
        [0, 0, 0, 0, 0, 0, 0],
    ], dtype=int)

    parser2 = Parser(grid2)
    sg2 = parser2.parse()

    print(f"\nGrid 2 shape: {grid2.shape}")
    print(f"Objects found: {len(sg2.objects)}")
    for obj in sg2.objects:
        print(f"  Object {obj.id}: color={obj.color}, shape={obj.shape}, "
              f"area={obj.area}, centroid=({obj.centroid[0]:.1f},{obj.centroid[1]:.1f})")
    print(f"Edges ({len(sg2.edges)}):")
    for edge in sg2.edges:
        print(f"  {edge[0]} --[{edge[2]}]--> {edge[1]}")

    return sg1, sg2


def test_noether_invariants():
    """Test Noether invariants computation."""
    print("\n" + "=" * 60)
    print("🧪 TEST 2: Noether Invariants & D4 Symmetry")
    print("=" * 60)

    grid = np.array([
        [0, 1, 1, 0],
        [0, 1, 1, 0],
        [0, 0, 0, 0],
    ], dtype=int)

    inv = NoetherInvariants(grid)
    all_inv = inv.compute_all()

    print(f"Chromatic mass: {all_inv['chromatic_mass']}")
    print(f"Color palette: {all_inv['color_palette']}")
    print(f"Components: {all_inv['connected_components']['n_components']}")
    print(f"Component sizes: {all_inv['connected_components']['component_sizes']}")
    print(f"Holes: {all_inv['topological_features']['n_holes']}")
    print(f"Betti: {all_inv['betti_numbers']}")
    print(f"D4 signature: {all_inv['d4_signature']['symmetry_order']} symmetries")

    # Test invariant distance
    rotated = np.rot90(grid, k=1)
    inv_rot = NoetherInvariants(rotated)
    dist = inv.invariant_distance(inv_rot)
    print(f"Invariant distance (original vs rotated): {dist:.4f} (should be small)")

    # Test D4 best transform
    name, score = D4Transformer.find_best_transform(grid, rotated)
    print(f"D4 best transform: {name} (score: {score:.4f})")

    return all_inv


def test_wl_kernel():
    """Test WL kernel signature."""
    print("\n" + "=" * 60)
    print("🧪 TEST 3: WL Kernel Signature")
    print("=" * 60)

    grid_a = np.array([
        [0, 1, 1, 0],
        [0, 1, 1, 0],
        [0, 0, 0, 0],
    ], dtype=int)

    grid_b = np.array([
        [0, 2, 2, 0],
        [0, 2, 2, 0],
        [0, 0, 0, 0],
    ], dtype=int)  # Different color, same structure

    grid_c = np.array([
        [0, 3, 0, 0],
        [3, 3, 3, 0],
        [0, 0, 0, 0],
    ], dtype=int)  # Different structure (T-shape)

    wl = WLKSKernel(n_iterations=2)

    sig_a = wl.compute_signature(grid_a)
    sig_b = wl.compute_signature(grid_b)
    sig_c = wl.compute_signature(grid_c)

    sim_ab = wl.signature_similarity(sig_a, sig_b)
    sim_ac = wl.signature_similarity(sig_a, sig_c)

    print(f"Grid A (rect) vs Grid B (rect, diff color): {sim_ab:.4f}")
    print(f"Grid A (rect) vs Grid C (T-shape): {sim_ac:.4f}")
    print(f"→ A-B should be HIGHER than A-C")

    return sim_ab, sim_ac


def test_gc_vsa():
    """Test Grid-Cell VSA encoding and translation."""
    print("\n" + "=" * 60)
    print("🧪 TEST 4: Grid-Cell VSA")
    print("=" * 60)

    config = VSAConfig(dimension=128, n_grid_modules=3)  # Small for fast test
    gc_vsa = GridCellVSA(config)

    # Encode two nearby positions
    v1 = gc_vsa.encode_position(3.0, 5.0)
    v2 = gc_vsa.encode_position(3.0, 5.0)  # Same position
    v3 = gc_vsa.encode_position(10.0, 20.0)  # Far position

    sim_same = gc_vsa.similarity(v1, v2)
    sim_far = gc_vsa.similarity(v1, v3)

    print(f"Same position similarity: {sim_same:.4f} (should be ~1.0)")
    print(f"Far position similarity: {sim_far:.4f} (should be < 0.5)")

    # Test translation
    v_translated = gc_vsa.translate(v1, -7.0, -15.0)
    sim_after_trans = gc_vsa.similarity(v_translated, v3)
    print(f"After translation similarity (→far): {sim_after_trans:.4f}")

    # Position distance
    dist_near = gc_vsa.position_distance((3.0, 5.0), (4.0, 6.0))
    dist_far = gc_vsa.position_distance((3.0, 5.0), (30.0, 50.0))
    print(f"Distance (near): {dist_near:.4f}")
    print(f"Distance (far): {dist_far:.4f}")

    return gc_vsa


def test_visual_primitives():
    """Test shape descriptors and Hu moments."""
    print("\n" + "=" * 60)
    print("🧪 TEST 5: Visual Primitives (Hu Moments)")
    print("=" * 60)

    # Rectangle mask
    rect_mask = np.zeros((10, 10), dtype=bool)
    rect_mask[2:8, 2:8] = True

    # Circle-like mask (roughly circular)
    circle_mask = np.zeros((10, 10), dtype=bool)
    cy, cx = 5, 5
    for r in range(10):
        for c in range(10):
            if (r - cy) ** 2 + (c - cx) ** 2 <= 9:
                circle_mask[r, c] = True

    desc_rect = ShapeDescriptor.from_binary_mask(rect_mask)
    desc_circle = ShapeDescriptor.from_binary_mask(circle_mask)

    print(f"Rectangle: area={desc_rect['area']}, elongation={desc_rect.get('elongation', 'N/A'):.2f}, "
          f"compactness={desc_rect['compactness']:.4f}")
    print(f"Circle:    area={desc_circle['area']}, elongation={desc_circle.get('elongation', 'N/A'):.2f}, "
          f"compactness={desc_circle['compactness']:.4f}")

    hu_dist = ShapeDescriptor.hu_distance(desc_rect, desc_circle)
    print(f"Hu distance (rect vs circle): {hu_dist:.4f}")

    # Same rectangle rotated should have small Hu distance
    rect_mask_90 = np.rot90(rect_mask)
    desc_rect_90 = ShapeDescriptor.from_binary_mask(rect_mask_90)
    hu_dist_same = ShapeDescriptor.hu_distance(desc_rect, desc_rect_90)
    print(f"Hu distance (rect vs rect@90°): {hu_dist_same:.4f} (should be small)")

    return desc_rect, desc_circle


def test_arc_games():
    """Test with real ARC-AGI game data if available."""
    print("\n" + "=" * 60)
    print("🧪 TEST 6: Real ARC-AGI Game Data")
    print("=" * 60)

    if datasets is None:
        print("SKIPPED: arc_agi not installed.")
        return

    try:
        arc_data = datasets.load_dataset()
        games = list(arc_data.keys())
        print(f"ARC-AGI dataset loaded: {len(games)} games")

        # Test first 3 games
        for game_id in games[:3]:
            game = arc_data[game_id]
            print(f"\n{'─' * 50}")
            print(f"Game: {game_id}")

            # Access training pairs
            for i, pair in enumerate(game.train):
                input_grid = np.array(pair.input, dtype=int)
                output_grid = np.array(pair.output, dtype=int) if pair.output else None

                print(f"  Train pair {i}: input={input_grid.shape} output={output_grid.shape if output_grid is not None else 'None'}")

                # Parse input
                parser = Parser(input_grid)
                sg = parser.parse()

                print(f"    Input: {len(sg.objects)} objects, "
                      f"{sg.global_properties['n_objects']} components, "
                      f"colors={sg.global_properties['colors_present']}")

                for obj in sg.objects:
                    print(f"      Obj {obj.id}: c={obj.color} s={obj.shape} a={obj.area} "
                          f"bbox=({obj.bbox[0]},{obj.bbox[1]})→({obj.bbox[2]},{obj.bbox[3]})")

                # Compare input→output if available
                if output_grid is not None:
                    parser_out = Parser(output_grid)
                    sg_out = parser_out.parse()
                    print(f"    Output: {len(sg_out.objects)} objects")

                    # Object correspondence
                    mapping = ObjectComparator.find_correspondence(sg, sg_out)
                    print(f"    Object correspondence: {mapping}")

            # Test pair (if available)
            if hasattr(game, 'test'):
                for i, pair in enumerate(game.test):
                    test_grid = np.array(pair.input, dtype=int) if pair.input else None
                    if test_grid is not None:
                        parser_test = Parser(test_grid)
                        sg_test = parser_test.parse()
                        print(f"  Test {i}: {len(sg_test.objects)} objects, "
                              f"shape={test_grid.shape}")

    except Exception as e:
        print(f"ERROR loading ARC-AGI data: {e}")
        import traceback
        traceback.print_exc()


def test_comparator():
    """Test ObjectComparator for correspondence detection."""
    print("\n" + "=" * 60)
    print("🧪 TEST 7: Object Comparator")
    print("=" * 60)

    grid_source = np.array([
        [0, 0, 0, 0, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ], dtype=int)

    grid_target = np.array([
        [0, 0, 0, 0, 0],
        [0, 0, 1, 1, 0],
        [0, 0, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ], dtype=int)  # Moved right by 1

    parser_src = Parser(grid_source)
    parser_tgt = Parser(grid_target)
    sg_src = parser_src.parse()
    sg_tgt = parser_tgt.parse()

    mapping = ObjectComparator.find_correspondence(sg_src, sg_tgt)
    print(f"Object correspondence: {mapping}")
    print(f"Source objects: {len(sg_src.objects)}")
    print(f"Target objects: {len(sg_tgt.objects)}")

    return mapping


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("🚀 ARC-DSR Fase 1 — Test Suite")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    tests = [
        ("Synthetic Grids", test_synthetic_grids),
        ("Noether Invariants", test_noether_invariants),
        ("WL Kernel", test_wl_kernel),
        ("GC-VSA", test_gc_vsa),
        ("Visual Primitives", test_visual_primitives),
        ("Object Comparator", test_comparator),
        ("ARC-AGI Games", test_arc_games),
    ]

    results = []
    start_time = time.time()

    for name, func in tests:
        try:
            func()
            results.append((name, "✅ PASS"))
        except Exception as e:
            print(f"\n💥 TEST FAILED: {name}")
            import traceback
            traceback.print_exc()
            results.append((name, f"❌ FAIL: {e}"))

    elapsed = time.time() - start_time

    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    for name, status in results:
        print(f"  {status} — {name}")
    print(f"\n⏱️  Total time: {elapsed:.2f}s")
    print(f"✅ {sum(1 for _, s in results if 'PASS' in s)}/{len(results)} tests passed")


if __name__ == "__main__":
    run_all_tests()
