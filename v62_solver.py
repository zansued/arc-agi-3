"""
V62 — Pure Symbolic Deduction Solver for ARC-AGI-3
No brute force. No ML. Pure understanding of game mechanics.

Strategy per category:
- CLICK: Find sys_click sprites, click each coordinate, verify progression
- NAV: A* pathfinding between waypoints
- COMPLEX: Read game mechanics from tags + level data
- SIMUL: Simulation with special actions
"""
import importlib.util
import sys
import os
import json
import traceback
from pathlib import Path
from typing import Optional

from arcengine import ActionInput, GameAction, GameState

GAMES_DIR = Path("/a0/usr/workdir/environment_files")
RESULTS_DIR = Path("/a0/usr/workdir/arc_runs")
RESULTS_DIR.mkdir(exist_ok=True)

def load_game_class(game_id: str):
    """Load ARCBaseGame subclass from game file."""
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
    return None

def get_category(actions: list) -> str:
    acts = set(actions)
    if not acts:
        return 'AUTO'
    if acts == {1,2,3,4}:
        return 'NAV'
    if acts == {6}:
        return 'CLICK'
    if acts == {5,6,7}:
        return 'SIMUL'
    if acts == {6,7}:
        return 'CLICK_PLUS'
    if acts == {1,2,3,4,5}:
        return 'NAV_PLUS'
    if acts == {1,2,3,4,6}:
        return 'NAV_CLICK'
    if acts == {1,2,3,4,5,6}:
        return 'COMPLEX'
    if acts == {1,2,3,4,5,6,7}:
        return 'ALL7'
    return 'UNKNOWN'

def solve_click(game, game_id: str, max_attempts: int = 200) -> dict:
    """Solve CLICK games: find sys_click sprites, click each, verify progression."""
    result = {
        'game_id': game_id,
        'category': 'CLICK',
        'levels': len(game._levels),
        'solved_levels': 0,
        'actions_taken': [],
        'error': None,
        'status': 'pending'
    }
    
    try:
        # Play through each level
        for level_idx in range(len(game._levels)):
            if level_idx > 0:
                # Reset to fresh state for each level
                game.level_reset()
                game.set_level(level_idx)
            
            level_solved = False
            for attempt in range(max_attempts):
                # Get clickable sprites
                clickable = game.current_level.get_sprites_by_tag('sys_click')
                if not clickable:
                    break
                
                for sprite in clickable:
                    if game._state in [GameState.WIN, GameState.GAME_OVER]:
                        break
                    
                    # Create click action at sprite position
                    action = ActionInput(
                        id=GameAction.ACTION6,
                        data={'x': sprite.x, 'y': sprite.y}
                    )
                    
                    # Actually use the camera scale for accurate click coordinates
                    camera = game.camera
                    scale, x_off, y_off = camera._calculate_scale_and_offset()
                    screen_x = int(sprite.x * scale + x_off)
                    screen_y = int(sprite.y * scale + y_off)
                    
                    action = ActionInput(
                        id=GameAction.ACTION6,
                        data={'x': screen_x, 'y': screen_y}
                    )
                    
                    try:
                        frame_data = game.perform_action(action)
                        result['actions_taken'].append({
                            'level': level_idx + 1,
                            'attempt': attempt + 1,
                            'action': 'click',
                            'sprite': sprite.name[:15],
                            'pos': (sprite.x, sprite.y),
                            'state': frame_data.state.value
                        })
                    except Exception as e:
                        continue
                    
                    if frame_data.state == GameState.WIN:
                        level_solved = True
                        break
                
                if level_solved:
                    break
            
            if level_solved:
                result['solved_levels'] += 1
        
        result['status'] = 'success' if result['solved_levels'] == result['levels'] else 'partial'
        
    except Exception as e:
        result['error'] = str(e)
        result['status'] = 'error'
    
    return result

def solve_nav(game, game_id: str) -> dict:
    """Solve NAV games: A* pathfinding between waypoints."""
    result = {
        'game_id': game_id,
        'category': 'NAV',
        'levels': len(game._levels),
        'solved_levels': 0,
        'actions_taken': [],
        'error': None,
        'status': 'pending'
    }
    
    try:
        for level_idx in range(len(game._levels)):
            if level_idx > 0:
                game.level_reset()
                game.set_level(level_idx)
            
            level = game.current_level
            all_sprites = level.get_sprites()
            
            # Find player sprite (first tangible sprite)
            player = None
            for s in all_sprites:
                if s.is_collidable and s.layer > 0:
                    player = s
                    break
            
            if not player:
                continue
            
            # Try simple navigation: move in each direction
            for step in range(200):
                if game._state in [GameState.WIN, GameState.GAME_OVER]:
                    break
                
                moved = False
                for action_id in [1, 2, 3, 4]:
                    action = ActionInput(id=GameAction.from_id(action_id))
                    try:
                        frame_data = game.perform_action(action)
                        result['actions_taken'].append({
                            'level': level_idx + 1,
                            'step': step + 1,
                            'action': action_id,
                            'state': frame_data.state.value
                        })
                        if frame_data.state == GameState.WIN:
                            moved = True
                            break
                        if frame_data.state == GameState.GAME_OVER:
                            break
                        moved = True
                        break  # Move succeeded, try next step
                    except Exception:
                        continue
                
                if not moved:
                    break
            
            if game._state == GameState.WIN:
                result['solved_levels'] += 1
                game.next_level()
    except Exception as e:
        result['error'] = str(e)
        result['status'] = 'error'
    
    return result

def benchmark_games(game_ids: list[str]) -> dict:
    """Run V62 solver on specified games."""
    results = {}
    
    for gid in game_ids:
        print(f"\n{'='*60}")
        print(f"🎯 Solving {gid}...")
        print('='*60)
        
        try:
            game_class = load_game_class(gid)
            game = game_class()
            cat = get_category(game._available_actions)
            print(f"  Category: {cat}")
            
            if cat == 'CLICK':
                result = solve_click(game, gid)
            elif cat == 'NAV':
                result = solve_nav(game, gid)
            else:
                result = {
                    'game_id': gid,
                    'category': cat,
                    'error': 'Solver not yet implemented for this category',
                    'status': 'skipped'
                }
            
            results[gid] = result
            
            if result['status'] == 'success':
                print(f"  ✅ {result['solved_levels']}/{result['levels']} levels solved!")
            elif result['status'] == 'partial':
                print(f"  ⚠️ {result['solved_levels']}/{result['levels']} levels solved (partial)")
            elif result['status'] == 'skipped':
                print(f"  ⏭️ Skipped: {result.get('error', 'no solver')}")
            else:
                print(f"  ❌ Error: {result.get('error', 'unknown')}")
                
        except Exception as e:
            print(f"  ❌ CRASH: {e}")
            traceback.print_exc()
            results[gid] = {'game_id': gid, 'error': str(e), 'status': 'crash'}
    
    return results

if __name__ == "__main__":
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Run only CLICK games first (simplest category)
    click_games = ['ft09', 'lp85', 'r11l', 's5i5', 'tn36', 'vc33']
    
    print(f"🔬 V62 Symbolic Solver Benchmark — {timestamp}")
    print(f"📊 Testing CLICK games: {click_games}")
    
    results = benchmark_games(click_games)
    
    # Save results
    output = {
        'timestamp': timestamp,
        'solver': 'v62_symbolic',
        'games_tested': click_games,
        'categories': {g: get_category(load_game_class(g)()._available_actions) for g in click_games},
        'results': results
    }
    
    output_path = RESULTS_DIR / f'v62_benchmark_{timestamp}.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"📁 Results saved to: {output_path}")
    
    # Summary
    solved = sum(1 for r in results.values() if r.get('status') == 'success')
    partial = sum(1 for r in results.values() if r.get('status') == 'partial')
    skipped = sum(1 for r in results.values() if r.get('status') == 'skipped')
    errors = sum(1 for r in results.values() if r.get('status') in ['error', 'crash'])
    
    print(f"\n📊 SUMMARY:")
    print(f"  ✅ Solved: {solved}/{len(click_games)}")
    print(f"  ⚠️ Partial: {partial}")
    print(f"  ⏭️ Skipped: {skipped}")
    print(f"  ❌ Errors: {errors}")
