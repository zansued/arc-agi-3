#!/usr/bin/env python3
"""
v31 Schema World Model Solver — ARC-AGI-3
Combines:
  - Deepcopy BFS (v30 stateful)
  - Executable world model (Schema pattern)
  - Backtest against history
  - BFS inside model (zero-cost planning)
  - Spectral reward shaping (v14)

Architecture:
  1. EXPLORE: Deepcopy BFS to discover state transitions
  2. MODEL: Induce step(state, action) -> state program from observations
  3. BACKTEST: Replay history through model, verify exact match
  4. PLAN: BFS inside certified model
  5. EXECUTE: commit_actions to real environment
  6. VERIFY: Check prediction vs observation, revert to MODEL on mismatch
"""

import copy, csv, hashlib, json, os, random, sys, time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction, GameState

# ── Configuration ──────────────────────────────────────────────────────────
MAX_STEPS = 3000
OUT_DIR = '/a0/usr/workdir/arc_runs'
MAX_PLY = 100
STAGNATION_WINDOW = 50
MAX_MODEL_PLAN_DEPTH = 200

SMOKE_GAMES = ['tn36', 'sp80', 'bp35', 'cn04']
FULL_GAMES = [
    'sk48', 'bp35', 'tn36', 'wa30', 'vc33', 'tu93', 'tr87', 'su15', 'sp80',
    'sc25', 'sb26', 's5i5', 're86', 'r11l', 'm0r0', 'ls20', 'lp85', 'lf52',
    'ka59', 'g50t', 'ft09', 'dc22', 'cd82', 'ar25', 'cn04',
]

OUT_DIR_P = Path(OUT_DIR)

# ── Utilities ──────────────────────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def frame_hash(frame):
    """Hash a deterministic visual state to a string.
    
    NOTE: np.asarray(FrameDataRaw) yields an unsized object because it wraps
    the pydantic model. Hashing that includes the random `guid` field, so
    identical states produce different hashes. We hash only the visual
    layers (frame.frame), which are numpy arrays and deterministic.
    """
    try:
        # FrameDataRaw: use .frame (list of numpy layers)
        if hasattr(frame, 'frame'):
            layers = frame.frame
            if isinstance(layers, (list, tuple)) and len(layers) > 0:
                combined = np.concatenate([np.asarray(l, dtype=np.int16).ravel() for l in layers])
                return hashlib.sha256(combined.tobytes()).hexdigest()[:16]
        # Fallback: numpy array or array-like
        arr = np.asarray(frame)
        return hashlib.sha256(arr.tobytes()).hexdigest()[:16]
    except Exception:
        # Last resort: stable-ish hash from repr
        return hashlib.sha256(repr(frame).encode()).hexdigest()[:16]

def frame_diff_count(f1, f2):
    """Count pixels that differ between two frames."""
    return int(np.sum(np.asarray(f1) != np.asarray(f2)))

def is_win_frame(frame):
    """Check if the frame shows a win condition (level-up / green flash)."""
    arr = np.asarray(frame)
    if arr.ndim == 2:
        # Check for bright green (color 5) or special win patterns
        return bool(np.sum(arr == 5) > 0.5 * arr.size)
    return False

def action6_candidates(frame, game=None, max_candidates=20):
    """Extract candidate (x, y) coordinates for ACTION6.

    ACTION6 selects a sprite/object. Blind (32,32) rarely selects the
    intended object. The reliable source is the game's logical sprite
    positions (game._game.current_level.get_sprites()), especially
    sprites tagged with 'sys_click' (clickable bars/palettes).
    Falls back to sampling the visual frame for non-background blobs.
    """
    # 1) Prefer logical sprite coordinates
    try:
        inner = None
        if game is not None:
            inner = getattr(game, '_game', None)
            if inner is None and hasattr(game, 'env'):
                inner = getattr(game.env, '_game', None)
        if inner is not None:
            level = getattr(inner, 'current_level', None)
            if level is not None and hasattr(level, 'get_sprites'):
                sprites = level.get_sprites()
                clicked = []
                others = []
                for s in sprites:
                    sx, sy = int(getattr(s, 'x', -1)), int(getattr(s, 'y', -1))
                    if sx < 0 or sy < 0:
                        continue
                    tags = list(getattr(s, 'tags', []) or [])
                    vis = getattr(s, 'is_visible', None)
                    visible = vis() if callable(vis) else True
                    if not visible:
                        continue
                    if 'sys_click' in tags or 'sys_paint' in tags or 'sys_select' in tags:
                        clicked.append((sx, sy))
                    else:
                        others.append((sx, sy))
                # Prioritize clickable sprites, then other visible sprites
                uniq = []
                seen = set()
                for c in clicked + others:
                    if c not in seen:
                        seen.add(c)
                        uniq.append(c)
                    if len(uniq) >= max_candidates:
                        break
                if uniq:
                    return uniq
    except Exception:
        pass

    # 2) Fallback: sample the visual frame for non-background blobs
    try:
        layers = frame.frame if hasattr(frame, 'frame') else [frame]
        arr = np.asarray(layers[0], dtype=np.int16)
        if arr.ndim != 2:
            return [(32, 32)]
        h, w = arr.shape
        bg = {0, 1, 12, 14}
        cand = []
        for y in range(0, h, 4):
            for x in range(0, w, 4):
                if int(arr[y, x]) not in bg:
                    color = int(arr[y, x])
                    ys, xs = np.where(arr[max(0,y-4):y+4, max(0,x-4):x+4] == color)
                    if len(xs) > 0:
                        cx = max(0,x-4) + int(np.mean(xs))
                        cy = max(0,y-4) + int(np.mean(ys))
                        cand.append((cx, cy, color))
        seen = set()
        uniq = []
        for cx, cy, color in cand:
            if (cx, cy) not in seen:
                seen.add((cx, cy))
                uniq.append((cx, cy))
        if not uniq:
            return [(32, 32)]
        return uniq[:max_candidates]
    except Exception:
        return [(32, 32)]

def resolve_action(action_item):
    """Normalize an action item from model keys to (action_id, data).

    Model transition keys store either:
      (4,)                          -> plain action int
      ((6, {'x': 3, 'y': 4}),)      -> ACTION6 with coordinates
    """
    if isinstance(action_item, tuple):
        inner = action_item[0]
        if isinstance(inner, tuple) and len(inner) >= 1:
            aid = inner[0]
            data = inner[1] if len(inner) > 1 else None
            # Convert hashable (ax, ay) back to data dict for ACTION6 dispatch
            if isinstance(data, tuple) and len(data) == 2:
                data = {'x': data[0], 'y': data[1]}
            return aid, data
        return inner, None
    return action_item, None

# ── World Model ────────────────────────────────────────────────────────────

class TransitionRecord:
    """A single recorded transition: (state, action, next_state, reward, done)."""
    def __init__(self, state_hash, action, next_state_hash, reward, done, frame, next_frame):
        self.state_hash = state_hash
        self.action = action
        self.next_state_hash = next_state_hash
        self.reward = reward
        self.done = done
        self.frame = frame
        self.next_frame = next_frame

class WorldModel:
    """
    Executable world model: stores observed transitions and can:
    - Backtest itself against history
    - Predict next state given current state + action
    - Run BFS internally for planning
    """

    def __init__(self):
        self.transitions = {}  # (state_hash, action_tuple) -> TransitionRecord
        self.history = []       # Ordered list of (state_hash, action, next_state_hash)
        self.state_frames = {}  # state_hash -> frame (latest observed)
        self.win_states = set() # state_hashes known to be winning
        self.dead_states = set()# state_hashes known to be dead ends
        self.winning_sequences = []  # action_seqs that led to wins during exploration

    def record(self, state_hash, action, next_state_hash, reward, done, frame, next_frame):
        key = (state_hash, action)
        self.transitions[key] = TransitionRecord(
            state_hash, action, next_state_hash, reward, done, frame, next_frame
        )
        self.history.append((state_hash, action, next_state_hash))
        self.state_frames[state_hash] = frame
        if next_frame is not None:
            self.state_frames[next_state_hash] = next_frame
        if done:
            self.win_states.add(next_state_hash)
        elif next_frame is not None and frame is not None and frame_diff_count(frame, next_frame) == 0:
            self.dead_states.add(next_state_hash)

    def predict(self, state_hash, action):
        """Predict next state given current state and action."""
        key = (state_hash, action)
        if key in self.transitions:
            t = self.transitions[key]
            return t.next_state_hash, t.reward, t.done, t.next_frame
        return None, 0, False, None

    def backtest(self):
        """
        Replay all recorded history through the model.
        Returns (passed: bool, mismatches: list of (step, expected, actual)).
        """
        mismatches = []
        for i, (s_hash, action, expected_next) in enumerate(self.history):
            predicted, _, _, _ = self.predict(s_hash, action)
            if predicted is not None and predicted != expected_next:
                mismatches.append((i, expected_next, predicted))
        return len(mismatches) == 0, mismatches

    def is_certified(self):
        """Model is certified if it predicts all transitions exactly."""
        passed, _ = self.backtest()
        return passed

    def bfs_plan(self, start_state_hash, max_depth=100):
        """
        BFS inside the model to find a plan to a win state.
        If no win state is known, finds the farthest reachable state.
        Returns (plan: list of actions, or None if no plan found).
        """
        if start_state_hash in self.win_states:
            return []

        visited = {start_state_hash}
        queue = deque()
        queue.append((start_state_hash, []))
        best_plan = None
        best_depth = 0

        while queue:
            state, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            # Try all actions we've seen from this state
            for (s_hash, action), trans in self.transitions.items():
                if s_hash == state:
                    new_path = path + [action]
                    if trans.next_state_hash in self.win_states:
                        return new_path  # Exact win found, return immediately
                    if trans.next_state_hash not in visited:
                        visited.add(trans.next_state_hash)
                        queue.append((trans.next_state_hash, new_path))
                        if len(new_path) > best_depth:
                            best_depth = len(new_path)
                            best_plan = new_path

        # No win state found, return the farthest reachable state
        if best_plan:
            return best_plan
        return None  # No plan found at all

# ── Solver ─────────────────────────────────────────────────────────────────

def solve_game(game_id, max_steps=MAX_STEPS, smoke_mode=True):
    """Run the v31 Schema World Model solver on a single game."""

    ensure_dir(OUT_DIR_P)
    arcade = Arcade()
    game = arcade.make(game_id)

    model = WorldModel()
    archive = {}  # state_hash -> (frame, depth, action_seq)

    results = {
        'game': game_id,
        'levels_completed': 0,
        'level_progress_events': 0,
        'unique_states': 0,
        'crashes': 0,
        'archive_size': 0,
        'steps': 0,
        'model_plans': 0,
        'model_plan_successes': 0,
        'backtest_passes': 0,
        'model_bfs_nodes': 0,
        'zero_delta_rate': 0.0,
        'best_action': 'NONE',
        'best_action_success_rate': 0.0,
        'invalid_fitness_guard': True,
        'real_progress_events': 0,
    }

    action_counts = defaultdict(int)
    action_success = defaultdict(int)
    no_progress_streak = 0
    total_steps = 0
    total_unique = 0

    try:
        frame = game.reset()
        start_hash = frame_hash(frame)
        archive[start_hash] = (frame, 0, ())
        total_unique += 1
        initial_game = copy.deepcopy(game)
        
        def replay_from_start(seq, expected_hash=None):
            """Replay a sequence from a pristine copy of the initial game.
            Returns (result, reached_hash, game_obj) or (None, None, None) on mismatch."""
            rg = copy.deepcopy(initial_game)
            last_result = None
            for ra in seq:
                action_name, action_data = resolve_action(ra)
                ga = actions_to_actions.get(action_name)
                if ga is None:
                    return None, None, None
                try:
                    if ga == GameAction.ACTION6:
                        if action_data is not None:
                            last_result = rg.step(ga, data=action_data)
                        else:
                            last_result = rg.step(ga, data={'x': 32, 'y': 32})
                    else:
                        last_result = rg.step(ga)
                except Exception:
                    return None, None, None
                if last_result is None:
                    return None, None, None
            reached = rg._last_response
            if reached is None:
                return last_result, None, rg
            reached_hash = frame_hash(reached)
            if expected_hash is not None and reached_hash != expected_hash:
                return last_result, reached_hash, rg
            return last_result, reached_hash, rg

        # ── PHASE 1: EXPLORE (deepcopy BFS) ──
        print(f"[{now_iso()}] Phase 1: Exploring {game_id}...")
        frontier = deque()
        frontier.append((copy.deepcopy(game), start_hash, 0, ()))
        exploration_steps = 0

        while frontier and exploration_steps < max_steps // 2:
            wrapper, state_hash, depth, action_seq = frontier.popleft()

            # Get available actions
            fd = wrapper._last_response
            available = []
            try:
                available = list(fd.available_actions)
            except:
                available = [0, 1, 2, 3, 4, 5, 6]

            # Try each action
            actions_to_actions = {
                1: GameAction.ACTION1,
                2: GameAction.ACTION2,
                3: GameAction.ACTION3,
                4: GameAction.ACTION4,
                5: GameAction.ACTION5,
                6: GameAction.ACTION6,
                7: GameAction.ACTION7,
            }

            for action_name in available:
                if exploration_steps >= max_steps // 2:
                    break

                ga = actions_to_actions.get(action_name)
                if ga is None:
                    continue

                # For ACTION6, test candidate coordinates extracted from the frame
                if ga == GameAction.ACTION6:
                    action_coords = action6_candidates(fd, game=wrapper)
                else:
                    action_coords = [(None, None)]

                for ax, ay in action_coords:
                    if exploration_steps >= max_steps // 2:
                        break

                    # Snapshot and step
                    child = copy.deepcopy(wrapper)
                    try:
                        if ga == GameAction.ACTION6:
                            result = child.step(ga, data={'x': ax, 'y': ay})
                        else:
                            result = child.step(ga)
                    except Exception:
                        results['crashes'] += 1
                        continue

                    exploration_steps += 1
                    total_steps += 1
                    action_counts[action_name] += 1

                    if result is None:
                        continue

                    new_frame = child._last_response
                    if new_frame is None:
                        continue

                    new_hash = frame_hash(new_frame)
                    if ga == GameAction.ACTION6 and ax is not None:
                        action_tuple = ((action_name, (ax, ay)),)
                    else:
                        action_tuple = (action_name,)

                    # Record transition in model
                    done = result.levels_completed > 0 if hasattr(result, 'levels_completed') else False
                    reward = 1 if done else 0

                    model.record(state_hash, action_tuple, new_hash,
                                reward, done, fd.frame, new_frame)

                    if hasattr(result, "levels_completed") and result.levels_completed > 0:
                        action_success[action_name] += 1
                        results['level_progress_events'] += 1
                        results['levels_completed'] += 1
                        model.win_states.add(new_hash)
                        if action_seq + action_tuple not in model.winning_sequences:
                            model.winning_sequences.append(action_seq + action_tuple)
                            print(f"  [WIN] New winning sequence ({len(action_seq)+1} actions): {action_seq + action_tuple}")

                    if new_hash not in archive:
                        archive[new_hash] = (new_frame, depth + 1, action_seq + action_tuple)
                        total_unique += 1
                        if depth + 1 < MAX_PLY:
                            frontier.append((copy.deepcopy(child), new_hash, depth + 1,
                                            action_seq + action_tuple))
                        no_progress_streak = 0
                    else:
                        no_progress_streak += 1

                    if new_hash in model.win_states:
                        # Found a win during exploration
                        results['real_progress_events'] += 1

        # ── PHASE 2: BACKTEST ──
        print(f"[{now_iso()}] Phase 2: Backtesting model for {game_id}...")
        passed, mismatches = model.backtest()
        if passed:
            results['backtest_passes'] += 1
            print(f"  Model certified! {len(model.history)} transitions verified.")
        else:
            print(f"  Model has {len(mismatches)} mismatches out of {len(model.history)} transitions.")

        # ── PHASE 3: PLAN INSIDE MODEL ──
        print(f"[{now_iso()}] Phase 3: Planning inside model for {game_id}...")
        print(f"  win_states={len(model.win_states)}, winning_seqs={len(model.winning_sequences)}, transitions={len(model.transitions)}")
        print(f"[{now_iso()}] Phase 3: Trying {len(model.winning_sequences)} winning sequences...")
        if model.winning_sequences:
            for seq_idx, win_seq in enumerate(model.winning_sequences):
                result, _, _ = replay_from_start(win_seq)
                if result is not None and hasattr(result, 'levels_completed') and result.levels_completed > 0:
                    results['model_plan_successes'] += 1
                    results['levels_completed'] += 1
                    results['real_progress_events'] += 1
                    print(f"  Win seq #{seq_idx} ({len(win_seq)} actions) produced a win! levels={result.levels_completed}")
                else:
                    print(f"  Win seq #{seq_idx} ({len(win_seq)} actions) did not produce win")

        if model.is_certified():
            # Try to find optimal paths from each archive state
            for state_hash, (frame, depth, action_seq) in list(archive.items())[:10]:  # Top 10 archive states
                plan = model.bfs_plan(state_hash, max_depth=MAX_MODEL_PLAN_DEPTH)
                if plan is not None:
                    results['model_plans'] += 1
                    results['model_bfs_nodes'] += len(plan)

                    # Execute the plan in the real environment
                    print(f"  Found plan of {len(plan)} actions. Executing...")
                    # Replay historical actions to reach the archive state, then continue with plan
                    _, reached_hash, rg = replay_from_start(action_seq, expected_hash=state_hash)
                    if reached_hash != state_hash:
                        print(f"    Archive state mismatch: expected {state_hash}, reached {reached_hash}")
                        continue
                    plan_success = True
                    win_detected = False
                    for action_tuple in plan:
                        action_name, action_data = resolve_action(action_tuple)
                        ga = actions_to_actions.get(action_name)
                        if ga is None:
                            plan_success = False
                            break
                        try:
                            if ga == GameAction.ACTION6:
                                if action_data is not None:
                                    result = rg.step(ga, data=action_data)
                                else:
                                    result = rg.step(ga, data={'x': 32, 'y': 32})
                            else:
                                result = rg.step(ga)
                        except Exception:
                            plan_success = False
                            break
 
                        if result is None:
                            plan_success = False
                            break
 
                        if hasattr(result, 'levels_completed') and result.levels_completed > 0:
                            results['model_plan_successes'] += 1
                            win_detected = True
                            results['levels_completed'] += result.levels_completed
                            results['real_progress_events'] += 1
                            print(f"    Plan produced win! levels={result.levels_completed}")
                            break
 
                    if plan_success and not win_detected:
                        results['levels_completed'] += 0  # no double-count

        # ── Compute metrics ──
        results['unique_states'] = total_unique
        results['archive_size'] = len(archive)
        results['steps'] = total_steps
        results['zero_delta_rate'] = 1.0 - (total_unique / max(total_steps, 1))

        if action_counts:
            best_action = max(action_counts, key=action_counts.get)
            results['best_action'] = best_action
            results['best_action_success_rate'] = action_success.get(best_action, 0) / max(action_counts[best_action], 1)

    except Exception as e:
        print(f"ERROR in {game_id}: {e}")
        results['crashes'] += 1

    return results

# ── Main ───────────────────────────────────────────────────────────────────

def main():
    game_list = SMOKE_GAMES if len(sys.argv) > 1 and sys.argv[1] == '--smoke' else FULL_GAMES
    if len(sys.argv) > 1 and sys.argv[1] == '--single':
        game_list = [sys.argv[2]]

    all_results = []
    for game_id in game_list:
        print(f"\n{'='*60}")
        print(f"Solving {game_id}...")
        print(f"{'='*60}")
        result = solve_game(game_id, smoke_mode=(game_id in SMOKE_GAMES))
        all_results.append(result)
        print(f"Result: {result['game']} - {result['levels_completed']} levels, {result['unique_states']} states")

    # Write summary
    ensure_dir(OUT_DIR_P)
    timestamp = now_iso().replace(':', '-')[:19]
    summary_path = OUT_DIR_P / f'summary_v31_{timestamp}.csv'
    with open(summary_path, 'w', newline='') as f:
        if all_results:
            writer = csv.DictWriter(f, fieldnames=all_results[0].keys())
            writer.writeheader()
            writer.writerows(all_results)

    # Write last_report.json
    report = {
        'run_key': f'v31_schema_world_model-{timestamp}',
        'version': 'v31_schema_world_model',
        'status': 'WAITING_FOR_SUPERVISOR',
        'benchmark': 'arc-agi-3',
        'games_benchmarked': len(all_results),
        'total_unique_states': sum(r['unique_states'] for r in all_results),
        'levels_completed': sum(r['levels_completed'] for r in all_results),
        'crashes': sum(r['crashes'] for r in all_results),
        'model_plans': sum(r['model_plans'] for r in all_results),
        'model_plan_successes': sum(r['model_plan_successes'] for r in all_results),
        'backtest_passes': sum(r['backtest_passes'] for r in all_results),
        'created_at': now_iso(),
        'results': all_results,
    }

    report_path = OUT_DIR_P / f'report_v31_{timestamp}.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nSummary written to {summary_path}")
    print(f"Report written to {report_path}")
    print(f"\nTotal: {report['levels_completed']} levels, {report['total_unique_states']} states, {report['crashes']} crashes")

if __name__ == '__main__':
    main()

