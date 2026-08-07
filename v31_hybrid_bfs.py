#!/usr/bin/env python3
"""
v31_hybrid_bfs — Hybrid solver: v30 deepcopy BFS + v28 archive-replay mechanism.

Architecture:
- Base: v30_stateful_bfs_solver.py deepcopy snapshot BFS (FIFO frontier, stagnation fallback)
- Addition: v28-style MinimalVisitedArchive tracking state transitions and replay selection
- Hybrid replay: when BFS stagnation is detected (3+ consecutive expansions with 0 new states),
  trigger archive replay: pop to the archived state with highest solved transitions and restart BFS

Key difference from v30:
  v30 stagnation -> random jump to any safe-stash node
  v31 stagnation -> archive-guided replay to highest-transition-count state with unexplored actions

Key difference from v28:
  v28 archive drives full search via replay-reset cycles
  v31 archive is a recovery layer grafted ONTO v30's BFS — BFS explores normally, archive
  catches it when it gets stuck and redirects to the most promising earlier state.

Design constraints from Hermes guidance:
- Graft replay as a wrapper, not an invasive rewrite
- Maintain v30's deepcopy isolation for parallel branches
- Apply replay as a recovery step: when branch hits 0 frontier expansion for N consecutive steps
- Archive stores {state_hash: transition_count} per exploration path
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

# ── Configuration ──────────────────────────────────────────────────────────
MAX_STEPS = 500          # Total actions across all expansions
OUT_DIR = 'arc_runs'
MAX_PLY = 100             # Max depth per path before stopping
STAGNATION_WINDOW = 50    # Consecutive expansions without new unique state (v30)
ARCHIVE_REPLAY_STEPS = 3  # Consecutive 0-new-state expansions before archive replay triggers
MAX_ARCHIVE_RESETS = 6    # Max number of archive replays per game (v28 guard)
OUT_DIR_P = Path(OUT_DIR)

SMOKE_GAMES = ['tn36', 'sp80', 'bp35', 'cn04']
FULL_GAMES = [
    'sk48', 'bp35', 'tn36', 'wa30', 'vc33', 'tu93', 'tr87', 'su15', 'sp80',
    'sc25', 'sb26', 's5i5', 're86', 'r11l', 'm0r0', 'ls20', 'lp85', 'lf52',
    'ka59', 'g50t', 'ft09', 'dc22', 'cd82', 'ar25', 'cn04',
]

# ── Utilities ──────────────────────────────────────────────────────────────

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

# ── Archive Cell (v28 minimal archive-replay) ──────────────────────────────

class ArchiveCell:
    """A state in the archive with its transition metadata."""
    __slots__ = ('state_hash', 'action_seq', 'depth', 'levels_completed',
                 'transition_count', 'visits', 'children_hashes', 'score',
                 'wrapper_snapshot')

    def __init__(self, state_hash: str, action_seq: tuple,
                 depth: int, levels_completed: int,
                 wrapper_snapshot=None):
        self.state_hash = state_hash
        self.action_seq = action_seq
        self.depth = depth
        self.levels_completed = levels_completed
        self.transition_count = 0      # How many successful transitions from this state
        self.visits = 1
        self.children_hashes: set[str] = set()
        self.score = 0.0
        self.wrapper_snapshot = wrapper_snapshot

    def compute_score(self, current_depth: int = 0) -> float:
        """Score for replay selection. Higher = more promising to replay."""
        # Prefer states with:
        # - High transition count (many things happened from here)
        # - Low visits (not over-explored)
        # - Moderate depth (not root, not too deep)
        depth_bonus = min(1.0, self.depth / 20.0)
        novelty = 1.0 / (1.0 + self.visits)
        transition_bonus = math.log1p(self.transition_count) * 0.5
        level_bonus = self.levels_completed * 10.0
        child_exploration = 0.5 if len(self.children_hashes) == 0 else 0.1  # frontier states
        return novelty * 2.5 + depth_bonus * 0.8 + transition_bonus + level_bonus + child_exploration


class HybridArchive:
    """Archive tracking state transitions for replay guidance."""

    def __init__(self, max_size: int = 256):
        self.cells: dict[str, ArchiveCell] = {}
        self.max_size = max_size
        self.n_replays = 0
        self.n_replay_success = 0  # replay that led to new states

    def add_or_update(self, state_hash: str, action_seq: tuple,
                      depth: int, levels_completed: int,
                      parent_hash: str = None,
                      wrapper_snapshot=None):
        if not state_hash:
            return None
        if state_hash in self.cells:
            cell = self.cells[state_hash]
            cell.visits += 1
            # Keep shortest action sequence to reach this state
            if len(action_seq) < len(cell.action_seq):
                cell.action_seq = action_seq
                cell.depth = depth
                if wrapper_snapshot is not None:
                    cell.wrapper_snapshot = wrapper_snapshot
            if levels_completed > cell.levels_completed:
                cell.levels_completed = levels_completed
            return cell
        # Evict if full
        if len(self.cells) >= self.max_size:
            worst = min(self.cells.values(),
                        key=lambda c: (c.score, c.visits, len(c.action_seq)))
            del self.cells[worst.state_hash]
        cell = ArchiveCell(state_hash, action_seq, depth, levels_completed,
                           wrapper_snapshot)
        self.cells[state_hash] = cell
        if parent_hash and parent_hash in self.cells:
            self.cells[parent_hash].children_hashes.add(state_hash)
        return cell

    def record_transition(self, state_hash: str):
        """Increment transition count for a state."""
        if state_hash in self.cells:
            self.cells[state_hash].transition_count += 1

    def record_replay(self, led_to_new_states: bool):
        self.n_replays += 1
        if led_to_new_states:
            self.n_replay_success += 1

    def select_replay_target(self, stagnated: bool) -> ArchiveCell | None:
        """Select the best state to replay from."""
        # v28-style: select by action sequence length diversity, NOT deepcopy snapshot
        # Prefer cells with medium-length sequences (enough to reach interesting states)
        candidates = [c for c in self.cells.values()
                      if len(c.action_seq) > 0 and len(c.action_seq) <= 80]
        if not candidates:
            candidates = [c for c in self.cells.values() if len(c.action_seq) > 0]
        if not candidates:
            return None

        # v28-style score: novelty + frontier bias + depth balance
        for c in candidates:
            c.score = c.compute_score()

        # Top-5 selection, but prefer states with different action sequences
        ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
        top_n = min(5, len(ranked))
        selected = random.choice(ranked[:top_n])
        return selected

    def replay_from_archive(self, arcade: 'Arcade', cell: ArchiveCell) -> object:
        """
        v28-style replay: reset the game to initial state and replay the action sequence.
        This is fundamentally different from deepcopy snapshot restoration.
        """
        wrapper = arcade.make(cell.game_id) if hasattr(cell, 'game_id') else None
        if wrapper is None:
            return None
        wrapper.reset()
        for action_id in cell.action_seq:
            try:
                action = GameAction.from_id(action_id)
                if action_id == 6:
                    wrapper.step(action, data={'x': 32, 'y': 32})
                else:
                    wrapper.step(action)
            except Exception:
                return None
        return wrapper

    def size(self) -> int:
        return len(self.cells)

    def stats(self) -> dict:
        return {
            'archive_size': len(self.cells),
            'n_replays': self.n_replays,
            'n_replay_success': self.n_replay_success,
            'replay_success_rate': self.n_replay_success / max(1, self.n_replays),
        }


# ── BFS Hybrid Solver ──────────────────────────────────────────────────────

def replay_game_to_state(arcade: Arcade, game_id: str,
                          action_seq: tuple) -> object:
    """
    v28-style reset-and-replay: create fresh game, reset, replay actions.
    Returns wrapper at the target state, or None on failure.
    """
    try:
        wrapper = arcade.make(game_id)
        if wrapper is None:
            return None
        wrapper.reset()
        for action_id in action_seq:
            action = GameAction.from_id(action_id)
            if action_id == 6:
                fd = wrapper.step(action, data={'x': 32, 'y': 32})
            else:
                fd = wrapper.step(action)
            if fd is None:
                return None
        return wrapper
    except Exception:
        return None


def bfs_solve_game(game_id: str,
                   max_steps: int = MAX_STEPS,
                   max_ply: int = MAX_PLY,
                   stagnation_window: int = STAGNATION_WINDOW,
                   archive_replay_steps: int = ARCHIVE_REPLAY_STEPS) -> dict:
    """
    Hybrid BFS solver: v30 deepcopy base + v28 archive-replay recovery layer.

    The BFS explores normally using deepcopy snapshots. When the frontier
    produces 0 new states for `archive_replay_steps` consecutive expansions,
    the archive triggers a replay: v28-style reset+replay restores the game
    to a promising archive state by resetting and replaying action sequence.
    """
    # ── Initialize game ────────────────────────────────────────────────────
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

    # ── Archive (new in v31) ──────────────────────────────────────────────
    archive = HybridArchive(max_size=256)
    archive.add_or_update(
        state_hash=init_hash,
        action_seq=(),
        depth=0,
        levels_completed=init_levels,
        wrapper_snapshot=snapshot_wrapper(wrapper)
    )

    # ── Frontier (v30-style BFS) ──────────────────────────────────────────
    class BFSSnapshotNode:
        __slots__ = ('wrapper', 'state_hash', 'action_seq',
                     'depth', 'levels_completed')
        def __init__(self, wrapper, state_hash, action_seq,
                     depth, levels_completed):
            self.wrapper = wrapper
            self.state_hash = state_hash
            self.action_seq = action_seq
            self.depth = depth
            self.levels_completed = levels_completed

    init_node = BFSSnapshotNode(
        wrapper=snapshot_wrapper(wrapper),
        state_hash=init_hash,
        action_seq=(),
        depth=0,
        levels_completed=init_levels
    )

    frontier = [init_node]
    safe_stash: list[BFSSnapshotNode] = [init_node]
    visited_states: set[str] = {init_hash}

    total_actions_consumed = 0
    nodes_expanded = 0
    best_levels = 0
    best_action_str = ''
    best_state_hash = init_hash
    levels_progress_events: list[dict] = []

    # Stagnation tracking
    stagnation_counter = 0          # v30-style: long stagnation fallback
    expansions_without_new_state = 0
    fallbacks_triggered = 0         # v30-style fallback count

    # v31 archive-replay tracking
    consecutive_zero_new_states = 0  # triggers archive replay at threshold
    archive_replays_triggered = 0
    last_replay_state = None

    while frontier and total_actions_consumed < max_steps:
        # Initialize replay_target for scoping (may be assigned in archive replay block)
        replay_target = None

        # ── v30-style stagnation fallback (long window) ────────────────────
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
            consecutive_zero_new_states = 0

        # ── v31 archive replay trigger (short window) ──────────────────────
        if (consecutive_zero_new_states >= archive_replay_steps
                and archive.size() > 1
                and archive_replays_triggered < MAX_ARCHIVE_RESETS):
            replay_target = archive.select_replay_target(stagnated=True)
            if replay_target and replay_target.state_hash != last_replay_state:
                archive_replays_triggered += 1
                last_replay_state = replay_target.state_hash

                # Create a new BFS node from the archive cell
                replay_wrapper = snapshot_wrapper(replay_target.wrapper_snapshot)
                replay_node = BFSSnapshotNode(
                    wrapper=replay_wrapper,
                    state_hash=replay_target.state_hash,
                    action_seq=replay_target.action_seq,
                    depth=replay_target.depth,
                    levels_completed=replay_target.levels_completed
                )

                # Insert at front of frontier
                frontier.insert(0, replay_node)
                consecutive_zero_new_states = 0

                # Track whether this replay leads to new states
                replay_led_to_new = False
                print(f"[v31] {game_id}: Archive replay #{archive_replays_triggered} "
                      f"to state {replay_target.state_hash[:8]} "
                      f"(transitions={replay_target.transition_count}, "
                      f"depth={replay_target.depth})")

        # ── Pop node (v30 BFS) ─────────────────────────────────────────────
        node = frontier.pop(0)

        # Track which state we're expanding (for archive transition tracking)
        expanded_state_hash = node.state_hash

        # ── Generate successors ────────────────────────────────────────────
        any_new_state_in_this_expansion = False

        # Randomize action order slightly to avoid deterministic lock-in
        shuffled_actions = list(avail_actions)
        random.shuffle(shuffled_actions)

        for act in shuffled_actions:
            if total_actions_consumed >= max_steps:
                break

            # Deepcopy and step
            clone = snapshot_wrapper(node.wrapper)
            fd, frame, state_str, levels = step_and_fetch(clone, act)
            total_actions_consumed += 1
            nodes_expanded += 1

            if frame is None:
                continue

            h = frame_hash(frame)

            # Track level progress
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

            if h not in visited_states:
                visited_states.add(h)
                expansions_without_new_state = 0
                consecutive_zero_new_states = 0
                any_new_state_in_this_expansion = True

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

                # ── v31: Archive the new state with wrapper snapshot ────────
                archive.add_or_update(
                    state_hash=h,
                    action_seq=node.action_seq + (act,),
                    depth=new_depth,
                    levels_completed=levels,
                    parent_hash=expanded_state_hash,
                    wrapper_snapshot=clone  # save for future replay
                )

            else:
                expansions_without_new_state += 1
                consecutive_zero_new_states += 1

        # ── Record transition count for the expanded state ─────────────────
        if any_new_state_in_this_expansion:
            archive.record_transition(expanded_state_hash)
            if replay_target is not None:
                archive.record_replay(led_to_new_states=True)
        else:
            if archive_replays_triggered > 0:
                archive.record_replay(led_to_new_states=False)

        # Reset replay_target tracker each loop iteration
        replay_target = None

    # ── Return results ─────────────────────────────────────────────────────
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
        'archive_replay_success_rate': archive.stats()['replay_success_rate'],
    }


# ── Runner ─────────────────────────────────────────────────────────────────

def run_benchmark(game_list: list[str],
                  version_label: str = 'v31_smoke') -> list[dict]:
    prefix = f'{version_label}_hybrid_bfs'
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
              f"replays={stats.get('archive_replays_triggered', 0)}")

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


# ── CLI Entry ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='v31 Hybrid BFS (BFS + Archive Replay)')
    parser.add_argument('--smoke', action='store_true', help='Run on smoke games')
    parser.add_argument('--full', action='store_true', help='Run on full 25-game benchmark')
    parser.add_argument('--games', type=str, default='',
                        help='Comma-separated game IDs')
    args = parser.parse_args()

    if args.games:
        games = [g.strip() for g in args.games.split(',') if g.strip()]
    elif args.full:
        games = FULL_GAMES
    elif args.smoke:
        games = SMOKE_GAMES
    else:
        games = SMOKE_GAMES

    label = 'v31_full' if args.full else 'v31_smoke'
    print(f"[{now_iso()}] v31 Hybrid BFS starting on {len(games)} games...")
    print(f"[{now_iso()}] Stand-down: full 25-game benchmark NOT authorized for v30. v31 is the current target.")

    stats = run_benchmark(games, version_label=label)

    # Summary
    total_levels = sum(s.get('best_levels_completed', 0) for s in stats)
    total_states = sum(s.get('unique_states_discovered', 0) for s in stats)
    total_replays = sum(s.get('archive_replays_triggered', 0) for s in stats)
    games_with_levels = [s['game_id'] for s in stats if s.get('best_levels_completed', 0) > 0]

    print(f"\n{'='*60}")
    print(f"v31 Results Summary")
    print(f"{'='*60}")
    print(f"Games: {len(stats)}")
    print(f"Total levels: {total_levels}")
    print(f"Total states: {total_states}")
    print(f"Total archive replays: {total_replays}")
    print(f"Games with levels: {games_with_levels}")
    print(f"Errors: {sum(1 for s in stats if s.get('status') == 'ERROR')}")
    print(f"{'='*60}")

    # Auto-run post_run_report.py
    post_run = Path('post_run_report.py')
    if post_run.exists():
        import subprocess
        game_list_str = ','.join(games)
        solver_file = 'v31_hybrid_bfs.py'
        action_summary = (
            f"v31 hybrid BFS with archive replay. "
            f"{total_replays} archive replays triggered. "
            f"Games with levels: {games_with_levels}."
        )
        cmd = [
            sys.executable, 'post_run_report.py',
            '--version', label,
            '--game-list', game_list_str,
            '--solver-file', solver_file,
            '--full-benchmark', 'yes' if args.full else 'no',
            '--objective', 'ARC-AGI-3: v31 hybrid BFS + archive replay.',
            '--action-summary', action_summary,
        ]
        print(f"\n[BRIDGE] Calling post_run_report.py...")
        subprocess.run(cmd)
