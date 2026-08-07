#!/usr/bin/env python3
"""
ARC-AGI-3 DGM-lite v4 Planner (Progress-Seeking Planner)

Objetivo: reduzir estagnação (zero_delta_rate < 70%, last_new_state > 100).

Novidades vs v3:
- SequenceBuffer: salva sequências que geraram new_state/delta
- MacroExploration: blocos de ações quando preso
- StuckDetection: zero_delta_streak >= 8 ou steps_since_new >= 30
- ReplaySequence: repete/muta sequências promissoras
- Modos: PROBE -> DIVERSITY_BANDIT -> REPLAY/MUTATE -> STUCK_ESCAPE -> MACRO -> RESET
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
# Utility (shared with v3)
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
# ACTION6 coordinate generation
# ---------------------------------------------------------------------------

def candidate_points(frame):
    if frame is None:
        return [(32, 32)]
    frame = np.atleast_2d(np.asarray(frame, dtype=np.int32))
    if frame.shape == (0,):
        return [(32, 32)]
    if frame.ndim == 1:
        if frame.size == 0:
            return [(32, 32)]
        try:
            frame = frame.reshape(64, 64)
        except Exception:
            return [(32, 32)]
    points = [(32, 32), (0, 0), (0, 63), (63, 0), (63, 63)]
    for y in range(8, 64, 16):
        for x in range(8, 64, 16):
            points.append((x, y))
    bg = int(frame[0, 0]) if frame.shape[0] > 0 and frame.shape[1] > 0 else 0
    neg = np.where(frame != bg)
    if len(neg[0]) > 0:
        ys, xs = neg
        points.append((int(xs.mean()), int(ys.mean())))
        points.append((int(xs.min()), int(ys.min())))
        points.append((int(xs.max()), int(ys.max())))
    seen = set()
    out = []
    for x, y in points:
        x = max(0, min(63, int(x)))
        y = max(0, min(63, int(y)))
        if (x, y) not in seen:
            seen.add((x, y))
            out.append((x, y))
    return out

def expand_actions(available_actions, frame):
    expanded = []
    for action in available_actions:
        if isinstance(action, int):
            ga = GameAction.from_id(action)
            if action == 6:
                for x, y in candidate_points(frame):
                    expanded.append((ga, {"x": x, "y": y}))
            else:
                expanded.append((ga, None))
        else:
            name = getattr(action, "name", str(action))
            if name == "ACTION6":
                for x, y in candidate_points(frame):
                    expanded.append((action, {"x": x, "y": y}))
            else:
                expanded.append((action, None))
    return expanded

# ---------------------------------------------------------------------------
# SequenceBuffer
# ---------------------------------------------------------------------------

class SequenceBuffer:
    """Stores and retrieves sequences that produced novel states or high delta."""
    def __init__(self, max_sequences=100, seq_len=3):
        self.sequences = []
        self.max_sequences = max_sequences
        self.seq_len = seq_len
        self.action_window = deque(maxlen=seq_len)
        self.data_window = deque(maxlen=seq_len)

    def record_step(self, action, data, new_state_found, delta_pixels, delta_levels):
        """Record an action and data to the sliding window."""
        act_key = getattr(action, "name", str(action))
        if isinstance(data, dict):
            act_key = f"{act_key}:{data.get('x',32)},{data.get('y',32)}"
        self.action_window.append(act_key)
        if data is not None:
            self.data_window.append(data)
        else:
            self.data_window.append(None)
        if len(self.action_window) == self.seq_len and (new_state_found or delta_pixels > 50 or delta_levels > 0):
            seq = tuple(self.action_window)
            score = 3.0 * int(new_state_found) + 0.01 * delta_pixels + 10.0 * delta_levels
            self.sequences.append({
                "actions": seq,
                "score": score,
                "new_states": 1 if new_state_found else 0,
                "delta_pixels": delta_pixels,
                "delta_levels": delta_levels,
            })
        if len(self.sequences) > self.max_sequences:
            self.sequences.sort(key=lambda x: -x["score"])
            self.sequences = self.sequences[:self.max_sequences]

    def best_sequence(self):
        """Return the highest-scored sequence."""
        if not self.sequences:
            return None
        best = max(self.sequences, key=lambda x: x["score"])
        return best["actions"]

    def top_sequences(self, n=3):
        if not self.sequences:
            return []
        return [s["actions"] for s in sorted(self.sequences, key=lambda x: -x["score"])[:n]]

# ---------------------------------------------------------------------------
# MacroExploration
# ---------------------------------------------------------------------------

MACROS = [
    ["ACTION1", "ACTION1", "ACTION1"],
    ["ACTION2", "ACTION2", "ACTION2"],
    ["ACTION3", "ACTION4", "ACTION3", "ACTION4"],
    ["ACTION7", "ACTION1", "ACTION7"],
    ["ACTION6:32,32", "ACTION1"],
    ["ACTION6:32,32", "ACTION6:0,0"],
    ["ACTION1", "ACTION2", "ACTION3", "ACTION4"],
    ["ACTION2", "ACTION6:32,32", "ACTION5"],
    ["ACTION6:0,0", "ACTION6:63,63"],
    ["ACTION3", "ACTION3", "ACTION3", "ACTION3"],
    ["ACTION6:16,16", "ACTION6:48,48"],
    ["ACTION4", "ACTION5", "ACTION1", "ACTION2"],
    ["ACTION6:foreground", "ACTION6:foreground"],
    ["ACTION1", "ACTION6:32,32", "ACTION7", "ACTION6:32,32"],
    ["ACTION6:8,8", "ACTION6:56,56", "ACTION6:32,32"],
]

class MacroExploration:
    def __init__(self):
        self.macro_index = 0
        self.macro_scores = defaultdict(float)
        self.macro_trials = Counter()
        self.active_macro = None
        self.active_macro_idx = 0
        self.macro_actions = []

    def start_macro(self):
        choice = random.randint(0, len(MACROS) - 1)
        self.active_macro = MACROS[choice]
        self.active_macro_idx = 0
        self.macro_actions = self.active_macro
        return self._current_step()

    def _current_step(self):
        if self.active_macro is None or self.active_macro_idx >= len(self.macro_actions):
            return None
        return self.macro_actions[self.active_macro_idx]

    def advance(self):
        self.active_macro_idx += 1
        return self._current_step()

    def is_done(self):
        return self.active_macro is None or self.active_macro_idx >= len(self.macro_actions)

    def apply_score(self, macro_name, gain):
        self.macro_trials[macro_name] += 1
        old = self.macro_scores[macro_name]
        n = self.macro_trials[macro_name]
        self.macro_scores[macro_name] = (old * (n - 1) + gain) / n

    def best_macro(self):
        candidates = [(name, score) for name, score in self.macro_scores.items() if self.macro_trials[name] >= 2]
        if not candidates:
            return None
        return max(candidates, key=lambda x: x[1])[0]

# ---------------------------------------------------------------------------
# DiversityPlannerV4 (main scheduler)
# ---------------------------------------------------------------------------

class DiversityPlannerV4:
    def __init__(self, epsilon=0.12, repeat_window=15):
        self.t = 0
        self.epsilon = epsilon
        self.action_counts = Counter()
        self.action_rewards = defaultdict(float)
        self.action_trials = Counter()
        self.recent_actions = deque(maxlen=repeat_window)
        self.visited = set()
        self.last_state_hash = None
        self.zero_delta_streak = 0
        self.steps_since_new_state = 0
        self.last_new_state_step = 0
        self.best_progress = 0.0
        # Components
        self.sequence_buffer = SequenceBuffer()
        self.macro_explorer = MacroExploration()
        self.probe_tried = set()
        self.current_mode = "PROBE_ACTIONS"
        self.replay_queue = deque()
        self.last_action = None
        self.last_data = None
        self.stuck_escape_counter = 0

    def _action_key(self, action, data=None):
        key = getattr(action, "name", str(action))
        if isinstance(data, dict):
            key = f"{key}:{data.get('x',32)},{data.get('y',32)}"
        return key

    def choose_action(self, obs, raw, available_actions):
        self.t += 1
        state_hash = frame_hash(obs)
        is_new_state = state_hash not in self.visited
        self.visited.add(state_hash)
        if state_hash == self.last_state_hash:
            pass  # same state, tracker below
        self.last_state_hash = state_hash
        if is_new_state:
            self.steps_since_new_state = 0
            self.last_new_state_step = self.t
            self.zero_delta_streak = 0
        else:
            self.steps_since_new_state += 1
        frame = obs if isinstance(obs, np.ndarray) else None
        expanded = expand_actions(available_actions, frame)
        # --- Mode selection ---
        # 1. RESET if stuck too long
        if self.steps_since_new_state >= 60:
            self.current_mode = "RESET_IF_DEAD"
            self.stuck_escape_counter += 1
            # Force macro
            candidate = self.macro_explorer.start_macro()
            if candidate:
                act = self._resolve_macro_action(candidate)
                if act:
                    self.current_mode = f"RESET_MACRO({self.stuck_escape_counter})"
                    return act
        # 2. Stuck escape (zero delta streak)
        if self.zero_delta_streak >= 8:
            self.current_mode = "STUCK_ESCAPE"
            self.zero_delta_streak = 0
            return self._least_used(expanded)
        # 3. New state stagnation
        if self.steps_since_new_state >= 30:
            # Try macro or replay
            if random.random() < 0.4 and self.sequence_buffer.best_sequence() is not None:
                seq = self.sequence_buffer.best_sequence()
                self.replay_queue.extend(seq)
                self.current_mode = "REPLAY_SEQUENCE"
                return self._dequeue_or_fallback(expanded)
            self.current_mode = "MACRO_EXPLORATION"
            candidate = self.macro_explorer.start_macro()
            if candidate:
                act = self._resolve_macro_action(candidate)
                if act:
                    return act
        # 4. Probe untried
        untried = [a for a, _ in expanded if self._action_key(a) not in self.probe_tried]
        if untried:
            chosen = untried[0]
            self.probe_tried.add(self._action_key(chosen))
            self.current_mode = "PROBE_ACTIONS"
            self.last_action = chosen
            self.last_data = next((d for a, d in expanded if a is chosen), None)
            return chosen
        # 5. Replay queue
        if self.replay_queue:
            self.current_mode = "REPLAY_SEQUENCE"
            return self._dequeue_or_fallback(expanded)
        # 6. Epsilon greedy
        if random.random() < self.epsilon:
            self.current_mode = "EPSILON_GREEDY"
            return self._least_recent_or_random(expanded)
        # 7. Score
        self.current_mode = "PROGRESS_BANDIT"
        return self._score_action(expanded)

    def _resolve_macro_action(self, macro_key):
        """Resolve a macro action key into a GameAction and optional data dict."""
        if ":" in macro_key:
            base, coord = macro_key.split(":", 1)
            if "," in coord:
                parts = coord.split(",")
                x = int(parts[0].strip()) if parts[0].strip().lstrip("-").isdigit() else 32
                y = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().lstrip("-").isdigit() else 32
                x = max(0, min(63, x))
                y = max(0, min(63, y))
                return GameAction.ACTION6, {"x": x, "y": y}
        try:
            eid = int(macro_key.replace("ACTION", ""))
            if eid == 6:
                return GameAction.ACTION6, {"x": 32, "y": 32}
            return GameAction(eid), None
        except Exception:
            return None, None

    def _dequeue_or_fallback(self, expanded):
        if self.replay_queue:
            target = self.replay_queue.popleft()
            for act, data in expanded:
                key = self._action_key(act, data)
                if key == target:
                    self.last_action = act
                    self.last_data = data
                    return act
        # fallback
        return self._least_used(expanded)

    def _least_used(self, expanded):
        best_a, best_c = None, 10 ** 9
        for a, _ in expanded:
            k = self._action_key(a)
            c = self.action_trials[k]
            if c < best_c:
                best_a, best_c = a, c
        self.last_action = best_a if best_a is not None else (expanded[0][0] if expanded else 0)
        self.last_data = next((d for a, d in expanded if a is self.last_action), None) if best_a else None
        return self.last_action

    def _least_recent_or_random(self, expanded):
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

    def _score_action(self, expanded):
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
            stuck_bonus = 0.5 if self.steps_since_new_state > 15 else 0.0
            score = 1.0 * avg_reward + 1.3 * ucb - 0.8 * repeat - 1.0 * dominance + stuck_bonus
            scored.append((score, action, data))
        scored.sort(key=lambda x: x[0], reverse=True)
        chosen_action = scored[0][1]
        chosen_data = scored[0][2]
        self.last_action = chosen_action
        self.last_data = chosen_data
        return chosen_action

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
        # zero delta streak
        if delta_pixels == 0:
            self.zero_delta_streak += 1
        else:
            self.zero_delta_streak = 0
        # sequence buffer
        self.sequence_buffer.record_step(action, data, is_new_state, delta_pixels, int(levels_completed))

# ---------------------------------------------------------------------------
# Game loop (v4)
# ---------------------------------------------------------------------------

def run_game(game_id, max_steps=MAX_STEPS):
    game = Arcade().make(game_id)
    try: game.reset()
    except: pass
    import time as _t
    _t.sleep(0.2)
    planner = DiversityPlannerV4(epsilon=0.12, repeat_window=15)
    raw = game.observation_space
    obs = extract_frame(raw)
    win_levels = safe_win(raw)
    state_str = safe_state(raw)
    logs = []
    status = "running"
    for step_idx in range(max_steps):
        avail = list(getattr(raw, "available_actions", []) or [])
        if not avail:
            avail = list(range(1, 7))
        action = planner.choose_action(obs, raw, avail)
        if isinstance(action, tuple) and len(action) == 2:
            step_action, step_data = action
        elif isinstance(action, int):
            step_action = GameAction.from_id(action)
            step_data = {"x": 32, "y": 32} if action == 6 else None
        elif hasattr(action, "name") and getattr(action, "name", "") == "ACTION6":
            step_action = action
            step_data = {"x": 32, "y": 32}
        else:
            step_action = action
            step_data = planner.last_data
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
        is_new = after_hash not in planner.visited
        planner.visited.add(after_hash)
        planner.observe_result(action, planner.last_data, result["changed_pixels"], is_new, new_levels, new_win, new_state)
        act_key = getattr(action, "name", str(action))
        log = {
            "game_id": game_id,
            "step": step_idx,
            "action": act_key,
            "data": step_data,
            "state": new_state,
            "levels_completed": new_levels,
            "win_levels": new_win,
            "progress_ratio": round(new_pr, 4),
            "delta_levels": result["delta_levels"],
            "changed_pixels": result["changed_pixels"],
            "unique_states": len(planner.visited),
            "mode": getattr(planner, "current_mode", "UNKNOWN"),
            "zero_delta_streak": getattr(planner, "zero_delta_streak", 0),
            "steps_since_new": getattr(planner, "steps_since_new_state", 0),
            "before_hash": before_hash,
            "after_hash": after_hash,
            "is_new_state": is_new,
            "available_actions": [str(a) for a in avail],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logs.append(log)
        obs = new_obs
        raw = result["raw"]
        win_levels = new_win
        state_str = new_state
        if is_fail(state_str):
            status = "failed"
            break
        if is_win(state_str):
            status = "won"
            break
    tot = sum(planner.action_counts.values()) + 1
    ent = 0.0
    for c in planner.action_counts.values():
        p = c / tot
        if p > 0:
            ent -= p * math.log2(p)
    return {
        "game_id": game_id,
        "steps": len(logs),
        "status": status,
        "unique_states": len(planner.visited),
        "action_entropy": round(ent, 3),
        "action_counts": dict(planner.action_counts),
        "best_progress": round(planner.best_progress, 4),
        "max_levels": safe_levels(raw),
        "win_levels": win_levels,
        "mode_families": dict(Counter(l.get("mode", "?") for l in logs)),
        "logs": logs,
    }


def save_episode(result):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, f"v4_{result['game_id']}.jsonl")
    with open(fpath, "w", encoding="utf-8") as f:
        for row in result["logs"]:
            safe = {k: (v if isinstance(v, (int, float, bool, type(None))) else str(v)) for k, v in row.items()}
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")


def save_summary(results):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, "summary_v4.csv")
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        fields = ["game_id", "steps", "status", "unique_states", "action_entropy",
                  "best_progress", "max_levels", "win_levels", "mode_families", "action_counts"]
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
            })
    return fpath


def main():
    arcade = Arcade()
    envs = arcade.get_environments()
    game_ids = [e.game_id for e in envs]
    print(f"Found {len(game_ids)} public games (DGM-lite v4 Planner).")
    results = []
    for gid in game_ids:
        print(f"v4 {gid[:20]}...", end=" ", flush=True)
        r = run_game(gid)
        save_episode(r)
        results.append(r)
        print(f"steps={r['steps']} states={r['unique_states']} progress={r['best_progress']:.4f} {r['status']}")
    p = save_summary(results)
    print(f"\nSummary saved: {p}")
    return results


if __name__ == "__main__":
    main()
