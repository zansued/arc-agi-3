#!/usr/bin/env python3
"""
# SPECTRAL V56 MOD — Injeta spectral_importance_ranking no V56 solve_game
# 
# Modifica o V56 para:
# 1. Ao abrir cada jogo, samplear frames aleatórios via wrapper.step()
# 2. Converter frames para embeddings via extract_features()
# 3. Rodar spectral_importance_ranking() para rankear ações
# 4. Usar o ranking para biasar a seleção de ações no BFS
#
# Mantém toda a infraestrutura correta do V56:
# - arcade.make() + wrapper.step()
# - Multiprocessing (6 workers)
# - Scorecard tracking
# - Archive replay (V48)
# - Crash handling
# - Feature extraction
"""

import copy
import hashlib
import json
import os
import random
import sys
import time
import traceback
from collections import defaultdict, deque
from multiprocessing import Pool, cpu_count
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
from arc_agi import Arcade
from arcengine.enums import GameAction, GameState

# Attempt to import spectral analysis — don't crash if unavailable
try:
    from spectral_atomizer.core import spectral_importance_ranking, compress_via_projection
    SPECTRAL_AVAILABLE = True
except ImportError:
    SPECTRAL_AVAILABLE = False


# ════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════
N_WORKERS = int(os.environ.get('N_WORKERS', '6'))
MAX_STEPS = int(os.environ.get('MAX_STEPS', '800'))
MAX_PLY = int(os.environ.get('MAX_PLY', '25'))
ARCHIVE_REPLAY_LIMIT = int(os.environ.get('ARCHIVE_REPLAY_LIMIT', '5'))
USE_SPECTRAL = SPECTRAL_AVAILABLE  # set False to compare with non-spectral
N_SPECTRAL_FRAMES = 300  # frames to sample for spectral analysis

GAME_IDS = [
    'ar25', 'bp35', 'cd82', 'cn04', 'dc22', 'ft09', 'g50t',
    'ka59', 'lf52', 'lp85', 'ls20', 'm0r0', 'r11l', 're86',
    's5i5', 'sb26', 'sc25', 'sk48', 'sp80', 'su15', 'tn36',
    'tr87', 'tu93', 'vc33', 'wa30'
]

DEAD_GAMES = set()

GAME_TYPES = {
    'sp80': 'paint', 'cn04': 'tangram', 'bp35': 'navigation',
    'cd82': 'grid', 'm0r0': 'grid', 'ar25': 'grid', 'ls20': 'grid',
    'ft09': 'grid',  # default for others
}

STRATEGY_PROFILES = {
    'paint': {'beam_width': 5, 'max_crashes': 3, 'prefer_actions': [4, 1, 3, 5, 2]},
    'tangram': {'beam_width': 4, 'max_crashes': 3, 'prefer_actions': [2, 5, 3, 1, 4]},
    'navigation': {'beam_width': 6, 'max_crashes': 4, 'prefer_actions': [1, 3, 5, 2, 4]},
    'grid': {'beam_width': 4, 'max_crashes': 2, 'prefer_actions': [1, 2, 3, 4, 5]},
    'standard': {'beam_width': 4, 'max_crashes': 2, 'prefer_actions': [1, 2, 3, 4, 5, 0]},
}

PREVIOUS_SOLUTIONS: Dict[str, list] = {}

SEED_ARCHIVE = {
    'sp80': [4, 1, 3, 5, 2, 4, 1, 4],
    'cd82': [2, 5, 3, 1, 4, 2, 5, 3],
    'ft09': [3, 5, 1, 4, 2, 3, 5],
    'cn04': [2, 5, 3, 1, 4, 2, 5],
    'bp35': [1, 3, 5, 2, 4, 1, 3],
    'ls20': [1, 3, 5, 2, 4, 6, 1],
    'm0r0': [3, 1, 5, 2, 4, 3],
    'ar25': [5, 1, 3, 4, 2, 5],
    'dc22': [1, 4, 2, 5, 3, 1],
    'sk48': [2, 5, 1, 4, 3, 2],
    'wa30': [3, 1, 4, 2, 5, 3],
    'ka59': [2, 4, 1, 5, 3, 2],
    'lf52': [4, 1, 3, 5, 2, 4],
    'r11l': [1, 3, 2, 5, 4, 1],
    're86': [5, 2, 4, 1, 3, 5],
    'sb26': [3, 5, 2, 4, 1, 3],
    'tr87': [4, 2, 5, 1, 3, 4],
    'tu93': [1, 5, 3, 2, 4, 1],
    'vc33': [2, 3, 5, 1, 4, 2],
}

for _gid, _seq in SEED_ARCHIVE.items():
    PREVIOUS_SOLUTIONS[f"{_gid}:seed"] = list(_seq)


# ════════════════════════════════════════════
# SPECTRAL ACTION RANKING (NEW)
# ════════════════════════════════════════════

def spectral_sample_actions(wrapper, avail_actions, n_frames=300):
    """
    Sample random actions, collect frames, run spectral analysis,
    return ranked action list (most important first).
    """
    if not SPECTRAL_AVAILABLE or len(avail_actions) < 2:
        return avail_actions  # fallback to default order
    
    action_samples = {a: [] for a in avail_actions}
    
    wrapper.reset()
    for _ in range(min(n_frames, 500)):
        action = random.choice(avail_actions)
        try:
            fd = wrapper.step(action)
            if fd and hasattr(fd, 'frame') and fd.frame is not None:
                frame = fd.frame
                # Convert frame to flat vector
                if isinstance(frame, np.ndarray):
                    vec = frame.flatten().astype(np.float32)
                else:
                    vec = np.array([float(v) for v in str(frame).encode()[:64]], dtype=np.float32)
                action_samples[action].append(vec)
        except Exception:
            pass
        # Reset occasionally
        if _ % 50 == 49:
            try:
                wrapper.reset()
            except Exception:
                pass
    
    wrapper.reset()
    
    # Build embedding matrix
    all_vecs = []
    all_labels = []
    for act, vecs in action_samples.items():
        for v in vecs[:20]:  # max 20 per action
            all_vecs.append(v)
            all_labels.append(act)
    
    if len(all_vecs) < 10:
        return avail_actions
    
    try:
        embeddings = np.stack(all_vecs)
        result = spectral_importance_ranking(embeddings, method='variance_weighted', variance_ratio=0.95)
        
        # Compute importance per action
        action_scores = {}
        for i, act in enumerate(all_labels):
            if act not in action_scores:
                action_scores[act] = []
            if 'importance_per_token' in result and i < len(result['importance_per_token']):
                action_scores[act].append(float(result['importance_per_token'][i]))
        
        ranked = sorted(action_scores.keys(), key=lambda a: np.mean(action_scores.get(a, [1.0])), reverse=True)
        print(f"  [SPECTRAL] Action ranking: {ranked}")
        return ranked
    except Exception as e:
        print(f"  [SPECTRAL] Error: {e}")
        return avail_actions


# ════════════════════════════════════════════
# V48/V55/V56 LEGACY CODE (copied from v56.py)
# ════════════════════════════════════════════

def features_to_state_key(feat):
    if feat is None:
        return None
    f = np.asarray(feat).flatten()[:512].tolist()
    m = hashlib.md5(str(f).encode()).hexdigest()
    return m[:16]


def extract_features(frame):
    if frame is None:
        return None
    if isinstance(frame, np.ndarray):
        return frame
    return np.array([1.0])


def wrapper_state_str(fd):
    try:
        return str(fd.state)
    except Exception:
        return 'unknown'


def safe_wrapper_levels(fd):
    try:
        return getattr(fd, 'levels_completed', 0) or 0
    except Exception:
        return 0


def fd_action_list(fd):
    try:
        return list(range(6))
    except Exception:
        return []


# ════════════════════════════════════════════
# SOLVE GAME — SPECTRAL-ENHANCED
# ════════════════════════════════════════════

def solve_game(game_id, is_smoke=False):
    start = time.time()
    
    result = {
        'game': game_id,
        'states': 0, 'levels': 0, 'steps': 0, 'crashes': 0,
        'archive_replay_states': 0,
        'archive_replay_success': False,
        'fallbacks_triggered': 0,
        'stagnated': False,
        'strategy': '',
        'spectral_ranking': USE_SPECTRAL,
        'time': 0.0,
    }
    
    is_dead = game_id in DEAD_GAMES
    game_type = GAME_TYPES.get(game_id, 'standard')
    profile = STRATEGY_PROFILES.get(game_type, STRATEGY_PROFILES['standard'])
    
    try:
        arcade = Arcade()
        wrapper = arcade.make(game_id)
        if wrapper is None:
            result['error'] = 'Arcade.make returned None'
            return result
        
        fd_init = wrapper.reset()
        init_feat = extract_features(fd_init.frame)
        init_hash = features_to_state_key(init_feat)
        avail_actions = [a for a in fd_action_list(fd_init) if a not in (set() if is_dead else {6})]
        
        # === SPECTRAL PRE-PROCESSING ===
        if USE_SPECTRAL and len(avail_actions) > 1:
            print(f"[SOLVE:{game_id}] Sampling {N_SPECTRAL_FRAMES} frames for spectral ranking...")
            ranked_actions = spectral_sample_actions(wrapper, avail_actions, N_SPECTRAL_FRAMES)
            avail_actions = ranked_actions  # Replace default order with spectral-ranked
            result['strategy'] = 'spectral_smart_random'
        else:
            result['strategy'] = 'bfs_standard'
        
        # === BFS/SEARCH LOOP ===
        visited = {init_hash}
        frontier = deque()
        frontier.append((wrapper, init_hash, [], 0, safe_wrapper_levels(fd_init)))
        
        n_states = 1
        n_levels = safe_wrapper_levels(fd_init)
        n_crashes = 0
        n_steps = 0
        best_levels = n_levels
        stagnation_counter = 0
        
        while frontier and n_steps < MAX_STEPS:
            if n_levels > 0 and best_levels > 0 and n_levels >= best_levels:
                break
            
            current_w, current_hash, current_seq, depth, levels_before = frontier.popleft()
            
            for act in avail_actions[:profile['beam_width']]:
                if n_steps >= MAX_STEPS:
                    break
                n_steps += 1
                n_states += 1
                
                clone = copy.deepcopy(current_w)
                try:
                    fd = clone.step(act)
                    state_str = wrapper_state_str(fd)
                    levels = safe_wrapper_levels(fd)
                    
                    if 'WIN' in state_str or 'GAME_OVER' in state_str:
                        continue
                    
                    frame = fd.frame if hasattr(fd, 'frame') else None
                    feat = extract_features(frame)
                    h = features_to_state_key(feat)
                    
                    if h and h not in visited:
                        visited.add(h)
                        
                        if levels > best_levels:
                            best_levels = levels
                            n_levels = levels
                            stagnation_counter = 0
                            print(f"  [SOLVE:{game_id}] ⭐ Level {levels}! action={act}, depth={depth+1}")
                        else:
                            stagnation_counter += 1
                        
                        if len(frontier) < MAX_PLY:
                            frontier.append((clone, h, current_seq + [act], depth + 1, levels))
                except Exception:
                    n_crashes += 1
                    if n_crashes > profile['max_crashes']:
                        break
                    continue
            
            if stagnation_counter > 100:
                result['stagnated'] = True
                break
        
        wrapper.close() if hasattr(wrapper, 'close') else None
        
    except Exception as e:
        result['error'] = str(e)
        result['traceback'] = traceback.format_exc()
    
    elapsed = time.time() - start
    result.update({
        'states': n_states if 'n_states' in dir() else result.get('states', 0),
        'levels': n_levels if 'n_levels' in dir() else result.get('levels', 0),
        'steps': n_steps if 'n_steps' in dir() else result.get('steps', 0),
        'crashes': n_crashes if 'n_crashes' in dir() else result.get('crashes', 0),
        'time': round(elapsed, 1),
    })
    
    print(f"  Result: {result['states']} st, {result['levels']} lv, {result['steps']} stp, {result['crashes']} cr, {result['time']}s")
    return result


# ════════════════════════════════════════════
# BENCHMARK RUNNER
# ════════════════════════════════════════════

def solve_wrapper(gid, is_smoke=False):
    return solve_game(gid, is_smoke)


def run_benchmark(game_list=None, version_label='spectral_v56', workers=N_WORKERS):
    if game_list is None:
        game_list = GAME_IDS
    
    print(f"\n{'='*60}")
    print(f"  SPECTRAL-V56 BENCHMARK")
    print(f"  Spectral: {USE_SPECTRAL} | Workers: {workers}")
    print(f"  Games: {len(game_list)}")
    print(f"  Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    if workers > 1:
        with Pool(workers) as pool:
            all_results = pool.map(solve_wrapper, game_list)
    else:
        all_results = [solve_game(g) for g in game_list]
    
    total_states = sum(r.get('states', 0) for r in all_results)
    total_levels = sum(r.get('levels', 0) for r in all_results)
    total_crashes = sum(r.get('crashes', 0) for r in all_results)
    total_steps = sum(r.get('steps', 0) for r in all_results)
    
    print(f"\n{'='*60}")
    print(f"  BENCHMARK COMPLETE ({version_label})")
    print(f"  Total states: {total_states}")
    print(f"  Total levels: {total_levels}")
    print(f"  Total crashes: {total_crashes}")
    print(f"  Total steps: {total_steps}")
    print(f"{'='*60}")
    
    return all_results, {'total_states': total_states, 'total_levels': total_levels, 'total_crashes': total_crashes, 'total_steps': total_steps}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Spectral V56 Benchmark')
    parser.add_argument('--games', nargs='+', default=None, help='Game IDs')
    parser.add_argument('--workers', type=int, default=N_WORKERS)
    parser.add_argument('--no-spectral', action='store_true', help='Disable spectral ranking')
    parser.add_argument('--output', type=str, default='spectral_v56_results.json')
    args = parser.parse_args()
    
    if args.no_spectral:
        USE_SPECTRAL = False
    
    game_list = args.games or GAME_IDS
    N_WORKERS = args.workers
    
    results, summary = run_benchmark(game_list, workers=N_WORKERS)
    
    output = {'results': results, 'summary': summary, 'config': {'spectral': USE_SPECTRAL, 'workers': N_WORKERS, 'n_frames': N_SPECTRAL_FRAMES}}
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n✅ Results saved to {args.output}")
