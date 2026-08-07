#!/usr/bin/env python3
"""
V62.3 — ARC-AGI-3 CLICK Game Solver Benchmark
Targets: ft09, lp85, r11l, s5i5, tn36, vc33
"""
import importlib.util
import sys, os, json, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/a0/usr/workdir')
from arcengine import ActionInput, GameAction, GameState

GAMES_DIR = Path("/a0/usr/workdir/environment_files")
RESULTS_DIR = Path("/a0/usr/workdir/arc_runs")
RESULTS_DIR.mkdir(exist_ok=True)

def load_game_class(game_id):
    game_dir = GAMES_DIR / game_id
    subdir = list(game_dir.iterdir())[0]
    py_file = subdir / f"{game_id}.py"
    spec = importlib.util.spec_from_file_location(game_id, py_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, obj in module.__dict__.items():
        if isinstance(obj, type) and hasattr(obj, '__bases__'):
            for base in obj.__bases__:
                if 'ARCBaseGame' in str(base):
                    return obj
    return None

def probe_mapping(game):
    """Find display→grid mapping by probing."""
    mapping = {}
    for dx in range(0, 130, 2):
        for dy in [dx]:
            r = game.camera.display_to_grid(dx, dy)
            if r:
                gx, gy = r
                gxi, gyi = int(gx), int(gy)
                key = f"{gxi},{gyi}"
                if key not in mapping:
                    mapping[key] = (dx, dy)
                    if len(mapping) >= 20:
                        return mapping
    return mapping

def analyze_game(game_id):
    result = {
        'game_id': game_id,
        'total_levels': 0,
        'solved_levels': 0,
        'level_results': [],
        'all_tags': [],
        'camera_mapping': {},
        'level0_data': {},
        'sprite_sample': [],
        'error': None,
    }
    try:
        GameClass = load_game_class(game_id)
        if not GameClass:
            result['error'] = 'Could not load game class'
            return result
        
        game = GameClass()
        result['total_levels'] = len(game._levels)
        
        # Camera
        cam = game.camera
        result['camera'] = {'x': cam.x, 'y': cam.y, 'w': cam.width, 'h': cam.height}
        
        # Probe mapping
        mapping = probe_mapping(game)
        result['camera_mapping'] = {k: v for k, v in list(mapping.items())[:10]}
        
        # Level 0 analysis
        l0 = game._levels[0]
        tags = l0.get_all_tags()
        result['all_tags'] = sorted(list(tags)) if tags else []
        
        if hasattr(l0, '_data'):
            result['level0_data'] = {k: (v if isinstance(v, (int,str,bool,list)) else str(v)[:80]) for k,v in l0._data.items()}
        
        # Sprite sample
        sprites = list(l0._sprites)[:20]
        for s in sprites:
            result['sprite_sample'].append({
                'name': s.name,
                'pos': (s.x, s.y),
                'tags': list(s.tags) if s.tags else [],
                'w': s.width, 'h': s.height,
            })
        
        # Try clicking on sprites
        level0_result = {'level': 0, 'attempts': [], 'solved': False}
        
        # Try click on each sprite type
        for s in sprites[:8]:
            sx, sy = s.x, s.y
            # Try various display coords
            for mult in [2, 4, 1, 8]:
                dx, dy = sx * mult, sy * mult
                try:
                    fresh = GameClass()
                    frame = fresh.perform_action(ActionInput(id=GameAction.ACTION6, data={'x': dx, 'y': dy}))
                    advanced = fresh.level_index > 0
                    state = str(frame.state) if frame else 'NONE'
                    grid = fresh.camera.display_to_grid(dx, dy)
                    level0_result['attempts'].append({
                        'sprite': s.name, 'grid_pos': (sx, sy),
                        'display': (dx, dy), 'grid_result': str(grid),
                        'state': state, 'advanced': advanced,
                    })
                    if advanced:
                        level0_result['solved'] = True
                        result['solved_levels'] += 1
                except Exception as e:
                    pass
        
        result['level_results'].append(level0_result)
        del game
        
    except Exception as e:
        result['error'] = f"{type(e).__name__}: {e}"
    
    return result

if __name__ == '__main__':
    print('V62.3 — CLICK Game Solver Benchmark')
    all_results = {}
    for game_id in ['ft09', 'lp85', 'r11l', 's5i5', 'tn36', 'vc33']:
        print(f'  Analyzing {game_id}...', end=' ')
        start = time.time()
        res = analyze_game(game_id)
        elapsed = time.time() - start
        err = res.get('error', 'ok')[:60]
        solved = res.get('solved_levels', 0)
        print(f'{solved} solved, {elapsed:.1f}s, error: {err}')
        all_results[game_id] = res
    
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    out_path = RESULTS_DIR / f'v62_3_results_{timestamp}.json'
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f'\nSaved to {out_path}')
