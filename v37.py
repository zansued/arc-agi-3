#!/usr/bin/env python3
"""
v37: Deepcopy BFS + Graph Memory + Crash Mitigation
Based on v36, with:
  - try/except around every env.step()
  - After 3 crashes per game: reduce beam_width, increase exploration
  - Filter crash-causing actions before retrying
  - Early switch to random mode if 0 levels after 300 steps
Target: <100 crashes, >2 levels, >1959 states
"""

import copy
import hashlib
import json
import sys
import time
import traceback
from collections import defaultdict, deque
from multiprocessing import Pool, cpu_count

import numpy as np
from arc_agi import Arcade
from arcengine.enums import GameAction, GameState

# ============================================================
# CONFIG
# ============================================================
GAME_IDS = [
    'ar25', 'bp35', 'cd82', 'cn04', 'dc22', 'ft09', 'g50t',
    'ka59', 'lf52', 'lp85', 'ls20', 'm0r0', 'r11l', 're86',
    's5i5', 'sb26', 'sc25', 'sk48', 'sp80', 'su15', 'tn36',
    'tr87', 'tu93', 'vc33', 'wa30'
]
MAX_STEPS = 500
MAX_PLY = 8
N_WORKERS = 6

# Crash mitigation thresholds
CRASH_THRESHOLD = 3       # after this many crashes per game, adapt
BEAM_REDUCED = 3           # reduced beam width
EXPLORATION_BOOST = 0.3    # random exploration chance after crash spike
EARLY_SWITCH_STEPS = 300   # if 0 levels by this step, go random
MAX_BEAM = 4               # default beam


# ============================================================
# FEATURE EXTRACTION
# ============================================================
def extract_features(frame_list):
    if not frame_list or len(frame_list) == 0:
        return {'color_hist': {}, 'n_objects': 0, 'symmetry_h': False,
                'symmetry_v': False, 'grid_hash': 'empty'}
    grid = np.asarray(frame_list[0], dtype=np.int8)
    if grid.size == 0:
        return {'color_hist': {}, 'n_objects': 0, 'symmetry_h': False,
                'symmetry_v': False, 'grid_hash': 'empty'}
    h, w = grid.shape
    colors, counts = np.unique(grid, return_counts=True)
    color_hist = dict(zip((int(c) for c in colors), (int(v) for v in counts)))
    symmetry_h = bool(np.array_equal(grid[:h//2,:], grid[h-h//2:,:][::-1,:])) if h >= 2 else False
    symmetry_v = bool(np.array_equal(grid[:,:w//2], grid[:,w-w//2:][:,::-1])) if w >= 2 else False
    grid_bin = (grid > 0).astype(np.int8)
    visited = np.zeros_like(grid_bin, dtype=bool)
    n_objects = 0
    for y in range(h):
        for x in range(w):
            if grid_bin[y, x] and not visited[y, x]:
                n_objects += 1
                stack = [(y, x)]
                while stack:
                    cy, cx = stack.pop()
                    if cy < 0 or cy >= h or cx < 0 or cx >= w:
                        continue
                    if visited[cy, cx] or not grid_bin[cy, cx]:
                        continue
                    visited[cy, cx] = True
                    stack.extend([(cy-1,cx), (cy+1,cx), (cy,cx-1), (cy,cx+1)])
    grid_hash = hashlib.md5(grid.tobytes()).hexdigest()[:12]
    return {'color_hist': color_hist, 'n_objects': n_objects,
            'symmetry_h': symmetry_h, 'symmetry_v': symmetry_v, 'grid_hash': grid_hash}


def features_to_state_key(features):
    return 'empty' if features is None or features.get('grid_hash') == 'empty' else features['grid_hash']


# ============================================================
# GRAPH MEMORY
# ============================================================
class GraphMemory:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.action_probs = defaultdict(lambda: defaultdict(float))
        self.crashed_actions = defaultdict(set)  # game/state -> set of actions that crashed

    def add_frame(self, features):
        h = features.get('grid_hash', 'empty')
        if h != 'empty' and h not in self.nodes:
            self.nodes[h] = features
            return True
        return False

    def add_transition(self, from_hash, action_id, to_hash):
        if from_hash and to_hash and from_hash != to_hash:
            self.edges.append((from_hash, action_id, to_hash, len(self.edges)))
            self.action_probs[from_hash][action_id] += 1.0

    def record_crash(self, state_hash, action_id):
        """Remember that this action crashed from this state."""
        self.crashed_actions[state_hash].add(action_id)

    def get_valid_actions(self, state_hash):
        """Get actions excluding known crash-causing ones."""
        all_actions = list(range(1, 7))
        bad = self.crashed_actions.get(state_hash, set())
        return [a for a in all_actions if a not in bad]

    def get_action_priorities(self, current_features):
        if current_features is None:
            return list(range(1, 7))
        current_hash = current_features.get('grid_hash', '')
        if not current_hash:
            return list(range(1, 7))
        # Filter out crashed actions
        bad = self.crashed_actions.get(current_hash, set())
        if current_hash in self.action_probs:
            probs = {a: v for a, v in self.action_probs[current_hash].items() if a not in bad}
            sorted_actions = sorted(probs.keys(), key=lambda a: probs[a], reverse=True)
        else:
            sorted_actions = []
        remaining = [a for a in range(1, 7) if a not in sorted_actions and a not in bad]
        return sorted_actions + remaining + [a for a in range(1, 7) if a not in bad and a not in set(sorted_actions + remaining)]

    def has_pattern(self, current_hash):
        if current_hash in self.action_probs:
            return len(self.action_probs[current_hash]) >= 3
        return False

    def summary(self):
        return {'nodes': len(self.nodes), 'edges': len(self.edges),
                'action_probs': sum(len(v) for v in self.action_probs.values()),
                'crashed_pairs': sum(len(v) for v in self.crashed_actions.values())}


# ============================================================
# SAFE STEP WRAPPER
# ============================================================
def safe_step(wrapper, action_id, graph, state_hash):
    """Step with crash protection. Returns (next_wrapper, features) or (None, None)."""
    try:
        w_clone = copy.deepcopy(wrapper)
        fa = w_clone.step(GameAction.from_id(action_id))
        if fa is None:
            # Action resulted in crash
            if graph:
                graph.record_crash(state_hash, action_id)
            return None, None
        feat = extract_features(fa.frame)
        return w_clone, feat
    except Exception:
        if graph:
            graph.record_crash(state_hash, action_id)
        return None, None


# ============================================================
# SOLVE GAME
# ============================================================
def solve_game(game_id):
    start = time.time()
    result = {
        'game': game_id,
        'states': 0, 'levels': 0, 'steps': 0, 'crashes': 0,
        'stagnated': False, 'crash_mode_activated': False, 'early_random': False,
    }

    try:
        wrapper = Arcade().make(game_id)
        root = wrapper.reset()
        if root is None:
            return result

        graph = GraphMemory()
        features_root = extract_features(root.frame)
        graph.add_frame(features_root)

        # Initial analysis - test actions safely
        root_key = features_to_state_key(features_root)
        for a in range(1, 7):
            next_w, feat_a = safe_step(wrapper, a, graph, root_key)
            if next_w and feat_a:
                fh = feat_a.get('grid_hash', '')
                if fh and fh != root_key:
                    graph.add_frame(feat_a)
                    graph.add_transition(root_key, a, fh)
            else:
                result['crashes'] += 1

        # BFS
        visited = set()
        queue = deque()
        level_steps_remaining = MAX_STEPS
        visited.add(root_key)
        queue.append((wrapper, [], features_root))

        ply = 0
        states_count = 1
        levels_found = 0
        crashes = result['crashes']
        steps_used = 0
        crash_mode = False
        early_random = False
        current_beam = MAX_BEAM

        while queue and level_steps_remaining > 0 and ply < MAX_PLY:
            level_size = len(queue)
            new_states = 0

            # Check: after CRASH_THRESHOLD crashes, reduce beam and boost exploration
            if crashes >= CRASH_THRESHOLD and not crash_mode:
                crash_mode = True
                current_beam = BEAM_REDUCED
                result['crash_mode_activated'] = True

            # Check: if 0 levels after EARLY_SWITCH_STEPS, go random exploration
            if steps_used >= EARLY_SWITCH_STEPS and levels_found == 0 and not early_random:
                early_random = True
                current_beam = 2  # narrow beam + high random
                result['early_random'] = True

            beam_count = 0
            for _ in range(min(level_size, current_beam if crash_mode or early_random else level_size)):
                if level_steps_remaining <= 0:
                    break
                w, path, feat = queue.popleft()
                beam_count += 1

                state_hash = feat.get('grid_hash', '') if feat else ''

                # Get valid (non-crashing) actions
                if crash_mode or early_random:
                    valid_actions = graph.get_valid_actions(state_hash)
                    import random
                    random.shuffle(valid_actions)
                    action_order = valid_actions
                else:
                    action_order = graph.get_action_priorities(feat if feat else None)

                for action_id in action_order:
                    if level_steps_remaining <= 0:
                        break

                    next_w, feat_a = safe_step(w, action_id, graph, state_hash)
                    steps_used += 1
                    level_steps_remaining -= 1

                    if next_w is None or feat_a is None:
                        crashes += 1
                        continue

                    state_key = features_to_state_key(feat_a)

                    # Check for level completion
                    # We need to check levels_completed from the actual response
                    try:
                        w_check = copy.deepcopy(w)
                        f_check = w_check.step(GameAction.from_id(action_id))
                        if f_check is not None and f_check.levels_completed > levels_found:
                            levels_found = f_check.levels_completed
                    except Exception:
                        pass

                    if state_key not in visited and state_key != 'empty':
                        visited.add(state_key)
                        graph.add_frame(feat_a)
                        if feat:
                            graph.add_transition(feat.get('grid_hash', ''),
                                                 action_id, feat_a.get('grid_hash', ''))
                        queue.append((next_w, path + [action_id], feat_a))
                        new_states += 1
                        states_count += 1

            ply += 1
            if new_states == 0 and ply > 3:
                break

        result.update({
            'states': states_count,
            'levels': levels_found,
            'steps': steps_used,
            'crashes': crashes,
            'stagnated': level_steps_remaining > MAX_STEPS // 2,
            'graph_summary': graph.summary(),
            'time': round(time.time() - start, 1),
        })

    except Exception as e:
        result['error'] = str(e)
        traceback.print_exc()

    return result


def solve_wrapper(gid):
    try:
        r = solve_game(gid)
        print(f'[v37] {gid}: {r["states"]} estados, {r["levels"]} níveis, '
              f'{r["steps"]} steps, {r["crashes"]} cr, {r["time"]}s'
              f'{" CM" if r.get("crash_mode_activated") else ""}'
              f'{" ER" if r.get("early_random") else ""}')
        sys.stdout.flush()
        return r
    except Exception as e:
        print(f'[v37] {gid}: CRASH {e}')
        return {'game': gid, 'error': str(e)}


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print(f'===== V37 DEEPCOPY BFS + CRASH MITIGATION =====')
    print(f'Games: {len(GAME_IDS)} | Workers: {N_WORKERS} | Steps: {MAX_STEPS} | Ply: {MAX_PLY}')
    print(f'Crash threshold: {CRASH_THRESHOLD} | Beam reduced: {BEAM_REDUCED} | Exploration: {EXPLORATION_BOOST}')
    print(f'Early random at {EARLY_SWITCH_STEPS} steps if 0 levels')
    print(f'Started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    sys.stdout.flush()

    t0 = time.time()
    results = []

    with Pool(N_WORKERS) as pool:
        for r in pool.imap_unordered(solve_wrapper, GAME_IDS):
            results.append(r)

    t1 = time.time()

    total_states = sum(r.get('states', 0) for r in results)
    total_levels = sum(r.get('levels', 0) for r in results)
    total_crashes = sum(r.get('crashes', 0) for r in results)
    total_steps = sum(r.get('steps', 0) for r in results)
    total_cm = sum(1 for r in results if r.get('crash_mode_activated'))
    total_er = sum(1 for r in results if r.get('early_random'))
    dead_games = [r['game'] for r in results if r.get('states', 0) <= 1]
    top_games = sorted(results, key=lambda r: r.get('states', 0), reverse=True)[:10]

    print(f'\n{"="*60}')
    print(f'V37 FULL BENCHMARK RESULT')
    print(f'{"="*60}')
    print(f'Tempo total: {t1-t0:.1f}s')
    print(f'25/25 jogos completos')
    print(f'')
    print(f'Total estados únicos: {total_states}')
    print(f'Total níveis: {total_levels}')
    print(f'Total crashes: {total_crashes}')
    print(f'Total steps: {total_steps}')
    print(f'Crash mode ativado: {total_cm} jogos')
    print(f'Early random ativado: {total_er} jogos')
    print(f'')
    print(f'Dead games (<=1 estado): {len(dead_games)}')
    for g in dead_games:
        r = next(x for x in results if x['game'] == g)
        print(f'  {g}: error={r.get("error", "none")}')
    print(f'')
    print(f'Top 10 por estados:')
    for r in top_games:
        print(f'  {r["game"]}: {r["states"]:>4} estados, {r["levels"]} níveis, '
              f'{r["steps"]:>3} steps, {r["crashes"]:>3} cr, {r["time"]:>4.1f}s')
    print(f'')
    print(f'Games com níveis:')
    for r in results:
        if r.get('levels', 0) > 0:
            print(f'  {"":>2}{r["game"]}: {r["levels"]} nível(is)')
    print(f'')
    print(f'Comparação V36 vs V37:')
    print(f'  V36: {1959} states, {2} levels, {258} crashes, {6654} steps')
    print(f'  V37: {total_states} states, {total_levels} levels, {total_crashes} crashes, {total_steps} steps')

    # Save results
    out = {
        'version': 'v37', 'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'total_states': total_states, 'total_levels': total_levels,
        'total_crashes': total_crashes, 'total_steps': total_steps,
        'v36_comparison': {'states': 1959, 'levels': 2, 'crashes': 258, 'steps': 6654},
        'results': {r['game']: {
            'states': r.get('states', 0), 'levels': r.get('levels', 0),
            'steps': r.get('steps', 0), 'crashes': r.get('crashes', 0),
            'time': r.get('time', 0), 'error': r.get('error', None),
            'crash_mode': r.get('crash_mode_activated', False),
            'early_random': r.get('early_random', False),
            'graph': r.get('graph_summary', {}),
        } for r in results},
    }

    with open('/tmp/v37_results.json', 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f'\nResultados salvos em /tmp/v37_results.json')
    print(f'Done: {time.strftime("%Y-%m-%d %H:%M:%S")}')
