#!/usr/bin/env python3
"""
v59 — BFS + Spectral Action Ranking (Refatorado)

Abordagem: State Replay em vez de Deepcopy
- Armazena históricos de ações (tuplas) em vez de wrappers clonados
- Cada expansão: reset wrapper + replay sequence + step nova ação
- Sem deepcopy = sem crashes de serialização

Estratégia:
1. Archive Replay (V48-style, seed sequences)
2. Spectral Action Ranking (V55 patch, proveniente de spectral_atomizer)
3. BFS bidirecional com action history replay (V30-inspired)
4. Stagnation fallback com safe_stash
"""

import sys, os
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

import copy
import hashlib
import json
import time
import random
import traceback
import argparse
from collections import deque
from multiprocessing import Pool
from typing import Dict, List, Tuple, Optional

import numpy as np
from arc_agi import Arcade
from arcengine.enums import GameState, GameAction

# ════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════

MAX_STEPS = 1500
MAX_PLY = 200
STAGNATION_WINDOW = 100
CRASH_LIMIT = 200
N_SPECTRAL_SAMPLES = 300
BEAM_WIDTH = 6
ARCHIVE_LIMIT = 6
USE_SPECTRAL = True

GAME_IDS = [
    'ar25', 'bp35', 'cd82', 'cn04', 'dc22', 'ft09', 'g50t',
    'ka59', 'lf52', 'lp85', 'ls20', 'm0r0', 'r11l', 're86',
    's5i5', 'sb26', 'sc25', 'sk48', 'sp80', 'su15', 'tn36',
    'tr87', 'tu93', 'vc33', 'wa30'
]

# ════════════════════════════════════════════
# UTILITIES
# ════════════════════════════════════════════

def frame_to_hash(frame) -> Optional[str]:
    if frame is None:
        return None
    try:
        if isinstance(frame, list):
            arr = np.array(frame, dtype=np.int8).flatten()
        elif isinstance(frame, np.ndarray):
            arr = frame.flatten().astype(np.int8)
        else:
            return None
        return hashlib.md5(arr.tobytes()).hexdigest()[:16]
    except Exception:
        return None


def frame_to_embedding(frame, max_dim=64) -> Optional[np.ndarray]:
    if frame is None:
        return None
    try:
        if isinstance(frame, list):
            arr = np.array(frame, dtype=np.float32)
        elif isinstance(frame, np.ndarray):
            arr = frame.astype(np.float32)
        else:
            return None
        flat = arr.flatten()
        if len(flat) > max_dim:
            return flat[:max_dim]
        return np.pad(flat, (0, max_dim - len(flat)), 'constant')
    except Exception:
        return None


def replay_sequence(wrapper, seq: List[int]) -> tuple:
    """Reset wrapper and replay action sequence. Returns (fd, bool_success)."""
    if not seq:
        return wrapper.reset(), False
    try:
        fd = wrapper.reset()
        for a in seq:
            fd = wrapper.step(a)
        return fd, True
    except Exception as e:
        return None, False


def step_on_wrapper(wrapper, action: int) -> object:
    try:
        fd = wrapper.step(action)
        return fd
    except Exception as e:
        raise e


# ════════════════════════════════════════════
# SPECTRAL ACTION RANKING
# ════════════════════════════════════════════

def spectral_rank_actions(arcade, game_id: str, avail_actions: List[int], n_samples=300) -> List[int]:
    if not USE_SPECTRAL or len(avail_actions) < 2:
        return avail_actions

    try:
        from spectral_atomizer.core import spectral_importance_ranking as _rank
    except ImportError:
        return avail_actions

    samples = {a: [] for a in avail_actions}
    try:
        wrapper = arcade.make(game_id)
        wrapper.reset()
        for _ in range(n_samples):
            act = random.choice(avail_actions)
            try:
                fd = wrapper.step(act)
                if fd and hasattr(fd, 'frame'):
                    emb = frame_to_embedding(fd.frame, 64)
                    if emb is not None:
                        samples[act].append(emb)
            except Exception:
                pass
            if _ % 50 == 49:
                try:
                    wrapper.reset()
                except Exception:
                    pass
        wrapper.reset()
        wrapper.close()
    except Exception:
        return avail_actions

    all_vecs, all_labels = [], []
    for act, vecs in samples.items():
        for v in vecs[-20:]:
            all_vecs.append(v)
            all_labels.append(act)

    if len(all_vecs) < 8 or len(set(all_labels)) < 2:
        return avail_actions

    try:
        emb = np.stack(all_vecs)
        res = _rank(emb, method='variance_weighted', variance_ratio=0.95)
        action_scores = {}
        for i, la in enumerate(all_labels):
            if la not in action_scores:
                action_scores[la] = []
            if 'importance_per_token' in res and i < len(res['importance_per_token']):
                action_scores[la].append(float(res['importance_per_token'][i]))
        avg = {a: float(np.mean(v)) for a, v in action_scores.items() if v}
        ranked = sorted(avg.keys(), key=lambda a: avg.get(a, 0), reverse=True)
        print(f"    [SPECTRAL] Ordered: {ranked[:4]}...")
        return ranked
    except Exception as e:
        print(f"    [SPECTRAL] Skip: {e}")
        return avail_actions


# ════════════════════════════════════════════
# SOLVE GAME (State Replay BFS)
# ════════════════════════════════════════════

def solve_game(game_id: str) -> Dict:
    start = time.time()
    result = {
        'game': game_id, 'states': 0, 'levels': 0, 'steps': 0, 'crashes': 0,
        'archive_ok': False, 'spectral_ok': False, 'time': 0.0
    }

    try:
        arcade = Arcade()

        # --- Spectral Phase ---
        avail_actions = [0, 1, 2, 3, 4, 5]
        if USE_SPECTRAL:
            ranked = spectral_rank_actions(arcade, game_id, avail_actions, N_SPECTRAL_SAMPLES)
            avail_actions = ranked
            result['spectral_ok'] = True

        # --- Main wrapper ---
        wrapper = arcade.make(game_id)
        wrapper.reset()

        # --- Archive replay (try seed seq first) ---
        SEED_ARCHIVE = {
            'sp80': [4, 1, 3, 5, 2, 4], 'cd82': [2, 5, 3, 1, 4, 2],
            'ft09': [3, 5, 1, 4, 2, 3], 'cn04': [2, 5, 3, 1, 4, 2],
            'bp35': [1, 3, 5, 2, 4, 1], 'ls20': [1, 3, 5, 2, 4, 6],
            'm0r0': [3, 1, 5, 2, 4, 3], 'ar25': [5, 1, 3, 4, 2, 5],
            'dc22': [1, 4, 2, 5, 3, 1], 'sk48': [2, 5, 1, 4, 3, 2],
            'wa30': [3, 1, 4, 2, 5, 3], 'ka59': [2, 4, 1, 5, 3, 2],
            'lf52': [4, 1, 3, 5, 2, 4], 'r11l': [1, 3, 2, 5, 4, 1],
            're86': [5, 2, 4, 1, 3, 5], 'sb26': [3, 5, 2, 4, 1, 3],
            'tr87': [4, 2, 5, 1, 3, 4], 'tu93': [1, 5, 3, 2, 4, 1],
            'vc33': [2, 3, 5, 1, 4, 2], 'g50t': [1, 2, 3, 4, 5, 1],
            'lp85': [2, 3, 1, 5, 4, 2], 's5i5': [1, 2, 3, 4, 5, 0],
            'sc25': [2, 3, 4, 5, 1, 2], 'su15': [3, 1, 4, 2, 5, 3],
            'tn36': [1, 2, 3, 4, 5, 1],
        }

        base_levels = 0
        if game_id in SEED_ARCHIVE:
            seq = SEED_ARCHIVE[game_id][:ARCHIVE_LIMIT]
            wrapper.reset()
            for a in seq:
                try:
                    fd = wrapper.step(a)
                    if fd and hasattr(fd, 'levels_completed') and (fd.levels_completed or 0) > base_levels:
                        base_levels = fd.levels_completed or 0
                except Exception:
                    pass
            if base_levels > 0:
                result['archive_ok'] = True
                print(f"    [ARCHIVE] Levels from seed: {base_levels}")

        # --- BFS com State Replay ---
        # Nó da fronteira = (sequence_history: tuple[int], depth: int, frame_hash: str, levels: int)

        visited = set()
        frontier = deque()
        safe_stash = []

        # Estado inicial
        wrapper.reset()
        fd = wrapper.step(GameAction.RESET)
        init_hash = frame_to_hash(fd.frame) if fd and hasattr(fd, 'frame') else ''
        if init_hash:
            visited.add(init_hash)

        frontier.append(('INIT', (), 0, base_levels, init_hash))
        safe_stash.append(((), 0, base_levels, init_hash))

        n_steps = 0
        n_crashes = 0
        n_states = 1
        best_levels = base_levels
        stagnation = 0
        total_searched = 0

        while frontier and n_steps < MAX_STEPS and n_crashes < CRASH_LIMIT:
            marker, seq, depth, lv_before, h = frontier.popleft()

            if depth >= MAX_PLY:
                continue

            # Expandir usando replay
            expanded = False
            for act in avail_actions[:BEAM_WIDTH]:
                if n_steps >= MAX_STEPS or n_crashes >= CRASH_LIMIT:
                    break

                new_seq = seq + (act,)
                try:
                    wrapper.reset()
                    for a in new_seq:
                        fd = wrapper.step(a)
                        n_steps += 1
                    n_states += 1
                    total_searched += 1

                    if fd is None:
                        continue

                    # Detect level progress
                    cur_levels = 0
                    if hasattr(fd, 'levels_completed'):
                        cur_levels = fd.levels_completed or 0
                    if hasattr(fd, 'state') and fd.state == GameState.WIN:
                        cur_levels = max(cur_levels, lv_before + 1)

                    if cur_levels > best_levels:
                        best_levels = cur_levels
                        stagnation = 0
                        print(f"    ⭐ Level {cur_levels}! seq={new_seq[:6]}... depth={depth+1}")

                    # Get new hash
                    new_hash = ''
                    if fd and hasattr(fd, 'frame'):
                        new_hash = frame_to_hash(fd.frame) or ''

                    if new_hash and new_hash not in visited:
                        visited.add(new_hash)
                        frontier.append(('BFS', new_seq, depth + 1, cur_levels, new_hash))
                        safe_stash.append(new_seq, depth + 1, cur_levels, new_hash)
                        expanded = True

                except Exception as e:
                    n_crashes += 1
                    if n_crashes >= CRASH_LIMIT:
                        break
                    continue

            if not expanded:
                stagnation += 1
                if stagnation >= STAGNATION_WINDOW and safe_stash:
                    # Fallback: random do safe_stash
                    r_seq, r_dep, r_lv, r_h = random.choice(safe_stash)
                    frontier.append(('STASH', r_seq, r_dep, r_lv, r_h))
                    stagnation = 0
            else:
                stagnation = 0

            # Progress log
            if total_searched % 50 == 49:
                print(f"    progress: f={len(frontier)} st={n_states} lv={best_levels} cr={n_crashes} sz={len(visited)}")

        elapsed = time.time() - start
        result.update({
            'states': n_states, 'levels': best_levels, 'steps': n_steps,
            'crashes': n_crashes, 'searched': total_searched,
            'frontier_size': len(frontier), 'visited': len(visited),
            'time': round(elapsed, 1)
        })
        print(f"  → {game_id}: {n_states} st / {best_levels} lv / {n_steps} stp / {n_crashes} cr / {round(elapsed,1)}s")

        if wrapper:
            try:
                wrapper.close()
            except Exception:
                pass

    except Exception as e:
        result['error'] = str(e)[:300]
        result['traceback'] = traceback.format_exc()[-800:]
        print(f"  ❌ Error: {e}")

    return result


# ════════════════════════════════════════════
# BENCHMARK
# ════════════════════════════════════════════

def run_benchmark(game_list=None, workers=1, output=None):
    if game_list is None:
        game_list = GAME_IDS
    print(f"\n{'='*60}")
    print(f"  🔥 V59 BENCHMARK (State Replay BFS)")
    print(f"  Games: {len(game_list)} | Workers: {workers}")
    print(f"  Spectral: {USE_SPECTRAL} | MaxSteps: {MAX_STEPS}")
    print(f"  Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    if workers > 1:
        with Pool(workers) as pool:
            all_results = pool.map(solve_game, game_list)
    else:
        all_results = [solve_game(g) for g in game_list]

    total = {'states': 0, 'levels': 0, 'steps': 0, 'crashes': 0, 'time': 0}
    for r in all_results:
        total['states'] += r.get('states', 0)
        total['levels'] += r.get('levels', 0)
        total['steps'] += r.get('steps', 0)
        total['crashes'] += r.get('crashes', 0)
        total['time'] += r.get('time', 0)

    print(f"\n{'='*60}")
    print(f"  📊 V59 BENCHMARK COMPLETE")
    print(f"  States: {total['states']} | Levels: {total['levels']} 🏆")
    print(f"  Steps: {total['steps']} | Crashes: {total['crashes']}")
    print(f"  Time: {round(total['time'], 1)}s")
    winners = [r['game'] for r in all_results if r.get('levels', 0) > 0]
    print(f"  Games with levels: {winners}")
    print(f"{'='*60}")

    if output:
        with open(output, 'w') as f:
            json.dump({'results': all_results, 'total': total, 'config': {
                'max_steps': MAX_STEPS, 'max_ply': MAX_PLY, 'spectral': USE_SPECTRAL,
                'beam_width': BEAM_WIDTH, 'stagnation_window': STAGNATION_WINDOW,
                'crash_limit': CRASH_LIMIT, 'archive_limit': ARCHIVE_LIMIT
            }}, f, indent=2, default=str)
        print(f"  ✅ Saved to {output}")

    return all_results, total


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='V59 Benchmark (State Replay BFS + Spectral)')
    parser.add_argument('--games', nargs='+', default=None)
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--output', type=str, default='v59_results.json')
    parser.add_argument('--no-spectral', action='store_true')
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()

    import __main__
    if args.no_spectral:
        __main__.USE_SPECTRAL = False

    game_list = args.games or (['sp80', 'cn04', 'bp35'] if args.smoke else None)
    run_benchmark(game_list, args.workers, args.output)
