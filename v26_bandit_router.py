#!/usr/bin/env python3
"""
v26 Bandit Router — UCB1 Bandit over ARC-AGI-3 Action Set

Strategic correction from SENHOR @ZANSUED:
- Build Layer 1 only: UCB1 bandit over the action set
- No trajectory transfer, no HeuristicBFS, no Spectral Embeddings
- Train on SMOKE_GAMES (r11l, sp80, bp35), eval on all 25 games
- Every phase must output a working Python file and a real execution run
- Reward: 1 if level completed, 0 otherwise
- max_actions = 500 per game

Author: @ZANSUED
Date: 2026-06-08
"""

import csv
import hashlib
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction, GameState

# ──────────────────────────────────────────────
# ARCADE MANAGER (singleton, OFFLINE mode)
# ──────────────────────────────────────────────
_ARC_MANAGER = None
_GAME_ENV_CACHE = {}

def get_arcade_manager():
    global _ARC_MANAGER
    if _ARC_MANAGER is None:
        _ARC_MANAGER = Arcade(
            environments_dir="environment_files",
            operation_mode="offline",
        )
    return _ARC_MANAGER

def resolve_game_id(short_id):
    """Resolve short game ID (e.g. 'bp35') to full env ID with version hash."""
    if short_id not in _GAME_ENV_CACHE:
        mgr = get_arcade_manager()
        for env in mgr.get_environments():
            if env.game_id.startswith(short_id):
                _GAME_ENV_CACHE[short_id] = env.game_id
                break
        if short_id not in _GAME_ENV_CACHE:
            _GAME_ENV_CACHE[short_id] = short_id
    return _GAME_ENV_CACHE[short_id]

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
MAX_STEPS = 500
OUT_DIR = "arc_runs"

# UCB1 parameters
INITIAL_Q = 0.0
UCB_C = 1.5
WARMUP_ROUNDS = 5
WARMUP_GAMES = ["r11l", "sp80", "bp35"]
EPSILON_GREEDY = 0.15

FULL_GAMES = [
    "sk48", "bp35", "tn36", "wa30", "vc33", "tu93", "tr87", "su15", "sp80",
    "sc25", "sb26", "s5i5", "re86", "r11l", "m0r0", "ls20", "lp85", "lf52",
    "ka59", "g50t", "ft09", "dc22", "cd82", "ar25", "cn04",
]

# ACTION6 click points (64x64 grid)
ACTION6_POINTS = [
    (32, 32),  (16, 16), (48, 48), (16, 48), (48, 16),
    (8, 32), (56, 32), (32, 8), (32, 56),
]

# ──────────────────────────────────────────────
# UTILITY
# ──────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def frame_hash(arr):
    if arr is None:
        return ""
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def extract_frame_as_array(obs):
    """Extract frame as numpy array from observation."""
    if obs is None:
        return None
    if hasattr(obs, "frame"):
        arr = np.asarray(obs.frame)
        return arr.squeeze() if arr.ndim > 2 else arr
    return None

def safe_state(obs):
    if obs is None:
        return "UNKNOWN"
    s = getattr(obs, "state", None)
    return str(s) if s is not None else "UNKNOWN"

def safe_levels(obs):
    if obs is None:
        return 0
    return int(getattr(obs, "levels_completed", 0) or 0)

def safe_win(obs):
    if obs is None:
        return 0
    return int(getattr(obs, "win_levels", 0) or 0)

def safe_avail(obs):
    if obs is None:
        return []
    return list(getattr(obs, "available_actions", []) or [])

def count_changed_pixels(prev, curr):
    if prev is None or curr is None:
        return 0
    try:
        a = np.asarray(prev, dtype=np.int32).squeeze()
        b = np.asarray(curr, dtype=np.int32).squeeze()
        if a.shape != b.shape:
            return -1
        return int(np.sum(a != b))
    except Exception:
        return -1

def action_name(a_id):
    """Get action name from id."""
    if a_id == 6:
        return "ACTION6_CLICK"
    try:
        return GameAction(a_id).name
    except Exception:
        return f"ACTION{a_id}"

def get_action_enum(a_id):
    """Get GameAction enum from action id."""
    try:
        return GameAction(a_id)
    except Exception:
        return GameAction(0)  # RESET as fallback

def get_action6_coords(step_count):
    return ACTION6_POINTS[step_count % len(ACTION6_POINTS)]

# ──────────────────────────────────────────────
# UCB1 BANDIT
# ──────────────────────────────────────────────

class UCBBandit:
    """
    UCB1 Multi-Armed Bandit over action IDs (0-12).
    Reward = 1 if level completed, 0 otherwise.
    """
    
    def __init__(self, n_actions=13, c=1.5, initial_q=0.0):
        self.n_actions = n_actions
        self.c = c
        self.counts = np.zeros(n_actions, dtype=np.float64)
        self.rewards = np.zeros(n_actions, dtype=np.float64)
        self.q_values = np.full(n_actions, initial_q, dtype=np.float64)
        self.total_steps = 0
        self.last_action_id = None
        self.levels_completed_total = 0
        self.action_counts = defaultdict(int)
        self.action_successes = defaultdict(int)
    
    def select_action(self, available_action_ids, epsilon=0.0):
        """UCB1 selection with epsilon-greedy fallback."""
        if not available_action_ids:
            return 0
        
        if random.random() < epsilon:
            return random.choice(available_action_ids)
        
        n_total = max(self.total_steps, 1)
        best_action = None
        best_ucb = -float('inf')
        
        for a_id in available_action_ids:
            n_a = max(self.counts[a_id], 1e-10)
            q_a = self.q_values[a_id]
            ucb = q_a + self.c * math.sqrt(math.log(n_total) / n_a)
            if ucb > best_ucb:
                best_ucb = ucb
                best_action = a_id
        
        self.last_action_id = best_action
        return best_action
    
    def observe_reward(self, levels_completed_before, levels_completed_after):
        """Observe reward: 1 if level count increased, 0 otherwise."""
        action_id = self.last_action_id
        if action_id is None:
            return
        
        reward = 1.0 if levels_completed_after > levels_completed_before else 0.0
        
        self.counts[action_id] += 1
        self.rewards[action_id] += reward
        self.total_steps += 1
        self.levels_completed_total = max(self.levels_completed_total, levels_completed_after)
        self.q_values[action_id] = self.rewards[action_id] / self.counts[action_id]
        self.action_counts[action_id] += 1
        if reward > 0:
            self.action_successes[action_id] += 1
    
    def get_stats(self):
        return {
            "total_steps": self.total_steps,
            "levels_completed": self.levels_completed_total,
            "action_counts": {str(k): int(v) for k, v in sorted(self.action_counts.items())},
            "action_successes": {str(k): int(v) for k, v in sorted(self.action_successes.items())},
            "q_values": {str(i): round(float(self.q_values[i]), 4) for i in range(self.n_actions)},
        }
    
    def get_action_distribution(self):
        total = max(sum(self.action_counts.values()), 1)
        dist = {}
        for a_id in range(self.n_actions):
            if self.action_counts[a_id] > 0:
                dist[f"ACTION{a_id}"] = round(self.action_counts[a_id] / total, 4)
        return dist
    
    def reset_game(self):
        self.last_action_id = None
        self.levels_completed_total = 0

# ──────────────────────────────────────────────
# GAME RUNNER (using EnvironmentWrapper API)
# ──────────────────────────────────────────────

def run_game(game_id, bandit, max_steps=MAX_STEPS, epsilon=EPSILON_GREEDY,
             warmup=False, out_dir=OUT_DIR):
    """
    Run one game with bandit-guided action selection.
    Uses EnvironmentWrapper API: game.observation_space, game.step().
    """
    ensure_dir(out_dir)
    effective_epsilon = 0.5 if warmup else epsilon
    
    try:
        mgr = get_arcade_manager()
        full_game_id = resolve_game_id(game_id)
        game = mgr.make(full_game_id, save_recording=False, include_frame_data=True)
        if game is None:
            raise RuntimeError(f"Arcade.make returned None for {full_game_id}")
    except Exception as e:
        print(f"  [ERROR] Failed to load game {game_id}: {e}", flush=True)
        return [], {"game_id": game_id, "status": "LOAD_ERROR", "steps": 0,
                     "unique_states": 0, "levels_completed": 0, "win_levels": 0}
    
    logs = []
    seen_hashes = set()
    bandit.reset_game()
    
    for step_idx in range(max_steps):
        obs = game.observation_space
        if obs is None:
            break
        
        frame_arr = extract_frame_as_array(obs)
        state_hash = frame_hash(frame_arr)
        current_state = safe_state(obs)
        levels_before = safe_levels(obs)
        win_levels = safe_win(obs)
        avail = safe_avail(obs)
        
        seen_hashes.add(state_hash)
        
        # Select action via bandit
        action_id = bandit.select_action(avail, epsilon=effective_epsilon)
        
        # Execute step (pass raw action int directly — arcengine accepts it)
        if action_id == 6:
            x, y = get_action6_coords(step_idx)
            result_obs = game.step(action_id, data={'x': x, 'y': y})
        else:
            result_obs = game.step(action_id)
        
        # Get new observation after step
        obs_after = result_obs if result_obs is not None else game.observation_space
        levels_after = safe_levels(obs_after)
        state_after = safe_state(obs_after)
        
        # Count changed pixels
        frame_after = extract_frame_as_array(obs_after)
        changed_pixels = count_changed_pixels(frame_arr, frame_after)
        
        # Update bandit
        bandit.observe_reward(levels_before, levels_after)
        levels_before = levels_after
        win_levels = max(win_levels, safe_win(obs_after))
        
        # Log
        log_entry = {
            "step": step_idx,
            "action_id": action_id,
            "action_name": action_name(action_id),
            "state_hash": state_hash,
            "state": state_after,
            "changed_pixels": changed_pixels,
            "levels_completed": levels_after,
            "win_levels": win_levels,
            "unique_states": len(seen_hashes),
            "epsilon": effective_epsilon,
        }
        logs.append(log_entry)
        
        # Terminal check
        if "WIN" in state_after.upper() or "FAIL" in state_after.upper():
            break
    
    
    # Summary
    total_steps = len(logs)
    unique_states = len(seen_hashes)
    zero_delta_count = sum(1 for l in logs if l.get("changed_pixels", -1) == 0)
    zero_delta_rate = zero_delta_count / max(1, total_steps)
    max_levels = max((l.get("levels_completed", 0) for l in logs), default=0)
    win_final = max((l.get("win_levels", 0) for l in logs), default=0)
    status = safe_state(game.observation_space) if game.observation_space else "UNKNOWN"
    early_stag = 1 if unique_states < 30 else 0
    
    summary = {
        "game_id": game_id,
        "status": status,
        "steps": total_steps,
        "unique_states": unique_states,
        "zero_delta_rate": round(zero_delta_rate, 4),
        "max_levels_completed": max_levels,
        "win_levels": win_final,
        "early_stagnation": early_stag,
        "epsilon": effective_epsilon,
    }
    
    # Save logs
    safe_id = game_id.replace("/", "_")
    log_path = os.path.join(out_dir, f"v26_bandit_{safe_id}.jsonl")
    with open(log_path, "w") as f:
        for entry in logs:
            json.dump(entry, f)
            f.write(chr(10))
    
    print(f"    → {status:8s} | states={unique_states:3d} | "
          f"levels={max_levels}/{win_final} | zd={zero_delta_rate:.2%} | early_stag={early_stag}", flush=True)
    
    return logs, summary

# ──────────────────────────────────────────────
# BENCHMARK
# ──────────────────────────────────────────────

def run_warmup(bandit, games=None, rounds=WARMUP_ROUNDS, out_dir=OUT_DIR):
    if games is None:
        games = WARMUP_GAMES
    print(f"\n{'='*60}")
    print(f"v26 WARMUP — {rounds} rounds each on {games}")
    print(f"{'='*60}")
    all_results = []
    for rnd in range(rounds):
        for gid in games:
            print(f"  Warmup round {rnd+1}/{rounds}: {gid}...", flush=True)
            logs, summary = run_game(gid, bandit, warmup=True, out_dir=out_dir)
            all_results.append(summary)
    csv_path = os.path.join(out_dir, "v26_warmup.csv")
    with open(csv_path, "w", newline="") as f:
        if all_results:
            w = csv.DictWriter(f, fieldnames=list(all_results[0].keys()))
            w.writeheader()
            w.writerows(all_results)
    return all_results

def run_benchmark(bandit, games=None, out_dir=OUT_DIR):
    if games is None:
        games = FULL_GAMES
    print(f"\n{'='*60}")
    print(f"v26 FULL BENCHMARK — {len(games)} games, UCB1 C={UCB_C}")
    print(f"{'='*60}")
    results = []
    for gid in games:
        print(f"  [v26_bandit] {gid}...", flush=True)
        logs, summary = run_game(gid, bandit, out_dir=out_dir)
        results.append(summary)
    csv_path = os.path.join(out_dir, "v26_summary.csv")
    with open(csv_path, "w", newline="") as f:
        if results:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
    return results

def print_final_report(results, bandit):
    print(f"\n{'='*60}")
    print("v26 BANDIT ROUTER — FINAL REPORT")
    print(f"{'='*60}")
    for r in results:
        print(f"{r['game_id']:15s} {r['status']:8s} | states={r['unique_states']:3d} | levels={r['max_levels_completed']}/{r['win_levels']} | early_stag={r['early_stagnation']}")
    
    completed = [r for r in results if r['status'] not in ('LOAD_ERROR',)]
    avg_states = sum(r['unique_states'] for r in completed) / max(1, len(completed))
    avg_zd = sum(r['zero_delta_rate'] for r in completed) / max(1, len(completed))
    early_stag_count = sum(r['early_stagnation'] for r in completed)
    games_with_levels = [r for r in completed if r['win_levels'] > 0]
    lev_done = sum(r['max_levels_completed'] for r in games_with_levels)
    lev_total = sum(r['win_levels'] for r in games_with_levels)
    
    print(f"\n{'─'*60}")
    print("SUMMARY")
    print(f"{'─'*60}")
    print(f"Games: {len(completed)}")
    print(f"Avg states: {avg_states:.1f}")
    print(f"Zero-delta: {avg_zd:.2%}")
    print(f"Early stagnation: {early_stag_count}/{len(completed)}")
    print(f"Levels completed: {lev_done}/{lev_total} ({lev_done/max(1,lev_total):.2%})")
    print(f"Total bandit steps: {bandit.total_steps}")
    
    print(f"\n{'─'*60}")
    print("ACTION DISTRIBUTION")
    print(f"{'─'*60}")
    action_dist = bandit.get_action_distribution()
    for a_name, pct in sorted(action_dist.items()):
        aid = int(a_name.replace('ACTION', ''))
        cnt = bandit.action_counts[aid]
        succ = bandit.action_successes[aid]
        qv = bandit.q_values[aid]
        print(f"  {a_name:15s} | count={cnt:4d} | success={succ:3d} | Q={qv:.4f} | pct={pct:.2%}")
    
    print(f"\nQ-VALUE RANKING:")
    ranked = sorted([(i, bandit.q_values[i]) for i in range(bandit.n_actions)], key=lambda x: -x[1])
    for aid, qv in ranked:
        cnt = bandit.action_counts[aid]
        print(f"  ACTION{aid}: Q={qv:.4f} (picked {cnt} times)")

# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    timestamp = now_iso().replace(":", "-").replace("T", "_")
    print(f"v26 Bandit Router — {timestamp}")
    print(f"UCB1 C={UCB_C}, epsilon={EPSILON_GREEDY}, warmup_rounds={WARMUP_ROUNDS}")
    
    bandit = UCBBandit(n_actions=13, c=UCB_C, initial_q=INITIAL_Q)
    
    # Phase 1: Warmup
    warmup_results = run_warmup(bandit, rounds=WARMUP_ROUNDS)
    
    print(f"\nWarmup complete. Q-values:")
    for i in range(bandit.n_actions):
        print(f"  ACTION{i}: Q={bandit.q_values[i]:.4f} (picked {int(bandit.counts[i])} times)")
    
    # Phase 2: Full benchmark
    results = run_benchmark(bandit, games=FULL_GAMES)
    
    # Phase 3: Report
    print_final_report(results, bandit)
    
    print(f"\nLogs: {OUT_DIR}/v26_bandit_*.jsonl")
    print(f"Summary: {OUT_DIR}/v26_summary.csv")
