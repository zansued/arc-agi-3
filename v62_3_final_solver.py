#!/usr/bin/env python3
"""
V62.3 FINAL — Proper Solver for 6 CLICK games
Key fix: display_to_grid(display_x, display_y) maps to grid via stride
Camera(w=32) → display=grid*2 for ft09/vc33 (32px grid)
Camera(w=64) → display=grid*1 for r11l/s5i5/tn36 (64px grid)
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
    raise ValueError(f"No ARCBaseGame subclass in {py_file}")

def make_click(x_disp, y_disp):
    return ActionInput(id=GameAction.ACTION6, data={'x': x_disp, 'y': y_disp})

def grid_to_display(game, grid_x, grid_y, max_search=64):
    """Find display coords that map to given grid coords."""
    cam = game.camera
    for dx in range(max_search):
        for dy in range(max_search):
            result = cam.display_to_grid(dx, dy)
            if result and result[0] == grid_x and result[1] == grid_y:
                return (dx, dy)
    return None

def test_all_clicks(game, display_coords, level_idx, GameClass, max_depth=3):
    """Try clicking positions to find winning sequence."""
    for dx, dy in display_coords[:8]:
        for clicks in range(1, max_depth + 1):
            try:
                g = GameClass()
                for _ in range(level_idx):
                    try: g.next_level()
                    except: pass
                for _ in range(clicks):
                    act = make_click(dx, dy)
                    try: g.perform_action(act)
                    except: pass
                if g.current_level.state == GameState.WIN:
                    return {"solved": True, "coord": (dx, dy), "clicks": clicks, "total_actions": clicks}
            except:
                pass
    return None


def solve_ft09_level(GameClass, level_idx):
    """ft09: 8 Hkx tiles in 3x3, stride 4, click cycles neighbors via gqb palette."""
    try:
        g = GameClass()
        for _ in range(level_idx):
            try: g.next_level()
            except: break
    except Exception as e:
        return {"level": level_idx, "err": str(e)}
    
    hkx = list(g.current_level.get_sprites_by_tag("Hkx"))
    bsT = list(g.current_level.get_sprites_by_tag("bsT"))
    gqb = g.current_level.get_data("cwU") or [9, 8]
    max_steps = g.current_level.get_data("kCv") or 200
    
    if not hkx:
        return {"level": level_idx, "solved": False, "err": "no hkx tiles"}
    
    # Find display coords for each tile
    tile_display = {}
    for s in hkx:
        coord = grid_to_display(g, s.x, s.y, 64)
        if coord:
            tile_display[(s.x, s.y)] = coord
    
    if not tile_display:
        return {"level": level_idx, "solved": False, "err": "no display coords found"}
    
    display_list = list(tile_display.values())
    n_tiles = len(display_list)
    n_colors = len(gqb)
    
    # BFS over color states: each tile can be 0..n_colors-1 clicks
    # Brute force: try all color combinations for all tiles
    total_combos = n_colors ** n_tiles
    
    # If too many combos, try smaller search
    if total_combos > 10000:
        # Try each tile independently first
        for idx, (dx, dy) in enumerate(display_list):
            for clicks in range(1, n_colors * 2 + 2):
                try:
                    g = GameClass()
                    for _ in range(level_idx):
                        try: g.next_level()
                        except: pass
                    for _ in range(clicks):
                        act = make_click(dx, dy)
                        try: g.perform_action(act)
                        except: pass
                    if g.current_level.state == GameState.WIN:
                        return {"level": level_idx, "solved": True, "method": "single_tile", "idx": idx, "clicks": clicks, "coord": [dx, dy]}
                except:
                    pass
        return {"level": level_idx, "solved": False, "err": f"combo too large ({total_combos})"}
    
    # Try all color combinations
    for combo in itertools.product(range(n_colors), repeat=n_tiles):
        try:
            g = GameClass()
            for _ in range(level_idx):
                try: g.next_level()
                except: pass
            
            total_actions = 0
            for tile_idx, click_count in enumerate(combo):
                dx, dy = display_list[tile_idx]
                for _ in range(click_count):
                    act = make_click(dx, dy)
                    try: g.perform_action(act)
                    except: pass
                    total_actions += 1
                    if total_actions > max_steps:
                        raise TimeoutError("exceeded max_steps")
            
            if g.current_level.state == GameState.WIN:
                return {"level": level_idx, "solved": True, "method": "combinatorial", "combo": list(combo), "total_actions": total_actions}
        except:
            pass
    
    return {"level": level_idx, "solved": False}


def solve_generic_level(GameClass, level_idx):
    """Generic solver for sys_click games."""
    try:
        g = GameClass()
        for _ in range(level_idx):
            try: g.next_level()
            except: break
    except:
        return {"level": level_idx, "solved": False, "err": "init"}
    
    # Get sys_click sprites
    try:
        sys_click = list(g.current_level.get_sprites_by_tag("sys_click"))
    except:
        sys_click = []
    
    # Try finding display coords for sys_click sprites
    display_coords = []
    for s in sys_click:
        # Try center and edges of sprite
        for ox in [0, s.width // 2, s.width - 1]:
            for oy in [0, s.height // 2, s.height - 1]:
                coord = grid_to_display(g, s.x + ox, s.y + oy, 128)
                if coord and coord not in display_coords:
                    display_coords.append(coord)
    
    if not display_coords:
        return {"level": level_idx, "solved": False, "err": "no sys_click sprites mapped"}
    
    # Test each coord with 1-3 clicks
    return test_all_clicks(g, display_coords, level_idx, GameClass, max_depth=3)


if __name__ == "__main__":
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {}
    print(f"=== V62.3 FINAL CLICK Solver === {ts}")
    
    # ft09: specialized solver
    print("\n=== ft09 (specialized) ===")
    try:
        G = load_game_class("ft09")
        levels = 6
        solved = 0
        level_results = []
        for li in range(levels):
            lr = solve_ft09_level(G, li)
            level_results.append(lr)
            if lr.get("solved"):
                solved += 1
            print(f"  Level {li}: {'✓' if lr.get('solved') else '✗'} {lr.get('method', lr.get('err', ''))}")
        results["ft09"] = {"id": "ft09", "levels": levels, "solved": solved, "level_results": level_results}
    except Exception as e:
        results["ft09"] = {"id": "ft09", "err": str(e)}
        print(f"  ERROR: {e}")
    
    # Other games: generic solver
    for gid in ["lp85", "r11l", "s5i5", "tn36", "vc33"]:
        print(f"\n=== {gid} (generic) ===")
        try:
            G = load_game_class(gid)
            # Count levels
            g = G()
            n_levels = len(g._levels) if hasattr(g, '_levels') else len(g.levels) if hasattr(g, 'levels') else 0
            
            solved = 0
            level_results = []
            for li in range(min(n_levels, 8)):
                lr = solve_generic_level(G, li)
                if lr and lr.get("solved"):
                    solved += 1
                    print(f"  Level {li}: ✓ coord={lr.get('coord')} clicks={lr.get('clicks')}")
                else:
                    print(f"  Level {li}: ✗ {lr.get('err', 'no solution') if lr else 'no result'}")
                level_results.append(lr or {"level": li, "solved": False})
            
            results[gid] = {"id": gid, "levels": n_levels, "solved": solved, "level_results": level_results}
        except Exception as e:
            results[gid] = {"id": gid, "err": str(e)}
            print(f"  ERROR: {e}")
    
    # Save
    out_path = f"/a0/usr/workdir/arc_runs/v62_3_results_{ts}.json"
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n=== Saved: {out_path} ===")
    print(f"Results: {sum(r.get('solved', 0) for r in results.values() if 'err' not in r)}/{sum(r.get('levels', 0) for r in results.values() if 'err' not in r)}")
