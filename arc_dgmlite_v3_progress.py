#!/usr/bin/env python3
"""
ARC-AGI-3 DGM-lite v3 Progress-Aware

Métrica principal: progress = levels_completed / win_levels

step_game() não usa tupla — retorna FrameDataRaw diretamente.
Reward:  10x delta_levels + 1x visual_delta + 0.5x novelty - 5x fail
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
# Utility (shared with v2)
# ---------------------------------------------------------------------------

def ensure_dir(path): os.makedirs(path, exist_ok=True)

def frame_hash(arr):
    if arr is None: return ""
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def count_changed_pixels(prev, curr):
    if prev is None or curr is None: return 0
    try:
        a = np.asarray(prev, dtype=np.int32)
        b = np.asarray(curr, dtype=np.int32)
        if a.shape != b.shape: return -1
        return int(np.sum(a != b))
    except Exception: return -1

def extract_frame(raw):
    """Extract (64,64) ndarray from FrameDataRaw or ndarray."""
    if raw is None: return None
    if isinstance(raw, np.ndarray):
        return raw.squeeze() if raw.ndim > 2 else raw
    if hasattr(raw, "frame"):
        arr = np.asarray(raw.frame, dtype=np.int32)
        if arr.ndim == 3: arr = arr[0]
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

# ---------------------------------------------------------------------------
# step_game() — CORRECT API: step() returns FrameDataRaw (not tuple)
# ---------------------------------------------------------------------------

def step_game(game, action, data=None, reasoning=None):
    """Execute one step, return dict with real progress fields."""
    raw_before = game.observation_space
    frame_before = extract_frame(raw_before)
    try:
        if data is not None:
            raw_after = game.step(action, data=data, reasoning=reasoning)
        else:
            raw_after = game.step(action, reasoning=reasoning)
    except Exception as e:
        raise
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
        "levels_before": levels_before,
        "levels_completed": levels_after,
        "win_levels": win_lvls,
        "progress_ratio": progress_ratio(levels_after, win_lvls),
        "delta_levels": delta_levels,
        "delta_progress_ratio": progress_ratio(levels_after, win_lvls) - progress_ratio(levels_before, win_lvls),
        "changed_pixels": count_changed_pixels(frame_before, frame_after),
        "available_actions": list(getattr(raw_after, "available_actions", [])),
    }

def is_fail(state_str):
    return "FAIL" in state_str.upper()
def is_win(state_str):
    return "WIN" in state_str.upper()

# ---------------------------------------------------------------------------
# ACTION6 coordinate generation
# ---------------------------------------------------------------------------

def candidate_points(frame):
    if frame is None: return [(32,32)]
    frame = np.atleast_2d(np.asarray(frame, dtype=np.int32))
    if frame.shape == (0,): return [(32,32)]
    if frame.ndim == 1:
        if frame.size == 0: return [(32,32)]
        try: frame = frame.reshape(64,64)
        except: return [(32,32)]
    points = [(32,32),(0,0),(0,63),(63,0),(63,63)]
    for y in range(8, 64, 16):
        for x in range(8, 64, 16):
            points.append((x,y))
    bg = int(frame[0,0]) if frame.shape[0]>0 and frame.shape[1]>0 else 0
    ys, xs = np.where(frame != bg)
    if len(xs) > 0:
        points.append((int(xs.mean()), int(ys.mean())))
        points.append((int(xs.min()), int(ys.min())))
        points.append((int(xs.max()), int(ys.max())))
    seen = set()
    out = []
    for x,y in points:
        x = max(0, min(63, int(x)))
        y = max(0, min(63, int(y)))
        if (x,y) not in seen:
            seen.add((x,y))
            out.append((x,y))
    return out

def expand_actions(available_actions, frame):
    expanded = []
    for action in available_actions:
        if isinstance(action, int):
            ga = GameAction.from_id(action)
            if action == 6:
                for x,y in candidate_points(frame):
                    expanded.append((ga, {"x":x, "y":y}))
            else:
                expanded.append((ga, None))
        else:
            name = getattr(action, "name", str(action))
            if name == "ACTION6":
                for x,y in candidate_points(frame):
                    expanded.append((action, {"x":x, "y":y}))
            else:
                expanded.append((action, None))
    return expanded

# ---------------------------------------------------------------------------
# ProbePolicy (from v2)
# ---------------------------------------------------------------------------

class ProbePolicy:
    def __init__(self):
        self.tried = set()
    def choose_probe(self, available_actions):
        for a in available_actions:
            key = getattr(a, "name", str(a))
            if key not in self.tried:
                self.tried.add(key)
                return a
        return None

# ---------------------------------------------------------------------------
# DiversityLyapunovSchedulerV3 (progress-aware)
# ---------------------------------------------------------------------------

class DiversityLyapunovSchedulerV3:
    """
    Recompensa progresso real (levels_completed) muito mais que mudança visual.
    Mantém diversidade da v2 mas adiciona:
      - reward = 10*delta_levels + 1*visual_delta + 0.5*novelty - 5*fail
      - fail_penalty
    """
    def __init__(self, epsilon=0.15, repeat_window=12):
        self.t = 0
        self.epsilon = epsilon
        self.action_counts = Counter()
        self.action_rewards = defaultdict(float)  # cumulative reward
        self.action_trials = Counter()
        self.recent_actions = deque(maxlen=repeat_window)
        self.last_state_hash = None
        self.stuck_steps = 0
        self.visited = set()
        self.current_family = "ProbePolicy"
        self.probe_policy = ProbePolicy()
        self.last_action = None
        self.best_progress = 0.0

    def choose_action(self, obs, info, avail):
        self.t += 1
        state_hash = frame_hash(obs)
        self.visited.add(state_hash)
        if state_hash == self.last_state_hash:
            self.stuck_steps += 1
        else:
            self.stuck_steps = 0
        self.last_state_hash = state_hash
        frame = obs if isinstance(obs, np.ndarray) else None
        expanded = expand_actions(avail, frame)
        probe = self.probe_policy.choose_probe([a for a,_ in expanded])
        if probe is not None:
            self.current_family = "ProbePolicy"
            self.last_action = probe
            return probe
        if self.stuck_steps >= 5:
            chosen = self._least_used(expanded)
            self.current_family = f"StuckEscape(stuck={self.stuck_steps})"
            self.last_action = chosen
            return chosen
        if random.random() < self.epsilon:
            chosen = self._least_recent_or_random(expanded)
            self.current_family = "EpsilonGreedy"
            self.last_action = chosen
            return chosen
        scored = self._score_actions(expanded)
        chosen = scored[0][1] if scored else (expanded[0][0] if expanded else 0)
        self.last_action = chosen
        self.current_family = "ProgressAwareBandit"
        return chosen

    def observe_result(self, action, delta_pixels, is_new_state, levels_completed, win_levels, state_str):
        """Update statistics with REAL progress signal."""
        key = getattr(action, "name", str(action))
        self.action_counts[key] += 1
        self.action_trials[key] += 1
        # Reward formula: progress >> visual change
        did_fail = is_fail(state_str)
        is_win_flag = is_win(state_str)
        pr = progress_ratio(levels_completed, win_levels)
        # Prior progress
        prior_progress = self.action_rewards[key] / max(1, self.action_trials[key])
        delta_progress = max(0, pr - prior_progress)
        reward = (
            20.0 * delta_progress
            + 1.0 * (delta_pixels / max(1, 64*64))
            + 0.5 * (1.0 if is_new_state else 0.0)
            - 5.0 * (1.0 if did_fail else 0.0)
            + 10.0 * (1.0 if is_win_flag else 0.0)
        )
        self.action_rewards[key] += reward
        if isinstance(action, int):
            self.recent_actions.append(str(action))
        else:
            self.recent_actions.append(getattr(action, "name", str(action)))
        if pr > self.best_progress:
            self.best_progress = pr

    def _least_used(self, expanded):
        best_a, best_c = None, 10**9
        for a,_ in expanded:
            k = getattr(a, "name", str(a))
            c = self.action_trials[k]
            if c < best_c:
                best_a, best_c = a, c
        return best_a if best_a is not None else (expanded[0][0] if expanded else 0)

    def _least_recent_or_random(self, expanded):
        recent = set(self.recent_actions)
        cand = [a for a,_ in expanded if getattr(a, "name", str(a)) not in recent]
        if cand: return random.choice(cand)
        return random.choice(expanded)[0]

    def _score_actions(self, expanded):
        scored = []
        total_trials = sum(self.action_trials.values()) + 1
        total_counts = sum(self.action_counts.values()) + 1
        for action,_ in expanded:
            key = getattr(action, "name", str(action))
            trials = self.action_trials[key]
            count = self.action_counts[key]
            avg_reward = self.action_rewards[key] / max(1, trials)
            ucb = math.sqrt(math.log(total_trials) / (trials + 1))
            repeat = sum(1 for a in self.recent_actions if a == key)
            dominance = count / total_counts
            score = (
                1.0 * avg_reward
                + 1.2 * ucb
                - 0.8 * repeat
                - 1.0 * dominance
            )
            scored.append((score, action))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

# ---------------------------------------------------------------------------
# Game loop (v3)
# ---------------------------------------------------------------------------

def run_game(game_id, max_steps=MAX_STEPS):
    game = Arcade().make(game_id)
    try: game.reset()
    except: pass
    import time as _t
    _t.sleep(0.2)
    scheduler = DiversityLyapunovSchedulerV3(epsilon=0.15, repeat_window=12)
    # First observation
    raw = game.observation_space
    obs = extract_frame(raw)
    state_str = safe_state(raw)
    levels_completed = safe_levels(raw)
    win_levels = safe_win(raw)
    logs = []
    status = "running"
    for step_idx in range(max_steps):
        avail = list(getattr(raw, "available_actions", []) or [])
        if not avail: avail = list(range(6))
        action = scheduler.choose_action(obs, raw, avail)
        # Convert to GameAction
        if isinstance(action, tuple):
            step_action, step_data = action
        elif isinstance(action, int):
            step_action = GameAction.from_id(action)
            step_data = {"x":32,"y":32} if action==6 else None
        elif hasattr(action, "name") and getattr(action,"name","")=="ACTION6":
            step_action = action
            step_data = {"x":32,"y":32}
        else:
            step_action = action
            step_data = None
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
        is_new = after_hash not in scheduler.visited
        scheduler.visited.add(after_hash)
        scheduler.observe_result(action, result["changed_pixels"], is_new, new_levels, new_win, new_state)
        log = {
            "game_id": game_id,
            "step": step_idx,
            "action": str(action),
            "action_key": getattr(action, "name", str(action)),
            "data": step_data,
            "state": new_state,
            "levels_completed": new_levels,
            "win_levels": new_win,
            "progress_ratio": round(new_pr, 4),
            "delta_levels": result["delta_levels"],
            "delta_progress_ratio": round(result["delta_progress_ratio"], 4),
            "changed_pixels": result["changed_pixels"],
            "unique_states": len(scheduler.visited),
            "family": scheduler.current_family,
            "before_hash": before_hash,
            "after_hash": after_hash,
            "is_new_state": is_new,
            "available_actions": [str(a) for a in avail],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logs.append(log)
        obs = new_obs
        raw = result["raw"]
        levels_completed = new_levels
        win_levels = new_win
        state_str = new_state
        if is_fail(state_str):
            status = "failed"
            break
        if is_win(state_str):
            status = "won"
            break
    tot = sum(scheduler.action_counts.values())+1
    ent = 0.0
    for c in scheduler.action_counts.values():
        p = c/tot
        if p>0: ent -= p*math.log2(p)
    return {
        "game_id": game_id,
        "steps": len(logs),
        "status": status,
        "unique_states": len(scheduler.visited),
        "action_entropy": round(ent, 3),
        "action_counts": dict(scheduler.action_counts),
        "best_progress": round(scheduler.best_progress, 4),
        "max_levels": levels_completed,
        "win_levels": win_levels,
        "logs": logs,
    }

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_episode(result):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, f"v3_{result['game_id']}.jsonl")
    with open(fpath, "w", encoding="utf-8") as f:
        for row in result["logs"]:
            safe = {k: (v if isinstance(v, (int, float, bool, type(None))) else str(v)) for k, v in row.items()}
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")

def save_summary(results):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, "summary_v3.csv")
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        fields = ["game_id","steps","status","unique_states","action_entropy",
                  "best_progress","max_levels","win_levels","action_counts"]
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
                "action_counts": json.dumps(r["action_counts"]),
            })
    return fpath

def main():
    arcade = Arcade()
    envs = arcade.get_environments()
    game_ids = [e.game_id for e in envs]
    print(f"Found {len(game_ids)} public games (DGM-lite v3 Progress-Aware).")
    results = []
    for gid in game_ids:
        print(f"v3 {gid[:20]}...", end=" ", flush=True)
        r = run_game(gid)
        save_episode(r)
        results.append(r)
        print(f"steps={r['steps']} states={r['unique_states']} progress={r['best_progress']:.4f} {r['status']}")
    p = save_summary(results)
    print(f"\nSummary saved: {p}")
    return results

if __name__ == "__main__":
    main()
