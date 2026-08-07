#!/usr/bin/env python3
"""
v30_fix1_stochastic_bfs.py — v30 with fix for cn04 regression.

Fixes applied:
1. Stochastic action ordering (randomize iteration order per node)
2. Reduced stagnation threshold: 50 → 20
3. Increased MAX_STEPS to 1500 for bottleneck games
4. Added action diversity bonus: prefer actions not tried recently from similar states

Based on cn04_debug_report.md root cause analysis.
"""

import copy
import csv
import hashlib
import json
import os
import random
import sys
import time
from collections import defaultdict, Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction
from arcengine.enums import GameState

# ── Configuration ──────────────────────────────────────────────────────────
MAX_STEPS = 1500          # Increased from 500 (cn04 needs deeper exploration)
OUT_DIR = 'arc_runs'
MAX_PLY = 100             # Unchanged
STAGNATION_WINDOW = 20    # Reduced from 50 (trigger safe-stash fallback earlier)
ENABLE_STOCHASTIC_ACTIONS = True  # NEW: randomize action order per node
ENABLE_DIVERSITY_BONUS = True      # NEW: track and penalize overused actions

SMOKE_GAMES = ['tn36', 'sp80', 'bp35', 'cn04']
FULL_GAMES = [
    'sk48', 'bp35', 'tn36', 'wa30', 'vc33', 'tu93', 'tr87', 'su15', 'sp80',
    'sc25', 'sb26', 's5i5', 're86', 'r11l', 'm0r0', 'ls20', 'lp85', 'lf52',
    'ka59', 'g50t', 'ft09', 'dc22', 'cd82', 'ar25', 'cn04',
]

OUT_DIR_P = Path(OUT_DIR)

ACTION_NAMES = {
    0: 'RESET', 1: 'ROTATE_CW', 2: 'ROTATE_CCW',
    3: 'FLIP_H', 4: 'FLIP_V', 5: 'TRANSLATE', 6: 'ACTION6/CROP_PASTE',
}

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def frame_from_fd(fd):
    if hasattr(fd, 'frame') and fd.frame is not None and len(fd.frame) > 0:
        return np.asarray(fd.frame[0])
    return None

def frame_hash(arr):
    if arr is None:
        return ''
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def fd_action_list(fd):
    avail = getattr(fd, 'available_actions', None)
    if avail is not None and len(avail) > 0:
        return [int(a) for a in avail]
    return [0, 1, 2, 3, 4, 5, 6]

def is_win(state_val):
    return state_val in (GameState.WIN, 'WIN')

def is_game_over(state_val):
    return state_val in (GameState.GAME_OVER, 'GAME_OVER')

def wrapper_state_str(fd):
    st = getattr(fd, 'state', None)
    return str(st) if st is not None else 'UNKNOWN'

def safe_wrapper_levels(fd):
    return int(getattr(fd, 'levels_completed', 0) or 0)

def snapshot_wrapper(wrapper):
    return copy.deepcopy(wrapper)

def step_and_fetch(wrapper, action_id):
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
    lvl = safe_wrapper_levels(fd)
    return fd, frame, st, lvl

class BFSSnapshotNode:
    __slots__ = ('wrapper', 'state_hash', 'action_seq', 'depth', 'levels_completed')
    def __init__(self, wrapper, state_hash, action_seq, depth, levels_completed):
        self.wrapper = wrapper
        self.state_hash = state_hash
        self.action_seq = action_seq
        self.depth = depth
        self.levels_completed = levels_completed

class ActionDiversityTracker:
    """Track action usage per hash-cluster to prevent overuse of popular actions."""
    def __init__(self, decay=0.95):
        self.action_counts = Counter()  # action_id -> count
        self.hash_action_counts = {}    # hash -> {action_id -> count}
        self.decay = decay
    
    def record(self, hsh, action_id):
        self.action_counts[action_id] += 1
        if hsh not in self.hash_action_counts:
            self.hash_action_counts[hsh] = Counter()
        self.hash_action_counts[hsh][action_id] += 1
    
    def score_actions(self, avail_actions):
        """Return list of (action_id, diversity_penalty) — higher penalty = less diverse."""
        total = max(1, sum(self.action_counts.values()))
        scores = []
        for a in avail_actions:
            freq = self.action_counts.get(a, 0) / total
            # Diversity bonus: penalize overused actions, favor underused ones
            penalty = 1.0 + freq * 0.5  # up to 1.5x penalty for overused
            scores.append((a, penalty))
        return scores

def bfs_solve_game(game_id: str, max_steps: int = MAX_STEPS,
                   max_ply: int = MAX_PLY,
                   stagnation_window: int = STAGNATION_WINDOW,
                   enable_stochastic: bool = ENABLE_STOCHASTIC_ACTIONS,
                   enable_diversity: bool = ENABLE_DIVERSITY_BONUS) -> dict:
    """BFS with deepcopy snapshots, stochastic actions, and diversity tracking."""
    arcade = Arcade()
    wrapper = arcade.make(game_id)
    if wrapper is None:
        return {'game_id': game_id, 'status': 'ERROR',
                'error': 'Arcade.make returned None'}

    fd_init = wrapper.reset()
    init_frame = frame_from_fd(fd_init)
    init_hash = frame_hash(init_frame)
    init_state_str = wrapper_state_str(fd_init)
    init_levels = safe_wrapper_levels(fd_init)
    avail_actions = fd_action_list(fd_init)

    init_node = BFSSnapshotNode(
        wrapper=snapshot_wrapper(wrapper),
        state_hash=init_hash,
        action_seq=(),
        depth=0,
        levels_completed=init_levels
    )

    frontier = [init_node]
    safe_stash = [init_node]
    visited_states: set[str] = {init_hash}
    diversity_tracker = ActionDiversityTracker()

    total_actions_consumed = 0
    nodes_expanded = 0
    best_levels = 0
    best_action_str = ''
    best_state_hash = init_hash
    levels_progress_events: list[dict] = []
    expansions_without_new_state = 0
    fallbacks_triggered = 0

    while frontier and total_actions_consumed < max_steps:
        # Stagnation fallback — trigger earlier (reduced window)
        if expansions_without_new_state >= stagnation_window and len(safe_stash) > 1:
            fallbacks_triggered += 1
            candidates = [n for n in safe_stash if n.depth > 0]
            if not candidates:
                candidates = safe_stash
            fallback_node = random.choice(candidates)
            fallback_snapshot = BFSSnapshotNode(
                wrapper=snapshot_wrapper(fallback_node.wrapper),
                state_hash=fallback_node.state_hash,
                action_seq=fallback_node.action_seq,
                depth=fallback_node.depth,
                levels_completed=fallback_node.levels_completed
            )
            frontier.insert(0, fallback_snapshot)
            expansions_without_new_state = 0
            safe_stash.append(fallback_snapshot)

        # Pop node
        node = frontier.pop(0)

        # Determine action order (stochastic or deterministic)
        if enable_stochastic:
            # Shuffle action order to break plateaus
            action_order = list(avail_actions)
            random.shuffle(action_order)
        else:
            action_order = list(avail_actions)

        # Apply diversity bonus: reorder so less-used actions are tried first
        if enable_diversity:
            scores = diversity_tracker.score_actions(action_order)
            # Sort by penalty ascending (try diverse actions first)
            action_order = [a for a, p in sorted(scores, key=lambda x: x[1])]

        # Generate successors
        for act in action_order:
            if total_actions_consumed >= max_steps:
                break

            # Max depth check
            if node.depth >= max_ply:
                continue

            # Deepcopy the node's wrapper, step one action
            clone = snapshot_wrapper(node.wrapper)
            fd, frame, state_str, levels = step_and_fetch(clone, act)
            total_actions_consumed += 1
            nodes_expanded += 1
            diversity_tracker.record(node.state_hash, act)

            if frame is None:
                continue

            h = frame_hash(frame)

            # Track progress
            if levels > best_levels:
                best_levels = levels
                new_seq = node.action_seq + (act,)
                best_action_str = str(new_seq)
                best_state_hash = h
                levels_progress_events.append({
                    'seq': best_action_str,
                    'levels': best_levels,
                    'hash': h,
                    'state': state_str,
                })

            # State deduplication
            if h not in visited_states:
                visited_states.add(h)
                expansions_without_new_state = 0

                new_depth = node.depth + 1
                new_node = BFSSnapshotNode(
                    wrapper=clone,
                    state_hash=h,
                    action_seq=node.action_seq + (act,),
                    depth=new_depth,
                    levels_completed=levels
                )

                if new_depth < max_ply and not is_game_over(state_str):
                    frontier.append(new_node)
                safe_stash.append(new_node)
            else:
                expansions_without_new_state += 1

    return {
        'game_id': game_id,
        'status': 'OK',
        'nodes_expanded': nodes_expanded,
        'total_actions_consumed': total_actions_consumed,
        'unique_states_discovered': len(visited_states),
        'best_levels_completed': best_levels,
        'best_action_sequence': best_action_str,
        'best_state_hash': best_state_hash,
        'levels_progress_events': len(levels_progress_events),
        'frontier_remaining': len(frontier),
        'fallbacks_triggered': fallbacks_triggered,
        'stagnation_window_max': stagnation_window,
    }


def run_benchmark(game_list: list[str],
                  version_label: str = 'v30_fix1_smoke') -> list[dict]:
    prefix = f'{version_label}_stochastic_bfs'
    ensure_dir(OUT_DIR_P)
    all_stats = []

    for game_id in game_list:
        print(f"[{now_iso()}] Processing {game_id}...")
        start = time.time()
        try:
            stats = bfs_solve_game(game_id)
            elapsed = time.time() - start
            stats['elapsed_seconds'] = round(elapsed, 2)
        except Exception as e:
            import traceback
            stats = {
                'game_id': game_id,
                'status': 'ERROR',
                'error': str(e),
                'error_traceback': traceback.format_exc(),
                'elapsed_seconds': round(time.time() - start, 2),
            }

        all_stats.append(stats)
        print(f"  -> levels={stats.get('best_levels_completed', '?')}, "
              f"states={stats.get('unique_states_discovered', '?')}, "
              f"nodes={stats.get('nodes_expanded', '?')}, "
              f"elapsed={stats.get('elapsed_seconds', '?')}s")

        # Per-game JSONL log
        log_file = OUT_DIR_P / f'{prefix}_{game_id}.jsonl'
        with open(log_file, 'a') as f:
            f.write(json.dumps({'timestamp': now_iso(), **stats}) + '\n')

    # Summary CSV
    summary_file = OUT_DIR_P / f'{version_label}_smoke_summary.csv'
    if all_stats:
        fieldnames = list(all_stats[0].keys())
        with open(summary_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_stats)

    return all_stats


if __name__ == '__main__':
    if '--smoke' in sys.argv or '-s' in sys.argv:
        games_to_run = SMOKE_GAMES
        version_label = 'v30_fix1_smoke'
    elif '--full' in sys.argv or '-f' in sys.argv:
        games_to_run = FULL_GAMES
        version_label = 'v30_fix1'
    elif '--test-5' in sys.argv or '-5' in sys.argv:
        games_to_run = ['cn04', 'sp80', 'cd82', 'tn36', 'bp35']
        version_label = 'v30_fix1_test5'
    else:
        games_to_run = ['cn04', 'sp80', 'cd82', 'tn36', 'bp35']
        version_label = 'v30_fix1_test5'

    print(f"[{now_iso()}] v30_fix1 Stochastic BFS Solver")
    print(f"Games: {games_to_run}")
    print(f"Max steps: {MAX_STEPS}")
    print(f"Max ply: {MAX_PLY}")
    print(f"Stagnation window: {STAGNATION_WINDOW}")
    print(f"Stochastic actions: {ENABLE_STOCHASTIC_ACTIONS}")
    print(f"Diversity bonus: {ENABLE_DIVERSITY_BONUS}")
    print()

    stats = run_benchmark(games_to_run, version_label)

    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    for s in stats:
        print(f"  {s['game_id']}: levels={s.get('best_levels_completed', '?')}, "
              f"states={s.get('unique_states_discovered', '?')}, "
              f"nodes={s.get('nodes_expanded', '?')}, "
              f"status={s.get('status', '?')}")

    has_errors = any(s.get('status') == 'ERROR' for s in stats)
    has_zero_levels = all(s.get('best_levels_completed', 0) == 0 for s in stats)

    print()
    if has_errors:
        print("⚠️  Some games errored")
    elif has_zero_levels:
        print("⚠️  Failed — no levels completed")
    else:
        print("✅  Smoke test: levels achieved!")

    print(f"\n[{now_iso()}] Done.")
