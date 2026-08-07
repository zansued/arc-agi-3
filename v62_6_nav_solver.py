"""
v62_6_nav_solver.py — Solver Simbólico com A* para NAV games

Baseado na análise real do tu93.step():
- ACTION1=UP, ACTION2=DOWN, ACTION3=LEFT, ACTION4=RIGHT
- Nav grid (tag 0005uvnhiglpvh): pixel=2 = walkable, outros = blocked
- Player (tag 0017unajnymcki): navega pelo grid
- Exit (tag 0015msvpvzxhqf): posição de vitória

Uso: python3 v62_6_nav_solver.py <game_id> [max_levels]
"""
import sys
import json
import time
import numpy as np
from pathlib import Path
from collections import deque
from heapq import heappush, heappop

sys.path.insert(0, '.')
from arc_agi import Arcade
from arcengine.enums import GameAction, GameState

DIR_VEC = [(0,-1), (0,1), (-1,0), (1,0)]  # UP, DOWN, LEFT, RIGHT
DIR_ACT = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4]
NAV_COLOR = 2


def a_star(start, goal, grid):
    """A* pathfinding. start(px,py), goal(ex,ey). Nav grid: pixel=2 is walkable."""
    h, w = grid.shape
    sx, sy = start
    gx, gy = goal
    
    def walkable(x, y):
        return 0 <= y < h and 0 <= x < w and grid[y, x] == NAV_COLOR
    
    # If start not walkable, find nearest walkable
    if not walkable(sx, sy):
        best = None
        best_d = 999
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                nx, ny = sx+dx, sy+dy
                if walkable(nx, ny):
                    d = abs(dx)+abs(dy)
                    if d < best_d:
                        best_d = d
                        best = (nx, ny)
        if best:
            sx, sy = best
            print(f"    Start adjusted: ({sx},{sy})", flush=True)
        else:
            return None
    
    # If goal not walkable, find nearest walkable adjacent cell
    target_goal = (gx, gy)
    if not walkable(gx, gy):
        best = None
        best_d = 999
        for dx, dy in [(0,0), (0,-1), (0,1), (-1,0), (1,0)]:
            nx, ny = gx+dx, gy+dy
            if walkable(nx, ny):
                d = abs(dx)+abs(dy)
                if d < best_d:
                    best_d = d
                    best = (nx, ny)
        if best:
            gx, gy = best
            print(f"    Goal adjusted: ({gx},{gy}) -> exit at ({target_goal[0]},{target_goal[1]})", flush=True)
        else:
            return None
    
    # A*
    open_set = [(0, sx, sy)]
    came_from = {}
    g_score = {(sx, sy): 0}
    
    while open_set:
        _, cx, cy = heappop(open_set)
        if cx == gx and cy == gy:
            path = []
            current = (cx, cy)
            while current in came_from:
                prev = came_from[current]
                dx = current[0] - prev[0]
                dy = current[1] - prev[1]
                path.append((dx, dy))
                current = prev
            path.reverse()
            return path
        
        for dx, dy in DIR_VEC:
            nx, ny = cx+dx, cy+dy
            if not walkable(nx, ny):
                continue
            tent_g = g_score[(cx, cy)] + 1
            if (nx, ny) not in g_score or tent_g < g_score[(nx, ny)]:
                g_score[(nx, ny)] = tent_g
                f = tent_g + abs(gx-nx) + abs(gy-ny)
                heappush(open_set, (f, nx, ny))
                came_from[(nx, ny)] = (cx, cy)
    return None


def solve_one_level(wrapper):
    """Solve current level using A* pathfinding."""
    game = wrapper._game
    level = game.current_level
    
    nav_maps = level.get_sprites_by_tag("0005uvnhiglpvh")
    players = level.get_sprites_by_tag("0017unajnymcki")
    exits = level.get_sprites_by_tag("0015msvpvzxhqf")
    
    if not nav_maps or not players or not exits:
        print("    Missing sprites: nav=%s, player=%s, exit=%s" % (
            bool(nav_maps), bool(players), bool(exits)), flush=True)
        return None
    
    nav = nav_maps[0]
    player = players[0]
    exit_s = exits[0]
    
    # Relative coords
    px = player.x - nav.x
    py = player.y - nav.y
    ex = exit_s.x - nav.x
    ey = exit_s.y - nav.y
    
    print(f"    Player: world({player.x},{player.y}) nav({px},{py}) | Exit: world({exit_s.x},{exit_s.y}) nav({ex},{ey})", flush=True)
    
    path = a_star((px, py), (ex, ey), nav.pixels)
    if not path:
        print(f"    A*: NO PATH", flush=True)
        return None
    
    print(f"    A* path: {len(path)} steps", flush=True)
    
    # Convert to actions
    actions = []
    for dx, dy in path:
        for i, (vx, vy) in enumerate(DIR_VEC):
            if dx == vx and dy == vy:
                actions.append(DIR_ACT[i])
                break
    
    # Execute action sequence
    wrapper.step(GameAction.RESET)
    for i, act in enumerate(actions):
        try:
            fd = wrapper.step(act)
        except Exception as e:
            print(f"    Step {i}: FAILED - {e}", flush=True)
            return None
        
        if getattr(wrapper._game, '_next_level', False):
            # After next_level, we need to "re-enter" the game
            print(f"    >> LEVEL CLEAR in {i+1} actions!", flush=True)
            return actions[:i+1]
        
        if (i+1) % 30 == 0:
            print(f"    {i+1}/{len(actions)}...", flush=True)
    
    # Check win after full sequence
    if getattr(wrapper._game, '_next_level', False):
        print(f"    >> LEVEL CLEAR after full path ({len(actions)} actions)", flush=True)
        return actions
    print(f"    Full path ({len(actions)}) executed but no win", flush=True)
    return None


def solve(game_id, max_levels=9):
    """Solve all levels."""
    results = {
        'game_id': game_id,
        'solver': 'v62_6_nav_solver',
        'levels': [],
        'solved': 0,
        'total': 0,
        'time': 0,
    }
    
    print(f"\n{'='*60}", flush=True)
    print(f"  V62.6 Nav Solver — {game_id}", flush=True)
    print(f"{'='*60}", flush=True)
    
    start = time.time()
    
    a = Arcade()
    wrapper = a.make(game_id, seed=0, save_recording=False)
    wrapper.step(GameAction.RESET)
    
    game = wrapper._game
    total = min(len(getattr(game, '_levels', [])), max_levels)
    results['total'] = total
    print(f"  Levels: {total}", flush=True)
    
    for level_idx in range(total):
        print(f"\n  [{level_idx+1}/{total}] Level {level_idx+1}...", flush=True)
        wrapper.step(GameAction.RESET)
        
        solution = solve_one_level(wrapper)
        
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
    
    Path(f"v62_6_{game_id}_result.json").write_text(json.dumps(results, indent=2))
    print(f"  Saved v62_6_{game_id}_result.json", flush=True)
    
    return results


if __name__ == '__main__':
    args = sys.argv[1:]
    gid = args[0] if args else 'tu93'
    ml = int(args[1]) if len(args) > 1 else 9
    solve(gid, ml)
