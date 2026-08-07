#!/usr/bin/env python3
"""
v31_deepcopy_bfs.py - ARC-AGI-3 solver v31
BFS com deepcopy do wrapper, step correto com data pra ACTION6.
"""

import os, sys, json, time, random, hashlib, copy
from arc_agi import Arcade
from arcengine import GameAction
from arcengine.enums import GameState
import numpy as np

os.environ["ARC_AGI_ENV_DIR"] = "/a0/usr/workdir/environment_files"

MAX_STATES = 3000
MAX_DEPTH = 15
TIMEOUT_S = 120

def frame_hash(arr):
    if arr is None:
        return ''
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def frame_from_fd(fd):
    if hasattr(fd, 'frame') and fd.frame is not None and len(fd.frame) > 0:
        return np.asarray(fd.frame[0])
    return None

def wrapper_state_str(fd):
    s = str(fd.state)
    lv = fd.levels_completed
    wl = fd.win_levels
    return f"{s}|lv{lv}|wl{wl}"

def safe_levels(fd):
    return (fd.levels_completed, fd.win_levels)

def step_and_fetch(wrapper, action_id):
    """Step one action, handle ACTION6 data."""
    try:
        action = GameAction.from_id(action_id)
        if action_id == 6:
            fd = wrapper.step(action, data={'x': 32, 'y': 32})
        else:
            fd = wrapper.step(action)
    except Exception as e:
        return None, None, f'STEP_ERR: {e}', 0
    if fd is None:
        return None, None, 'FD_NONE', 0
    frame = frame_from_fd(fd)
    st = wrapper_state_str(fd)
    lvl_int = fd.levels_completed + fd.win_levels
    return fd, frame, st, lvl_int


def solve_game(arcade, game_id):
    """BFS with deepcopy wrapper snapshots, matching v30 approach."""
    game_start = time.time()
    
    wrapper = arcade.make(game_id)
    fd_init = wrapper.reset()
    
    init_frame = frame_from_fd(fd_init)
    init_hash = frame_hash(init_frame)
    init_lvl = safe_levels(fd_init)
    avail = fd_init.available_actions if hasattr(fd_init, 'available_actions') and fd_init.available_actions else [1,2,3,4,5,6]
    
    # Frontier
    frontier = [(copy.deepcopy(wrapper), 0, (), init_hash)]
    visited = {init_hash}
    
    states_explored = 1
    nodes_popped = 0
    total_crashes = 0
    best_levels = init_lvl
    stagnation_count = 0
    
    while frontier and states_explored < MAX_STATES:
        if time.time() - game_start > TIMEOUT_S:
            break
        
        w, depth, path, h = frontier.pop(0)
        nodes_popped += 1
        
        if depth >= MAX_DEPTH:
            continue
        
        # Available actions
        actions = list(w.action_space)
        action_ids = [int(a.value) if hasattr(a, 'value') else int(a) for a in actions]
        
        expanded = False
        for aid in action_ids:
            if states_explored >= MAX_STATES:
                break
            if time.time() - game_start > TIMEOUT_S:
                break
            
            try:
                child = copy.deepcopy(w)
                fd, fr, st_str, lvl_int = step_and_fetch(child, aid)
                
                if fd is None:
                    continue
                
                fr_hash = frame_hash(fr) if fr is not None else hashlib.md5(st_str.encode()).hexdigest()[:16]
                
                # Check level-up
                cur_lv = safe_levels(fd)
                if cur_lv[0] + cur_lv[1] > best_levels[0] + best_levels[1]:
                    best_levels = cur_lv
                    # Reset BFS around this state
                    visited = {fr_hash}
                    frontier = [(child, depth + 1, path + (aid,), fr_hash)]
                    states_explored += 1
                    expanded = True
                    continue
                
                if fr_hash not in visited:
                    visited.add(fr_hash)
                    states_explored += 1
                    frontier.append((child, depth + 1, path + (aid,), fr_hash))
                    expanded = True
                    stagnation_count = 0
                else:
                    stagnation_count += 1
                    
            except Exception as e:
                total_crashes += 1
        
        if not expanded:
            stagnation_count += 3  # penalty
    
    elapsed = time.time() - game_start
    
    # Compute max depth from remaining frontier
    md = max(d for _, d, _, _ in frontier) if frontier else depth
    
    return {
        "game_id": game_id,
        "ok": True,
        "levels_completed": best_levels[0],
        "win_levels": best_levels[1],
        "total_levels": best_levels[0] + best_levels[1],
        "states_explored": states_explored,
        "nodes_popped": nodes_popped,
        "max_depth": md,
        "frontier_remaining": len(frontier),
        "crashes": total_crashes,
        "stagnation": stagnation_count,
        "time_seconds": round(elapsed, 2),
    }


def main():
    GAMES = [
        "sp80","cn04","bp35","tn36","cd82","re86","tr87","wa30","tu93","ls20",
        "ft09","g50t","lp85","sc25","dc12","ge84","jg12","ls07","ma36","nd33",
        "qa83","sf82","sp77","ti11","vi87"
    ]
    
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["sp80","cn04","bp35","tn36","cd82","ft09","g50t","lp85","sc25"]
    
    print(f"v31 — games={targets}", flush=True)
    
    arcade = Arcade()
    results = []
    
    for gid in targets:
        try:
            r = solve_game(arcade, gid)
            results.append(r)
            print(json.dumps(r), flush=True)
        except Exception as e:
            print(json.dumps({"game_id": gid, "ok": False, "error": str(e)}), flush=True)
            results.append({"game_id": gid, "ok": False, "error": str(e)})
    
    total_lv = sum(r.get("total_levels", 0) for r in results)
    total_st = sum(r.get("states_explored", 0) for r in results)
    total_cr = sum(r.get("crashes", 0) for r in results)
    
    print(f"\n=== v31 SUMMARY ===")
    print(f"Games: {len(results)}/{len(targets)} OK")
    print(f"Levels: {total_lv}  States: {total_st}  Crashes: {total_cr}")
    print()
    for r in sorted(results, key=lambda x: -x.get("total_levels", 0)):
        ok = "OK" if r.get("ok") else "FAIL"
        st_str = str(r.get("states_explored", "?"))
        print(f"  {r['game_id']:6s}: {ok:4s} levels={r.get('total_levels',0):2d} states={st_str:>5s} "
              f"depth={r.get('max_depth',0):2d} fr_left={r.get('frontier_remaining',0):3d} "
              f"crash={r.get('crashes',0):2d} stagn={r.get('stagnation',0):3d} "
              f"time={r.get('time_seconds',0):.1f}s")

if __name__ == "__main__":
    main()
