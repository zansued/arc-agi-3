#!/usr/bin/env python3
"""
ARC-AGI-3 Random Baseline — mesma estrutura do DGM-lite, política aleatória.
"""
import os, json, csv, random, hashlib
from datetime import datetime, timezone
import numpy as np
from arc_agi import Arcade
from arcengine import GameAction

MAX_STEPS = 500
OUT_DIR = "arc_runs"

def ensure_dir(path): os.makedirs(path, exist_ok=True)

def frame_hash(obs):
    return hashlib.md5(np.asarray(obs, dtype=np.int32).tobytes()).hexdigest()

def count_changed_pixels(prev, obs):
    if prev is None or obs is None: return 0
    try:
        a = np.asarray(prev, dtype=np.int32)
        b = np.asarray(obs, dtype=np.int32)
        if a.shape != b.shape: return -1
        return int(np.sum(a != b))
    except Exception: return -1

def safe_get_obs(game):
    raw = getattr(game, "observation_space", None) or getattr(game, "observation", None)
    if raw is None: return np.zeros((64, 64), dtype=np.int32)
    if hasattr(raw, "frame"):
        arr = np.asarray(raw.frame, dtype=np.int32)
        if arr.ndim == 3: arr = arr[0]
        return arr
    if hasattr(raw, "grid"): return np.asarray(raw.grid, dtype=np.int32)
    return np.asarray(raw, dtype=np.int32).squeeze()

def safe_get_info(game):
    info = getattr(game, "info", {})
    if hasattr(info, "model_dump"): info = info.model_dump()
    return info or {}

def get_available_actions(game, info):
    actions = info.get("available_actions") if isinstance(info, dict) else None
    if actions is None:
        raw = getattr(game, "observation_space", None)
        if raw is not None and hasattr(raw, "available_actions"):
            acts = raw.available_actions
            if acts is not None and len(acts) > 0: actions = acts
    if actions is None:
        aspace = getattr(game, "action_space", None)
        if hasattr(aspace, "n"): actions = list(range(aspace.n))
        elif isinstance(aspace, (list, tuple, set)): actions = list(aspace)
    if actions is None: actions = list(range(6))
    return list(actions)

def random_action(obs, info, avail):
    """Política aleatória pura"""
    return random.choice(avail) if avail else 0

def run_game_random(game_id, max_steps=MAX_STEPS):
    game = Arcade().make(game_id)
    try: game.reset()
    except: pass
    import time as _t; _t.sleep(0.1)
    obs, info = safe_get_obs(game), safe_get_info(game)
    logs = []
    start_score = info.get("score") if isinstance(info, dict) else None
    final_score = start_score
    status = "running"
    visited = set()
    action_counts = {}
    zero_delta_steps = 0
    stuck_steps = 0
    last_hash = None
    for step_idx in range(max_steps):
        avail = get_available_actions(game, info)
        action = random_action(obs, info, avail)
        # Convert to GameAction
        if isinstance(action, int):
            step_action = GameAction.from_id(action)
            step_data = {'x': random.randint(0, 63), 'y': random.randint(0, 63)} if action == 6 else None
        else:
            step_action = action
            step_data = None
        before_hash = frame_hash(obs)
        try:
            if step_data:
                result = game.step(step_action, data=step_data)
            else:
                result = game.step(step_action)
        except Exception as e:
            status = f"error: {type(e).__name__}: {e}"
            break
        # normalize
        if isinstance(result, tuple):
            if len(result) == 5:
                new_obs, reward, terminated, truncated, new_info = result
            elif len(result) == 4:
                new_obs, reward, done, new_info = result
                terminated = bool(done)
            elif len(result) >= 1:
                new_obs = result[0]
                new_info = safe_get_info(game)
                terminated, truncated = False, False
            else:
                new_obs = safe_get_obs(game)
                new_info = safe_get_info(game)
                terminated, truncated = False, False
        else:
            new_obs = safe_get_obs(game)
            new_info = safe_get_info(game)
            terminated, truncated = False, False
        new_obs = np.asarray(new_obs, dtype=np.int32) if new_obs is not None else safe_get_obs(game)
        changed = count_changed_pixels(obs, new_obs)
        after_hash = frame_hash(new_obs)
        is_new_state = after_hash not in visited
        visited.add(after_hash)
        if changed == 0: zero_delta_steps += 1
        if last_hash == after_hash: stuck_steps += 1
        last_hash = after_hash
        s = str(action)
        action_counts[s] = action_counts.get(s, 0) + 1
        if isinstance(new_info, dict):
            final_score = new_info.get("score", final_score)
        log = {
            "game_id": game_id,
            "step": step_idx,
            "action": str(action),
            "family": "RandomBaseline",
            "changed_pixels": changed,
            "score_before": final_score,
            "score_after": final_score,
            "before_hash": before_hash,
            "after_hash": after_hash,
            "is_new_state": is_new_state,
            "unique_states": len(visited),
            "stagnation": stuck_steps,
            "available_actions": [str(a) for a in avail],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logs.append(log)
        obs = new_obs
        info = new_info
        if terminated or truncated:
            status = "terminated" if terminated else "truncated"
            break
    total_actions = sum(action_counts.values())
    action_entropy = 0.0
    if total_actions > 0:
        for c in action_counts.values():
            p = c / total_actions
            if p > 0: action_entropy -= p * np.log2(p)
    return {
        "game_id": game_id,
        "steps": len(logs),
        "start_score": start_score,
        "final_score": final_score,
        "status": status,
        "unique_states": len(visited),
        "action_counts": action_counts,
        "action_entropy": round(action_entropy, 3),
        "zero_delta_steps": zero_delta_steps,
        "stuck_steps": stuck_steps,
        "logs": logs,
    }

def save_episode(result):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, f"random_{result['game_id']}.jsonl")
    with open(fpath, "w", encoding="utf-8") as f:
        for row in result["logs"]:
            safe = {k: (v if isinstance(v, (int, float, bool, type(None))) else str(v)) for k, v in row.items()}
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")

def save_summary(results):
    ensure_dir(OUT_DIR)
    fpath = os.path.join(OUT_DIR, "random_summary.csv")
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        fields = ["game_id","steps","start_score","final_score","status","unique_states","action_entropy","zero_delta_steps","stuck_steps","action_counts"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({
                "game_id": r["game_id"], "steps": r["steps"],
                "start_score": r["start_score"], "final_score": r["final_score"],
                "status": r["status"], "unique_states": r["unique_states"],
                "action_entropy": r["action_entropy"],
                "zero_delta_steps": r["zero_delta_steps"],
                "stuck_steps": r["stuck_steps"],
                "action_counts": json.dumps(r["action_counts"]),
            })
    return fpath

def main():
    arcade = Arcade()
    game_ids = [e.game_id for e in arcade.get_environments()]
    print(f"Found {len(game_ids)} public games (random baseline).")
    results = []
    for gid in game_ids:
        print(f"Random {gid[:20]}...", end=" ", flush=True)
        r = run_game_random(gid)
        save_episode(r)
        results.append(r)
        print(f"steps={r['steps']} states={r['unique_states']} entr={r['action_entropy']} stuck={r['stuck_steps']} {r['status']}")
    p = save_summary(results)
    print(f"\nRandom baseline summary saved: {p}")
    return results

if __name__ == "__main__":
    main()
