#!/usr/bin/env python3
"""
V62.3 — Proper Solver for 6 CLICK games
Uses correct arcengine API and game-specific mechanics
"""
import importlib.util, sys, os, json, time, datetime, itertools
from pathlib import Path
from arcengine import ActionInput, GameAction, GameState

GAMES_DIR = Path("/a0/usr/workdir/environment_files")

def load_game_class(game_id: str):
    game_dir = GAMES_DIR / game_id
    subdirs = list(game_dir.iterdir())
    py_file = subdirs[0] / f"{game_id}.py"
    spec = importlib.util.spec_from_file_location(game_id, py_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, obj in module.__dict__.items():
        if isinstance(obj, type):
            for base in obj.__bases__:
                if 'ARCBaseGame' in str(base):
                    return obj
    raise ValueError(f"No ARCBaseGame subclass found")

def make_click(x_disp, y_disp):
    return ActionInput(id=GameAction.ACTION6, data={'x': x_disp, 'y': y_disp})

def find_display_coord(game, target_grid_x, target_grid_y, search_radius=12):
    """Find display coords that map to given grid coords."""
    cam = game.camera
    for dx in range(search_radius):
        for dy in range(search_radius):
            result = cam.display_to_grid(dx, dy)
            if result:
                gx, gy = result
                if gx == target_grid_x and gy == target_grid_y:
                    return (dx, dy)
    return None


def solve_ft09_level(GameClass, level_idx):
    """
    ft09 mechanics:
    - 8 Hkx tiles in 3x3 grid (stride 4)
    - Click cycles neighbor colors through gqb palette
    - Win: bsT target pixel[1][1] matches adjacent tile color
    - Strategy: try systematic click sequences using BFS
    """
    try:
        g = GameClass()
        for _ in range(level_idx):
            try: g.next_level()
            except: break
    except Exception as e:
        return {"level": level_idx, "err": f"init: {e}"}
    
    # Get Hkx tiles and bsT targets
    hkx_tiles = g.current_level.get_sprites_by_tag("Hkx")
    bsT_targets = g.current_level.get_sprites_by_tag("bsT")
    gqb = g.current_level.get_data("cwU") or [9, 8]
    
    if not hkx_tiles or not bsT_targets:
        return {"level": level_idx, "err": "no Hkx or bsT sprites"}
    
    # Find display coords for each Hkx tile
    hkx_display = {}
    for tile in hkx_tiles:
        coord = find_display_coord(g, tile.x, tile.y)
        if coord:
            hkx_display[(tile.x, tile.y)] = coord
    
    if not hkx_display:
        # Fallback: try broader search
        for tile in hkx_tiles:
            cam = g.camera
            for dx in range(48):
                for dy in range(48):
                    result = cam.display_to_grid(dx, dy)
                    if result and result[0] == tile.x and result[1] == tile.y:
                        hkx_display[(tile.x, tile.y)] = (dx, dy)
                        break
                if (tile.x, tile.y) in hkx_display:
                    break
    
    display_coords = list(hkx_display.values())
    
    if not display_coords:
        return {"level": level_idx, "err": "no display coords found"}
    
    # BFS: try increasing click sequences
    num_tiles = len(display_coords)
    max_clicks_per_tile = len(gqb)
    max_total_actions = min(g.current_level.get_data("kCv") or 200, 200)
    
    # Try each tile individually first (simple solve)
    for tile_idx, (dx, dy) in enumerate(display_coords):
        for clicks in range(1, max_clicks_per_tile):
            try:
                g2 = GameClass()
                for _ in range(level_idx):
                    try: g2.next_level()
                    except: break
                
                for _ in range(clicks):
                    action = make_click(dx, dy)
                    frame = g2.perform_action(action)
                
                if g2.current_level.state == GameState.WIN:
                    return {"level": level_idx, "solved": True, "method": "single_tile", "tile_idx": tile_idx, "clicks": clicks, "coord": [dx, dy]}
            except:
                pass
    
    # Try neighbor pair patterns (clicking one tile affects its 3x3 neighbors)
    # From the code: GBS offsets [(dx,dy)] for each (i,j) where elp[j][i]==1
    # Default elp = [[0,0,0],[0,1,0],[0,0,0]] → only center (0,0) is active
    # So clicking a tile only affects itself (offset (0,0)*4 = center)
    # Win: each bsT matches adjacent Hkx/NTi color
    # This means: click tiles until their colors match corresponding bsT targets
    
    # Try fixed-length sequences
    for seq_len in range(1, min(max_clicks_per_tile * 2, 8)):
        # Generate combinations: which tiles to click (with repeats, sequence matters)
        for click_seq in itertools.product(range(num_tiles), repeat=seq_len):
            try:
                g2 = GameClass()
                for _ in range(level_idx):
                    try: g2.next_level()
                    except: break
                
                for tile_idx in click_seq:
                    dx, dy = display_coords[tile_idx]
                    action = make_click(dx, dy)
                    frame = g2.perform_action(action)
                
                if g2.current_level.state == GameState.WIN:
                    seq_str = "-".join(str(i) for i in click_seq)
                    return {"level": level_idx, "solved": True, "method": "sequence", "sequence": seq_str, "len": seq_len}
            except:
                pass
    
    return {"level": level_idx, "solved": False}


def solve_generic_click(GameClass, game_id, max_levels=10):
    """Generic solver for click-based games."""
    # Get level count
    try:
        g = GameClass()
        levels = len(g._levels) if hasattr(g, '_levels') else len(g.levels) if hasattr(g, 'levels') else 0
    except:
        return {"id": game_id, "err": "init"}
    
    level_results = []
    solved_count = 0
    
    for level_idx in range(min(levels, max_levels)):
        # Get clickable sprites
        try:
            g = GameClass()
            for _ in range(level_idx):
                try: g.next_level()
                except: break
        except:
            level_results.append({"level": level_idx, "err": "init"})
            continue
        
        # Find all sys_click and button sprites
        clickable = []
        try:
            sys_click = g.current_level.get_sprites_by_tag("sys_click")
            clickable.extend(list(sys_click))
            for tag_suffix in ["button", "Hkx"]:
                all_sprites = list(g.current_level._sprites) if hasattr(g.current_level, '_sprites') else []
                for s in all_sprites:
                    if hasattr(s, 'tags') and s.tags:
                        for t in s.tags:
                            if tag_suffix in t and s not in clickable:
                                clickable.append(s)
                                break
        except:
            pass
        
        if not clickable:
            level_results.append({"level": level_idx, "solved": False, "err": "no clickable sprites"})
            continue
        
        # Map sprites to display coords
        display_coords = []
        for s in clickable:
            # Try various click positions within sprite
            for ox in [0, s.width // 3, s.width // 2, 2 * s.width // 3, s.width - 1]:
                for oy in [0, s.height // 3, s.height // 2, 2 * s.height // 3, s.height - 1]:
                    coord = find_display_coord(g, s.x + ox, s.y + oy)
                    if coord:
                        display_coords.append(coord)
                        break
                if display_coords and len(display_coords) % 5 != 0:
                    break
        
        if not display_coords:
            # Broader search
            for s in clickable:
                for dx in range(48):
                    for dy in range(48):
                        result = g.camera.display_to_grid(dx, dy)
                        if result:
                            gx, gy = result
                            if s.x <= gx < s.x + s.width and s.y <= gy < s.y + s.height:
                                display_coords.append((dx, dy))
                                break
                    if len(display_coords) > level_idx:
                        break
                if len(display_coords) > level_idx:
                    break
        
        # Try clicking each found position
        solved = False
        for dx, dy in display_coords[:8]:
            for repeat in [1, 2, 3]:
                try:
                    g2 = GameClass()
                    for _ in range(level_idx):
                        try: g2.next_level()
                        except: break
                    
                    for _ in range(repeat):
                        action = make_click(dx, dy)
                        frame = g2.perform_action(action)
                    
                    if g2.current_level.state == GameState.WIN:
                        level_results.append({"level": level_idx, "solved": True, "coord": [dx, dy], "repeats": repeat})
                        solved_count += 1
                        solved = True
                        break
                except:
                    pass
            if solved:
                break
        
        if not solved:
            level_results.append({"level": level_idx, "solved": False, "coords_tried": len(display_coords)})
    
    return {
        "id": game_id,
        "levels": levels,
        "solved": solved_count,
        "level_results": level_results,
    }


if __name__ == "__main__":
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {}
    
    print(f"=== V62.3 Proper CLICK Solver === {ts}")
    
    # ft09 gets specialized solver
    print("\n--- ft09 (specialized solver) ---")
    try:
        GameClass = load_game_class("ft09")
        total_levels = 6
        level_results = []
        solved = 0
        for li in range(total_levels):
            lr = solve_ft09_level(GameClass, li)
            level_results.append(lr)
            if lr.get("solved"):
                solved += 1
            print(f"  Level {li}: {'WIN' if lr.get('solved') else 'FAIL'} - {lr.get('method', lr.get('err', 'unknown'))}")
        results["ft09"] = {"id": "ft09", "levels": total_levels, "solved": solved, "level_results": level_results}
    except Exception as e:
        results["ft09"] = {"id": "ft09", "err": str(e)}
        print(f"  ERROR: {e}")
    
    # Other games: generic solver
    for gid in ["lp85", "r11l", "s5i5", "tn36", "vc33"]:
        print(f"\n--- {gid} (generic solver) ---")
        try:
            GameClass = load_game_class(gid)
            result = solve_generic_click(GameClass, gid)
            results[gid] = result
            print(f"  Levels: {result.get('levels', '?')}, Solved: {result.get('solved', '?')}")
            for lr in result.get('level_results', [])[:5]:
                print(f"    Level {lr.get('level', '?')}: {'WIN' if lr.get('solved') else 'FAIL'} - {lr.get('coord', lr.get('err', 'no solution'))}")
        except Exception as e:
            results[gid] = {"id": gid, "err": str(e)}
            print(f"  ERROR: {e}")
    
    # Save
    out_path = f"/a0/usr/workdir/arc_runs/v62_3_results_{ts}.json"
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n=== Saved to {out_path} ===")
    total = sum(r.get('levels', 0) for r in results.values() if 'err' not in r)
    solved = sum(r.get('solved', 0) for r in results.values() if 'err' not in r)
    print(f"Total: {solved}/{total} levels solved")
