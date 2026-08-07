#!/usr/bin/env python3
"""
ARC-AGI-3 DGM-lite v5 MicroSequence Planner

Lições da v4:
- REPLAY_SEQUENCE: 94.74 NSP100, 0% zero_delta ✅ (MANTER)
- PROBE_ACTIONS: 86 NSP100, 14% zero_delta ✅ (MANTER)
- STUCK_ESCAPE: 0 NSP100, 100% zero_delta ❌ (REMOVER)
- MACRO_EXPLORATION: 53.85 NSP100, 46% zero_delta ❌ (REDUZIR)
- Zero-delta caiu de 83% → 30% mas estados caíram de 81.5 → 22.7

v5 = v3 (diversity bandit robusto) + microsequências curtas adaptativas
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
# Utility (shared)
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
# step_game() — CORRECT API (FrameDataRaw)
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
# MicroSequence memory
# ---------------------------------------------------------------------------

class MicroSequenceMemory:
    """Stores short sequences (2-3 actions) that produced novelty."""
    def __init__(self, seq_len=2, max_seqs=20):
        self.seq_len = seq_len
        self.max_seqs = max_seqs
        self.sequences = []
        self.window = deque(maxlen=seq_len)
        self.active_seq = None
        self.active_idx = 0
        self.steps_without_new = 0
        self.sequence_penalties = Counter()

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
        seq = self.best_sequence()
        return seq is not None

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
        # Abort if 3 consecutive steps without new state
        if self.steps_without_new >= 3:
            if self.active_seq:
                self.penalize(tuple(self.active_seq))
            self.active_seq = None
            return None
        return self._next()

    def is_active(self):
        return self.active_seq is not None

# ---------------------------------------------------------------------------
# DiversityBanditV5 (core = v3 robust)
# ---------------------------------------------------------------------------

class DiversityBanditV5:
    def __init__(self, epsilon=0.12, repeat_window=12):
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
        self.best_progress = 0.0
        self.probe_tried = set()
        self.current_mode = "PROBE_ACTIONS"
        self.micro_seq = MicroSequenceMemory(seq_len=2, max_seqs=20)

    def _action_key(self, action, data=None):
        key = getattr(action, "name", str(action))
        if isinstance(data, dict):
            key = f"{key}:{data.get('x',32)},{data.get('y',32)}"
        return key

    def choose_action(self, obs, raw, available_actions):
        self.t += 1
        state_hash = frame_hash(obs)
        is_new = state_hash not in self.visited
        self.visited.add(state_hash)
        if is_new:
            self.steps_since_new_state = 0
            self.zero_delta_streak = 0
        else:
            self.steps_since_new_state += 1
        frame = obs if isinstance(obs, np.ndarray) else None
        expanded = expand_actions(available_actions, frame)
        # 1. MicroSequence in progress?
        if self.micro_seq.is_active():
            candidate = self.micro_seq.advance(is_new)
            if candidate is not None:
                self.current_mode = "MICRO_SEQUENCE"
                return self._resolve_from_key(candidate, expanded)
            self.micro_seq.active_seq = None
        # 2. Probe untried actions first
        untried = [a for a, _ in expanded if self._action_key(a) not in self.probe_tried]
        if untried and len(self.probe_tried) < len(available_actions) * 2:
            chosen = untried[0]
            self.probe_tried.add(self._action_key(chosen))
            self.current_mode = "PROBE_ACTIONS"
            self.last_action = chosen
            self.last_data = next((d for a, d in expanded if a is chosen), None)
            return chosen
        # 3. Try good sequence (25% chance, only if quality > 50 NSP100 proxy)
        if self.micro_seq.has_good_sequence() and random.random() < 0.25:
            seq = self.micro_seq.best_sequence()
            candidate = self.micro_seq.start_replay(seq)
            if candidate is not None:
                self.current_mode = "MICRO_SEQUENCE"
                return self._resolve_from_key(candidate, expanded)
        # 4. Epsilon greedy
        if random.random() < self.epsilon:
            self.current_mode = "EPSILON_GREEDY"
            return self._least_recent_or_random(expanded)
        # 5. Score (v3 diversity bandit)
        self.current_mode = "PROGRESS_BANDIT"
        return self._score_action(expanded)

    def _resolve_from_key(self, key, expanded):
        for a, d in expanded:
            if self._action_key(a, d) == key:
                self.last_action = a
                self.last_data = d
                return a
        # fallback
        return self._least_used(expanded)

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
        # Record micro-sequence (action key WITHOUT coordinates for generality)
        base_key = getattr(action, "name", str(action))
        self.micro_seq.record_step(base_key, is_new_state)

    def _least_used(self, expanded):
        best_a, best_c = None, 10 ** 9
        for a, _ in expanded:
            k = self._action_key(a)
            c = self.action_trials[k]
            if c < best_c:
                best_a, best_c = a, c
        return best_a if best_a is not None else (expanded[0][0] if expanded else 0)

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
            score = 1.0 * avg_reward + 1.3 * ucb - 0.8 * repeat - 1.0 * dominance
            scored.append((score, action, data))
        scored.sort(key=lambda x: x[0], reverse=True)
        chosen_action = scored[0][1] if scored else (expanded[0][0] if expanded else 0)
        chosen_data = scored[0][2] if scored else None
        self.last_action = chosen_action
        self.last_data = chosen_data
        return chosen_action

# ---------------------------------------------------------------------------
# Game loop (v5)
# ---------------------------------------------------------------------------

def run_game(game_id, max_steps=MAX_STEPS):
    game = Arcade().make(game_id)
    try:
        game.reset()
    except Exception:
        pass
    import time as _t
    _t.sleep(0.2)
    bandit = DiversityBanditV5(epsilon=0.12, repeat_window=12)
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
        elif hasattr(action, "name") and getattr(action, "name", "") == "ACTION6":
            step_action = action
            step_data = {"x": 32, "y": 32}
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
        bandit.observe_result(action, bandit.last_data, result["changed_pixels"], is_new, new_levels, new_win, new_state)
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
        "logs": logs,
    }


def save_episode(result):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, f"v5_{result['game_id']}.jsonl")
    with open(fpath, "w", encoding="utf-8") as f:
        for row in result["logs"]:
            safe = {k: (v if isinstance(v, (int, float, bool, type(None))) else str(v)) for k, v in row.items()}
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")


def save_summary(results):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, "summary_v5.csv")
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
    print(f"Found {len(game_ids)} public games (DGM-lite v5 MicroSequence Planner).")
    results = []
    for gid in game_ids:
        print(f"v5 {gid[:20]}...", end=" ", flush=True)
        r = run_game(gid)
        save_episode(r)
        results.append(r)
        print(f"steps={r['steps']} states={r['unique_states']} progress={r['best_progress']:.4f} {r['status']}")
    p = save_summary(results)
    print(f"\nSummary saved: {p}")
    return results


if __name__ == "__main__":
    main()
