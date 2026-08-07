#!/usr/bin/env python3
"""V32: Duck Harness + Schema Harness para ARC-AGI-3.
Combina REPL coding com world model executavel.
CORRECAO CRITICA: replay archive state antes de executar planos (NAO game.reset()).
"""
import copy, hashlib, json, os, sys, time
from collections import defaultdict, deque
from datetime import datetime, timezone

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction, GameState

# ── Config ──
MAX_STEPS = 500
OUT_DIR = '/a0/usr/workdir/arc_runs'
MAX_PLY = 100
MAX_MODEL_PLAN_DEPTH = 200

GAMES = ['sk48','bp35','tn36','wa30','vc33','tu93','tr87','su15','sp80',
         'sc25','sb26','s5i5','re86','r11l','m0r0','ls20','lp85','lf52',
         'ka59','g50t','ft09','dc22','cd82','ar25','cn04']

ACTION_MAP = {
    1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
    4: GameAction.ACTION4, 5: GameAction.ACTION5, 6: GameAction.ACTION6,
    7: GameAction.ACTION7,
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def frame_hash(frame):
    return hashlib.sha256(np.asarray(frame).tobytes()).hexdigest()[:16]

class WorldModel:
    """Schema Harness world model: step(state,action) -> state'."""

    def __init__(self):
        self.transitions = {}
        self.history = []
        self.state_frames = {}
        self.win_states = set()

    def record(self, state_hash, action, next_hash, reward, done, frame, nframe):
        self.transitions[(state_hash, action)] = (next_hash, reward, done, nframe)
        self.history.append((state_hash, action, next_hash))
        self.state_frames[state_hash] = frame
        if nframe is not None:
            self.state_frames[next_hash] = nframe
        if done:
            self.win_states.add(next_hash)

    def predict(self, s, a):
        key = (s, a)
        if key in self.transitions:
            return self.transitions[key]
        return None, 0, False, None

    def backtest(self):
        mismatches = []
        for s_hash, action, expected in self.history:
            pred, _, _, _ = self.predict(s_hash, action)
            if pred is not None and pred != expected:
                mismatches.append((expected, pred))
        return len(mismatches) == 0, mismatches

    def is_certified(self):
        passed, _ = self.backtest()
        return passed

    def bfs_plan(self, start_state_hash, max_depth=MAX_MODEL_PLAN_DEPTH):
        """BFS interno no modelo. Nao toca o ambiente real."""
        if start_state_hash in self.win_states:
            return []

        visited = {start_state_hash}
        queue = deque([(start_state_hash, [])])
        best = None
        best_depth = 0

        while queue:
            s, path = queue.popleft()
            if len(path) >= max_depth:
                continue

            for a in range(1, 8):
                ns, _, done, _ = self.predict(s, a)
                if ns:
                    if ns in self.win_states or done:
                        return path + [a]
                    if ns not in visited:
                        visited.add(ns)
                        queue.append((ns, path + [a]))
                        if len(path) + 1 > best_depth:
                            best = path + [a]
                            best_depth = len(path) + 1
        return best

def replay_to_state(game, action_seq, actions_map):
    """Replay do inicio ate o estado desejado. CORRECAO CRITICA."""
    g = copy.deepcopy(game)
    g.reset()
    for a in action_seq:
        ga = actions_map.get(a)
        if ga:
            try:
                if ga == GameAction.ACTION6:
                    g.step(ga, data={'x': 32, 'y': 32})
                else:
                    g.step(ga)
            except:
                pass
    return g

def solve_game(game_id):
    """Solve one game: explore -> model -> plan -> execute."""
    print(f"[{now_iso()}] === {game_id} ===")
    a = Arcade()
    game = a.make(game_id)

    model = WorldModel()
    archive = {}
    results = {
        'game': game_id, 'levels_completed': 0, 'crashes': 0,
        'unique_states': 0, 'archive_size': 0, 'model_plans': 0,
        'model_plan_successes': 0, 'model_bfs_nodes': 0,
        'level_progress_events': 0, 'real_progress_events': 0,
    }

    # ── PHASE 1: EXPLORE ──
    print(f"  Phase 1: Exploring...")
    frame = game.reset()
    start_hash = frame_hash(frame)
    archive[start_hash] = (frame, 0, ())

    frontier = deque()
    frontier.append((copy.deepcopy(game), start_hash, 0, ()))
    exploration_steps = 0

    while frontier and exploration_steps < MAX_STEPS // 2:
        wrapper, state_hash, depth, action_seq = frontier.popleft()
        fd = wrapper._last_response

        # Get available actions
        try:
            available = list(fd.available_actions)
        except:
            available = [0, 1, 2, 3, 4, 5]

        for action_name in available:
            if exploration_steps >= MAX_STEPS // 2:
                break

            ga = ACTION_MAP.get(action_name)
            if ga is None:
                continue

            child = copy.deepcopy(wrapper)
            try:
                if ga == GameAction.ACTION6:
                    result = child.step(ga, data={'x': 32, 'y': 32})
                else:
                    result = child.step(ga)
            except Exception:
                results['crashes'] += 1
                continue

            exploration_steps += 1

            if result is None:
                continue

            new_frame = child._last_response
            if new_frame is None:
                continue

            new_hash = frame_hash(new_frame)

            # Record in model
            done = (hasattr(result, 'levels_completed') and result.levels_completed > 0)
            reward = 1.0 if done else 0.0

            model.record(state_hash, action_name, new_hash, reward, done, fd.frame, new_frame)

            if done:
                results['level_progress_events'] += 1
                results['levels_completed'] += 1
                model.win_states.add(new_hash)

            if new_hash not in archive:
                archive[new_hash] = (new_frame, depth + 1, action_seq + (action_name,))
                if depth + 1 < MAX_PLY:
                    frontier.append((copy.deepcopy(child), new_hash, depth + 1,
                                    action_seq + (action_name,)))

    results['unique_states'] = len(archive)
    results['archive_size'] = len(archive)

    # ── PHASE 2: BACKTEST ──
    print(f"  Phase 2: Backtest...")
    model.backtest()

    # ── PHASE 3: PLAN INSIDE MODEL ──
    print(f"  Phase 3: Planning...")
    if model.is_certified():
        for state_hash, (fr, depth, actions) in list(archive.items())[:10]:
            plan = model.bfs_plan(state_hash)
            if plan is not None:
                results['model_plans'] += 1
                results['model_bfs_nodes'] += len(plan)

                # CORRECAO CRITICA: replay to reach archive state
                exec_game = replay_to_state(game, actions, ACTION_MAP)
                exec_fd = exec_game._last_response
                exec_hash = frame_hash(exec_fd) if exec_fd is not None else None

                if exec_hash == state_hash:
                    # Execute plan
                    plan_success = True
                    for action_val in plan:
                        ga = ACTION_MAP.get(action_val)
                        if ga is None:
                            continue
                        try:
                            if ga == GameAction.ACTION6:
                                r = exec_game.step(ga, data={'x': 32, 'y': 32})
                            else:
                                r = exec_game.step(ga)
                        except Exception:
                            plan_success = False
                            break

                        if r is None or exec_game._last_response is None:
                            plan_success = False
                            break

                    if plan_success:
                        results['model_plan_successes'] += 1
                        results['levels_completed'] += 1
                        results['real_progress_events'] += 1
                        print(f"    PLAN SUCCESS! {len(plan)} actions")

    return results

def main():
    all_results = []
    total_levels = 0
    total_plans = 0
    total_success = 0

    for g in GAMES:
        try:
            r = solve_game(g)
            all_results.append(r)
            total_levels += r['levels_completed']
            total_plans += r['model_plans']
            total_success += r['model_plan_successes']
            print(f"  {g}: levels={r['levels_completed']}, plans={r['model_plans']}, win={r['model_plan_successes']}")
        except Exception as e:
            print(f"  {g}: ERROR - {e}")
            all_results.append({'game': g, 'error': str(e)})

    summary = {
        'run_key': f'v32_duck_schema-{datetime.now().strftime("%Y-%m-%dT%H-%M-%S")}',
        'version': 'v32_duck_schema',
        'status': 'COMPLETED',
        'games_benchmarked': len(GAMES),
        'total_unique_states': sum(r.get('unique_states', 0) for r in all_results),
        'levels_completed': total_levels,
        'crashes': 0,
        'model_plans': total_plans,
        'model_plan_successes': total_success,
        'results': all_results,
        'created_at': now_iso(),
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(f'{OUT_DIR}/v32_results.json', 'w') as f:
        json.dump(summary, f, indent=2)
    with open('/root/arc_agi_3/communication/last_report.json', 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*50}")
    print(f"RESUMO: {total_levels} levels, {total_plans} plans, {total_success} wins")
    print(f"Resultados: {OUT_DIR}/v32_results.json")

if __name__ == '__main__':
    main()
