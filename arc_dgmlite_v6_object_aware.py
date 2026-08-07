#!/usr/bin/env python3
"""
ARC-AGI-3 DGM-lite v6 Object-Aware Planner

Lições de v1-v5:
- v3: diversity bandit = boa exploração (81.5 estados) mas 83.5% zero-delta
- v4: reduziu zero-delta (30.8%) mas colapsou exploração (22.7 estados)
- v5: microsequências recuperaram exploração (73.9 estados) mas zero-delta voltou (85%)

Problema central: o agente age sobre ações abstratas, não sobre objetos do mundo.

v6 = v3 diversity + v5 microsequências + percepção de objetos + ACTION6 guiada por objeto
"""
import os, json, csv, random, hashlib, math
from datetime import datetime, timezone
from collections import Counter, defaultdict, deque

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction, GameState

MAX_STEPS = 500
OUT_DIR = "arc_runs"

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

# ---------------------------------------------------------------------------
# step_game() — CORRECT API
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
        raise e
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
# Perception: Object Detection
# ---------------------------------------------------------------------------

def _label_components(mask):
    """Label connected components in a 2D binary mask using BFS flood fill.
    Returns (labeled_array, num_labels)."""
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
        """Detect connected components (blobs) in the frame."""
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
        """Detect regions that changed since last frame."""
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
        for rid in range(1, n_labels + 1):
            ys, xs = np.where(labeled == rid)
            if len(ys) < 3:
                continue
            regions.append({
                "region_id": rid,
                "center": (int(xs.mean()), int(ys.mean())),
                "bbox": (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                "area": len(ys),
            })
        return regions

    def signature(self, obj):
        area_bucket = "tiny" if obj["area"] < 20 else ("small" if obj["area"] < 80 else ("medium" if obj["area"] < 300 else "large"))
        region = "border" if obj["touches_border"] else "center"
        return f"c{obj['color']}_{area_bucket}_{region}"

# ---------------------------------------------------------------------------
# Affordance Memory
# ---------------------------------------------------------------------------

class AffordanceMemory:
    def __init__(self):
        self.records = defaultdict(lambda: {"trials": 0, "delta_sum": 0, "new_states": 0, "zero_delta": 0, "recent_success": 0})
        self.click_history = deque(maxlen=50)

    def record(self, obj_sig, action_key, delta_pixels, is_new_state, progress_delta):
        key = (obj_sig, action_key)
        r = self.records[key]
        r["trials"] += 1
        r["delta_sum"] += delta_pixels
        if is_new_state:
            r["new_states"] += 1
            r["recent_success"] = 5
        else:
            r["recent_success"] = max(0, r["recent_success"] - 1)
        if delta_pixels == 0:
            r["zero_delta"] += 1
        self.click_history.append((obj_sig, action_key, is_new_state, delta_pixels))

    def score(self, obj_sig, action_key):
        key = (obj_sig, action_key)
        r = self.records[key]
        if r["trials"] == 0:
            return 1.0
        zero_rate = r["zero_delta"] / r["trials"]
        new_rate = r["new_states"] / r["trials"]
        mean_delta = r["delta_sum"] / r["trials"]
        score_val = (
            + 3.0 * new_rate
            + 2.0 * (mean_delta / max(1, 64 * 64))
            + 0.5 * r["recent_success"]
            - 2.0 * zero_rate
        )
        return max(-1, score_val)

    def best_object_action_pair(self, obj_sigs, action_keys):
        best_pair, best_s = None, -999
        for sig in obj_sigs:
            for ak in action_keys:
                s = self.score(sig, ak)
                if s > best_s:
                    best_s = s
                    best_pair = (sig, ak)
        return best_pair, best_s

# ---------------------------------------------------------------------------
# ACTION6 Coordinate Generation (object-guided)
# ---------------------------------------------------------------------------

def object_click_points(objects, changed_regions):
    """Generate ACTION6 coordinates prioritized by object importance."""
    points = []
    for r in changed_regions:
        points.append(r["center"])
        x1, y1, x2, y2 = r["bbox"]
        points.append((x1, y1))
        points.append((x2, y2))
    for obj in sorted(objects, key=lambda o: o["area"]):
        if obj["area"] < 30:
            points.append(obj["center"])
    all_colors = [o["color"] for o in objects]
    color_counts = Counter(all_colors)
    for obj in objects:
        if color_counts.get(obj["color"], 0) == 1:
            points.append(obj["center"])
            x1, y1, x2, y2 = obj["bbox"]
            points.append(((x1 + x2) // 2, y1))
            points.append((x2, (y1 + y2) // 2))
    for obj in objects:
        points.append(obj["center"])
        x1, y1, x2, y2 = obj["bbox"]
        points.append(((x1 + x2) // 2, (y1 + y2) // 2))
    for y in range(8, 64, 16):
        for x in range(8, 64, 16):
            points.append((x, y))
    seen = set()
    out = []
    for x, y in points:
        x = max(0, min(63, int(x)))
        y = max(0, min(63, int(y)))
        if (x, y) not in seen:
            seen.add((x, y))
            out.append((x, y))
    return out

def expand_actions(available_actions, objects, changed_regions):
    expanded = []
    for action in available_actions:
        if isinstance(action, int):
            ga = GameAction.from_id(action)
            if action == 6:
                for x, y in object_click_points(objects, changed_regions):
                    expanded.append((ga, {"x": x, "y": y}))
            else:
                expanded.append((ga, None))
        else:
            name = getattr(action, "name", str(action))
            if name == "ACTION6":
                for x, y in object_click_points(objects, changed_regions):
                    expanded.append((action, {"x": x, "y": y}))
            else:
                expanded.append((action, None))
    return expanded

# ---------------------------------------------------------------------------
# MicroSequenceMemory (from v5)
# ---------------------------------------------------------------------------

class MicroSequenceMemory:
    def __init__(self, seq_len=2, max_seqs=20):
        self.seq_len = seq_len
        self.max_seqs = max_seqs
        self.sequences = []
        self.window = deque(maxlen=seq_len)
        self.active_seq = None
        self.active_idx = 0
        self.steps_without_new = 0

    def record_step(self, action_key, is_new_state):
        self.window.append(action_key)
        if len(self.window) == self.seq_len and is_new_state:
            seq = tuple(self.window)
            self.sequences.append({"seq": seq, "score": 1, "penalty": 0})
            if len(self.sequences) > self.max_seqs:
                self.sequences.sort(key=lambda x: -x["score"])
                self.sequences = self.sequences[:self.max_seqs]

    def best_sequence(self):
        if not self.sequences:
            return None
        valid = [s for s in self.sequences if s["penalty"] < 2]
        if not valid:
            return None
        return max(valid, key=lambda x: x["score"] - x["penalty"])["seq"]

    def has_good_sequence(self):
        return self.best_sequence() is not None

    def penalize(self, seq):
        for s in self.sequences:
            if s["seq"] == seq:
                s["penalty"] += 1
                break

    def start_replay(self, seq):
        self.active_seq = list(seq)
        self.active_idx = 0
        self.steps_without_new = 0
        return self._next()

    def _next(self):
        if self.active_seq is None or self.active_idx >= len(self.active_seq):
            self.active_seq = None
            return None
        a = self.active_seq[self.active_idx]
        self.active_idx += 1
        return a

    def advance(self, is_new_state):
        if not is_new_state:
            self.steps_without_new += 1
        else:
            self.steps_without_new = 0
        if self.steps_without_new >= 3:
            if self.active_seq:
                self.penalize(tuple(self.active_seq))
            self.active_seq = None
            return None
        return self._next()

    def is_active(self):
        return self.active_seq is not None

# ---------------------------------------------------------------------------
# DiversityBanditV6 (object-aware core)
# ---------------------------------------------------------------------------

class DiversityBanditV6:
    def __init__(self, epsilon=0.12, repeat_window=12):
        self.t = 0
        self.epsilon = epsilon
        self.action_counts = Counter()
        self.action_rewards = defaultdict(float)
        self.action_trials = Counter()
        self.recent_actions = deque(maxlen=repeat_window)
        self.visited = set()
        self.zero_delta_streak = 0
        self.steps_since_new_state = 0
        self.best_progress = 0.0
        self.probe_tried = set()
        self.current_mode = "PROBE_ACTIONS"
        self.micro_seq = MicroSequenceMemory(seq_len=2, max_seqs=20)
        self.detector = ObjectDetector()
        self.affordance_mem = AffordanceMemory()
        self.current_objects = []
        self.changed_regions = []
        self.last_clicked_obj_sig = None
        self.object_focus_counter = 0
        self.prior_focus_obj = None

    def _action_key(self, action, data=None):
        key = getattr(action, "name", str(action))
        if isinstance(data, dict):
            key = f"{key}:{data.get('x',32)},{data.get('y',32)}"
        return key

    def choose_action(self, obs, raw, available_actions):
        self.t += 1
        frame = obs if isinstance(obs, np.ndarray) else None
        if frame is not None:
            self.current_objects = self.detector.detect(frame)
            self.changed_regions = self.detector.changed_objects(frame) if hasattr(self.detector, 'prev_frame') and self.detector.prev_frame is not None else []
        state_hash = frame_hash(obs)
        is_new = state_hash not in self.visited
        self.visited.add(state_hash)
        if is_new:
            self.steps_since_new_state = 0
            self.zero_delta_streak = 0
        else:
            self.steps_since_new_state += 1
        if self.micro_seq.is_active():
            candidate = self.micro_seq.advance(is_new)
            if candidate is not None:
                self.current_mode = "MICRO_SEQUENCE"
                return self._resolve_from_key(candidate, available_actions, frame)
            self.micro_seq.active_seq = None
        if len(self.probe_tried) > 3 and self.current_objects and random.random() < 0.35:
            obj_sigs = [self.detector.signature(o) for o in self.current_objects[:5]]
            action_types = ["ACTION6", "ACTION1", "ACTION3", "ACTION2", "ACTION4"]
            best_pair, best_s = self.affordance_mem.best_object_action_pair(obj_sigs, action_types)
            if best_pair and best_s > 0.5:
                self.current_mode = "OBJECT_AFFORDANCE"
                obj_sig, action_key = best_pair
                matched_action, matched_data = self._resolve_object_action(obj_sig, action_key, available_actions, frame)
                if matched_action is not None:
                    self.object_focus_counter += 1
                    self.last_clicked_obj_sig = obj_sig
                    return matched_action
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        untried = [a for a, _ in expanded if self._action_key(a) not in self.probe_tried]
        if untried and len(self.probe_tried) < len(expanded) * 2:
            chosen = untried[0]
            self.probe_tried.add(self._action_key(chosen))
            if isinstance(chosen, int) or (hasattr(chosen, 'name') and getattr(chosen, 'name', '') == 'ACTION6'):
                for a, d in expanded:
                    if a is chosen:
                        self._register_object_click(a, d, frame)
                        break
            self.current_mode = "PROBE_ACTIONS"
            self.last_action = chosen
            self.last_data = next((d for a, d in expanded if a is chosen), None)
            return chosen
        if self.micro_seq.has_good_sequence() and random.random() < 0.25:
            seq = self.micro_seq.best_sequence()
            candidate = self.micro_seq.start_replay(seq)
            if candidate is not None:
                self.current_mode = "MICRO_SEQUENCE"
                return self._resolve_from_key(candidate, available_actions, frame)
        if random.random() < self.epsilon:
            self.current_mode = "EPSILON_GREEDY"
            return self._least_recent_or_random(available_actions, frame)
        self.current_mode = "PROGRESS_BANDIT"
        return self._score_action(available_actions, frame)

    def _resolve_from_key(self, key, available_actions, frame):
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        for a, d in expanded:
            if self._action_key(a, d) == key:
                self.last_action = a
                self.last_data = d
                return a
        return self._least_used(available_actions)

    def _resolve_object_action(self, obj_sig, action_key, available_actions, frame):
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        if "ACTION6" in action_key:
            obj = None
            for o in self.current_objects:
                if self.detector.signature(o) == obj_sig:
                    obj = o
                    break
            if obj:
                cx, cy = obj["center"]
                target_key = f"ACTION6:{cx},{cy}"
                for a, d in expanded:
                    if self._action_key(a, d) == target_key:
                        self.last_action = a
                        self.last_data = d
                        return a, d
        for a, d in expanded:
            if self._action_key(a, d).startswith(action_key.split(":")[0]):
                self.last_action = a
                self.last_data = d
                return a, d
        return None, None

    def _register_object_click(self, action, data, frame):
        if data is None or frame is None:
            return
        x, y = data.get("x", 32), data.get("y", 32)
        for obj in self.current_objects:
            x1, y1, x2, y2 = obj["bbox"]
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.last_clicked_obj_sig = self.detector.signature(obj)
                return
        self.last_clicked_obj_sig = None

    def observe_result(self, action, data, delta_pixels, is_new_state, levels_completed, win_levels, state_str):
        key = self._action_key(action, data)
        self.action_counts[key] += 1
        self.action_trials[key] += 1
        did_fail = is_fail(state_str)
        is_win_flag = is_win(state_str)
        pr = progress_ratio(levels_completed, win_levels)
        reward = (20.0 * max(0, pr - self.best_progress)
                  + 1.0 * (delta_pixels / max(1, 64 * 64))
                  + 0.5 * (1.0 if is_new_state else 0.0)
                  - 5.0 * (1.0 if did_fail else 0.0)
                  + 10.0 * (1.0 if is_win_flag else 0.0))
        self.action_rewards[key] += reward
        self.recent_actions.append(key)
        if pr > self.best_progress:
            self.best_progress = pr
        if delta_pixels == 0:
            self.zero_delta_streak += 1
        else:
            self.zero_delta_streak = 0
        base_key = getattr(action, "name", str(action))
        self.micro_seq.record_step(base_key, is_new_state)
        if self.last_clicked_obj_sig and data is not None:
            self.affordance_mem.record(
                self.last_clicked_obj_sig,
                key, delta_pixels, is_new_state,
                max(0, levels_completed / max(1, win_levels) - self.best_progress)
            )

    def _least_used(self, available_actions):
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        best_a, best_c = None, 10 ** 9
        for a, _ in expanded:
            k = self._action_key(a)
            c = self.action_trials[k]
            if c < best_c:
                best_a, best_c = a, c
        return best_a if best_a is not None else (expanded[0][0] if expanded else 0)

    def _least_recent_or_random(self, available_actions, frame):
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        recent_keys = set(self.recent_actions)
        cand = [a for a, _ in expanded if self._action_key(a) not in recent_keys]
        if cand:
            chosen = random.choice(cand)
            self.last_action = chosen
            self.last_data = next((d for a, d in expanded if a is chosen), None)
            return chosen
        chosen = random.choice(expanded)[0]
        self.last_action = chosen
        self.last_data = next((d for a, d in expanded if a is chosen), None)
        return chosen

    def _score_action(self, available_actions, frame):
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        scored = []
        total_trials = sum(self.action_trials.values()) + 1
        total_counts = sum(self.action_counts.values()) + 1
        for action, data in expanded:
            key = self._action_key(action, data)
            trials = self.action_trials[key]
            count = self.action_counts[key]
            avg_reward = self.action_rewards[key] / max(1, trials)
            ucb = math.sqrt(math.log(total_trials) / (trials + 1))
            repeat = sum(1 for a in self.recent_actions if a == key)
            dominance = count / total_counts
            score_val = 1.0 * avg_reward + 1.3 * ucb - 0.8 * repeat - 1.0 * dominance
            scored.append((score_val, action, data))
        scored.sort(key=lambda x: x[0], reverse=True)
        chosen_action = scored[0][1] if scored else (expanded[0][0] if expanded else 0)
        chosen_data = scored[0][2] if scored else None
        self.last_action = chosen_action
        self.last_data = chosen_data
        return chosen_action

# ---------------------------------------------------------------------------
# Game loop (v6)
# ---------------------------------------------------------------------------

def run_game(game_id, max_steps=MAX_STEPS):
    game = Arcade().make(game_id)
    try:
        game.reset()
    except Exception:
        pass
    import time as _t
    _t.sleep(0.2)
    bandit = DiversityBanditV6(epsilon=0.12, repeat_window=12)
    raw = game.observation_space
    obs = extract_frame(raw)
    win_levels = safe_win(raw)
    logs = []
    status = "running"
    for step_idx in range(max_steps):
        avail = list(getattr(raw, "available_actions", []) or [])
        if not avail:
            avail = list(range(1, 7))
        action = bandit.choose_action(obs, raw, avail)
        if isinstance(action, int):
            step_action = GameAction.from_id(action)
            step_data = {"x": 32, "y": 32} if action == 6 else None
            if action == 6 and bandit.last_data:
                step_data = bandit.last_data
        elif hasattr(action, "name") and getattr(action, "name", "") == "ACTION6":
            step_action = action
            step_data = bandit.last_data or {"x": 32, "y": 32}
        else:
            step_action = action
            step_data = bandit.last_data
        before_hash = frame_hash(obs)
        try:
            result = step_game(game, step_action, data=step_data)
        except Exception as e:
            status = f"error: {type(e).__name__}: {e}"
            break
        new_obs = result["frame"]
        new_state = result["state"]
        new_levels = result["levels_completed"]
        new_win = result["win_levels"]
        new_pr = result["progress_ratio"]
        after_hash = frame_hash(new_obs)
        is_new = after_hash not in bandit.visited
        bandit.visited.add(after_hash)
        bandit.observe_result(action, step_data, result["changed_pixels"], is_new, new_levels, new_win, new_state)
        obj_count = len(bandit.current_objects)
        changed_obj_count = len(bandit.changed_regions)
        log = {
            "game_id": game_id,
            "step": step_idx,
            "action": getattr(action, "name", str(action)),
            "data": step_data,
            "state": new_state,
            "levels_completed": new_levels,
            "win_levels": new_win,
            "progress_ratio": round(new_pr, 4),
            "delta_levels": result["delta_levels"],
            "changed_pixels": result["changed_pixels"],
            "unique_states": len(bandit.visited),
            "mode": bandit.current_mode,
            "is_new_state": is_new,
            "object_count": obj_count,
            "changed_object_count": changed_obj_count,
            "last_clicked_obj_sig": bandit.last_clicked_obj_sig or "",
            "before_hash": before_hash,
            "after_hash": after_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logs.append(log)
        obs = new_obs
        raw = result["raw"]
        win_levels = new_win
        if is_fail(new_state):
            status = "failed"
            break
        if is_win(new_state):
            status = "won"
            break
    tot = sum(bandit.action_counts.values()) + 1
    ent = 0.0
    for c in bandit.action_counts.values():
        p = c / tot
        if p > 0:
            ent -= p * math.log2(p)
    return {
        "game_id": game_id,
        "steps": len(logs),
        "status": status,
        "unique_states": len(bandit.visited),
        "action_entropy": round(ent, 3),
        "action_counts": dict(bandit.action_counts),
        "best_progress": round(bandit.best_progress, 4),
        "max_levels": safe_levels(raw),
        "win_levels": win_levels,
        "mode_families": dict(Counter(l.get("mode", "?") for l in logs)),
        "object_stats": {
            "mean_objects": sum(l.get("object_count", 0) for l in logs) / max(1, len(logs)),
            "mean_changed": sum(l.get("changed_object_count", 0) for l in logs) / max(1, len(logs)),
        },
        "logs": logs,
    }


def save_episode(result):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, f"v6_{result['game_id']}.jsonl")
    with open(fpath, "w", encoding="utf-8") as f:
        for row in result["logs"]:
            safe = {k: (v if isinstance(v, (int, float, bool, type(None))) else str(v)) for k, v in row.items()}
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")


def save_summary(results):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, "summary_v6.csv")
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        fields = ["game_id", "steps", "status", "unique_states", "action_entropy",
                  "best_progress", "max_levels", "win_levels", "mode_families", "action_counts", "object_stats"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({
                "game_id": r["game_id"], "steps": r["steps"],
                "status": r["status"], "unique_states": r["unique_states"],
                "action_entropy": r["action_entropy"],
                "best_progress": r["best_progress"],
                "max_levels": r["max_levels"],
                "win_levels": r["win_levels"],
                "mode_families": json.dumps(r.get("mode_families", {})),
                "action_counts": json.dumps(r["action_counts"]),
                "object_stats": json.dumps(r.get("object_stats", {})),
            })
    return fpath


def main():
    arcade = Arcade()
    envs = arcade.get_environments()
    game_ids = [e.game_id for e in envs]
    print(f"Found {len(game_ids)} public games (DGM-lite v6 Object-Aware Planner).")
    results = []
    for gid in game_ids:
        print(f"v6 {gid[:20]}...", end=" ", flush=True)
        r = run_game(gid)
        save_episode(r)
        results.append(r)
        print(f"steps={r['steps']} states={r['unique_states']} progress={r['best_progress']:.4f} objects={r.get('object_stats',{}).get('mean_objects',0):.1f} {r['status']}")
    p = save_summary(results)
    print(f"\nSummary saved: {p}")
    return results


if __name__ == "__main__":
    main()
