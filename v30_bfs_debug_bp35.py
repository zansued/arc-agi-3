#!/usr/bin/env python3
"""
v30_bfs_debug_bp35 — Debug-instrumented v30 BFS for bp35 anomaly diagnosis.
Purpose: Log every BFS frontier expansion step to trace WHY 183+ unique states
produce 0 level completions on bp35. Outputs detailed debug trace to
arc_runs/v30_bp35_debug_trace.log.
Based on v30_stateful_bfs_solver.py with extensive logging added.
"""
import copy
import csv
import hashlib
import json
import os
import random
import sys
import time
import traceback
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
# Debug log file
DEBUG_LOG = OUT_DIR_P / 'v30_bp35_debug_trace.log'
DEBUG_JSONL = OUT_DIR_P / 'v30_bp35_debug_expansions.jsonl'
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
def now_iso():
    return datetime.now(timezone.utc).isoformat()
def dlog(msg):
    """Write to debug log with timestamp."""
    timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S.%f')[:-3]
    line = f'[{timestamp}] {msg}'
    with open(DEBUG_LOG, 'a') as f:
        f.write(line + '\n')
    print(line)
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
def description_for_action(action_id):
    """Human-readable action description."""
    descriptions = {
        0: 'NoOp',
        1: 'Left',
        2: 'Right',
        3: 'Up',
        4: 'Down',
        5: 'Action5',
        6: 'Action6(click)',
    }
    return descriptions.get(action_id, f'Action{action_id}')
# ── Wrapper deep-copy helpers ──────────────────────────────────────────────
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
# ── Frontier Node ──────────────────────────────────────────────────────────
class BFSSnapshotNode:
    __slots__ = ('wrapper', 'state_hash', 'action_seq', 'depth', 'levels_completed')
    def __init__(self, wrapper, state_hash: str, action_seq: tuple,
                 depth: int, levels_completed: int):
        self.wrapper = wrapper
        self.state_hash = state_hash
        self.action_seq = action_seq
        self.depth = depth
        self.levels_completed = levels_completed
# ── Stateful BFS Solver with Debug ─────────────────────────────────────────
def bfs_solve_game_debug(game_id: str, max_steps: int = MAX_STEPS,
                         max_ply: int = MAX_PLY,
                         stagnation_window: int = STAGNATION_WINDOW) -> dict:
    # Clear debug log
    ensure_dir(OUT_DIR_P)
    with open(DEBUG_LOG, 'w') as f:
        f.write(f'[DEBUG] bp35 debug trace started at {now_iso()}\n')
        f.write(f'[DEBUG] max_steps={max_steps}, max_ply={max_ply}, stagnation_window={stagnation_window}\n\n')
    # Clear JSONL expansions log
    with open(DEBUG_JSONL, 'w') as f:
        f.write(json.dumps({'type': 'init', 'timestamp': now_iso(), 'config': {
            'max_steps': max_steps, 'max_ply': max_ply, 'stagnation_window': stagnation_window
        }}) + '\n')
    dlog(f"=== Starting bp35 debug BFS at {now_iso()} ===")
    # Initialize game
    arcade = Arcade()
    wrapper = arcade.make(game_id)
    if wrapper is None:
        dlog("ERROR: Arcade.make returned None")
        return {'game_id': game_id, 'status': 'ERROR', 'error': 'Arcade.make returned None'}
    fd_init = wrapper.reset()
    init_frame = frame_from_fd(fd_init)
    init_hash = frame_hash(init_frame)
    init_state_str = wrapper_state_str(fd_init)
    init_levels = safe_wrapper_levels(fd_init)
    avail_actions = fd_action_list(fd_init)
    dlog(f"Initial state: hash={init_hash}, levels={init_levels}, state={init_state_str}")
    dlog(f"Available actions: {avail_actions} -> {[description_for_action(a) for a in avail_actions]}")
    dlog(f"Frame shape: {init_frame.shape if init_frame is not None else 'None'}, dtype={init_frame.dtype if init_frame is not None else 'None'}")
    # Log initial levels_completed attribute details
    fd_init_attrs = [a for a in dir(fd_init) if not a.startswith('_')]
    dlog(f"FrameDataRaw attrs: {fd_init_attrs}")
    # Check what levels_completed looks like
    lvl_raw = getattr(fd_init, 'levels_completed', 'NOT_FOUND')
    dlog(f"levels_completed raw value: {lvl_raw} (type={type(lvl_raw).__name__})")
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
    # Debug counters
    total_visited_hits = 0
    total_pruned_ply = 0
    total_pruned_gameover = 0
    total_step_errors = 0
    total_win_hits = 0
    total_game_over_hits = 0
    max_depth_reached = 0
    deepest_level_at_depth = []
    while frontier and total_actions_consumed < max_steps:
        # Stagnation fallback
        if expansions_without_new_state >= stagnation_window and len(safe_stash) > 1:
            fallbacks_triggered += 1
            candidates = [n for n in safe_stash if n.depth > 0]
            if not candidates:
                candidates = safe_stash
            fallback_node = random.choice(candidates)
            dlog(f"STAGNATION: fallback #{fallbacks_triggered} to depth={fallback_node.depth}, "
                 f"hash={fallback_node.state_hash[:12]}..., seq_len={len(fallback_node.action_seq)}")
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
        total_actions_consumed += 1  # count the pop as a unit of work
        dlog(f"")
        dlog(f"--- POP node: seq_len={len(node.action_seq)}, depth={node.depth}, "
             f"levels={node.levels_completed}, hash={node.state_hash[:16]}...")
        dlog(f"     action_seq={node.action_seq} -> {[description_for_action(a) for a in node.action_seq]}")
        dlog(f"     frontier size before expansion: {len(frontier)}")
        # Generate successors
        for act_idx, act in enumerate(avail_actions):
            if nodes_expanded >= max_steps:
                break
            act_name = description_for_action(act)
            act_coord = ' (32,32)' if act == 6 else ''
            # Deepcopy the node's wrapper, step one action
            try:
                clone = snapshot_wrapper(node.wrapper)
            except Exception as e:
                dlog(f"  [DEEPCOPY ERROR] action={act_name}: {e}")
                total_step_errors += 1
                continue
            fd, frame, state_str, levels = step_and_fetch(clone, act)
            nodes_expanded += 1
            if frame is None:
                total_step_errors += 1
                dlog(f"  [STEP FAIL] action={act_name}{act_coord}: fd=None or frame=None (state={state_str})")
                continue
            h = frame_hash(frame)
            old_levels = best_levels
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
                    'depth': node.depth + 1,
                })
                dlog(f"  🎯 LEVEL PROGRESS: levels={old_levels} -> {levels}! "
                     f"action={act_name}{act_coord}, depth={node.depth+1}, seq={new_seq}")
                deepest_level_at_depth.append((node.depth+1, levels))
            # Check state types
            is_win_state = is_win(state_str)
            is_go_state = is_game_over(state_str)
            if is_win_state:
                total_win_hits += 1
            if is_go_state:
                total_game_over_hits += 1
            # Track max depth
            if node.depth + 1 > max_depth_reached:
                max_depth_reached = node.depth + 1
            is_new_state = h not in visited_states
            new_depth = node.depth + 1
            pruned_reason = None
            # Determine if this node should be added to frontier
            if new_depth >= max_ply:
                pruned_reason = f'max_ply ({max_ply})'
            elif is_go_state and not is_win_state:
                pruned_reason = f'GAME_OVER (not WIN)'
            elif not is_new_state:
                pruned_reason = 'already_visited'
            # Detailed logging for every expansion
            log_entry = {
                'node_num': nodes_expanded,
                'parent_depth': node.depth,
                'parent_hash': node.state_hash[:16],
                'action': int(act),
                'action_name': act_name,
                'action_coord': '32,32' if act == 6 else None,
                'new_hash': h[:16],
                'new_depth': new_depth,
                'is_new_state': is_new_state,
                'state_str': state_str,
                'is_win': is_win_state,
                'is_game_over': is_go_state,
                'levels': levels,
                'best_levels': best_levels,
                'pruned_reason': pruned_reason,
                'frontier_size_after': 0,
                'steps_remaining': max_steps - nodes_expanded,
            }
            if is_new_state:
                visited_states.add(h)
                expansions_without_new_state = 0
                new_node = BFSSnapshotNode(
                    wrapper=clone,
                    state_hash=h,
                    action_seq=node.action_seq + (act,),
                    depth=new_depth,
                    levels_completed=levels
                )
                if new_depth < max_ply and not is_go_state:
                    frontier.append(new_node)
                    log_entry['frontier_size_after'] = len(frontier)
                    log_entry['action'] = 'ADDED_TO_FRONTIER'
                else:
                    log_entry['action'] = 'ADDED_TO_SAFESTASH_ONLY'
                    if new_depth >= max_ply:
                        total_pruned_ply += 1
                    if is_go_state:
                        total_pruned_gameover += 1
                safe_stash.append(new_node)
            else:
                expansions_without_new_state += 1
                total_visited_hits += 1
                log_entry['action'] = 'SKIPPED_ALREADY_VISITED'
                log_entry['frontier_size_after'] = len(frontier)
            # Log condensed per-action
            status_icon = '🆕' if is_new_state else '⏭️'
            if pruned_reason == 'max_ply':
                status_icon = '✂️'
            elif is_win_state:
                status_icon = '🏆'
            elif is_go_state:
                status_icon = '💀'
            dlog(f"  {status_icon} [{nodes_expanded:>4d}] {act_name:>15s}{act_coord:>8s} -> "
                 f"hash={h[:12]}... depth={new_depth} levels={levels} state={state_str} "
                 f"{'NEW' if is_new_state else 'VISITED'}"
                 f"{' ✂️PLY' if pruned_reason == 'max_ply' else ''}"
                 f"{' 🏆WIN' if is_win_state else ''}"
                 f"{' 💀GAMEOVER' if is_go_state else ''}"
                 f" | frontier={len(frontier)}")
            # Write JSONL entry
            with open(DEBUG_JSONL, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
    dlog(f"")
    dlog(f"=== DEBUG SUMMARY ===")
    dlog(f"Total expansions: {nodes_expanded}")
    dlog(f"Unique states: {len(visited_states)}")
    dlog(f"Best levels: {best_levels}")
    dlog(f"Best action seq: {best_action_str}")
    dlog(f"Frontier remaining: {len(frontier)}")
    dlog(f"Safe stash size: {len(safe_stash)}")
    dlog(f"Fallbacks triggered: {fallbacks_triggered}")
    dlog(f"Max depth reached: {max_depth_reached}")
    dlog(f"Total visited hits: {total_visited_hits}")
    dlog(f"Total pruned by max_ply: {total_pruned_ply}")
    dlog(f"Total pruned by GAME_OVER: {total_pruned_gameover}")
    dlog(f"Total step errors: {total_step_errors}")
    dlog(f"Total WIN state hits: {total_win_hits}")
    dlog(f"Total GAME_OVER state hits: {total_game_over_hits}")
    dlog(f"Level progress events: {len(levels_progress_events)}")
    dlog(f"Deepest level at depths: {deepest_level_at_depth}")
    dlog(f"Actions consumed (pop-based): {total_actions_consumed}")
    # Check if any safe stash nodes have levels > 0
    stash_with_levels = [n for n in safe_stash if n.levels_completed > 0]
    dlog(f"Safe stash nodes with levels>0: {len(stash_with_levels)}")
    for sn in stash_with_levels[:5]:
        dlog(f"  -> depth={sn.depth}, levels={sn.levels_completed}, hash={sn.state_hash[:16]}..., seq={sn.action_seq}")
    # Check the last 10 nodes in safe stash
    dlog(f"")
    dlog(f"Last 10 safe stash nodes:")
    for sn in safe_stash[-10:]:
        dlog(f"  depth={sn.depth}, levels={sn.levels_completed}, hash={sn.state_hash[:16]}..., seq_len={len(sn.action_seq)}")
    # Check the first 10 nodes from the beginning
    dlog(f"")
    dlog(f"First 10 safe stash nodes:")
    for sn in safe_stash[:10]:
        dlog(f"  depth={sn.depth}, levels={sn.levels_completed}, hash={sn.state_hash[:16]}..., seq_len={len(sn.action_seq)}")
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
        # Debug stats
        'max_depth_reached': max_depth_reached,
        'total_visited_hits': total_visited_hits,
        'total_pruned_ply': total_pruned_ply,
        'total_pruned_gameover': total_pruned_gameover,
        'total_step_errors': total_step_errors,
        'total_win_hits': total_win_hits,
        'total_game_over_hits': total_game_over_hits,
        'debug_trace_log': str(DEBUG_LOG),
        'debug_expansions_jsonl': str(DEBUG_JSONL),
    }
# ── Runner ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    ensure_dir(OUT_DIR_P)
    print(f"=" * 70)
    print(f"v30_bfs_debug_bp35 — Debug-Instrumented BFS for bp35 Anomaly")
    print(f"=" * 70)
    print(f"Max steps: {MAX_STEPS}")
    print(f"Max ply: {MAX_PLY}")
    print(f"Stagnation window: {STAGNATION_WINDOW}")
    print(f"Debug log: {DEBUG_LOG}")
    print(f"Expansions JSONL: {DEBUG_JSONL}")
    print()
    start = time.time()
    try:
        stats = bfs_solve_game_debug('bp35')
        elapsed = time.time() - start
        stats['elapsed_seconds'] = round(elapsed, 2)
    except Exception as e:
        elapsed = time.time() - start
        stats = {
            'game_id': 'bp35',
            'status': 'ERROR',
            'error': str(e),
            'error_traceback': traceback.format_exc(),
            'elapsed_seconds': round(elapsed, 2),
        }
        dlog(f"CRASH: {e}")
        dlog(traceback.format_exc())
    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print()
    print(f"Debug trace: {DEBUG_LOG}")
    print(f"Elapsed: {round(elapsed, 2)}s")
    # Write result JSONL
    result_file = OUT_DIR_P / 'v30_bp35_debug_result.json'
    with open(result_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"Result written to {result_file}")
