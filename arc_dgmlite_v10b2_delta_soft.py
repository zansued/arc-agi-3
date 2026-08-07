#!/usr/bin/env python3
"""
ARC-AGI-3 DGM-lite v9 Go-Explore Archive Planner

Lições de v1-v8:
- v3: diversity bandit = boa exploracao (81.5 estados) mas 83.5% zero-delta, 14/25 early stagnation
- v4: reduziu zero-delta (30.8%) mas colapsou exploracao (22.7 estados)
- v5: microsequencias recuperaram exploracao (73.9 estados) mas zero-delta voltou (85%)
- v6: melhor compromisso (79.3 estados, 83.4% zd, 12/25 estagnacao) com 3.4% object-aware
- v7: object-aware forcado (25%) colapsou (5.0 estados, 89.5% zd)
- v8: causal-object threshold 2.5 nunca ativou (5.2 estados, 86.3% zd)
- v8.5: causal-object threshold 1.0 max_rate=8% + ACTION6 bug KeyError 'x'

Problema central de TODAS as versoes:
    exploracao existe, mas nao ha planejamento causal. Agente descobre
    70-80 estados e depois ESTAGNA em todos os 25 jogos.

v9 = Go-Explore Archive:
    Em vez de explorar sempre do estado atual, guardar estados
    interessantes, VOLTAR a eles e explorar ramos novos.

Metodo: Go-Explore (Ecoffet et al., 2019) adaptado para ARC-AGI-3
    archive[state_hash] = (sequence, score, visits, children, frame)
    score = 3*children + 2*novelty + 10*progress - 1.5*visits - 0.05*len(sequence)
    Modos: EXPLORE_CURRENT -> ARCHIVE_SELECT -> RESET -> REPLAY -> EXPLORE_FROM_CELL
    MAX_REPLAY_LEN = 80, MAX_ARCHIVE_RESETS = 3  # v10a Coliseu: reduced to preserve more steps for exploration
    ACTION6 explicitamente ignorado (evitar bug KeyError 'x')
"""
import os, json, csv, random, hashlib, math, sys, copy
from datetime import datetime, timezone
from collections import Counter, defaultdict, deque

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction, GameState

MAX_STEPS = 500
OUT_DIR = "arc_runs"

# Go-Explore parameters
MAX_REPLAY_LEN = 80
MAX_ARCHIVE_RESETS = 3  # v10a Coliseu: reduced to preserve more steps for exploration
STAGNATION_STEPS = 30
ZERO_DELTA_STREAK = 8
ARCHIVE_PERIOD = 100  # also try archive select periodically

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

def extract_frame(raw):
    if raw is None:
        return None
    if isinstance(raw, np.ndarray):
        return raw.squeeze() if raw.ndim > 2 else raw
    if hasattr(raw, "frame"):
        arr = np.asarray(raw.frame, dtype=np.int32)
        if arr.ndim == 3:
            arr = arr[0]
        return arr
    if hasattr(raw, "grid"):
        return np.asarray(raw.grid, dtype=np.int32)
    return None

def safe_state(raw):
    s = getattr(raw, "state", None)
    return str(s) if s is not None else "UNKNOWN"

def safe_levels(raw):
    return int(getattr(raw, "levels_completed", 0) or 0)

def safe_win(raw):
    return int(getattr(raw, "win_levels", 0) or 0)

def progress_ratio(levels_completed, win_levels):
    return levels_completed / max(1, win_levels)

def is_fail(state_str):
    return "FAIL" in state_str.upper()

def is_win(state_str):
    return "WIN" in state_str.upper()

def normalize_action_result(result):
    """Normalize planner return to (GameAction, data_or_None)."""
    if isinstance(result, tuple):
        if len(result) == 2:
            return result[0], result[1]
        raise ValueError(f"Invalid action tuple length: {len(result)}")
    return result, None


# ---------------------------------------------------------------------------
# Delta Reward (v10b)
# ---------------------------------------------------------------------------
def delta_reward(changed_pixels: int) -> float:
    """Soft reward based on changed pixels. No penalty for zero-delta."""
    if changed_pixels <= 0:
        return 0.0
    if changed_pixels < 10:
        return 0.03
    if changed_pixels < 50:
        return 0.12
    if changed_pixels < 100:
        return 0.30
    return 0.50


# ---------------------------------------------------------------------------
# step_game()
# ---------------------------------------------------------------------------

def step_game(game, action, data=None, reasoning=None):
    raw_before = game.observation_space
    frame_before = extract_frame(raw_before)
    try:
        if data is not None:
            raw_after = game.step(action, data=data, reasoning=reasoning)
        else:
            raw_after = game.step(action, reasoning=reasoning)
    except Exception as e:
        # If step fails, use observation_space as fallback
        raw_after = game.observation_space
    if raw_after is None:
        raw_after = game.observation_space
    frame_after = extract_frame(raw_after)
    levels_before = safe_levels(raw_before)
    levels_after = safe_levels(raw_after)
    delta_levels = max(0, levels_after - levels_before)
    win_lvls = safe_win(raw_after) or safe_win(raw_before)
    state_str = safe_state(raw_after)
    return {
        "raw": raw_after,
        "frame": frame_after,
        "state": state_str,
        "levels_completed": levels_after,
        "win_levels": win_lvls,
        "progress_ratio": progress_ratio(levels_after, win_lvls),
        "delta_levels": delta_levels,
        "delta_progress_ratio": progress_ratio(levels_after, win_lvls) - progress_ratio(levels_before, win_lvls),
        "changed_pixels": count_changed_pixels(frame_before, frame_after),
        "available_actions": list(getattr(raw_after, "available_actions", [])),
    }

# ---------------------------------------------------------------------------
# GO-EXPLORE ARCHIVE
# ---------------------------------------------------------------------------

class ArchiveCell:
    """A cell in the Go-Explore archive: a discovered state + how to reach it."""
    def __init__(self, state_hash, sequence, frame, score=0.0):
        self.state_hash = state_hash
        self.sequence = list(sequence)  # list of action dicts
        self.frame = frame.copy() if frame is not None else None
        self.score = score
        self.visits = 0
        self.children = set()  # child state hashes discovered from here
        self.max_levels = 0
        self.last_improved_step = 0
        self.novelty = 1.0  # starts high, decays with visits
        self.untried_actions = set()
        self.cell_frontier_score = 0.0
        self.cell_depth_score = 0.0

    def to_dict(self):
        return {
            "state_hash": self.state_hash,
            "sequence_len": len(self.sequence),
            "score": round(self.score, 2),
            "visits": self.visits,
            "children": len(self.children),
            "max_levels": self.max_levels,
            "novelty": round(self.novelty, 3),
        }


class GoExploreArchive:
    """Archive of discovered states with scoring and selection."""
    def __init__(self):
        self.cells = {}  # state_hash -> ArchiveCell
        self.total_visits = 0
        self.n_resets = 0
        self.n_replays = 0
        self.n_replay_success = 0
        self.max_size = 200  # prevent unbounded growth
        self.last_selector = "none"
        self.phase_step = 0

    def add_or_update(self, state_hash, frame, sequence, parent_hash=None, levels=0, step=0):
        if state_hash in self.cells:
            cell = self.cells[state_hash]
            # Update max_levels
            if levels > cell.max_levels:
                cell.max_levels = levels
                cell.last_improved_step = step
            # Update novelty (decays with visits across archive)
            cell.novelty = 1.0 / (1.0 + cell.visits)
            return cell

        if len(self.cells) >= self.max_size:
            # Evict lowest-score cell
            worst = min(self.cells.values(), key=lambda c: c.score)
            del self.cells[worst.state_hash]

        cell = ArchiveCell(state_hash, sequence, frame)
        cell.max_levels = levels
        cell.last_improved_step = step
        self.cells[state_hash] = cell

        # Link to parent
        if parent_hash and parent_hash in self.cells:
            self.cells[parent_hash].children.add(state_hash)

        return cell

    def select_cell_v9_score(self, candidates=None):
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
            return (
                3.0 * children_val
                + 2.0 * novelty_val
                + 10.0 * levels_val
                - 1.5 * visits_val
                - 0.05 * seq_len_val
            )

        ranked = sorted(valid, key=score, reverse=True)
        cell = random.choice(ranked[:min(5, len(ranked))])
        cell.last_score_val = score(cell)
        return cell

    def select_cell_dual_pool(self, step: int):
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
            return self.select_cell_v9_score(frontier)
        if depth:
            self.last_selector = "depth_pool"
            return self.select_cell_v9_score(depth)
        if general:
            self.last_selector = "general_pool"
            return self.select_cell_v9_score(general)
        self.last_selector = "v9_fallback"
        return self.select_cell_v9_score(cells)

    def select_cell(self, step: int = 0):
        return self.select_cell_dual_pool(step)

        # Update scores for all cells
        for cell in self.cells.values():
            cell.score = (
                3.0 * len(cell.children)
                + 2.0 * cell.novelty
                + 10.0 * cell.max_levels
                - 1.5 * cell.visits
                - 0.05 * len(cell.sequence)
            )

        # Prefer cells with short sequences, high novelty, unvisited branches
        candidates = [c for c in self.cells.values()
                      if len(c.sequence) <= MAX_REPLAY_LEN]

        if not candidates:
            candidates = list(self.cells.values())

        # Sort by score descending
        candidates.sort(key=lambda c: -c.score)

        # Add small randomness to avoid always picking the same cell
        top_n = max(1, min(5, len(candidates)))
        best = random.choice(candidates[:top_n])
        return best

    def mark_visit(self, state_hash):
        if state_hash in self.cells:
            self.cells[state_hash].visits += 1
            self.cells[state_hash].novelty = 1.0 / (1.0 + self.cells[state_hash].visits)
            self.total_visits += 1

    def record_replay(self, success):
        self.n_replays += 1
        if success:
            self.n_replay_success += 1

    def record_reset(self):
        self.n_resets += 1

    def get_stats(self):
        return {
            "archive_size": len(self.cells),
            "n_resets": self.n_resets,
            "n_replays": self.n_replays,
            "n_replay_success": self.n_replay_success,
            "replay_success_rate": (self.n_replay_success / max(1, self.n_replays)),
            "total_visits": self.total_visits,
        }


# ---------------------------------------------------------------------------
# Object Detector (from v6)
# ---------------------------------------------------------------------------

def _label_components(mask):
    h, w = mask.shape
    labeled = np.zeros((h, w), dtype=np.int32)
    label_num = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] > 0 and labeled[y, x] == 0:
                label_num += 1
                queue = [(y, x)]
                labeled[y, x] = label_num
                for sy, sx in queue:
                    for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
                        ny, nx = sy + dy, sx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] > 0 and labeled[ny, nx] == 0:
                            labeled[ny, nx] = label_num
                            queue.append((ny, nx))
    return labeled, label_num


class ObjectDetector:
    def __init__(self):
        self.prev_frame = None
        self.prev_objects = []

    def detect(self, frame):
        if frame is None:
            return []
        f = np.asarray(frame, dtype=np.int32)
        if f.ndim == 3:
            f = f[0]
        if f.shape != (64, 64):
            return []
        bg_val = int(np.median(f)) if f.size > 0 else 0
        mask = (f != bg_val).astype(np.int32)
        if mask.sum() == 0:
            return []
        labeled, n_labels = _label_components(mask)
        objects = []
        for obj_id in range(1, n_labels + 1):
            ys, xs = np.where(labeled == obj_id)
            if len(ys) < 3:
                continue
            color = int(f[ys[0], xs[0]])
            area = len(ys)
            x1, x2 = int(xs.min()), int(xs.max())
            y1, y2 = int(ys.min()), int(ys.max())
            cx, cy = int(xs.mean()), int(ys.mean())
            touches = x1 <= 0 or y1 <= 0 or x2 >= 63 or y2 >= 63
            aspect = (x2 - x1 + 1) / max(1, (y2 - y1 + 1))
            obj = {
                "id": obj_id,
                "color": color,
                "area": area,
                "bbox": (x1, y1, x2, y2),
                "center": (cx, cy),
                "w": x2 - x1 + 1,
                "h": y2 - y1 + 1,
                "touches_border": touches,
                "aspect_ratio": round(aspect, 2),
            }
            objects.append(obj)
        objects.sort(key=lambda o: -o["area"])
        self.prev_frame = frame
        self.prev_objects = objects
        return objects

    def changed_objects(self, frame):
        if self.prev_frame is None:
            return []
        prev = np.asarray(self.prev_frame, dtype=np.int32)
        curr = np.asarray(frame, dtype=np.int32)
        if prev.shape != curr.shape:
            return []
        diff = (prev != curr).astype(np.int32)
        if diff.sum() < 3:
            return []
        labeled, n_labels = _label_components(diff)
        regions = []
        for obj_id in range(1, n_labels + 1):
            ys, xs = np.where(labeled == obj_id)
            if len(ys) < 3:
                continue
            regions.append({
                "center": (int(xs.mean()), int(ys.mean())),
                "area": len(ys),
                "bbox": (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
            })
        return regions


# ---------------------------------------------------------------------------
# Diversity Bandit (from v6)
# ---------------------------------------------------------------------------

class ProgressBandit:
    """Tracks action statistics and selects diverse actions."""
    def __init__(self):
        self.action_stats = defaultdict(lambda: {
            "count": 0, "successes": 0, "zero_deltas": 0,
            "total_delta": 0, "reward_sum": 0.0, "reward_count": 0,
            "recent_changes": deque(maxlen=10),
        })
        self.history = deque(maxlen=50)
        self.current_mode = "EXPLORE_CURRENT"
        self.reset_state()

    def reset_state(self):
        self.last_frame = None
        self.last_hash = None
        self.zero_delta_streak = 0
        self.steps_since_new_state = 0
        self.step_count = 0
        self.unique_states = set()
        self.sequence = []  # action records for archive
        self.current_hash = None
        self.max_levels = 0
        self.archive_timer = 0

    def observe_result(self, action, data, changed, state_hash, levels, progress):
        self.step_count += 1
        self.archive_timer += 1

        # Skip if action is None
        if action is None:
            return

        # Get action key
        action_name = getattr(action, "name", str(action))
        stats = self.action_stats[action_name]
        stats["count"] += 1
        stats["recent_changes"].append(changed)

        is_new = state_hash not in self.unique_states

        if is_new:
            self.unique_states.add(state_hash)
            stats["successes"] += 1
            self.zero_delta_streak = 0
            self.steps_since_new_state = 0
        else:
            self.steps_since_new_state += 1

        if changed == 0:
            stats["zero_deltas"] += 1
            self.zero_delta_streak += 1
        else:
            stats["total_delta"] += changed
            self.zero_delta_streak = 0

        # v10b: compute delta reward
        novelty_rew = 1.0 if is_new else -0.1
        progress_rew = levels * 0.5
        delta_rew = delta_reward(changed)
        total_rew = novelty_rew + progress_rew + delta_rew
        total_rew = max(-0.5, min(1.5, total_rew))
        stats["reward_sum"] += total_rew
        stats["reward_count"] += 1

        # Store for JSONL logging
        self._last_rewards = {
            "novelty_reward": novelty_rew,
            "progress_reward": progress_rew,
            "delta_reward": delta_rew,
            "total_bandit_reward": total_rew,
        }

        # Update levels
        if levels > self.max_levels:
            self.max_levels = levels

        self.last_hash = state_hash
        self.current_hash = state_hash

    def is_stagnated(self):
        return (self.zero_delta_streak >= ZERO_DELTA_STREAK or
                self.steps_since_new_state >= STAGNATION_STEPS)

    def _safe_actions(self, available_actions):
        """Filter available actions, removing ACTION6 to avoid KeyError bug."""
        safe = []
        for a in available_actions:
            name = getattr(a, "name", str(a))
            if name == "ACTION6":
                continue  # Skip ACTION6 due to KeyError bug
            safe.append(a)
        if not safe:
            # Fallback to RESET if only ACTION6 is available
            return [GameAction.RESET]
        return safe

    def _choose_least_used(self, available_actions):
        safe = self._safe_actions(available_actions)
        if not safe:
            return GameAction.RESET, None
        safe.sort(key=lambda a: self.action_stats[getattr(a, "name", str(a))]["count"])
        return safe[0], None

    def _choose_random_probe(self, available_actions):
        safe = self._safe_actions(available_actions)
        if not safe:
            return GameAction.RESET, None
        # Weight by count (prefer less-used) and reward (prefer high-delta)
        weights = []
        for a in safe:
            name = getattr(a, "name", str(a))
            stats = self.action_stats[name]
            w = 1.0 / (1.0 + stats["count"] * 0.1)
            # v10b: reward bonus
            if stats["reward_count"] > 0:
                mean_rew = stats["reward_sum"] / stats["reward_count"]
                reward_mult = 1.0 + max(-0.5, min(0.5, mean_rew))
                w *= reward_mult
            weights.append(max(w, 0.01))
        total = sum(weights)
        if total == 0:
            return random.choice(safe), None
        p = [w / total for w in weights]
        idx = random.choices(range(len(safe)), weights=p, k=1)[0]
        return safe[idx], None

    def choose_action(self, available_actions, mode="EXPLORE_CURRENT"):
        """Choose action based on current mode."""
        self.current_mode = mode
        safe = self._safe_actions(available_actions)

        if not safe:
            return GameAction.RESET, None

        if mode == "EXPLORE_CURRENT":
            # Diversity bandit: prefer less-used actions
            return self._choose_least_used(safe)

        elif mode == "EXPLORE_FROM_CELL":
            # Same as EXPLORE_CURRENT but slightly more random
            return self._choose_random_probe(safe)

        elif mode == "REPLAY_SEQUENCE":
            # During replay, don't decide - just return the next action
            return None, None

        else:
            return self._choose_least_used(safe)


# ---------------------------------------------------------------------------
# Main game runner
# ---------------------------------------------------------------------------

def run_game(game_id, max_steps=MAX_STEPS, out_dir=OUT_DIR):
    """Run a single game with Go-Explore Archive."""
    logs = []
    ensure_dir(out_dir)

    game = Arcade().make(game_id)
    game.reset()
    raw = game.observation_space
    frame = extract_frame(raw)
    state_hash = frame_hash(frame)
    levels_completed = safe_levels(raw)
    win_levels = safe_win(raw)

    # Initialize objects
    bandit = ProgressBandit()
    archive = GoExploreArchive()
    detector = ObjectDetector()

    bandit.reset_state()
    bandit.current_hash = state_hash
    bandit.unique_states.add(state_hash)
    bandit.last_frame = frame

    current_mode = "EXPLORE_CURRENT"
    selected_cell = None
    replay_idx = 0
    sequence = []
    n_resets = 0
    paused = False

    for step_idx in range(max_steps):
        avail = list(getattr(raw, "available_actions", []) or [])
        if not avail:
            avail = list(range(1, 7))

        # ---- Decision Logic ----

        # Check for stagnation or periodic archive selection
        if current_mode == "EXPLORE_CURRENT":
            should_select = (bandit.is_stagnated() or
                             step_idx > 0 and step_idx % ARCHIVE_PERIOD == 0)

            if should_select and archive.cells:
                selected_cell = archive.select_cell()
                if selected_cell and len(selected_cell.sequence) <= MAX_REPLAY_LEN and n_resets < MAX_ARCHIVE_RESETS:
                    current_mode = "ARCHIVE_SELECT"
                else:
                    current_mode = "EXPLORE_CURRENT"

        if current_mode == "ARCHIVE_SELECT":
            current_mode = "RESET_TO_CELL"
            n_resets += 1

        if current_mode == "RESET_TO_CELL":
            game.reset()
            archive.record_reset()
            raw = game.observation_space
            frame = extract_frame(raw)
            state_hash = frame_hash(frame)
            replay_idx = 0
            current_mode = "REPLAY_SEQUENCE"

        if current_mode == "REPLAY_SEQUENCE":
            if replay_idx < len(selected_cell.sequence):
                # Replay next action
                record = selected_cell.sequence[replay_idx]
                action_id = record["action_id"]
                action_data = record.get("data")
                try:
                    action = GameAction.from_id(action_id)
                except Exception:
                    action = GameAction.RESET
                result = step_game(game, action, data=action_data,
                                   reasoning=f"v10_REPLAY_{replay_idx}")
                raw = result["raw"]
                frame = result["frame"]
                replay_idx += 1

                # Check if we reached the target state
                current_hash = frame_hash(frame)
                replay_success = (current_hash == selected_cell.state_hash)

                # Log replay step
                log_entry = {
                    "step": step_idx,
                    "mode": "REPLAY_SEQUENCE",
                    "action_id": action_id,
                    "action_name": getattr(action, "name", str(action)),
                    "replay_idx": replay_idx,
                    "target_hash": selected_cell.state_hash,
                    "current_hash": current_hash,
                    "replay_success": replay_success,
                    "sequence_len": len(selected_cell.sequence),
                    "state": safe_state(raw),
                    "levels_completed": safe_levels(raw),
                    "win_levels": safe_win(raw),
                    "changed_pixels": result["changed_pixels"],
                    "unique_states": len(bandit.unique_states),
                    "archive_size": len(archive.cells),
                    "zero_delta_streak": bandit.zero_delta_streak,
                    "steps_since_new_state": bandit.steps_since_new_state,
                }
                logs.append(log_entry)
                continue

            # Replay complete
            archive.record_replay(frame_hash(frame) == selected_cell.state_hash)
            archive.mark_visit(selected_cell.state_hash)
            bandit.current_hash = frame_hash(frame)
            current_mode = "EXPLORE_FROM_CELL"

        # ---- Normal action selection ----
        chosen = bandit.choose_action(avail, mode=current_mode)
        action, data = normalize_action_result(chosen)

        # Safety: skip if action is None (shouldn't happen)
        if action is None:
            action = GameAction.RESET

        action_name = getattr(action, "name", str(action))

        result = step_game(game, action, data=data,
                           reasoning=f"v10_{current_mode}")

        raw = result["raw"]
        frame = result["frame"]
        state_hash = frame_hash(frame)
        levels_completed = result["levels_completed"]
        changed_pixels = result["changed_pixels"]

        # Build action record for archive
        action_record = {
            "action_id": int(action.value) if hasattr(action, "value") else 0,
            "action_name": action_name,
            "data": data,
        }
        sequence.append(action_record)

        # Update bandit
        bandit.observe_result(action, data, changed_pixels, state_hash,
                              levels_completed, result["progress_ratio"])

        # Check if this state should go to archive
        is_new = state_hash not in archive.cells
        if is_new and state_hash:
            archive.add_or_update(
                state_hash=state_hash,
                frame=frame,
                sequence=list(sequence),
                parent_hash=bandit.last_hash,
                levels=levels_completed,
                step=step_idx,
            )

        # Check for WIN or FAIL
        state_str = safe_state(raw)
        if is_win(state_str):
            current_mode = "WIN"
        elif is_fail(state_str):
            current_mode = "FAIL"

        # Update archive phase_step
        archive.phase_step = step_idx

        # Log entry
        archive_stats = archive.get_stats()
        log_entry = {
            "step": step_idx,
            "mode": current_mode,
            "action_id": int(action.value) if hasattr(action, "value") else 0,
            "action_name": action_name,
            "state_hash": state_hash,
            "state": state_str,
            "changed_pixels": changed_pixels,
            "levels_completed": levels_completed,
            "win_levels": result["win_levels"],
            "unique_states": len(bandit.unique_states),
            "archive_size": archive_stats["archive_size"],
            "n_resets": archive_stats["n_resets"],
            "n_replays": archive_stats["n_replays"],
            "replay_success_rate": round(archive_stats["replay_success_rate"], 3),
            "zero_delta_streak": bandit.zero_delta_streak,
            "steps_since_new_state": bandit.steps_since_new_state,
            "selected_cell": selected_cell.state_hash[:8] if selected_cell else None,
            "sequence_len": len(sequence),
            "archive_selector": getattr(archive, 'last_selector', 'none'),
            "novelty_reward": bandit._last_rewards.get("novelty_reward", 0.0),
            "progress_reward": bandit._last_rewards.get("progress_reward", 0.0),
            "delta_reward": bandit._last_rewards.get("delta_reward", 0.0),
            "total_bandit_reward": bandit._last_rewards.get("total_bandit_reward", 0.0),
        }
        logs.append(log_entry)

        # Check terminal conditions
        if state_str in ("WIN", "FAIL"):
            break

    # Generate summary
    unique_states = len(bandit.unique_states)
    total_steps = len(logs)
    zero_delta_count = sum(1 for l in logs if l.get("changed_pixels", -1) == 0)
    zero_delta_rate = zero_delta_count / max(1, total_steps)
    max_levels_completed = max((l.get("levels_completed", 0) for l in logs), default=0)
    win_levels_final = max((l.get("win_levels", 0) for l in logs), default=0)

    status = safe_state(raw) if raw is not None else "UNKNOWN"

    # Count early stagnation
    early_stagnation = 0
    if unique_states < 30:
        early_stagnation = 1

    summary = {
        "game_id": game_id,
        "status": status,
        "steps": total_steps,
        "unique_states": unique_states,
        "zero_delta_rate": round(zero_delta_rate, 4),
        "max_levels_completed": max_levels_completed,
        "win_levels": win_levels_final,
        "early_stagnation": early_stagnation,
        "archive_size": len(archive.cells),
        "n_resets": archive.n_resets,
        "n_replays": archive.n_replays,
        "replay_success_rate": round(archive.n_replay_success / max(1, archive.n_replays), 3),
        "mean_zero_delta_streak": round(bandit.zero_delta_streak / max(1, total_steps), 4),
    }

    # Save logs
    safe_id = game_id.replace("/", "_")
    log_path = os.path.join(out_dir, f"v10b2_{safe_id}.jsonl")
    with open(log_path, "w") as f:
        for entry in logs:
            json.dump(entry, f)
            f.write(chr(10))
    return logs, summary


def run_benchmark(games, max_steps=MAX_STEPS, out_dir=OUT_DIR):
    """Run benchmark on multiple games."""
    results = []
    for gid in games:
        print(f"  [v10] {gid}...", flush=True)
        logs, summary = run_game(gid, max_steps, out_dir)
        results.append(summary)
        e = chr(39)
        print(f"    \u2192 {summary['status']:8s} | states={summary['unique_states']:3d} | "
              f"levels={summary['max_levels_completed']}/{summary['win_levels']} | "
              f"archive={summary['archive_size']:3d} | resets={summary['n_resets']} | "
              f"replay_ok={summary['replay_success_rate']:.2%}", flush=True)
    csv_path = os.path.join(out_dir, "summary_v10b2.csv")
    with open(csv_path, "w", newline="") as f:
        if results:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
    return results


if __name__ == "__main__":
    import sys
    games = sys.argv[1:] if len(sys.argv) > 1 else [
        "sk48", "bp35", "tn36",
        "wa30", "vc33", "tu93", "tr87", "su15",
        "sp80", "sc25", "sb26", "s5i5", "re86",
        "r11l", "m0r0", "ls20", "lp85", "lf52",
        "ka59", "g50t", "ft09", "dc22", "cd82",
        "ar25", "cn04",
    ]
    print("=" * 60)
    print("ARC-AGI-3 v10b2 Delta Soft Benchmark")
    print(f"Games: {len(games)}")
    print("=" * 60)
    results = run_benchmark(games)
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        e = chr(39)
        print(f"{r['game_id']:15s} {r['status']:8s} | states={r['unique_states']:3d} | levels={r['max_levels_completed']}/{r['win_levels']} | early_stag={r['early_stagnation']}")
    avg_states = sum(r['unique_states'] for r in results) / len(results)
    avg_zd = sum(r['zero_delta_rate'] for r in results) / len(results)
    early_stag_count = sum(r['early_stagnation'] for r in results)
    avg_archive = sum(r['archive_size'] for r in results) / len(results)
    avg_replay_ok = sum(r['replay_success_rate'] for r in results) / len(results)
    print(f"\nMEDIA: {avg_states:.1f} estados | {avg_zd:.1%} zero-delta | {early_stag_count}/25 early stag | archive={avg_archive:.0f} | replay_ok={avg_replay_ok:.1%}")
    print(f"Logs em: {OUT_DIR}/")
