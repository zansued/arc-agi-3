#!/usr/bin/env python3
"""
v30_verbose_cn04_diagnostic.py — Instrumented BFS diagnostic for cn04.

Hermann's directive: run v30_stateful_bfs_solver.py with verbose=true on cn04,
capturing the full state expansion log — every node popped, every transition
attempted, every pruning decision.

This script reimplements bfs_solve_game() from v30_stateful_bfs_solver.py with
full verbosity logging.
"""

import copy
import hashlib
import json
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

# ── Configuration ──────────────────────────────────────────────────────────
MAX_STEPS = 500
OUT_DIR = 'arc_runs'
MAX_PLY = 100
STAGNATION_WINDOW = 50

OUT_DIR_P = Path(OUT_DIR)

# Verbose log
VERBOSE_LOG = []

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def vlog(event_type, **kwargs):
    """Append a structured verbose log entry."""
    entry = {
        't': now_iso(),
        'step': len(VERBOSE_LOG),
        'event': event_type,
    }
    entry.update(kwargs)
    VERBOSE_LOG.append(entry)

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

ACTION_NAMES = {
    0: 'RESET', 1: 'ROTATE_CW', 2: 'ROTATE_CCW',
    3: 'FLIP_H', 4: 'FLIP_V', 5: 'TRANSLATE', 6: 'ACTION6/CROP_PASTE',
}

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


def verbose_bfs_solve_cn04(game_id: str = 'cn04',
                           max_steps: int = MAX_STEPS,
                           max_ply: int = MAX_PLY,
                           stagnation_window: int = STAGNATION_WINDOW) -> dict:
    """BFS with full verbose logging — every node pop, transition, and pruning decision."""
    global VERBOSE_LOG
    VERBOSE_LOG = []

    vlog('start', game_id=game_id, max_steps=max_steps, max_ply=max_ply, stagnation_window=stagnation_window)

    arcade = Arcade()
    wrapper = arcade.make(game_id)
    if wrapper is None:
        vlog('error', error='Arcade.make returned None')
        return {'game_id': game_id, 'status': 'ERROR', 'error': 'Arcade.make returned None'}

    fd_init = wrapper.reset()
    init_frame = frame_from_fd(fd_init)
    init_hash = frame_hash(init_frame)
    init_state_str = wrapper_state_str(fd_init)
    init_levels = safe_wrapper_levels(fd_init)
    avail_actions = fd_action_list(fd_init)

    vlog('init',
         init_hash=init_hash,
         init_state=init_state_str,
         init_levels=init_levels,
         avail_actions=[ACTION_NAMES.get(a, f'ACT{a}') for a in avail_actions],
         avail_actions_ids=avail_actions,
         frame_shape=list(init_frame.shape) if init_frame is not None else None)

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

    total_actions_consumed = 0
    nodes_expanded = 0
    best_levels = 0
    best_action_str = ''
    best_state_hash = init_hash
    levels_progress_events: list[dict] = []
    stagnation_counter = 0
    expansions_without_new_state = 0
    fallbacks_triggered = 0

    while frontier and total_actions_consumed < max_steps:
        # Stagnation fallback check
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
            vlog('fallback', 
                 trigger_num=fallbacks_triggered,
                 fallback_depth=fallback_node.depth,
                 fallback_seq=str(fallback_node.action_seq),
                 fallback_hash=fallback_node.state_hash,
                 frontier_size=len(frontier))

        # Pop node
        node = frontier.pop(0)
        vlog('pop_node',
             depth=node.depth,
             seq=str(node.action_seq),
             hash=node.state_hash,
             levels=node.levels_completed,
             frontier_remaining=len(frontier),
             safe_stash_size=len(safe_stash),
             visited_count=len(visited_states),
             total_actions_consumed=total_actions_consumed,
             expansions_without_new_state=expansions_without_new_state)

        # Generate successors
        for act in avail_actions:
            if total_actions_consumed >= max_steps:
                vlog('max_steps_reached', actions_consumed=total_actions_consumed)
                break

            # Depth check
            if node.depth >= max_ply:
                vlog('prune_max_depth',
                     action=ACTION_NAMES.get(act, f'ACT{act}'),
                     action_id=act,
                     node_depth=node.depth,
                     max_ply=max_ply)
                continue

            # Deepcopy the node's wrapper, step one action
            clone = snapshot_wrapper(node.wrapper)
            fd, frame, state_str, levels = step_and_fetch(clone, act)
            total_actions_consumed += 1
            nodes_expanded += 1

            if frame is None:
                vlog('frame_none',
                     action=ACTION_NAMES.get(act, f'ACT{act}'),
                     action_id=act,
                     state_str=state_str)
                continue

            h = frame_hash(frame)

            # Check if this transition produced progress
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
                vlog('progress',
                     levels=levels,
                     seq=str(new_seq),
                     hash=h,
                     state=state_str)

            # State deduplication check
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
                else:
                    if new_depth >= max_ply:
                        vlog('prune_frontier_max_depth',
                             action=ACTION_NAMES.get(act, f'ACT{act}'),
                             action_id=act,
                             depth=new_depth,
                             max_ply=max_ply,
                             hash=h)
                    if is_game_over(state_str):
                        vlog('prune_game_over',
                             action=ACTION_NAMES.get(act, f'ACT{act}'),
                             action_id=act,
                             state=state_str,
                             hash=h)
                safe_stash.append(new_node)
                vlog('new_state',
                     action=ACTION_NAMES.get(act, f'ACT{act}'),
                     action_id=act,
                     hash=h,
                     depth=new_depth,
                     seq=str(node.action_seq + (act,)),
                     levels=levels,
                     state=state_str,
                     frontier_size=len(frontier),
                     visited_count=len(visited_states))
            else:
                expansions_without_new_state += 1
                vlog('duplicate_state',
                     action=ACTION_NAMES.get(act, f'ACT{act}'),
                     action_id=act,
                     hash=h,
                     depth_attempted=node.depth + 1,
                     expansions_without_new_state=expansions_without_new_state,
                     frontier_size=len(frontier))

        # Check game-over or win conditions on the current node's state
        if is_game_over(wrapper_state_str(fd_init if 'fd_init' in dir() else fd_init)):
            # This is checked from the last stepped state
            pass

    result = {
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

    vlog('complete', result=result, verbose_log_entries=len(VERBOSE_LOG))

    return result


def save_verbose_log(path: str):
    """Save the verbose log as a JSONL file."""
    os.makedirs(Path(path).parent, exist_ok=True)
    with open(path, 'w') as f:
        for entry in VERBOSE_LOG:
            f.write(json.dumps(entry) + '\n')
    print(f"Verbose log saved: {path} ({len(VERBOSE_LOG)} entries)")


def save_summary_report(result: dict):
    """Save a human-readable summary of the BFS run."""
    summary_path = '/a0/usr/workdir/arc_runs/v30_cn04_verbose_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Summary saved: {summary_path}")
    return result


if __name__ == '__main__':
    print("=" * 70)
    print("v30 VERBOSE BFS DIAGNOSTIC — cn04")
    print("=" * 70)
    print(f"Start: {now_iso()}")
    print(f"Max steps: {MAX_STEPS}")
    print(f"Max ply: {MAX_PLY}")
    print(f"Stagnation window: {STAGNATION_WINDOW}")
    print()

    start = time.time()
    result = verbose_bfs_solve_cn04()
    elapsed = time.time() - start
    result['elapsed_seconds'] = round(elapsed, 2)

    print(f"\nResult: {json.dumps(result, indent=2)}")
    print(f"\nElapsed: {elapsed:.2f}s")
    print(f"Verbose log entries: {len(VERBOSE_LOG)}")

    # Save outputs
    save_verbose_log('/a0/usr/workdir/arc_runs/v30_cn04_verbose_log.jsonl')
    save_summary_report(result)

    # Print key findings for immediate analysis
    print("\n" + "=" * 70)
    print("KEY FINDINGS (v30 cn04 verbose)")
    print("=" * 70)
    print(f"Unique states discovered: {result['unique_states_discovered']}")
    print(f"Best levels: {result['best_levels_completed']}")
    print(f"Best action sequence: {result['best_action_sequence']}")
    print(f"Nodes expanded: {result['nodes_expanded']}")
    print(f"Fallbacks triggered: {result['fallbacks_triggered']}")
    print(f"Frontier remaining: {result['frontier_remaining']}")
    print(f"Progress events: {result['levels_progress_events']}")

    # Count event types
    from collections import Counter
    event_counts = Counter(e['event'] for e in VERBOSE_LOG)
    print(f"\nEvent type breakdown:")
    for evt, cnt in sorted(event_counts.items()):
        print(f"  {evt}: {cnt}")

    print(f"\n[{now_iso()}] Done.")
