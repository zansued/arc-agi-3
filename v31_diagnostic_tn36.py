#!/usr/bin/env python3
"""
v31_diagnostic_tn36 — Runs v31_hybrid_bfs on tn36 with detailed per-replay diagnostics.
"""
import json
import sys
sys.path.insert(0, '/a0/usr/workdir')
from pathlib import Path

from arc_agi import Arcade
from arcengine import GameAction
from arcengine.enums import GameState

import copy
import hashlib
import math
import os
import random
import numpy as np
from collections import defaultdict
from datetime import datetime, timezone

MAX_STEPS = 500
MAX_PLY = 100
STAGNATION_WINDOW = 50
ARCHIVE_REPLAY_STEPS = 3
MAX_ARCHIVE_RESETS = 6

def ensure_dir(p): os.makedirs(p, exist_ok=True)
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
    if avail is not None and len(avail) > 0:
        return [int(a) for a in avail]
    return [0,1,2,3,4,5,6]
def is_win(sv): return sv in (GameState.WIN, "WIN")
def is_game_over(sv): return sv in (GameState.GAME_OVER, "GAME_OVER")
def wrapper_state_str(fd):
    st = getattr(fd, 'state', None)
    return str(st) if st is not None else "UNKNOWN"
def safe_wrapper_levels(fd):
    return int(getattr(fd, 'levels_completed', 0) or 0)
def snapshot_wrapper(w): return copy.deepcopy(w)

def step_and_fetch(wrapper, action_id):
    try:
        action = GameAction.from_id(action_id)
        if action_id == 6:
            fd = wrapper.step(action, data={'x': 32, 'y': 32})
        else:
            fd = wrapper.step(action)
    except Exception as e:
        return None, None, f'STEP_ERR: {e}', 0
    if fd is None: return None, None, 'FD_NONE', 0
    frame = frame_from_fd(fd)
    st = wrapper_state_str(fd)
    lvl = safe_wrapper_levels(fd)
    return fd, frame, st, lvl

class ArchiveCell:
    __slots__ = ('state_hash', 'action_seq', 'depth', 'levels_completed',
                 'transition_count', 'visits', 'children_hashes', 'score',
                 'wrapper_snapshot', 'game_id')
    def __init__(self, state_hash, action_seq, depth, levels_completed, wrapper_snapshot=None):
        self.state_hash = state_hash
        self.action_seq = action_seq
        self.depth = depth
        self.levels_completed = levels_completed
        self.transition_count = 0
        self.visits = 1
        self.children_hashes = set()
        self.score = 0.0
        self.wrapper_snapshot = wrapper_snapshot
        self.game_id = None
    def compute_score(self, current_depth=0):
        depth_bonus = min(1.0, self.depth / 20.0)
        novelty = 1.0 / (1.0 + self.visits)
        transition_bonus = math.log1p(self.transition_count) * 0.5
        level_bonus = self.levels_completed * 10.0
        child_exploration = 0.5 if len(self.children_hashes) == 0 else 0.1
        return novelty * 2.5 + depth_bonus * 0.8 + transition_bonus + level_bonus + child_exploration

class HybridArchive:
    def __init__(self, max_size=256):
        self.cells = {}
        self.max_size = max_size
        self.n_replays = 0
        self.n_replay_success = 0
        self.total_archive_states_read = 0
        self.unique_new_states_from_replay = 0
        self.unique_new_levels_from_replay = 0
        self.replay_events = []  # detailed log per replay
    def size(self): return len(self.cells)  # detailed log per replay
    def add_or_update(self, state_hash, action_seq, depth, levels_completed, parent_hash=None, wrapper_snapshot=None):
        if not state_hash: return None
        if state_hash in self.cells:
            cell = self.cells[state_hash]
            cell.visits += 1
            if len(action_seq) < len(cell.action_seq):
                cell.action_seq = action_seq; cell.depth = depth
                if wrapper_snapshot is not None: cell.wrapper_snapshot = wrapper_snapshot
            if levels_completed > cell.levels_completed: cell.levels_completed = levels_completed
            return cell
        if len(self.cells) >= self.max_size:
            worst = min(self.cells.values(), key=lambda c: (c.score, c.visits, len(c.action_seq)))
            del self.cells[worst.state_hash]
        cell = ArchiveCell(state_hash, action_seq, depth, levels_completed, wrapper_snapshot)
        self.cells[state_hash] = cell
        if parent_hash and parent_hash in self.cells:
            self.cells[parent_hash].children_hashes.add(state_hash)
        return cell
    def record_transition(self, state_hash):
        if state_hash in self.cells: self.cells[state_hash].transition_count += 1
    def record_replay(self, led_to_new_states, frontier_size=0):
        self.n_replays += 1
        if led_to_new_states: self.n_replay_success += 1
    def select_replay_target(self, stagnated):
        candidates = [c for c in self.cells.values() if len(c.action_seq) > 0 and len(c.action_seq) <= 80]
        if not candidates:
            candidates = [c for c in self.cells.values() if len(c.action_seq) > 0]
        if not candidates: return None
        for c in candidates: c.score = c.compute_score()
        ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
        top_n = min(5, len(ranked))
        selected = random.choice(ranked[:top_n])
        return selected

def bfs_solve_game_diagnostic(game_id):
    """v31 with detailed diagnostic output per replay."""
    arcade = Arcade()
    wrapper = arcade.make(game_id)
    if wrapper is None:
        return {'game_id': game_id, 'status': 'ERROR', 'error': 'Arcade.make returned None'}

    fd_init = wrapper.reset()
    init_frame = frame_from_fd(fd_init)
    init_hash = frame_hash(init_frame)
    init_levels = safe_wrapper_levels(fd_init)
    avail_actions = fd_action_list(fd_init)

    archive = HybridArchive(max_size=256)
    archive.add_or_update(
        state_hash=init_hash, action_seq=(), depth=0,
        levels_completed=init_levels, wrapper_snapshot=snapshot_wrapper(wrapper))

    class BFSSnapshotNode:
        __slots__ = ('wrapper', 'state_hash', 'action_seq', 'depth', 'levels_completed')
        def __init__(self, wrapper, state_hash, action_seq, depth, levels_completed):
            self.wrapper = wrapper; self.state_hash = state_hash
            self.action_seq = action_seq; self.depth = depth; self.levels_completed = levels_completed

    init_node = BFSSnapshotNode(
        wrapper=snapshot_wrapper(wrapper), state_hash=init_hash,
        action_seq=(), depth=0, levels_completed=init_levels)

    frontier = [init_node]
    safe_stash = [init_node]
    visited_states = {init_hash}

    total_actions_consumed = 0
    nodes_expanded = 0
    best_levels = 0
    best_action_str = ''
    best_state_hash = init_hash
    levels_progress_events = []

    stagnation_counter = 0
    expansions_without_new_state = 0
    fallbacks_triggered = 0
    consecutive_zero_new_states = 0
    archive_replays_triggered = 0
    last_replay_state = None

    # Detailed replay diagnostics
    replay_diagnostics = []

    while frontier and total_actions_consumed < MAX_STEPS:
        replay_target = None
        frontier_size_before = len(frontier)

        # v30 stagnation fallback
        if expansions_without_new_state >= STAGNATION_WINDOW and len(safe_stash) > 1:
            fallbacks_triggered += 1
            candidates = [n for n in safe_stash if n.depth > 0]
            if not candidates: candidates = safe_stash
            fallback_node = random.choice(candidates)
            fallback_snapshot = BFSSnapshotNode(
                wrapper=snapshot_wrapper(fallback_node.wrapper),
                state_hash=fallback_node.state_hash,
                action_seq=fallback_node.action_seq,
                depth=fallback_node.depth,
                levels_completed=fallback_node.levels_completed)
            frontier.insert(0, fallback_snapshot)
            expansions_without_new_state = 0
            consecutive_zero_new_states = 0

        # v31 archive replay trigger
        if (consecutive_zero_new_states >= ARCHIVE_REPLAY_STEPS
                and archive.size() > 1
                and archive_replays_triggered < MAX_ARCHIVE_RESETS):
            replay_target = archive.select_replay_target(stagnated=True)
            if replay_target and replay_target.state_hash != last_replay_state:
                archive_replays_triggered += 1
                last_replay_state = replay_target.state_hash
                replay_wrapper = snapshot_wrapper(replay_target.wrapper_snapshot)
                replay_node = BFSSnapshotNode(
                    wrapper=replay_wrapper, state_hash=replay_target.state_hash,
                    action_seq=replay_target.action_seq, depth=replay_target.depth,
                    levels_completed=replay_target.levels_completed)
                frontier.insert(0, replay_node)
                consecutive_zero_new_states = 0
                replay_led_to_new = False
                # Log replay event
                replay_event = {
                    'replay_num': archive_replays_triggered,
                    'target_state_hash': replay_target.state_hash[:12],
                    'target_depth': replay_target.depth,
                    'target_transitions': replay_target.transition_count,
                    'target_visits': replay_target.visits,
                    'target_levels': replay_target.levels_completed,
                    'target_score': round(replay_target.score, 4),
                    'frontier_size_before_trigger': frontier_size_before,
                    'archive_size_before': archive.size(),
                    'led_to_new_states': False,
                    'new_states_generated': 0,
                }
                replay_diagnostics.append(replay_event)

        # Pop node
        node = frontier.pop(0)
        expanded_state_hash = node.state_hash
        any_new_state_in_this_expansion = False

        shuffled_actions = list(avail_actions)
        random.shuffle(shuffled_actions)

        before_expansion_states = len(visited_states)

        for act in shuffled_actions:
            if total_actions_consumed >= MAX_STEPS: break
            clone = snapshot_wrapper(node.wrapper)
            fd, frame, state_str, levels = step_and_fetch(clone, act)
            total_actions_consumed += 1
            nodes_expanded += 1
            if frame is None: continue
            h = frame_hash(frame)
            if levels > best_levels:
                best_levels = levels
                new_seq = node.action_seq + (act,)
                best_action_str = str(new_seq)
                best_state_hash = h
                levels_progress_events.append({'seq': best_action_str, 'levels': best_levels, 'hash': h, 'state': state_str})
            if h not in visited_states:
                visited_states.add(h)
                expansions_without_new_state = 0
                consecutive_zero_new_states = 0
                any_new_state_in_this_expansion = True
                new_depth = node.depth + 1
                new_node = BFSSnapshotNode(
                    wrapper=clone, state_hash=h, action_seq=node.action_seq + (act,),
                    depth=new_depth, levels_completed=levels)
                if new_depth < MAX_PLY and not is_game_over(state_str):
                    frontier.append(new_node)
                safe_stash.append(new_node)
                archive.add_or_update(
                    state_hash=h, action_seq=node.action_seq + (act,),
                    depth=new_depth, levels_completed=levels,
                    parent_hash=expanded_state_hash, wrapper_snapshot=clone)
            else:
                expansions_without_new_state += 1
                consecutive_zero_new_states += 1

        if any_new_state_in_this_expansion:
            archive.record_transition(expanded_state_hash)
            if replay_target is not None:
                archive.record_replay(led_to_new_states=True)
                # Update last replay event with new state info
                if replay_diagnostics:
                    replay_diagnostics[-1]['led_to_new_states'] = True
                    replay_diagnostics[-1]['new_states_generated'] = len(visited_states) - before_expansion_states
        else:
            if archive_replays_triggered > 0:
                archive.record_replay(led_to_new_states=False)

    # Summarize replay diagnostics
    unique_new_states_from_replay = sum(
        1 for ev in replay_diagnostics if ev['led_to_new_states'])
    unique_new_levels_from_replay = 0  # We'll check per-event

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
        'archive_replays_triggered': archive_replays_triggered,
        'archive_size_final': archive.size(),
        'archive_replay_success_rate': archive.n_replay_success / max(1, archive.n_replays),
        'replay_diagnostics': replay_diagnostics,
        'unique_replays_with_new_states': unique_new_states_from_replay,
        'unique_new_levels_from_replay': unique_new_levels_from_replay,
    }

# Run diagnostic on tn36 only
print(f"[{now_iso()}] v31 DIAGNOSTIC RUN ON tn36")
print("="*60)
result = bfs_solve_game_diagnostic('tn36')
print()
print("GAME:", result['game_id'])
print("STATUS:", result['status'])
print("Total levels:", result['best_levels_completed'])
print("Total states discovered:", result['unique_states_discovered'])
print("Total nodes expanded:", result['nodes_expanded'])
print("Total actions consumed:", result['total_actions_consumed'])
print("Fallbacks triggered:", result['fallbacks_triggered'])
print("Archive replays triggered:", result['archive_replays_triggered'])
print("Archive size final:", result['archive_size_final'])
print("Replay success rate:", result['archive_replay_success_rate'])
print("Unique replays that led to new states:", result['unique_replays_with_new_states'])
print("Unique new levels from replays:", result['unique_new_levels_from_replay'])
print("Frontier remaining:", result['frontier_remaining'])
print()
print("--- REPLAY DIAGNOSTICS ---")
for ev in result['replay_diagnostics']:
    print(f"  Replay #{ev['replay_num']}: target={ev['target_state_hash']}, depth={ev['target_depth']}, trans={ev['target_transitions']}, visits={ev['target_visits']}, score={ev['target_score']}")
    print(f"    frontier_before={ev['frontier_size_before_trigger']}, archive_before={ev['archive_size_before']}")
    print(f"    led_to_new_states={ev['led_to_new_states']}, new_states_gen={ev['new_states_generated']}")
print()
print("JSON OUTPUT (for parsing):")
print(json.dumps(result, default=str))
