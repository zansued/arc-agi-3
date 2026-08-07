"""
v62_7_greedy_nav.py — Greedy Heuristic Navigator

Abordagem: para cada ação disponível, testa qual reduz a distância ao goal.
Como um humano jogando: tenta cada direção, vê qual aproxima do objetivo.

Não usa A*, não usa BFS, não planeja offline.
Age e observa, como um humano.
"""
import sys
import json
import time
import copy
import numpy as np
from pathlib import Path

sys.path.insert(0, '.')
from arc_agi import Arcade
from arcengine.enums import GameAction, GameState

ACTION_IDS = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4,
              GameAction.ACTION5, GameAction.ACTION6, GameAction.ACTION7]


def get_player_pos(game):
    """Get player world position from game state."""
    try:
        level = game.current_level
        players = level.get_sprites_by_tag("0017unajnymcki")
        if players:
            p = players[0]
            return (p.x, p.y)
        # Fallback: search for goal-like sprites
        all_spr = level.get_sprites()
        for s in all_spr:
            if s.pixels.shape == (3, 3) and getattr(s, 'tag', '') != '':
                return (s.x, s.y)
    except:
        pass
    return None


def get_exit_pos(game):
    """Get exit/goal world position."""
    try:
        level = game.current_level
        exits = level.get_sprites_by_tag("0015msvpvzxhqf")
        if exits:
            e = exits[0]
            return (e.x, e.y)
    except:
        pass
    return None


def get_nav_grid(game):
    """Get walkability nav grid."""
    try:
        level = game.current_level
        navs = level.get_sprites_by_tag("0005uvnhiglpvh")
        if navs:
            return navs[0]
    except:
        pass
    return None


def is_walkable(nav, x, y):
    """Check if world coords (x,y) are walkable on nav grid."""
    if nav is None:
        return True
    rx = x - nav.x
    ry = y - nav.y
    h, w = nav.pixels.shape
    if 0 <= ry < h and 0 <= rx < w:
        return nav.pixels[ry, rx] == 2
    return False


def manhattan(p1, p2):
    if p1 is None or p2 is None:
        return 99999
    return abs(p1[0]-p2[0]) + abs(p1[1]-p2[1])


def solve_level_greedy(wrapper, game, max_steps=500):
    """
    Greedy: para cada ação disponível, step() e vê qual reduz distância ao goal.
    Escolhe a melhor, commit, repete.
    """
    # Available actions
    acts = getattr(game, '_available_actions', [1,2,3,4])
    
    goal = get_exit_pos(game)
    if not goal:
        print(f"    No goal found", flush=True)
        return None
    
    print(f"    Goal at {goal}", flush=True)
    
    solution = []
    pos = get_player_pos(game)
    print(f"    Start at {pos}", flush=True)
    
    nav = get_nav_grid(game)
    
    visited_states = set()
    
    for step_idx in range(max_steps):
        # Check win
        if getattr(game, '_next_level', False):
            print(f"    WIN after {step_idx} actions", flush=True)
            return solution
        
        best_act = None
        best_dist = manhattan(pos, goal)
        best_wrapper = None
        
        if best_dist == 0:
            print(f"    At goal! Distance=0", flush=True)
            return solution
        
        # Try each action
        for action_id in acts:
            act = GameAction(f'ACTION{action_id}')
            
            # Clone state
            w_copy = copy.deepcopy(wrapper)
            try:
                fd = w_copy.step(act)
            except:
                continue
            
            new_game = w_copy._game
            new_pos = get_player_pos(new_game)
            new_dist = manhattan(new_pos, goal)
            
            if new_pos and abs(pos[0]-new_pos[0]) + abs(pos[1]-new_pos[1]) > 10:
                # Teleport - probably bad
                continue
            
            if new_dist < best_dist:
                best_dist = new_dist
                best_act = act
                best_wrapper = w_copy
        
        if best_act is None:
            print(f"    Stuck at step {step_idx}, pos={pos}", flush=True)
            return None
        
        # Commit best action
        wrapper.step(best_act)
        game = wrapper._game
        solution.append(best_act)
        pos = get_player_pos(game)
        
        if (step_idx+1) % 50 == 0:
            print(f"    Step {step_idx+1}: pos={pos}, dist={best_dist}", flush=True)
    
    print(f"    Max steps ({max_steps}) reached", flush=True)
    return None


def solve(game_id, max_levels=9, max_steps=500):
    results = {
        'game_id': game_id,
        'solver': 'v62_7_greedy_nav',
        'levels': [],
        'solved': 0,
        'total': 0,
        'time': 0,
    }
    
    print(f"\n{'='*60}", flush=True)
    print(f"  V62.7 Greedy Nav — {game_id}", flush=True)
    print(f"{'='*60}", flush=True)
    
    start = time.time()
    
    a = Arcade()
    wrapper = a.make(game_id, seed=0, save_recording=False)
    wrapper.step(GameAction.RESET)
    game = wrapper._game
    
    total = min(len(getattr(game, '_levels', [])), max_levels)
    results['total'] = total
    print(f"  Levels: {total}, max_steps/level={max_steps}", flush=True)
    
    for level_idx in range(total):
        print(f"\n  [{level_idx+1}/{total}] Level {level_idx+1}...", flush=True)
        wrapper.step(GameAction.RESET)
        game = wrapper._game
        
        solution = solve_level_greedy(wrapper, game, max_steps)
        
        level_res = {
            'level': level_idx + 1,
            'solved': solution is not None,
            'steps': len(solution) if solution else 0,
        }
        results['levels'].append(level_res)
        
        if solution:
            results['solved'] += 1
            print(f"    ** Level {level_idx+1} SOLVED! {len(solution)} steps **", flush=True)
        else:
            print(f"    ** Level {level_idx+1} FAILED **", flush=True)
    
    results['time'] = round(time.time() - start, 1)
    
    print(f"\n{'='*60}", flush=True)
    print(f"  RESULT: {results['solved']}/{results['total']} levels in {results['time']}s", flush=True)
    print(f"{'='*60}", flush=True)
    
    Path(f"v62_7_{game_id}_result.json").write_text(json.dumps(results, indent=2, default=str))
    print(f"  Saved v62_7_{game_id}_result.json", flush=True)
    
    return results


if __name__ == '__main__':
    args = sys.argv[1:]
    gid = args[0] if args else 'tu93'
    ml = int(args[1]) if len(args) > 1 else 9
    ms = int(args[2]) if len(args) > 2 else 500
    solve(gid, ml, ms)
