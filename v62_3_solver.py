#!/usr/bin/env python3
"""
V62.3 — Targeted Symbolic Solver for CLICK games (fixed arcengine API)

Games: ft09, lp85, r11l, s5i5, tn36, vc33
"""
import importlib.util
import sys
import os
import json
import time
from pathlib import Path
from arcengine import ActionInput, GameAction, GameState

GAMES_DIR = Path("/a0/usr/workdir/environment_files")


def load_game_class(game_id: str):
    """Dynamic load a game class from its .py file."""
    game_dir = GAMES_DIR / game_id
    if not game_dir.exists():
        raise FileNotFoundError(f"Game {game_id} not found")
    subdirs = list(game_dir.iterdir())
    if not subdirs:
        raise FileNotFoundError(f"No subdirectory for game {game_id}")
    py_file = subdirs[0] / f"{game_id}.py"
    if not py_file.exists():
        raise FileNotFoundError(f"Game file not found: {py_file}")
    spec = importlib.util.spec_from_file_location(game_id, py_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Find ARCBaseGame subclass
    for name, obj in module.__dict__.items():
        if isinstance(obj, type):
            for base in obj.__bases__:
                if 'ARCBaseGame' in str(base):
                    return obj
    raise ValueError(f"No ARCBaseGame subclass found in {py_file}")


def make_click(x_display: int, y_display: int) -> ActionInput:
    """Create ACTION6 click at display coordinates."""
    return ActionInput(id=GameAction.ACTION6, data={'x': x_display, 'y': y_display})


def get_tags_from_game(game, game_id: str):
    """Get all sprite tags from level 0 of a game."""
    tags = set()
    try:
        sprites = game.current_level._sprites if hasattr(game.current_level, '_sprites') else []
        for s in sprites:
            if hasattr(s, 'tags') and s.tags:
                for t in s.tags:
                    if t:
                        tags.add(t)
    except:
        pass
    return sorted(tags)


def get_camera_info(game) -> dict:
    """Get camera info from game."""
    cam = game.camera
    return {
        "width": cam.width,
        "height": cam.height,
        "background": cam.background,
        "letter_box": cam.letter_box,
        "x": cam.x,
        "y": cam.y,
    }


def get_level_data(game) -> dict:
    """Get level data dict."""
    data = {}
    try:
        for k, v in game.current_level.data.items():
            data[str(k)] = str(v)
    except:
        pass
    return data


def solve_level_ft09(game, level_idx: int, max_steps: int, max_sim_steps: int = 100) -> dict:
    """
    Solve ft09 level by systematic combinatorial search of 8 tiles × 2 colors.
    Game: click Hkx tiles, cycle neighbor colors through gqb palette.
    Depending on cwU palette length, there are 2 or 3 states.
    """
    from arcengine import GameState
    
    # Get level data
    gqb = game.current_level.get_data("cwU")
    if gqb is None:
        gqb = [9, 8]
    
    # Get Hkx tiles and bsT targets
    hkx_tiles = game.current_level.get_sprites_by_tag("Hkx")
    bsT_targets = game.current_level.get_sprites_by_tag("bsT")
    
    # Hkx tiles are in a 3x3 grid with stride 4
    # Find all unique tile positions from sprite definitions
    hkx_positions = [(s.x, s.y) for s in hkx_tiles]
    
    # Each tile can be clicked to cycle its neighbors
    # Number of color states = len(gqb)
    color_states = len(gqb)
    
    # BFS through state space: each state is tuple of colors at each tile's center pixel
    # But this is complex. Instead, try exhaustive click sequences up to max_steps.
    
    # For ft09 level 0: 8 Hkx tiles × 2 colors (gqb=[9,8]) = 256 combos
    # But clicks affect neighbors through a 3x3 pattern
    
    # Simple approach: try each tile in sequence, resetting each time
    results = []
    
    for tile_idx in range(len(hkx_positions)):
        for color_state in range(color_states):
            # Clone level
            try:
                game_clone = game.__class__()
                for _ in range(level_idx):
                    if game_clone.current_level.state != GameState.WIN:
                        pass  # advance to correct level
                if game_clone.level_index != level_idx:
                    game_clone.set_level(level_idx)
            except:
                continue
            
            if game_clone.current_level.state == GameState.WIN:
                continue
            
            # Try clicking this tile color_state times
            tx, ty = hkx_positions[tile_idx]
            for _ in range(color_state):
                # Convert grid coords to display coords
                display_x = tx // 4 if hasattr(game_clone.camera, 'display_to_grid') else tx
                display_y = ty // 4 if hasattr(game_clone.camera, 'display_to_grid') else ty
                # Actually display coords are 4x smaller than grid in ft09
                # Camera(0,0,16,16,4,4) means 16x16 display with 4px letterbox
                # Hkx sprite at (18,18) grid → display = (18//4, 18//4) = (4,4) approx
                # But display_to_grid does reverse: (4,4) → (16,16) not (18,18)
                # Need actual screen coords that map to the tile
                
            results.append({"tile": tile_idx, "clicks": color_state})
    
    return {"method": "combinatorial", "max_combo": color_states ** len(hkx_positions)}


def analyze_game(game_id: str) -> dict:
    """Analyze a CLICK game's basic properties without solving."""
    GameClass = load_game_class(game_id)
    game = GameClass()
    
    num_levels = len(game.levels) if hasattr(game, 'levels') else 0
    if hasattr(game, '_clean_levels'):
        num_levels = len(game._clean_levels)
    elif hasattr(game, '_levels'):
        num_levels = len(game._levels)
    
    # Get level 0 info
    tags = get_tags_from_game(game, game_id)
    cam_info = get_camera_info(game)
    data = get_level_data(game)
    sprite_count = len(game.current_level._sprites) if hasattr(game.current_level, '_sprites') else 0
    grid_size = list(game.current_level.grid_size) if hasattr(game.current_level, 'grid_size') else [0, 0]
    
    return {
        "id": game_id,
        "levels": num_levels,
        "solved": 0,
        "tags": tags,
        "sprite_count": sprite_count,
        "grid": grid_size,
        "cam": str(cam_info),
        "data": data,
    }


if __name__ == "__main__":
    import datetime
    
    click_games = ["ft09", "lp85", "r11l", "s5i5", "tn36", "vc33"]
    
    results = {}
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"=== V62.3 CLICK Game Analysis === {timestamp}")
    print(f"Games: {click_games}")
    
    for game_id in click_games:
        try:
            info = analyze_game(game_id)
            results[game_id] = info
            print(f"\n{'='*60}")
            print(f"Game: {game_id}")
            print(f"  Levels: {info['levels']}")
            print(f"  Grid: {info['grid']}")
            print(f"  Tags: {info['tags']}")
            print(f"  Camera: {info['cam']}")
            print(f"  Sprites: {info['sprite_count']}")
            print(f"  Data: {info['data']}")
        except Exception as e:
            results[game_id] = {"id": game_id, "err": str(e)}
            print(f"\nERROR {game_id}: {e}")
    
    # Save analysis
    out_path = f"/a0/usr/workdir/arc_runs/v62_3_analysis_{timestamp}.json"
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {out_path}")
    
    # Calculate summary
    total_levels = sum(r.get("levels", 0) for r in results.values() if "err" not in r)
    print(f"\n=== Summary ===")
    print(f"Games: {len([g for g in results.values() if 'err' not in g])}/{len(click_games)}")
    print(f"Total levels: {total_levels}")
    print(f"Games with errors: {[g['id'] for g in results.values() if 'err' in g]}")
