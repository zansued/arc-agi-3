#!/usr/bin/env python3
"""
ARC-AGI-3 DGM-lite v8 Causal Object Planner

Lições:
- v6: 79.3 states, 83.4% zd, 12/25 estagnação (melhor baseline)
- v7: 5.0 states, 89.5% zd, 25/25 estagnação (FORÇAR object-aware MATA exploração)

v8 = v6 base + changed-region priority + causal memory + cooldown/blacklist
- SEM quota mínima para object-aware
- Object-aware precisa merecer ser escolhido (score >= threshold)
- Threshold conservador: 2.5
"""
import os, json, csv, random, hashlib, math
from datetime import datetime, timezone
from collections import Counter, defaultdict, deque

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction, GameState, ActionInput

MAX_STEPS = 500
OUT_DIR = "arc_runs"
OBJECT_SCORE_THRESHOLD = 2.5
BLACKLIST_STEPS = 50

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

def estimate_background(frame):
    """v8: border > frame_mode > 0"""
    if frame is None or frame.size == 0:
        return 0
    f = np.asarray(frame, dtype=np.int32)
    if f.ndim == 3:
        f = f[0]
    h, w = f.shape[:2]
    border = np.concatenate([
        f[0, :], f[-1, :], f[:, 0], f[:, -1],
    ])
    vals, counts = np.unique(border, return_counts=True)
    bg = int(vals[np.argmax(counts)])
    bg_ratio = counts.max() / len(border)
    if bg_ratio < 0.3:
        vals2, counts2 = np.unique(f, return_counts=True)
        bg = int(vals2[np.argmax(counts2)])
    return bg

def most_common_color(arr):
    vals, counts = np.unique(arr, return_counts=True)
    return int(vals[np.argmax(counts)])

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
        "changed_pixels": count_changed_pixels(frame_before, frame_after),
        "available_actions": list(getattr(raw_after, "available_actions", [])),
    }

# ---------------------------------------------------------------------------
# BFS flood fill
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

# ---------------------------------------------------------------------------
# Perception: Object Detector (v8 - background robusto)
# ---------------------------------------------------------------------------

class ObjectDetector:
    def __init__(self):
        self.prev_frame = None
        self.prev_objects = []
        self.prev_bg = None

    def detect(self, frame):
        if frame is None:
            return []
        f = np.asarray(frame, dtype=np.int32)
        if f.ndim == 3:
            f = f[0]
        if f.shape != (64, 64):
            return []
        bg_val = estimate_background(f)
        self.prev_bg = bg_val
        mask = (f != bg_val).astype(np.int32)
        if mask.sum() < 10:
            bg2 = most_common_color(f)
            if bg2 != bg_val:
                mask = (f != bg2).astype(np.int32)
        if mask.sum() < 5:
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
            obj = {
                "id": obj_id,
                "color": color,
                "area": area,
                "bbox": (x1, y1, x2, y2),
                "center": (cx, cy),
                "w": x2 - x1 + 1,
                "h": y2 - y1 + 1,
                "touches_border": touches,
            }
            objects.append(obj)
        objects.sort(key=lambda o: -o["area"])
        self.prev_frame = frame
        self.prev_objects = objects
        return objects[:15]

    def changed_regions(self, frame):
        if self.prev_frame is None:
            return []
        prev = np.asarray(self.prev_frame, dtype=np.int32)
        curr = np.asarray(frame, dtype=np.int32)
        if prev.shape != curr.shape:
            return []
        diff = (prev != curr).astype(np.int32)
        if diff.sum() < 5:
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
                "area": len(ys),
            })
        return regions

    def signature(self, obj):
        area_bucket = "tiny" if obj["area"] < 20 else ("small" if obj["area"] < 80 else ("medium" if obj["area"] < 300 else "large"))
        region = "border" if obj["touches_border"] else "center"
        x_bucket = "left" if obj["center"][0] < 21 else ("right" if obj["center"][0] > 42 else "mid")
        y_bucket = "top" if obj["center"][1] < 21 else ("bottom" if obj["center"][1] > 42 else "mid")
        return f"c{obj['color']}_{area_bucket}_{region}_{x_bucket}_{y_bucket}"

# ---------------------------------------------------------------------------
# CausalAffordanceMemory (v8 - causal ranking)
# ---------------------------------------------------------------------------

class CausalAffordanceMemory:
    def __init__(self):
        self.records = defaultdict(lambda: {
            "trials": 0, "delta_sum": 0, "new_states": 0,
            "zero_delta": 0, "recent_success": 0
        })
        self.blacklist = {}  # signature -> unblock_step
        self.recent_clicks = deque(maxlen=50)  # (signature, step)
        self.obj_affordance_steps = 0
        self.obj_affordance_new = 0
        self.action6_obj_count = 0
        self.action6_grid_count = 0
        self.action6_changed_count = 0
        self.obj_zd = 0
        self.grid_zd = 0
        self.changed_zd = 0

    def is_blacklisted(self, sig, current_step):
        unblock = self.blacklist.get(sig, 0)
        return current_step < unblock

    def blacklist_add(self, sig, current_step):
        self.blacklist[sig] = current_step + BLACKLIST_STEPS

    def recently_clicked(self, sig, window=20):
        count = sum(1 for s, _ in self.recent_clicks if s == sig)
        return count >= 1

    def record(self, obj_sig, action_key, delta_pixels, is_new_state,
               progress_delta, click_source, current_step):
        key = (obj_sig, key if isinstance(key:=action_key, str) else str(action_key))
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
        self.recent_clicks.append((obj_sig, current_step))
        self.obj_affordance_steps += 1
        if is_new_state:
            self.obj_affordance_new += 1
        # Track ACTION6 source
        if "ACTION6" in str(action_key) and click_source:
            if click_source in ("object_center", "object_small", "object_bbox_center", "rare_color", "rare_color_edge"):
                self.action6_obj_count += 1
                if delta_pixels == 0:
                    self.obj_zd += 1
            elif click_source == "changed_region":
                self.action6_changed_count += 1
                if delta_pixels == 0:
                    self.changed_zd += 1
            elif click_source == "grid_fallback":
                self.action6_grid_count += 1
                if delta_pixels == 0:
                    self.grid_zd += 1

    def score(self, obj_sig, action_key, current_step):
        """Causal score: 4*changed + 3*succ + 2*rare + 1*small - 3*zero - 2*repeat"""
        key = (obj_sig, action_key)
        r = self.records[key]
        if r["trials"] == 0:
            return 1.5  # untried = moderate novelty
        zero_rate = r["zero_delta"] / max(1, r["trials"])
        new_rate = r["new_states"] / max(1, r["trials"])
        mean_delta = r["delta_sum"] / max(1, r["trials"])
        # Cooldown penalty
        repeat_penalty = 2.0 if self.recently_clicked(obj_sig) else 0.0
        return max(-1, (
            4.0 * new_rate
            + 1.5 * (mean_delta / 4096)
            + 0.5 * r["recent_success"]
            - 3.0 * zero_rate
            - repeat_penalty
        ))

    def best_affordance(self, obj_sigs, action_keys, current_step):
        best_pair, best_s = None, -999
        for sig in obj_sigs:
            if self.is_blacklisted(sig, current_step):
                continue
            for ak in action_keys:
                s = self.score(sig, ak, current_step)
                if s > best_s:
                    best_s = s
                    best_pair = (sig, ak)
        return best_pair, best_s

    def feedback(self, obj_sig, action_key, delta_pixels, is_new_state, current_step, click_source="unknown"):
        if self._needs_blacklist(obj_sig, action_key, delta_pixels, current_step):
            self.blacklist_add(obj_sig, current_step)
        self.record(obj_sig, action_key, delta_pixels, is_new_state, 0, click_source, current_step)

    def _needs_blacklist(self, obj_sig, action_key, delta_pixels, current_step):
        key = (obj_sig, action_key)
        r = self.records[key]
        r["trials"] += 0  # just read, don't increment
        zero_streak = r.get("zero_delta", 0)
        return zero_streak >= 3

# ---------------------------------------------------------------------------
# ACTION6 coordinate generation (v8: changed-region priority)
# ---------------------------------------------------------------------------

def object_click_points(objects, changed_regions):
    points = []
    # 1. Changed regions (highest priority)
    for r in changed_regions:
        points.append((r["center"], "changed_region"))
    # 2. Small objects (likely interactive)
    for obj in sorted(objects, key=lambda o: o["area"]):
        if obj["area"] < 30:
            points.append((obj["center"], "object_small"))
    # 3. Rare colors
    all_colors = [o["color"] for o in objects]
    cc = Counter(all_colors)
    for obj in objects:
        if cc.get(obj["color"], 0) == 1:
            points.append((obj["center"], "rare_color"))
    # 4. All object centers
    for obj in objects:
        points.append((obj["center"], "object_center"))
    # 5. Grid fallback (lowest)
    for y in range(8, 64, 16):
        for x in range(8, 64, 16):
            points.append(((x, y), "grid_fallback"))
    seen = set()
    out = []
    for (x, y), source in points:
        x = max(0, min(63, int(x)))
        y = max(0, min(63, int(y)))
        if (x, y) not in seen:
            seen.add((x, y))
            out.append(((x, y), source))
    return out

def expand_actions(available_actions, objects, changed_regions):
    expanded = []
    for action in available_actions:
        if isinstance(action, int):
            ga = GameAction.from_id(action)
            if action == 6:
                for (x, y), source in object_click_points(objects, changed_regions):
                    expanded.append((ga, {"x": x, "y": y, "click_source": source}))
            else:
                expanded.append((ga, None))
        else:
            name = getattr(action, "name", str(action))
            if name == "ACTION6":
                for (x, y), source in object_click_points(objects, changed_regions):
                    expanded.append((action, {"x": x, "y": y, "click_source": source}))
            else:
                expanded.append((action, None))
    return expanded

# ---------------------------------------------------------------------------
# MicroSequenceMemory (preserved from v6)
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
# DiversityBanditV8 (Causal Object Core)
# ---------------------------------------------------------------------------

class DiversityBanditV8:
    def __init__(self, epsilon=0.10, repeat_window=12):
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
        self.affordance_mem = CausalAffordanceMemory()
        self.current_objects = []
        self.changed_regions = []
        self.last_action = None
        self.last_data = None
        self.last_click_source = None
        self.last_object_score = 0.0
        self.last_object_signature = "none"
        self.total_steps = 0
        self.step_counter = 0

    def _action_key(self, action, data=None):
        key = getattr(action, "name", str(action))
        if isinstance(data, dict):
            cs = data.get("click_source", "none")
            key = f"{key}:{data.get('x',32)},{data.get('y',32)}_{cs}"
        return key

    def _choose_causal_object(self, available_actions, frame):
        if not self.current_objects:
            return None
        obj_sigs = [self.detector.signature(o) for o in self.current_objects[:5]]
        action_types = ["ACTION6", "ACTION3", "ACTION1", "ACTION2", "ACTION4"]
        best_pair, best_s = self.affordance_mem.best_affordance(
            obj_sigs, action_types, self.step_counter
        )
        self.last_object_score = best_s if best_s > -999 else 0.0
        self.last_object_signature = best_pair[0] if best_pair else "none"
        if best_s >= OBJECT_SCORE_THRESHOLD:
            obj_sig, action_key = best_pair
            matched_action, matched_data = self._resolve_affordance(
                obj_sig, action_key, available_actions, frame
            )
            if matched_action is not None:
                self.current_mode = "CAUSAL_OBJECT"
                return matched_action
        return None

    def _resolve_affordance(self, obj_sig, action_key, available_actions, frame):
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        if "ACTION6" in action_key:
            obj = None
            for o in self.current_objects:
                if self.detector.signature(o) == obj_sig:
                    obj = o
                    break
            if obj:
                cx, cy = obj["center"]
                cx, cy = obj["center"]
                target_key = f"ACTION6:{cx},{cy}_object_center"
                for a, d in expanded:
                    if self._action_key(a, d) == target_key:
                        self.last_action = a
                        self.last_data = d
                        self.last_click_source = "object_center"
                        return a
        for a, d in expanded:
            if self._action_key(a, d).startswith(action_key.split(":")[0]):
                self.last_action = a
                self.last_data = d
                self.last_click_source = d.get("click_source", "unknown") if d else None
                return a
        return None

    def choose_action(self, obs, raw, available_actions):
        self.t += 1
        self.total_steps += 1
        self.step_counter += 1
        frame = obs if isinstance(obs, np.ndarray) else None
        if frame is not None:
            self.current_objects = self.detector.detect(frame)
            self.changed_regions = self.detector.changed_regions(frame) if self.detector.prev_frame is not None else []
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
        if self.current_objects:
            obj_action = self._choose_causal_object(available_actions, frame)
            if obj_action is not None:
                return obj_action
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        untried = [a for a, _ in expanded if self._action_key(a) not in self.probe_tried]
        if untried and len(self.probe_tried) < min(80, len(expanded) * 2):
            chosen = untried[0]
            self.probe_tried.add(self._action_key(chosen))
            self.current_mode = "PROBE_ACTIONS"
            self.last_action = chosen
            self.last_data = next((d for a, d in expanded if a is chosen), None)
            return chosen
        if self.micro_seq.has_good_sequence() and random.random() < 0.20:
            seq = self.micro_seq.best_sequence()
            candidate = self.micro_seq.start_replay(seq)
            if candidate is not None:
                self.current_mode = "MICRO_SEQUENCE"
                return self._resolve_from_key(candidate, available_actions, frame)
        if random.random() < self.epsilon or len(self.action_trials) < 5:
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

    def observe_result(self, action, data, delta_pixels, is_new_state,
                       levels_completed, win_levels, state_str, action_key_str=None):
        key = action_key_str or self._action_key(action, data)
        self.action_counts[key] += 1
        self.action_trials[key] += 1
        did_fail = is_fail(state_str)
        is_win_flag = is_win(state_str)
        pr = progress_ratio(levels_completed, win_levels)
        reward = (20.0 * max(0, pr - self.best_progress)
                  + 1.0 * (delta_pixels / 4096)
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
        if self.current_mode == "CAUSAL_OBJECT" and self.last_object_signature != "none":
            obj_sig = self.last_object_signature
            src = self.last_click_source or "unknown"
            self.affordance_mem.feedback(obj_sig, key, delta_pixels,
                                          is_new_state, self.step_counter, src)

    def _least_used(self, available_actions):
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        best_a, best_c = None, 10**9
        for a, _ in expanded:
            k = self._action_key(a)
            c = self.action_trials.get(k, 0)
            if c < best_c:
                best_a, best_c = a, c
        return best_a if best_a is not None else (expanded[0][0] if expanded else 0)

    def _least_recent_or_random(self, available_actions, frame):
        expanded = expand_actions(available_actions, self.current_objects, self.changed_regions)
        recent_keys = set(self.recent_actions)
        cand = [(a, d) for a, d in expanded if self._action_key(a, d) not in recent_keys]
        if cand:
            chosen = random.choice(cand)[0]
            self.last_action = chosen
            self.last_data = next((d for a, d in cand if a is chosen), None)
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
            trials = self.action_trials.get(key, 0)
            count = self.action_counts.get(key, 0)
            avg_reward = self.action_rewards.get(key, 0) / max(1, trials)
            ucb = math.sqrt(math.log(total_trials) / (trials + 1))
            repeat = sum(1 for a in self.recent_actions if a == key)
            dominance = count / total_counts
            score_val = 1.0 * avg_reward + 1.3 * ucb - 0.8 * repeat - 1.0 * dominance
            scored.append((score_val, action, data))
        scored.sort(key=lambda x: -x[0])
        chosen = scored[0][1] if scored else (expanded[0][0] if expanded else 0)
        self.last_action = chosen
        self.last_data = scored[0][2] if scored else None
        return chosen


# ---------------------------------------------------------------------------
# Game loop
# ---------------------------------------------------------------------------

def run_game(game_id, max_steps=500):
    game = Arcade().make(game_id)
    try:
        game.reset()
    except Exception:
        pass
    import time as _t
    _t.sleep(0.2)
    bandit = DiversityBanditV8(epsilon=0.10, repeat_window=12)
    raw = game.observation_space
    obs = extract_frame(raw) if raw is not None else None
    win_levels = safe_win(raw)
    logs = []
    status = "running"
    for step_idx in range(max_steps):
        avail = list(getattr(raw, "available_actions", []) or [])
        if not avail:
            avail = list(range(1, 7))
        action = bandit.choose_action(obs, raw, avail)
        if isinstance(action, int):
            ga = GameAction.from_id(action)
            if action == 6:
                data_dict = getattr(bandit, 'last_data', None) or {}
                inp = ActionInput(action_type=ga, x=data_dict.get("x", 32), y=data_dict.get("y", 32))
                result = step_game(game, inp, reasoning=f"v8_{bandit.current_mode}")
                action_key = f"ACTION6:{data_dict.get('x',32)},{data_dict.get('y',32)}"
            else:
                result = step_game(game, ga, reasoning=f"v8_{bandit.current_mode}")
                action_key = ga.name if hasattr(ga, 'name') else f"ACTION{action}"
        else:
            result = step_game(game, action, reasoning=f"v8_{bandit.current_mode}")
            action_key = getattr(action, "name", str(action))
        raw = result["raw"]
        obs = result["frame"]
        changed = result["changed_pixels"]
        is_new_flag = True
        levels_c = result["levels_completed"]
        wt = result["win_levels"]
        state_str = result["state"]
        bandit.observe_result(action, getattr(bandit, 'last_data', None), changed,
                              is_new_flag, levels_c, wt, state_str, action_key)
        log_entry = {
            "step": step_idx + 1,
            "action": action_key,
            "mode": bandit.current_mode,
            "state_hash": hashlib.md5(str(obs).encode()).hexdigest() if obs is not None else "",
            "changed_pixels": changed,
            "object_count": len(bandit.current_objects),
            "levels_completed": levels_c,
            "win_levels": wt,
            "state": state_str,
            "zero_delta_streak": bandit.zero_delta_streak,
            "steps_since_new_state": bandit.steps_since_new_state,
            "last_click_source": bandit.last_click_source,
            "last_object_score": bandit.last_object_score,
            "last_object_signature": bandit.last_object_signature,
            "action6_obj_count": bandit.affordance_mem.action6_obj_count,
            "action6_grid_count": bandit.affordance_mem.action6_grid_count,
            "action6_changed_count": bandit.affordance_mem.action6_changed_count,
        }
        logs.append(log_entry)
        state_upper = (result["state"] or "").upper()
        if "FAIL" in state_upper:
            status = "fail"
            break
        if "WIN" in state_upper:
            status = "win"
            if levels_c >= wt and wt > 0:
                break
    return logs, status


if __name__ == "__main__":
    import sys
    ensure_dir(OUT_DIR)
    game_ids = [
        "ar25-0c556536", "bp35-0a0ad940", "cd82-fb555c5d", "cn04-2fe56bfb",
        "dc22-fdcac232", "ft09-0d8bbf25", "g50t-5849a774", "ka59-38d34dbb",
        "lf52-271a04aa", "lp85-305b61c3", "ls20-9607627b", "m0r0-492f87ba",
        "r11l-495a7899", "re86-8af5384d", "s5i5-18d95033", "sb26-7fbdac44",
        "sc25-635fd71a", "sk48-d8078629", "sp80-589a99af", "su15-1944f8ab",
        "tn36-ef4dde99", "tr87-cd924810", "tu93-0768757b", "vc33-5430563c",
        "wa30-ee6fef47",
    ]
    log = []
    for gid in game_ids:
        print(f"[v8] Running {gid}...")
        try:
            l, s = run_game(gid)
            out = os.path.join(OUT_DIR, f"v8_{gid}.jsonl")
            with open(out, 'w') as f:
                for entry in l:
                    f.write(json.dumps(entry) + '\n')
            summary = {"game": gid, "status": s, "steps": len(l)}
            if l:
                unique_states = len(set(e.get("state_hash", "") for e in l if e.get("state_hash")))
                zero_delta = sum(1 for e in l if e.get("changed_pixels", 0) == 0)
                summary["unique_states"] = unique_states
                summary["zero_delta"] = zero_delta
                summary["zero_delta_rate"] = round(zero_delta / max(1, len(l)), 4)
                summary["max_levels"] = max(e.get("levels_completed", 0) for e in l)
                summary["max_obj_score"] = max(e.get("last_object_score", 0) for e in l)
                summary["object_clicks"] = max(e.get("action6_obj_count", 0) for e in l)
                summary["grid_clicks"] = max(e.get("action6_grid_count", 0) for e in l)
                summary["changed_clicks"] = max(e.get("action6_changed_count", 0) for e in l)
            log.append(summary)
            print(f"  -> {s}, {len(l)} steps, {summary.get('unique_states',0)} states")
        except Exception as e:
            print(f"  -> ERROR: {e}")
            log.append({"game": gid, "status": "error", "error": str(e)})
    csv_path = os.path.join(OUT_DIR, "summary_v8.csv")
    if log:
        keys = log[0].keys()
        with open(csv_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(log)
    print(f"Done! {len(log)} games. Summary saved to {csv_path}")
