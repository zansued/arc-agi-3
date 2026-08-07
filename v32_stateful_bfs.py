#!/usr/bin/env python3
"""
v32_stateful_bfs — Stateful BFS solver for ARC-AGI-3.

Base: v28_level_reward_shaping (confirmed working — 2 levels, sp80/cn04).
Additions over v28 base:
  1. State deduplication: canonical state set per game.
  2. Persistent state cache: per-game archive_dir (v30 mechanism) saves/loads state cache.
Removed: archive replay, hybrid dispatch, branching logic.
"""

import csv
import hashlib
import json
import math
import os
import random
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction

# ── Configuration ───────────────────────────────────────────────────────────
MAX_STEPS = 500
OUT_DIR = 'arc_runs'
OUT_DIR_P = Path(OUT_DIR)
MAX_PLY = 100
SMOKE_GAMES = ['tn36', 'sp80', 'bp35', 'cn04']
FULL_GAMES = [
    'sk48', 'bp35', 'tn36', 'wa30', 'vc33', 'tu93', 'tr87', 'su15', 'sp80',
    'sc25', 'sb26', 's5i5', 're86', 'r11l', 'm0r0', 'ls20', 'lp85', 'lf52',
    'ka59', 'g50t', 'ft09', 'dc22', 'cd82', 'ar25', 'cn04',
]
STATE_CACHE_DIR = os.path.join(OUT_DIR, 'v32_state_cache')

# ── Utilities (from v28) ────────────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def frame_hash(arr):
    if arr is None:
        return ''
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def extract_frame(raw):
    if raw is None:
        return None
    if isinstance(raw, np.ndarray):
        return raw.squeeze() if raw.ndim > 2 else raw
    if hasattr(raw, 'frame'):
        arr = np.asarray(raw.frame, dtype=np.int32)
        if arr.ndim == 3:
            arr = arr[0]
        return arr
    if hasattr(raw, 'grid'):
        return np.asarray(raw.grid, dtype=np.int32)
    return None

def safe_state(raw):
    s = getattr(raw, 'state', None)
    return str(s) if s is not None else 'UNKNOWN'

def safe_levels(raw):
    return int(getattr(raw, 'levels_completed', 0) or 0)

def safe_win(raw):
    return int(getattr(raw, 'win_levels', 0) or 0)

def is_win(state_str):
    return 'WIN' in state_str.upper()

def is_fail(state_str):
    return 'FAIL' in state_str.upper()

def is_game_over(state_str):
    s = state_str.upper()
    return 'WIN' in s or 'FAIL' in s or 'GAME_OVER' in s

def safe_info(game):
    info = getattr(game, 'info', {})
    if hasattr(info, 'model_dump'):
        info = info.model_dump()
    return info or {}

def to_game_action(action):
    if isinstance(action, GameAction):
        return action
    if isinstance(action, str):
        name = action.split('.')[-1]
        if name in GameAction.__members__:
            return GameAction[name]
        return GameAction.RESET
    try:
        value = int(getattr(action, 'value', action))
        return GameAction.from_id(value)
    except Exception:
        return GameAction.RESET

def action_name(action):
    if hasattr(action, 'name'):
        return action.name
    return str(action)

def get_available_actions(game, info):
    actions = None
    if isinstance(info, dict):
        actions = info.get('available_actions')
    if actions is None:
        raw = getattr(game, 'observation_space', None)
        if raw is not None and hasattr(raw, 'available_actions'):
            raw_actions = raw.available_actions
            if raw_actions:
                actions = raw_actions
    if actions is None:
        aspace = getattr(game, 'action_space', None)
        if hasattr(aspace, 'n'):
            actions = list(range(aspace.n))
        elif isinstance(aspace, (list, tuple, set)):
            actions = list(aspace)
    if actions is None:
        actions = list(range(1, 8))
    safe = []
    for raw_action in list(actions):
        ga = to_game_action(raw_action)
        if action_name(ga) == 'ACTION6':
            continue
        safe.append(ga)
    return safe or [GameAction.RESET]

def step_game(game, action, data=None, reasoning=None):
    raw_before = getattr(game, 'observation_space', None)
    frame_before = extract_frame(raw_before)
    try:
        if data is not None:
            raw_after = game.step(action, data=data, reasoning=reasoning)
        else:
            raw_after = game.step(action, reasoning=reasoning)
        crashed = False
        error = None
    except Exception as exc:
        raw_after = getattr(game, 'observation_space', None)
        crashed = True
        error = f'{type(exc).__name__}: {exc}'
    if raw_after is None:
        raw_after = getattr(game, 'observation_space', None)
    frame_after = extract_frame(raw_after)
    levels_before = safe_levels(raw_before)
    levels_after = safe_levels(raw_after)
    win_lvls = safe_win(raw_after) or safe_win(raw_before)
    state_str = safe_state(raw_after)
    return {
        'raw': raw_after,
        'frame': frame_after,
        'state': state_str,
        'levels_completed': levels_after,
        'win_levels': win_lvls,
        'delta_levels': max(0, levels_after - levels_before),
        'changed_pixels': int(np.sum(np.asarray(frame_before, dtype=np.int32) != np.asarray(frame_after, dtype=np.int32))) if (frame_before is not None and frame_after is not None and np.asarray(frame_before, dtype=np.int32).shape == np.asarray(frame_after, dtype=np.int32).shape) else 0,
        'crashed': crashed,
        'error': error,
    }

# ── State Cache (persistent per game — archive_dir mechanism from v30) ──

def load_state_cache(game_id: str) -> set:
    """Load persisted discovered-state hashes for a game (v30 archive_dir mechanism)."""
    ensure_dir(STATE_CACHE_DIR)
    cache_path = os.path.join(STATE_CACHE_DIR, f'{game_id}_states.json')
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            return set(data.get('visited_hashes', []))
        except Exception:
            return set()
    return set()

def save_state_cache(game_id: str, visited_hashes: set):
    """Save discovered-state hashes for a game (v30 archive_dir mechanism)."""
    ensure_dir(STATE_CACHE_DIR)
    cache_path = os.path.join(STATE_CACHE_DIR, f'{game_id}_states.json')
    try:
        with open(cache_path, 'w') as f:
            json.dump({'game_id': game_id, 'visited_hashes': list(visited_hashes)}, f)
    except Exception:
        pass

# ── BFS Solver (stateful, no archive replay) ──

def bfs_solve_game(game_id: str, max_steps: int = MAX_STEPS, max_ply: int = MAX_PLY) -> dict:
    """BFS solver using v28's step_game + deepcopy snapshots.
    
    Changes from v28 replay-based:
      - No PolicyArchiveRouter / MinimalVisitedArchive / archive replay
      - State deduplication via visited_states set (canonical state strings)
      - Persistent state cache (archive_dir mechanism from v30)
    """
    ensure_dir(OUT_DIR_P)
    
    # Log file
    log_path = os.path.join(OUT_DIR, f'v32_stateful_bfs_{game_id}.jsonl')
    
    # Persistent state cache — load prior discoveries (v30 archive_dir mechanism)
    state_cache = load_state_cache(game_id)
    
    # Seed for reproducibility
    seed = int(hashlib.md5(f'v32_stateful:{game_id}'.encode('utf-8')).hexdigest()[:8], 16)
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)
    
    # Initialize game
    arcade = Arcade()
    game_env = arcade.make(game_id)
    if game_env is None:
        return {
            'game_id': game_id, 'status': 'ERROR',
            'error': 'Arcade.make returned None',
            'levels_completed': 0, 'unique_states': 0, 'nodes_expanded': 0,
        }
    
    try:
        game_env.reset()
    except Exception:
        pass
    
    raw = getattr(game_env, 'observation_space', None)
    frame = extract_frame(raw)
    init_hash = frame_hash(frame)
    init_levels = safe_levels(raw)
    win_levels = safe_win(raw)
    state_str = safe_state(raw)
    info = safe_info(game_env)
    avail = get_available_actions(game_env, info)
    
    # State deduplication: set of canonical state strings (hash) per game
    visited_states: set = set(state_cache) if state_cache else set()
    visited_states.add(init_hash)
    
    # Frontier: queue of (game_env_snapshot, state_hash, action_seq_tuple, depth, levels_completed)
    # We use snapshot wrappers via copied game state (re-reset + replay)
    # Alternative: deepcopy the wrapper directly
    front_nodes = []
    
    # First, populate the initial frontier with all available actions from initial state
    for act in avail:
        act_id = int(getattr(act, 'value', 0))
        front_nodes.append({
            'action_seq': (act_id,),
            'depth': 0,
            'levels_before': init_levels,
            'state_hash_before': init_hash,
        })
    
    total_actions = 0
    nodes_expanded = 0
    best_levels = init_levels
    best_state_hash = init_hash
    best_action_seq = ()
    levels_progress_events = 0
    failed_expansions = 0
    error_msg = None
    
    with open(log_path, 'w', encoding='utf-8') as log_handle:
        log_handle.write(json.dumps({
            'event': 'start',
            'version': 'v32_stateful_bfs',
            'game': game_id,
            'timestamp': now_iso(),
            'max_steps': max_steps,
            'max_ply': max_ply,
            'init_hash': init_hash,
            'init_levels': init_levels,
            'state_cache_size': len(state_cache),
            'initial_frontier': len(front_nodes),
        }) + '\n')
        log_handle.flush()
        
        while front_nodes and total_actions < max_steps:
            # Pop from frontier (FIFO for BFS)
            node = front_nodes.pop(0)
            action_seq = node['action_seq']
            
            # Execute: reset game, replay sequence, then step one more action
            # First, check if we need to reset and replay
            success = True
            current_levels = init_levels
            try:
                game_env.reset()
                raw = getattr(game_env, 'observation_space', None)
            except Exception as exc:
                failed_expansions += 1
                log_handle.write(json.dumps({
                    'event': 'reset_error',
                    'error': str(exc),
                }) + '\n')
                continue
            
            # Replay the action sequence
            replay_ok = True
            for act_id in action_seq[:-1]:  # all but last action
                action = GameAction.from_id(act_id)
                try:
                    result = game_env.step(action, reasoning='v32_replay')
                except Exception:
                    replay_ok = False
                    break
                if result is None:
                    replay_ok = False
                    break
                raw = getattr(game_env, 'observation_space', None)
                current_levels = safe_levels(raw)
            
            if not replay_ok:
                failed_expansions += 1
                continue
            
            # Now step the final action (the new action for this frontier expansion)
            last_act_id = action_seq[-1]
            last_action = GameAction.from_id(last_act_id)
            
            result = step_game(game_env, last_action)
            total_actions += 1
            nodes_expanded += 1
            
            if result['crashed']:
                failed_expansions += 1
                log_handle.write(json.dumps({
                    'event': 'crash',
                    'action': action_name(last_action),
                    'action_seq': str(action_seq),
                    'error': result['error'],
                }) + '\n')
                continue
            
            new_raw = result['raw']
            new_frame = result['frame']
            new_hash = frame_hash(new_frame)
            new_levels = result['levels_completed']
            new_state_str = result['state']
            
            # Track progress
            if new_levels > best_levels:
                best_levels = new_levels
                best_state_hash = new_hash
                best_action_seq = action_seq
                levels_progress_events += 1
                log_handle.write(json.dumps({
                    'event': 'level_progress',
                    'step': total_actions,
                    'action_seq': str(action_seq),
                    'levels_completed': new_levels,
                    'hash': new_hash,
                }) + '\n')
            
            # State deduplication via canonical state strings (hash per game)
            is_new = new_hash not in visited_states
            if is_new:
                visited_states.add(new_hash)
                log_handle.write(json.dumps({
                    'event': 'new_state',
                    'step': total_actions,
                    'hash': new_hash,
                    'action_seq': str(action_seq),
                    'levels_completed': new_levels,
                    'visited_count': len(visited_states),
                }) + '\n')
                
                # Expand only if not terminal and within depth limit
                depth = len(action_seq)
                if depth < max_ply and not is_game_over(new_state_str):
                    raw_after = new_raw
                    info_after = safe_info(game_env)
                    new_avail = get_available_actions(game_env, info)
                    for next_act in new_avail:
                        next_act_id = int(getattr(next_act, 'value', 0))
                        if total_actions + sum(len(n['action_seq']) for n in front_nodes) >= max_steps:
                            break
                        front_nodes.append({
                            'action_seq': action_seq + (next_act_id,),
                            'depth': depth + 1,
                            'levels_before': new_levels,
                            'state_hash_before': new_hash,
                        })
            else:
                log_handle.write(json.dumps({
                    'event': 'duplicate_state',
                    'step': total_actions,
                    'hash': new_hash,
                }) + '\n')
        
        log_handle.write(json.dumps({'event': 'complete', 'total_actions': total_actions}) + '\n')
    
    # Save persistent state cache (v30 archive_dir mechanism)
    save_state_cache(game_id, visited_states)
    
    return {
        'game_id': game_id,
        'status': 'OK',
        'levels_completed': int(best_levels),
        'unique_states': int(len(visited_states)),
        'nodes_expanded': int(nodes_expanded),
        'total_actions': int(total_actions),
        'best_action_seq': str(best_action_seq),
        'best_state_hash': best_state_hash,
        'level_progress_events': int(levels_progress_events),
        'failed_expansions': int(failed_expansions),
        'frontier_remaining': int(len(front_nodes)),
        'state_cache_size': int(len(state_cache)),
        'error': error_msg,
    }


# ── Runner ──

def run_benchmark(game_list: list[str]) -> list[dict]:
    ensure_dir(OUT_DIR_P)
    all_stats = []
    for game_id in game_list:
        print(f"[{now_iso()}] Processing {game_id}...", flush=True)
        try:
            stats = bfs_solve_game(game_id)
        except Exception as e:
            import traceback
            stats = {
                'game_id': game_id,
                'status': 'ERROR',
                'error': str(e),
                'error_traceback': traceback.format_exc(),
                'levels_completed': 0,
                'unique_states': 0,
                'nodes_expanded': 0,
                'total_actions': 0,
                'best_action_seq': '',
                'best_state_hash': '',
                'level_progress_events': 0,
                'failed_expansions': 0,
                'frontier_remaining': 0,
                'state_cache_size': 0,
            }
        all_stats.append(stats)
        print(f"  -> levels={stats.get('levels_completed', '?')}, "
              f"states={stats.get('unique_states', '?')}, "
              f"nodes={stats.get('nodes_expanded', '?')}", flush=True)
    
    # Summary CSV
    summary_file = Path(OUT_DIR) / 'v32_smoke_summary.csv'
    if all_stats:
        fieldnames = list(all_stats[0].keys())
        with open(summary_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_stats)
    return all_stats


def build_smoke_report(stats_list: list[dict]) -> dict:
    """Build report with: total levels per game, total unique states per game,
    total nodes expanded per game, explicitly list which games made progress."""
    
    games_detail = []
    for s in stats_list:
        gid = s['game_id']
        levels = s.get('levels_completed', 0)
        states = s.get('unique_states', 0)
        nodes = s.get('nodes_expanded', 0)
        status = s.get('status', '?')
        err = s.get('error', None)
        has_progress = levels >= 1
        games_detail.append({
            'game': gid,
            'levels': levels,
            'unique_states': states,
            'nodes_expanded': nodes,
            'has_progress': has_progress,
            'status': status,
            'error': err,
        })
    
    games_with_progress = [g for g in games_detail if g['has_progress']]
    total_levels = sum(g['levels'] for g in games_detail)
    total_states = sum(g['unique_states'] for g in games_detail)
    total_nodes = sum(g['nodes_expanded'] for g in games_detail)
    
    report = {
        'version': 'v32_smoke_stateful_bfs',
        'games_tested': len(stats_list),
        'games_with_progress': len(games_with_progress),
        'total_levels_completed': total_levels,
        'total_unique_states': total_states,
        'total_nodes_expanded': total_nodes,
        'games_progress_list': [g['game'] for g in games_with_progress],
        'games_detail': games_detail,
        'status': 'PASS' if games_with_progress else 'FAIL',
        'timestamp': now_iso(),
    }
    return report


# ── Main ──

if __name__ == '__main__':
    if '--smoke' in sys.argv or '-s' in sys.argv:
        games_to_run = SMOKE_GAMES
    elif '--full' in sys.argv or '-f' in sys.argv:
        games_to_run = FULL_GAMES
    else:
        games_to_run = SMOKE_GAMES
    
    print('=' * 60)
    print('v32 Stateful BFS — Smoke Test')
    print(f'Games: {games_to_run}')
    print('=' * 60)
    
    stats = run_benchmark(games_to_run)
    
    print()
    print('=' * 60)
    print('SMOKE REPORT')
    print('=' * 60)
    
    report = build_smoke_report(stats)
    
    for g in report['games_detail']:
        status_str = '✅ PROGRESS' if g['has_progress'] else '❌ NO PROGRESS'
        err_str = f' | ERROR: {g["error"]}' if g['error'] else ''
        print(f"  {g['game']:15s}: levels={g['levels']:3d} | states={g['unique_states']:4d} | nodes={g['nodes_expanded']:4d} | {status_str}{err_str}")
    
    print()
    print(f"Total levels completed: {report['total_levels_completed']}")
    print(f"Total unique states: {report['total_unique_states']}")
    print(f"Total nodes expanded: {report['total_nodes_expanded']}")
    print(f"Games with progress: {report['games_progress_list'] or 'NONE'}")
    print(f"Smoke result: {report['status']}")
    
    # Save report
    ensure_dir(OUT_DIR_P)
    report_path = os.path.join(OUT_DIR, 'v32_smoke_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to {report_path}")
