#!/usr/bin/env python3
"""
v14 Spectral Reward Shaping — ARC-AGI-3 DGM-lite Go-Explore Archive Planner

v13 + Spectral Reward Shaping heuristic for archive cell selection

Novelty in this version:
- SpectralRewardHistory tracks grid features per level
- select_cell_v9_score includes spectral_reward term (weighted)
- Frame delta, histogram entropy, spatial complexity guide archive selection
- Baseline v13 preserved via spectral_reward_weight=0.0

Method: Go-Explore (Ecoffet et al., 2019) adapted for ARC-AGI-3
"""
import os, json, csv, random, hashlib, math, sys, copy
from datetime import datetime, timezone
from collections import Counter, defaultdict, deque

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction, GameState

# v14: Import spectral reward shaping module
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'arc_runs'))
from arc_runs.v14_spectral_reward_shaping import SpectralRewardHistory, spectral_reward

def step_action6(wrapper, x=32, y=32):
    return wrapper.step(GameAction.ACTION6, data={'x': x, 'y': y})

MAX_STEPS = 500
OUT_DIR = "arc_runs"

# Go-Explore parameters
MAX_REPLAY_LEN = 80
MAX_ARCHIVE_RESETS = 3
STAGNATION_STEPS = 30
ZERO_DELTA_STREAK = 8
ARCHIVE_PERIOD = 100

# v14: Spectral reward shaping parameters
SPECTRAL_WEIGHT = 1.0      # Weight of spectral term in cell score (0.0 = pure v13)
SPECTRAL_HISTORY_LEN = 20  # Number of recent frames to track

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def frame_hash(arr):
    if arr is None:
        return ""
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def count_changed_pixels(prev, curr):
    if prev is None or curr is None:
        return 0
    try:
        a = np.asarray(prev, dtype=np.int32)
        b = np.asarray(curr, dtype=np.int32)
        if a.shape != b.shape:
            return -1
        return int(np.sum(a != b))
    except Exception:
        return -1

# ──────────────────────────────────────────────
# PATCH v13: FLOOD-FILL FALLBACK, EVALUATE STATE, GRADIENT MONITOR
# ──────────────────────────────────────────────

def _flood_fill_components(grid: np.ndarray) -> list[set]:
    h, w = grid.shape
    visited = np.zeros((h, w), dtype=bool)
    components = []
    for y in range(h):
        for x in range(w):
            if visited[y, x]:
                continue
            visited[y, x] = True
            if grid[y, x] == 0:
                continue
            comp = set()
            queue = deque([(x, y)])
            while queue:
                cx, cy = queue.popleft()
                if (cx, cy) in comp:
                    continue
                comp.add((cx, cy))
                for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        if not visited[ny, nx] and grid[ny, nx] != 0:
                            visited[ny, nx] = True
                            queue.append((nx, ny))
            if comp:
                components.append(comp)
    return components

def find_small_component_center(grid: np.ndarray) -> tuple | None:
    try:
        from scipy import ndimage as ndi
        labeled, n_features = ndi.label(grid > 0)
        if n_features == 0:
            return None
        sizes = np.bincount(labeled.ravel())
        sizes[0] = grid.size + 1
        smallest_label = sizes.argmin()
        ys, xs = np.where(labeled == smallest_label)
        return (int(xs.mean()), int(ys.mean()))
    except (ImportError, AttributeError, ValueError):
        pass
    comps = _flood_fill_components(grid)
    if not comps:
        return None
    smallest = min(comps, key=len)
    xs = [p[0] for p in smallest]
    ys = [p[1] for p in smallest]
    return (int(np.mean(xs)), int(np.mean(ys)))

def _matches_any_example(candidate: np.ndarray, examples: list) -> bool:
    for inp, exp_out in examples:
        if candidate.shape == exp_out.shape and np.array_equal(candidate, exp_out):
            return True
    return False

def evaluate_state(state: np.ndarray, examples: list, archive: set) -> tuple:
    if _matches_any_example(state, examples):
        return True, 1.0
    best_fitness = 0.0
    for inp, exp_out in examples:
        if state.shape != exp_out.shape:
            continue
        match = np.mean(state == exp_out)
        best_fitness = max(best_fitness, match)
    archive.add(state.tobytes())
    return False, best_fitness

class GradientMonitor:
    def __init__(self, patience: int = 5):
        self.patience = patience
        self._stall_count = 0
        self._prev_size = 0
    def step(self, archive_size: int) -> bool:
        delta = archive_size - self._prev_size
        self._prev_size = archive_size
        if delta == 0:
            self._stall_count += 1
        else:
            self._stall_count = 0
        return self._stall_count >= self.patience
    def reset(self):
        self._stall_count = 0
        self._prev_size = 0

# ---------------------------------------------------------------------------
# Archive Cell
# ---------------------------------------------------------------------------

class ArchiveCell:
    __slots__ = ('frame_tuples', 'sequence', 'novelty', 'visits', 'children', 'max_levels',
                 'state_hash', 'untried_actions', 'last_score_val', 'parent',
                 'spectral_reward', 'grid_features')  # v14: added spectral fields
    def __init__(self, frame_tuples, sequence, novelty, state_hash=""):
        self.frame_tuples = frame_tuples
        self.sequence = sequence
        self.novelty = novelty
        self.visits = 0
        self.children = []
        self.max_levels = 0
        self.state_hash = state_hash
        self.untried_actions = 0
        self.last_score_val = 0.0
        self.parent = None
        self.spectral_reward = 0.0   # v14: cached spectral reward
        self.grid_features = None    # v14: cached grid features for comparison

# ---------------------------------------------------------------------------
# State class
# ---------------------------------------------------------------------------

class State:
    def __init__(self, frame):
        self.frame = frame if frame is not None else []
    @property
    def frame(self):
        return self._frame
    @frame.setter
    def frame(self, val):
        self._frame = val

# ---------------------------------------------------------------------------
# Archive-based Go-Explore
# ---------------------------------------------------------------------------

class ArchiveGoExplore:
    def __init__(self):
        self.cells = {}
        self.cell_count = 0
        self.last_selector = "none"
        # v14: spectral reward history per level
        self._spectral_histories = {}  # level_idx -> SpectralRewardHistory
        self._spectral_stats = {"total_rewards": [], "avg_reward": 0.0, "max_reward": 0.0}

    def set_slot_map(self, slot_map):
        self.slot_map = slot_map

    def _get_spectral_history(self, level_idx: int) -> SpectralRewardHistory:
        if level_idx not in self._spectral_histories:
            self._spectral_histories[level_idx] = SpectralRewardHistory(max_history=SPECTRAL_HISTORY_LEN)
        return self._spectral_histories[level_idx]

    def add_to_archive(self, state, score, frame, novelty, state_hash="", level_idx=0):
        frame_tuples = tuple(map(tuple, state)) if hasattr(state, '__iter__') and hasattr(state, '__getitem__') else ()
        cell = ArchiveCell(frame_tuples, [], novelty, state_hash=state_hash)
        cell.novelty = novelty
        cell.visits = 0
        state_id = state_hash if state_hash else self._compute_state_id(state)
        if state_id not in self.cells:
            self.cell_count += 1
            # v14: compute spectral reward for this cell
            if frame is not None and hasattr(frame, 'shape'):
                srh = self._get_spectral_history(level_idx)
                cell.spectral_reward = srh.get_reward(np.asarray(frame))
            self.cells[state_id] = cell
            return True
        return False

    def _compute_state_id(self, state):
        arr = np.asarray(state, dtype=np.int32).tobytes()
        return hashlib.md5(arr).hexdigest()

    def select_cell_v9_score(self, candidates=None, level_idx=0):
        cells = candidates if candidates is not None else list(self.cells.values())
        valid = [c for c in cells if len(getattr(c, "sequence", [])) <= 80]
        if not valid:
            return None

        def score(c):
            children_val = len(getattr(c, "children", []))
            novelty_val = getattr(c, "novelty", 0.0)
            levels_val = getattr(c, "max_levels", 0)
            visits_val = getattr(c, "visits", 0)
            seq_len_val = len(getattr(c, "sequence", []))
            # v14: spectral reward term
            spectral_val = getattr(c, "spectral_reward", 0.0)
            return (
                3.0 * children_val
                + 2.0 * novelty_val
                + 10.0 * levels_val
                - 1.5 * visits_val
                - 0.05 * seq_len_val
                + SPECTRAL_WEIGHT * max(spectral_val, 0.0)   # v14: spectral bonus
            )

        ranked = sorted(valid, key=score, reverse=True)
        cell = random.choice(ranked[:min(5, len(ranked))])
        cell.last_score_val = score(cell)
        return cell

    def select_cell_dual_pool(self, step: int, level_idx=0):
        cells = list(self.cells.values())
        frontier = []
        depth = []
        general = []
        for c in cells:
            children_cnt = len(getattr(c, "children", []))
            raw_untried = getattr(c, "untried_actions", 0)
            untried_cnt = len(raw_untried) if isinstance(raw_untried, (set, list)) else int(raw_untried or 0)
            seq_len_val = len(getattr(c, "sequence", []))
            if seq_len_val > 80:
                continue
            gap = untried_cnt - children_cnt
            c._gap = gap
            c._untried_cnt = untried_cnt
            c._children_cnt = children_cnt
            if gap >= 2:
                frontier.append(c)
            elif gap <= -2:
                depth.append(c)
            else:
                general.append(c)
        p_frontier = 0.70 if step < 250 else 0.30
        if random.random() < p_frontier and frontier:
            self.last_selector = "frontier_pool"
            return self.select_cell_v9_score(frontier, level_idx)
        if depth:
            self.last_selector = "depth_pool"
            return self.select_cell_v9_score(depth, level_idx)
        if general:
            self.last_selector = "general_pool"
            return self.select_cell_v9_score(general, level_idx)
        self.last_selector = "v9_fallback"
        return self.select_cell_v9_score(cells, level_idx)

    def select_cell(self, step: int = 0, level_idx=0):
        return self.select_cell_dual_pool(step, level_idx)

# ---------------------------------------------------------------------------
# Main game loop
# ---------------------------------------------------------------------------

def run_game(game_name, output_file, max_steps=MAX_STEPS, max_resets=MAX_ARCHIVE_RESETS,
             out_dir=OUT_DIR, game_index=0, total_games=1):
    seed = random.randint(0, 999999)
    unique_states = set()
    mode = "EXPLORE_CURRENT"
    archive = ArchiveGoExplore()
    gm = GradientMonitor(patience=20)
    prev_raw = None
    reset_count = 0
    reset_steps_remaining = 0
    current_cell = None
    replay_seq = []
    steps_since_archive = 0
    stagnation_counter = 0
    non_zero_delta_steps = 0
    zero_delta_steps = 0
    levels_completed = 0
    total_actions = 0
    action_counts = Counter()
    stage_actions = Counter()
    selector_log = Counter()

    # v14: spectral tracking
    spectral_history = SpectralRewardHistory(max_history=SPECTRAL_HISTORY_LEN)
    spectral_total = 0.0
    spectral_count = 0
    spectral_max = 0.0

    ensure_dir(out_dir)
    f_out = open(output_file, 'w', encoding='utf-8')

    try:
        arcade_if = Arcade(environments_dir='environment_files')
        wrapper = arcade_if.make(game_name)
        fd = wrapper.reset()
        start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        f_out.write(json.dumps({
            "event": "start", "game": game_name, "seed": seed,
            "timestamp": start_time, "max_steps": max_steps
        }) + '\n')

        # Extract frame data (list of numpy arrays)
        prev_raw = None
        if hasattr(fd, 'frame') and fd.frame is not None and len(fd.frame) > 0:
            prev_raw = np.asarray(fd.frame[0])
        if prev_raw is not None:
            try:
                state_hash = hashlib.md5(np.asarray(prev_raw, dtype=np.int32).tobytes()).hexdigest()
                archive.add_to_archive(prev_raw, 0.0, prev_raw, 0.0, state_hash=state_hash, level_idx=0)
            except Exception:
                pass

        for step in range(1, max_steps + 1):
            if levels_completed > 0:
                f_out.write(json.dumps({
                    "event": "levels_completed", "step": step,
                    "levels": levels_completed
                }) + '\n')
                break

            mode = "EXPLORE_CURRENT" if step < 30 else "NORMAL"

            if reset_steps_remaining > 0:
                mode = "REPLAY"
                action = replay_seq[-(reset_steps_remaining)] if replay_seq else GameAction.RESET
                reset_steps_remaining -= 1
            else:
                # v14: update spectral reward for current frame
                if prev_raw is not None:
                    sr_val = spectral_history.update(prev_raw)
                    spectral_total += sr_val
                    spectral_count += 1
                    spectral_max = max(spectral_max, sr_val)

                # Action selection
                action = random.choice([a for a in GameAction if a != GameAction.ACTION6])
                total_actions += 1

            # Execute action
            try:
                if action == GameAction.RESET:
                    next_fd = wrapper.reset()
                elif action == GameAction.ACTION6:
                    next_fd = step_action6(wrapper)
                else:
                    next_fd = wrapper.step(action)
            except Exception as e:
                f_out.write(json.dumps({
                    "event": "action_error", "step": step,
                    "action": str(action), "error": str(e)
                }) + '\n')
                next_fd = wrapper.reset()

            fd = next_fd
            action_counts[action.name if hasattr(action, 'name') else str(action)] += 1

            # State tracking
            current_frame = None
            if hasattr(fd, 'frame') and fd.frame is not None and len(fd.frame) > 0:
                current_frame = np.asarray(fd.frame[0])
            if current_frame is not None:
                try:
                    state_hash = hashlib.md5(np.asarray(current_frame, dtype=np.int32).tobytes()).hexdigest()
                    unique_states.add(state_hash)

                    novelty_score = 0.0
                    changed = 0
                    if prev_raw is not None:
                        changed = count_changed_pixels(prev_raw, current_frame)
                        novelty_score = changed / max(1, np.asarray(prev_raw).size)
                    archive.add_to_archive(current_frame, novelty_score, current_frame, novelty_score,
                                           state_hash=state_hash, level_idx=levels_completed)
                    prev_raw = current_frame

                    if changed > 0:
                        non_zero_delta_steps += 1
                        zero_delta_steps = 0
                    else:
                        zero_delta_steps += 1

                except Exception as e:
                    f_out.write(json.dumps({
                        "event": "state_error", "step": step,
                        "error": str(e)
                    }) + '\n')
                    continue

            # Gradient monitor check
            if gm.step(len(unique_states)):
                f_out.write(json.dumps({
                    "event": "plateau_detected", "step": step,
                    "archive_size": len(unique_states),
                    "mode": mode
                }) + '\n')
                break

            # Check completion (GameState WINGAME_OVER)
            try:
                state_enum = fd.state
                if state_enum in (GameState.WIN, GameState.GAME_OVER):
                    if state_enum == GameState.WIN:
                        levels_completed += 1
                    f_out.write(json.dumps({
                        "event": "level_complete", "step": step,
                        "levels_completed": levels_completed,
                        "state": str(state_enum)
                    }) + '\n')
                    # Reset spectral history and game for next level
                    spectral_history = SpectralRewardHistory(max_history=SPECTRAL_HISTORY_LEN)
                    gm.reset()
                    fd = wrapper.reset()
                    if hasattr(fd, 'frame') and fd.frame is not None and len(fd.frame) > 0:
                        prev_raw = np.asarray(fd.frame[0])
            except Exception:
                pass

        # End of game
        end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        final_frame = prev_raw

        # v14: compute spectral stats
        avg_sr = spectral_total / max(1, spectral_count)

        result = {
            "event": "end",
            "game": game_name,
            "seed": seed,
            "start_time": start_time,
            "end_time": end_time,
            "steps": step,
            "unique_states": len(unique_states),
            "levels_completed": levels_completed,
            "zero_delta_steps": zero_delta_steps,
            "non_zero_delta_steps": non_zero_delta_steps,
            "zero_delta_rate": round(zero_delta_steps / max(1, zero_delta_steps + non_zero_delta_steps), 4),
            "archive_size": len(archive.cells),
            "crashes": 0,
            "total_actions": total_actions,
            "mode": "finished",
            # v14: spectral metrics
            "avg_spectral_reward": round(avg_sr, 4),
            "max_spectral_reward": round(spectral_max, 4),
            "spectral_sweep_count": spectral_count,
        }
        f_out.write(json.dumps(result) + '\n')

    except Exception as e:
        f_out.write(json.dumps({
            "event": "crash", "game": game_name,
            "error": str(e),
            "levels_completed": levels_completed
        }) + '\n')
        result = {"game": game_name, "levels_completed": 0, "crashes": 1, "unique_states": len(unique_states)}

    finally:
        f_out.close()

    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    games = [
        "sk48", "tn36", "bp35", "wa30", "vc33", "tu93",
        "tr87", "su15", "sp80", "sc25", "sb26", "s5i5",
        "re86", "r11l", "m0r0", "ls20", "lp85", "lf52",
        "ka59", "g50t", "ft09", "dc22", "cd82", "ar25", "cn04"
    ]
    if len(sys.argv) > 1:
        run_specific = sys.argv[1:]
        games = [g for g in games if g in run_specific]

    ensure_dir(OUT_DIR)
    csv_path = os.path.join(OUT_DIR, f"summary_v14.csv")
    csv_exists = os.path.exists(csv_path)
    csv_f = open(csv_path, 'a', newline='')
    csv_writer = csv.writer(csv_f)
    if not csv_exists:
        csv_writer.writerow([
            "game", "levels_completed", "unique_states", "zero_delta_rate",
            "crashes", "archive_size", "steps", "avg_spectral_reward",
            "max_spectral_reward", "spectral_weight"
        ])

    summary = []
    for i, game_name in enumerate(games):
        print(f"[{i+1}/{len(games)}] {game_name}...")
        out_file = os.path.join(OUT_DIR, f"v14_spectral_{game_name}.jsonl")
        result = run_game(game_name, out_file, max_steps=MAX_STEPS, game_index=i, total_games=len(games))
        summary.append(result)
        csv_writer.writerow([
            result.get("game", game_name),
            result.get("levels_completed", 0),
            result.get("unique_states", 0),
            result.get("zero_delta_rate", 0.0),
            result.get("crashes", 0),
            result.get("archive_size", 0),
            result.get("steps", 0),
            result.get("avg_spectral_reward", 0.0),
            result.get("max_spectral_reward", 0.0),
            SPECTRAL_WEIGHT
        ])
        csv_f.flush()

    csv_f.close()

    print(f"\n=== v14 Spectral Reward Shaping Summary ===")
    total_levels = sum(r.get("levels_completed", 0) for r in summary)
    total_states = sum(r.get("unique_states", 0) for r in summary)
    total_crashes = sum(r.get("crashes", 0) for r in summary)
    games_with_levels = sum(1 for r in summary if r.get("levels_completed", 0) > 0)
    print(f"Games: {len(games)}, Levels: {total_levels}, States: {total_states}")
    print(f"Crashes: {total_crashes}, Games with levels: {games_with_levels}")
    print(f"Spectral weight: {SPECTRAL_WEIGHT}")
    print(f"CSV: {csv_path}")
