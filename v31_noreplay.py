#!/usr/bin/env python3
"""
v31_noreplay — v31_hybrid_bfs with archive replay DISABLED.
Pure stateful deepcopy BFS identical to v30 logic.
"""
import copy
import csv
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction
from arcengine.enums import GameState

MAX_STEPS = 500
OUT_DIR = 'arc_runs'
MAX_PLY = 100
STAGNATION_WINDOW = 50
SMOKE_GAMES = ['tn36', 'sp80', 'bp35', 'cn04']
OUT_DIR_P = Path(OUT_DIR)

def ensure_dir(path): os.makedirs(path, exist_ok=True)
def now_iso(): return datetime.now(timezone.utc).isoformat()
def frame_from_fd(fd):
    if hasattr(fd, 'frame') and fd.frame is not None and len(fd.frame) > 0:
        return np.asarray(fd.frame[0])
    return None
def frame_hash(arr):
    if arr is None: return ''
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()
def fd_action_list(fd):
    avail = getattr(fd, 'available_actions', None)
    if avail is not None and len(avail) > 0: return [int(a) for a in avail]
    return [0,1,2,3,4,5,6]
def is_win(sv): return sv in (GameState.WIN, 'WIN')
def is_game_over(sv): return sv in (GameState.GAME_OVER, 'GAME_OVER')
def wrapper_state_str(fd):
    st = getattr(fd, 'state', None)
    return str(st) if st is not None else 'UNKNOWN'
def safe_wrapper_levels(fd):
    return int(getattr(fd, 'levels_completed', 0) or 0)
def snapshot_wrapper(w): return copy.deepcopy(w)
def step_and_fetch(wrapper, action_id):
    try:
        action = GameAction.from_id(action_id)
        if action_id == 6: fd = wrapper.step(action, data={'x': 32, 'y': 32})
        else: fd = wrapper.step(action)
    except Exception as e: return None, None, f'STEP_ERR: {e}', 0
    if fd is None: return None, None, 'FD_NONE', 0
    frame = frame_from_fd(fd)
    st = wrapper_state_str(fd)
    lvl = safe_wrapper_levels(fd)
    return fd, frame, st, lvl

def bfs_solve_game_pure(game_id):
    """Pure stateful BFS - NO archive replay layer."""
    arcade = Arcade()
    wrapper = arcade.make(game_id)
    if wrapper is None:
        return {'game_id': game_id, 'status': 'ERROR', 'error': 'Arcade.make returned None'}

    fd_init = wrapper.reset()
    init_frame = frame_from_fd(fd_init)
    init_hash = frame_hash(init_frame)
    init_levels = safe_wrapper_levels(fd_init)
    avail_actions = fd_action_list(fd_init)

    class BFSSnapshotNode:
        __slots__ = ('wrapper', 'state_hash', 'action_seq', 'depth', 'levels_completed')
        def __init__(self, w, h, seq, d, lvl):
            self.wrapper = w; self.state_hash = h; self.action_seq = seq
            self.depth = d; self.levels_completed = lvl

    init_node = BFSSnapshotNode(snapshot_wrapper(wrapper), init_hash, (), 0, init_levels)
    frontier = [init_node]
    safe_stash = [init_node]
    visited_states = {init_hash}
    total_actions = 0
    nodes_expanded = 0
    best_levels = 0
    best_action_str = ''
    best_state_hash = init_hash
    levels_progress_events = []
    expansions_without_new_state = 0
    fallbacks_triggered = 0

    while frontier and total_actions < MAX_STEPS:
        if expansions_without_new_state >= STAGNATION_WINDOW and len(safe_stash) > 1:
            fallbacks_triggered += 1
            candidates = [n for n in safe_stash if n.depth > 0]
            if not candidates: candidates = safe_stash
            fb = random.choice(candidates)
            frontier.insert(0, BFSSnapshotNode(snapshot_wrapper(fb.wrapper), fb.state_hash, fb.action_seq, fb.depth, fb.levels_completed))
            expansions_without_new_state = 0

        node = frontier.pop(0)
        shuffled = list(avail_actions)
        random.shuffle(shuffled)

        for act in shuffled:
            if total_actions >= MAX_STEPS: break
            clone = snapshot_wrapper(node.wrapper)
            fd, frame, state_str, levels = step_and_fetch(clone, act)
            total_actions += 1
            nodes_expanded += 1
            if frame is None: continue
            h = frame_hash(frame)
            if levels > best_levels:
                best_levels = levels
                new_seq = node.action_seq + (act,)
                best_action_str = str(new_seq)
                best_state_hash = h
                levels_progress_events.append({'seq': best_action_str, 'levels': best_levels, 'hash': h})
            if h not in visited_states:
                visited_states.add(h)
                expansions_without_new_state = 0
                new_depth = node.depth + 1
                new_node = BFSSnapshotNode(clone, h, node.action_seq + (act,), new_depth, levels)
                if new_depth < MAX_PLY and not is_game_over(state_str):
                    frontier.append(new_node)
                safe_stash.append(new_node)
            else:
                expansions_without_new_state += 1

    return {
        'game_id': game_id, 'status': 'OK',
        'nodes_expanded': nodes_expanded,
        'total_actions_consumed': total_actions,
        'unique_states_discovered': len(visited_states),
        'best_levels_completed': best_levels,
        'best_action_sequence': best_action_str,
        'best_state_hash': best_state_hash,
        'levels_progress_events': len(levels_progress_events),
        'frontier_remaining': len(frontier),
        'fallbacks_triggered': fallbacks_triggered,
    }

# Run on all 4 smoke games
prefix = 'v31_noreplay'
ensure_dir(OUT_DIR_P)
all_stats = []
print(f"[{now_iso()}] v31 PURE BFS (no archive replay) on {len(SMOKE_GAMES)} smoke games")
print("="*60)

for game_id in SMOKE_GAMES:
    print(f"[{now_iso()}] Processing {game_id}...")
    start = time.time()
    try:
        stats = bfs_solve_game_pure(game_id)
        stats['elapsed_seconds'] = round(time.time() - start, 2)
    except Exception as e:
        import traceback
        stats = {'game_id': game_id, 'status': 'ERROR', 'error': str(e),
                 'error_traceback': traceback.format_exc(),
                 'elapsed_seconds': round(time.time() - start, 2)}
    all_stats.append(stats)
    print(f"  -> levels={stats.get('best_levels_completed', '?')}, "
          f"states={stats.get('unique_states_discovered', '?')}, "
          f"nodes={stats.get('nodes_expanded', '?')}")
    log_file = OUT_DIR_P / f'{prefix}_{game_id}.jsonl'
    with open(log_file, 'a') as f:
        f.write(json.dumps({'timestamp': now_iso(), **stats}) + '\n')

# Summary CSV
summary_file = OUT_DIR_P / f'{prefix}_smoke_summary.csv'
if all_stats:
    fieldnames = list(all_stats[0].keys())
    with open(summary_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_stats)

# Print summary
total_levels = sum(s.get('best_levels_completed', 0) for s in all_stats)
total_states = sum(s.get('unique_states_discovered', 0) for s in all_stats)
games_with_levels = [s['game_id'] for s in all_stats if s.get('best_levels_completed', 0) > 0]

print(f"\n{'='*60}")
print(f"v31_NOREPLAY Results Summary")
print(f"{'='*60}")
print(f"Games: {len(all_stats)}")
print(f"Total levels: {total_levels}")
print(f"Total states: {total_states}")
print(f"Games with levels: {games_with_levels}")
print(f"Errors: {sum(1 for s in all_stats if s.get('status') == 'ERROR')}")
print(f"{'='*60}")
