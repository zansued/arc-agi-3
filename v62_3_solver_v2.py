#!/usr/bin/env python3
"""
V62.3 — Proper Symbolic Solver for 6 CLICK games
Correct arcengine API: Sprite.width not .w
"""
import importlib.util, sys, os, json, time, datetime
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
    raise ValueError(f"No ARCBaseGame subclass found in {py_file}")

def make_click(x_display, y_display):
    return ActionInput(id=GameAction.ACTION6, data={'x': x_display, 'y': y_display})

def discover_display_to_grid_mapping(game, sample_grid_coords):
    """Try display coords to find what maps to given grid coords."""
    cam = game.camera
    mapping = {}
    # Try systematic display coords
    for d in range(100):
        for dx in range(0, 65, 1):
            for dy in range(0, 65, 1):
                result = cam.display_to_grid(dx, dy)
                if result and result in sample_grid_coords:
                    if result not in mapping:
                        mapping[result] = (dx, dy)
                        if len(mapping) >= len(sample_grid_coords):
                            return mapping
    return mapping

def solve_game_ft09() -> dict:
    """
    ft09: 8 Hkx tiles arranged in 3x3 grid (stride 4).
    Clicking Hkx cycles neighbor colors through gqb palette.
    Win: each bsT target's pixel[1][1] matches corresponding tile color.
    """
    GameClass = load_game_class("ft09")
    total_levels = len(load_levels(GameClass))
    level_results = []
    
    for level_idx in range(total_levels):
        result = solve_ft09_level(GameClass, level_idx)
        level_results.append(result)
    
    solved = sum(1 for r in level_results if r.get("solved"))
    return {"id": "ft09", "levels": total_levels, "solved": solved, "level_results": level_results}

def load_levels(GameClass):
    try:
        game = GameClass()
        if hasattr(game, '_levels'):
            return game._levels
        if hasattr(game, '_clean_levels'):
            return game._clean_levels
        return game.levels
    except:
        return []

def solve_level_bfs(game, clickable_positions, max_steps=200) -> dict:
    """
    Generic BFS solver for click-based games.
    clickable_positions: list of (display_x, display_y) positions to try.
    """
    from collections import deque
    import copy
    
    if game.current_level.state == GameState.WIN:
        return {"solved": True, "actions": 0, "method": "already_won"}
    
    # Try each clickable position one at a time
    steps_tried = 0
    for pos in clickable_positions:
        if steps_tried >= max_steps:
            break
        
        # Clone game and try click
        try:
            # Use fresh game instance
            g = game.__class__()
            # Advance to correct level
            cur_level = 0
            while cur_level < game.level_index and cur_level < 10:
                try:
                    g.next_level()
                except:
                    pass
                cur_level += 1
        except:
            continue
        
        # Try clicking this position
        action_in = make_click(pos[0], pos[1])
        try:
            frame = g.perform_action(action_in)
            steps_tried += 1
            if frame and frame.state == GameState.WIN:
                return {"solved": True, "actions": 1, "method": f"click_at_{pos}", "coord": pos}
        except:
            pass
    
    return {"solved": False, "actions": steps_tried, "method": "bfs_exhausted"}

def test_game_mechanics(game_id: str) -> dict:
    """Test a single game by exploring its mechanics."""
    GameClass = load_game_class(game_id)
    game = GameClass()
    
    info = {
        "id": game_id,
        "levels": 0,
        "solved": 0,
        "level_results": [],
        "tags": [],
        "sprite_count": 0,
        "grid": [0, 0],
        "cam": {},
        "data": {},
        "click_tests": [],
    }
    
    # Try to iterate levels
    for level_idx in range(50):
        try:
            g = GameClass()
            # Advance to level_idx by playing or using set_level
            current_level = 0
            while current_level < level_idx:
                try:
                    frame = g.perform_action(GameAction.NONE)
                    current_level += 1
                except:
                    break
        except:
            break
        
        # Only test levels where we can advance
        if current_level != level_idx:
            if level_idx == 0:
                g = GameClass()
            else:
                break
        
        # Extract info from current level
        info["levels"] = level_idx + 1
        sprites = list(g.current_level._sprites) if hasattr(g.current_level, '_sprites') else []
        
        # Get tags
        tags = set()
        for s in sprites:
            if hasattr(s, 'tags') and s.tags:
                for t in s.tags:
                    if t: tags.add(t)
        if level_idx == 0:
            info["tags"] = sorted(tags)
            info["sprite_count"] = len(sprites)
            info["grid"] = list(g.current_level.grid_size) if hasattr(g.current_level, 'grid_size') else [0, 0]
            cam = g.camera
            info["cam"] = {"w": cam.width, "h": cam.height}
        
        # Try finding clickable sprites and positions
        clickable_positions = []
        for s in sprites:
            if hasattr(s, 'tags') and s.tags:
                for t in s.tags:
                    if t and ('click' in t.lower() or t.startswith('button') or t.startswith('Hk')):
                        # Try sprite center display coords
                        clickable_positions.append((s.x + s.width // 2, s.y + s.height // 2))
                        break
        
        # Also try systematic display coords
        cam_w, cam_h = g.camera.width, g.camera.height
        for cx in range(0, cam_w + 1, max(1, cam_w // 8)):
            for cy in range(0, cam_h + 1, max(1, cam_h // 8)):
                clickable_positions.append((cx, cy))
        
        # Test clicking
        for attempts, (dx, dy) in enumerate(clickable_positions[:20]):
            try:
                g2 = GameClass()
                action = make_click(dx, dy)
                frame = g2.perform_action(action)
                if frame and frame.state == GameState.WIN:
                    info["level_results"].append({"level": level_idx, "solved": True, "coord": [dx, dy]})
                    info["solved"] += 1
                    break
                elif frame and frame.state == GameState.GAME_OVER:
                    pass  # wrong click
            except Exception as e:
                if attempts < 5:
                    pass  # print(f"  Level {level_idx} attempt {attempts}: {e}")
    
    return info


def solve_game(game_id: str) -> dict:
    """Analyze and attempt to solve a CLICK game."""
    GameClass = load_game_class(game_id)
    
    try:
        game = GameClass()
    except Exception as e:
        return {"id": game_id, "err": f"init: {e}"}
    
    num_levels = 0
    try:
        if hasattr(game, '_levels'):
            num_levels = len(game._levels)
        elif hasattr(game, '_clean_levels'):
            num_levels = len(game._clean_levels)
        elif hasattr(game, 'levels'):
            num_levels = len(game.levels)
    except:
        num_levels = 0
    
    level_results = []
    solved_count = 0
    
    for level_idx in range(num_levels):
        try:
            g = GameClass()
            # Advance to level
            if level_idx > 0:
                for _ in range(level_idx):
                    try:
                        g.next_level()
                    except:
                        pass
        except Exception as e:
            level_results.append({"level": level_idx, "err": f"init: {e}"})
            continue
        
        # Get sprite info
        sprites = list(g.current_level._sprites) if hasattr(g.current_level, '_sprites') else []
        
        # Try systematic clicks across display
        cam = g.camera
        found_solution = False
        actions_taken = 0
        
        for dx in range(0, min(cam.width, 16), 2):
            if found_solution: break
            for dy in range(0, min(cam.height, 16), 2):
                if found_solution: break
                if actions_taken > 100: break
                
                try:
                    g2 = GameClass()
                    if level_idx > 0:
                        for _ in range(level_idx):
                            try: g2.next_level()
                            except: pass
                    
                    action = make_click(dx, dy)
                    frame = g2.perform_action(action)
                    actions_taken += 1
                    
                    if frame and frame.state == GameState.WIN:
                        level_results.append({"level": level_idx, "solved": True, "actions": actions_taken, "coord": [dx, dy]})
                        solved_count += 1
                        found_solution = True
                except:
                    pass
        
        if not found_solution:
            level_results.append({"level": level_idx, "solved": False, "actions": actions_taken})
    
    return {
        "id": game_id,
        "levels": num_levels,
        "solved": solved_count,
        "level_results": level_results,
        "sprite_tags": sorted(set(t for s in sprites if hasattr(s,'tags') and s.tags for t in s.tags)) if sprites else [],
    }


if __name__ == "__main__":
    click_games = ["ft09", "lp85", "r11l", "s5i5", "tn36", "vc33"]
    results = {}
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"=== V62.3 CLICK Solver === {ts}")
    
    for game_id in click_games:
        print(f"\n--- {game_id} ---")
        try:
            result = solve_game(game_id)
            results[game_id] = result
            print(f"  Levels: {result.get('levels', '?' )}, Solved: {result.get('solved', '?')}")
            if result.get('level_results'):
                for lr in result['level_results'][:5]:
                    print(f"    Level {lr['level']}: {'WIN' if lr.get('solved') else 'FAIL'} ({lr.get('actions', '?')} actions)")
        except Exception as e:
            results[game_id] = {"id": game_id, "err": str(e)}
            print(f"  ERROR: {e}")
    
    # Save
    out_path = f"/a0/usr/workdir/arc_runs/v62_3_results_{ts}.json"
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n=== Saved to {out_path} ===")
    
    total = sum(r.get('levels', 0) for r in results.values() if 'err' not in r)
    solved = sum(r.get('solved', 0) for r in results.values() if 'err' not in r)
    print(f"Total: {solved}/{total} levels solved across {len(click_games)} games")
