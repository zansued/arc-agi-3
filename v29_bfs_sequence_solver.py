#!/usr/bin/env python3
"""
v29_bfs_sequence_solver.py — ARC-AGI-3 BFS Sequence Explorer

Complete architectural break from v24_fix4 family.
Primary loop: BFS over action sequences using reset+replay.
No spectral routing, no replay-archive, no stateless action selection.

Algorithm:
  BFS over action sequences, depth-bounded to max_ply per round.
  Each frontier entry = (frame_hash, action_sequence_tuple)
  Evaluate a sequence by calling game.reset(), then replaying the sequence.
  Replay cache keyed by (game_id, action_sequence_tuple) to skip duplicates.
  Hard cap: max_steps total per game.
  Stagnation detection: if no new unique state found in stagnation_limit
    consecutive sequences, switch to random baseline for remaining budget.

Usage:
  python3 v29_bfs_sequence_solver.py [--games sp80,cn04,bp35] [--max-ply 8] [--max-steps 500] [--full] [--output results.csv]
"""

import argparse
import csv
import hashlib
import os
import sys
import time
from collections import deque
from datetime import datetime, timezone

import numpy as np
from arc_agi import Arcade


FRAGILE_GAMES = {'tn36', 'vc33', 'su15', 'sk48', 'm0r0'}
FULL_GAMES = [
    'sk48', 'bp35', 'tn36', 'wa30', 'vc33', 'tu93', 'tr87', 'su15', 'sp80',
    'sc25', 'sb26', 's5i5', 're86', 'r11l', 'm0r0', 'ls20', 'lp85', 'lf52',
    'ka59', 'g50t', 'ft09', 'dc22', 'cd82', 'ar25', 'cn04',
]


def frame_hash(arr):
    """Canonical hash for game frame/grid"""
    if arr is None:
        return ''
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()


def extract_frame(raw):
    """Extract a numpy grid from whatever the environment returns"""
    if raw is None:
        return None
    if isinstance(raw, np.ndarray):
        return raw.squeeze() if raw.ndim > 2 else raw
    if hasattr(raw, 'frame'):
        arr = np.asarray(raw.frame, dtype=np.int32)
        if arr.ndim == 3:
            arr = arr[0]
        return arr
    if hasattr(raw, 'grid'):
        return np.asarray(raw.grid, dtype=np.int32)
    return None


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class BFSSolver:
    """BFS sequence explorer for ARC-AGI-3"""

    def __init__(self, max_ply=8, max_steps=500, stagnation_limit=50):
        self.max_ply = max_ply
        self.max_steps = max_steps
        self.stagnation_limit = stagnation_limit

    def solve(self, game_id, out_dir='arc_runs', verbose=True):
        """Run BFS sequence search for a single game"""
        game = Arcade().make(game_id)
        action_space = game.action_space
        # action_space can be a list of GameAction objects
        if hasattr(action_space, 'n'):
            n_actions = action_space.n
        elif isinstance(action_space, (list, tuple)):
            n_actions = len(action_space)
        else:
            n_actions = 8  # fallback

        steps = 0
        states_discovered = {}  # hash -> count
        levels_completed = 0
        crashes = 0
        replay_cache = set()

        frontier = deque()
        max_frontier = 0
        ply_reached = 0
        sequences_tried = 0
        total_cache_hits = 0

        # Start: reset game, capture initial state
        obs0 = extract_frame(game.reset())
        h0 = frame_hash(obs0)
        states_discovered[h0] = states_discovered.get(h0, 0) + 1
        frontier.append(((), h0))

        no_new_state_count = 0

        while frontier and steps < self.max_steps:
            max_frontier = max(max_frontier, len(frontier))
            seq, current_hash = frontier.popleft()

            # Check stagnation
            if no_new_state_count >= self.stagnation_limit:
                if verbose:
                    print(f"  Stagnation: no new states in {no_new_state_count} tries. Switching to random.")
                # Fall back to random actions for remaining budget
                remaining = self.max_steps - steps
                for _ in range(remaining):
                    if steps >= self.max_steps:
                        break
                    try:
                        # Use action_space.sample() if available, else random index
                        if hasattr(action_space, 'sample'):
                            a = action_space.sample()
                        elif isinstance(action_space, (list, tuple)):
                            a = random.choice(action_space)
                        else:
                            a = random.randrange(n_actions)
                        raw_after = game.step(a)
                        steps += 1
                        h = frame_hash(extract_frame(raw_after))
                        if h not in states_discovered:
                            states_discovered[h] = 0
                        states_discovered[h] += 1
                        if raw_after is not None:
                            lvls = int(getattr(raw_after, 'levels_completed', 0) or 0)
                            if lvls > levels_completed:
                                levels_completed = lvls
                    except Exception as e:
                        crashes += 1
                break

            # Depth limit
            current_ply = len(seq)
            if current_ply >= self.max_ply:
                continue

            # Generate action candidates
            for action_idx in range(n_actions):
                if steps >= self.max_steps:
                    break

                # Resolve action object: GameAction or raw int
                if isinstance(action_space, (list, tuple)):
                    action_obj = action_space[action_idx]
                else:
                    action_obj = action_idx

                new_seq = seq + (action_idx,)
                # Use action_obj in cache key for dedup
                cache_key = game_id + '|' + '|'.join(str(a) for a in new_seq)

                if cache_key in replay_cache:
                    total_cache_hits += 1
                    continue

                replay_cache.add(cache_key)
                sequences_tried += 1

                try:
                    # Reset and replay the full sequence
                    game.reset()
                    steps += 1  # reset costs a step
                    last_frame = None
                    reached_end = False

                    for act_idx in new_seq:
                        if steps >= self.max_steps:
                            break
                        # Resolve each action in the sequence
                        if isinstance(action_space, (list, tuple)):
                            act_obj = action_space[act_idx]
                        else:
                            act_obj = act_idx
                        # arc_agi step() returns raw frame, not (obs, reward, done, info)
                        raw_after = game.step(act_obj)
                        steps += 1
                        last_frame = raw_after
                        # Detect level completion via raw attributes
                        if raw_after is not None:
                            lvls = int(getattr(raw_after, 'levels_completed', 0) or 0)
                            if lvls > 0:
                                reached_end = True
                                break

                    frame = extract_frame(last_frame)
                    h = frame_hash(frame)
                    is_new = h not in states_discovered
                    states_discovered[h] = states_discovered.get(h, 0) + 1

                    if reached_end and not any(
                        s.endswith('_DONE') for s in states_discovered
                    ):
                        levels_completed += 1
                        if verbose:
                            print(f"  LEVEL {levels_completed}! seq={new_seq}, steps={steps}")

                    if is_new:
                        no_new_state_count = 0
                        ply_reached = max(ply_reached, current_ply + 1)
                        frontier.append((new_seq, h))
                    else:
                        no_new_state_count += 1

                except Exception as e:
                    crashes += 1
                    no_new_state_count += 1
                    if verbose:
                        print(f"  CRASH at seq={new_seq}: {e}")

        return {
            "game": game_id,
            "states": len(states_discovered),
            "levels": levels_completed,
            "crashes": crashes,
            "steps_used": min(steps, self.max_steps),
            "sequences_tried": sequences_tried,
            "cache_hits": total_cache_hits,
            "max_frontier": max_frontier,
            "max_ply_reached": ply_reached,
            "stagnation_hit": no_new_state_count >= self.stagnation_limit,
        }


def run_smoke(games, max_ply=8, max_steps=500, out_dir='arc_runs'):
    """Run solver on specified games verbosely"""
    solver = BFSSolver(max_ply=max_ply, max_steps=max_steps)
    results = []
    for gid in games:
        start = time.time()
        print(f"\n=== BFS {gid} ===")
        r = solver.solve(gid, out_dir=out_dir, verbose=True)
        elapsed = time.time() - start
        r["time_seconds"] = round(elapsed, 2)
        results.append(r)
        print(f"  Result: {r['levels']}L | {r['states']}S | "
              f"{r['steps_used']}st | {r['crashes']}X | "
              f"frontier={r['max_frontier']} ply={r['max_ply_reached']} [{elapsed:.1f}s]")
    return results


def run_full(games, max_ply=8, max_steps=500, out_dir='arc_runs'):
    """Run solver on all games"""
    solver = BFSSolver(max_ply=max_ply, max_steps=max_steps)
    results = []
    for i, gid in enumerate(games):
        start = time.time()
        print(f"[{i+1}/{len(games)}] BFS {gid}...", end="", flush=True)
        r = solver.solve(gid, out_dir=out_dir, verbose=False)
        elapsed = time.time() - start
        r["time_seconds"] = round(elapsed, 2)
        results.append(r)
        print(f" {r['levels']}L/{r['states']}S/{r['steps_used']}st [{elapsed:.1f}s]")
    return results


def print_table(results):
    print(f"\n{'Game':<8} {'Lvls':<6} {'States':<8} {'Steps':<8} {'Crash':<6} {'Frot':<6} {'Ply':<4} {'Seq':<6} {'Time':<8}")
    print("-"*66)
    tl = ts = tst = tc = 0
    for r in results:
        tl += r['levels']; ts += r['states']; tst += r['steps_used']; tc += r['crashes']
        print(f"{r['game']:<8} {r['levels']:<6} {r['states']:<8} {r['steps_used']:<8} "
              f"{r['crashes']:<6} {r['max_frontier']:<6} {r['max_ply_reached']:<4} "
              f"{r['sequences_tried']:<6} {r['time_seconds']:<8}")
    print("-"*66)
    print(f"{'TOTAL':<8} {tl:<6} {ts:<8} {tst:<8} {tc:<6}")
    return tl


def save_csv(results, path):
    fieldnames = ["game","states","levels","crashes","steps_used",
                   "sequences_tried","cache_hits","max_frontier",
                   "max_ply_reached","stagnation_hit","time_seconds"]
    ensure_dir(os.path.dirname(path) or '.')
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(results)
    print(f"\nResults saved to {path}")


def main():
    parser = argparse.ArgumentParser(description="v29 BFS Sequence Solver")
    parser.add_argument("--games", default=None, help="Comma-separated game IDs")
    parser.add_argument("--max-ply", type=int, default=8, help="Max BFS depth (default: 8)")
    parser.add_argument("--max-steps", type=int, default=500, help="Max steps per game (default: 500)")
    parser.add_argument("--full", action="store_true", help="Run full 25-game benchmark")
    parser.add_argument("--output", default=None, help="Output CSV path")
    parser.add_argument("--out-dir", default="arc_runs", help="Output directory")
    args = parser.parse_args()

    if args.games:
        games = [g.strip() for g in args.games.split(",")]
    elif args.full:
        games = FULL_GAMES
    else:
        games = ["sp80", "cn04", "bp35", "tn36"]

    print(f"v29 BFS Sequence Solver")
    print(f"  Games: {', '.join(games)} ({len(games)} total)")
    print(f"  Max ply: {args.max_ply}")
    print(f"  Max steps: {args.max_steps}")
    print(f"  Stagnation limit: 50")

    if len(games) <= 10:
        results = run_smoke(games, max_ply=args.max_ply, max_steps=args.max_steps, out_dir=args.out_dir)
    else:
        results = run_full(games, max_ply=args.max_ply, max_steps=args.max_steps, out_dir=args.out_dir)

    print_table(results)
    
    if args.output:
        save_csv(results, args.output)

    return results


if __name__ == "__main__":
    main()
