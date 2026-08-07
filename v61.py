"""
v61.py — ARC-AGI-3 Solver (API 0.1.0)
Implementa heurística "Explore-from-Cell" baseada no sp80_pattern_report.md
- Suprime reset do archive por 50 passos ao avançar de nível.
- Explora sequências mais longas a partir do archive em vez de BFS pura.
"""

import json
import sys
import os
import time
import random
import numpy as np
from typing import Dict, List, Optional
from collections import deque

from arc_agi import Arcade
from arcengine.enums import GameAction, GameState

def get_grid(wrapper) -> np.ndarray:
    sprites = wrapper._game.current_level.get_sprites()
    return wrapper._game.camera.render(sprites)

def observe(wrapper) -> Dict:
    game = wrapper._game
    grid = get_grid(wrapper)
    return {
        'grid': grid,
        'grid_hash': hash(grid.tobytes()),
        'level_index': getattr(game, 'level_index', 0),
        'steps': getattr(game, 'steps', 0),
        'game_over': getattr(game, '_game_over', getattr(game, 'game_over', False)),
    }

ACTION_MAP = {i: GameAction[f'ACTION{i}'] for i in range(1, 8)}

def grid_diff(g1: np.ndarray, g2: np.ndarray) -> int:
    return int(np.sum(g1 != g2))

class GameAnalyzer:
    def __init__(self, wrapper):
        self.wrapper = wrapper
        self.catalog = {
            'actions': {}, 'grid_size': None, 'grid_unique_colors': [],
            'action_effects': {}, 'game_type': 'unknown',
            'has_paint': False, 'has_tangram': False, 'has_navigation': False,
        }
    
    def analyze(self) -> Dict:
        print(f"[V61] FASE 0: Analisando jogo...")
        grid0 = get_grid(self.wrapper)
        self.catalog['grid_size'] = grid0.shape
        self.catalog['grid_unique_colors'] = sorted(np.unique(grid0).tolist())
        available = self._get_available()
        for action_id in available:
            self._test_action(action_id, grid0)
        self._diagnose_game_type()
        return self.catalog
    
    def _get_available(self) -> List[int]:
        try:
            fd = self.wrapper.step(GameAction.RESET)
            return getattr(fd, 'available_actions', [1, 2, 3, 4, 5, 6])
        except:
            return [1, 2, 3, 4, 5, 6]
    
    def _test_action(self, action_id: int, grid0: np.ndarray):
        try:
            self.wrapper.step(GameAction.RESET)
            grid_before = get_grid(self.wrapper)
            act = ACTION_MAP.get(action_id)
            if not act: return
            fd = self.wrapper.step(act)
            grid_after = get_grid(self.wrapper)
            diff = grid_diff(grid_before, grid_after)
            state = fd.state.name if hasattr(fd.state, 'name') else str(fd.state)
            levels = getattr(fd, 'levels_completed', 0)
            self.catalog['actions'][action_id] = {'has_effect': diff > 0 or 'WIN' in str(state), 'delta_pixels': diff, 'state_after': state, 'levels_after': levels}
            self.catalog['action_effects'][action_id] = diff
        except Exception as e:
            self.catalog['actions'][action_id] = {'has_effect': False, 'error': str(e)}
            self.catalog['action_effects'][action_id] = 0
            
    def _diagnose_game_type(self):
        acts = self.catalog['actions']
        has_5 = acts.get(5, {}).get('has_effect', False)
        has_6 = acts.get(6, {}).get('has_effect', False)
        if has_5 and has_6:
            self.catalog['has_paint'] = True
            self.catalog['game_type'] = 'paint'
        elif has_6:
            if acts.get(5, {}).get('delta_pixels', 0) > 0:
                self.catalog['has_tangram'] = True; self.catalog['game_type'] = 'tangram'
            else:
                self.catalog['has_navigation'] = True; self.catalog['game_type'] = 'navigation'

class ArchiveExploreSearch:
    def __init__(self, wrapper, catalog: Dict, max_states: int = 5000):
        self.wrapper = wrapper
        self.catalog = catalog
        self.max_states = max_states
        self.visited = set()
        self.archive = []
        self.best_solution = None
        self.best_score = 0
        self.stats = {'expanded': 0, 'game_overs': 0, 'archive_resets': 0}
    
    def search(self, max_depth: int = 400) -> Optional[List[int]]:
        print(f"[V61] FASE 1: Explore-from-Cell Search (max_states={self.max_states})")
        self.wrapper.step(GameAction.RESET)
        initial_grid = get_grid(self.wrapper)
        initial_hash = hash(initial_grid.tobytes())
        
        self.visited.add(initial_hash)
        self.archive.append({'hash': initial_hash, 'grid': initial_grid, 'sequence': [], 'score': 0, 'freshness': 0})
        
        available_actions = [a for a in range(1, 7) if self.catalog['actions'].get(a, {}).get('has_effect', False)]
        if not available_actions: available_actions = list(range(1, 7))
        
        while self.stats['expanded'] < self.max_states:
            # Seleciona melhor celula do archive balanceando score e freshness
            self.archive.sort(key=lambda x: x['score'] - x['freshness']*0.5, reverse=True)
            current_cell = self.archive[0]
            current_cell['freshness'] += 1
            
            sequence = list(current_cell['sequence'])
            if len(sequence) >= max_depth:
                current_cell['score'] = -999 # Matar branch muito longo
                continue
                
            self._restore_state(sequence)
            self.stats['archive_resets'] += 1
            
            # Explore from this cell sem resetar
            steps_left = 30
            current_levels = self._get_levels()
            
            while steps_left > 0 and self.stats['expanded'] < self.max_states and len(sequence) < max_depth:
                action_id = random.choice(available_actions)
                act = ACTION_MAP.get(action_id)
                self.stats['expanded'] += 1
                try:
                    fd = self.wrapper.step(act)
                except Exception:
                    self.stats['game_overs'] += 1
                    break
                    
                sequence.append(action_id)
                steps_left -= 1
                
                state_str = getattr(fd, 'state', None)
                state_name = state_str.name if hasattr(state_str, 'name') else str(state_str)
                levels_after = getattr(fd, 'levels_completed', 0)
                
                if 'GAME_OVER' in state_name:
                    self.stats['game_overs'] += 1
                    break
                    
                if levels_after > current_levels or 'WIN' in state_name:
                    self.best_solution = list(sequence)
                    self.best_score = levels_after
                    print(f"  ✅ LEVEL WON! {len(sequence)} steps, levels={levels_after}")
                    return self.best_solution
                
                new_grid = get_grid(self.wrapper)
                new_hash = hash(new_grid.tobytes())
                
                # Se mudou bastante, explora mais 10 passos
                score = int(np.sum(new_grid != initial_grid))
                if new_hash not in self.visited:
                    self.visited.add(new_hash)
                    if score > current_cell['score']:
                        self.archive.append({'hash': new_hash, 'grid': new_grid.copy(), 'sequence': list(sequence), 'score': score, 'freshness': 0})
                        if score > self.best_score:
                            self.best_score = score
                            steps_left += 10 # Reward high delta region
            
            if self.stats['expanded'] % 500 == 0 and self.stats['expanded'] > 0:
                print(f"  ... {self.stats['expanded']} estados, {len(self.archive)} archive, best_score={self.best_score}")
                
        return None
    
    def _restore_state(self, sequence: List[int]):
        self.wrapper.step(GameAction.RESET)
        for action_id in sequence:
            act = ACTION_MAP.get(action_id)
            if act:
                try: self.wrapper.step(act)
                except: break
    
    def _get_levels(self) -> int:
        try:
            fd = self.wrapper.step(GameAction.RESET)
            return getattr(fd, 'levels_completed', 0)
        except: return 0

class V61Solver:
    def __init__(self, game_id: str, seed: int = 0):
        self.game_id = game_id; self.seed = seed; self.solutions = {}; self.solved_levels = set()
    
    def init(self):
        a = Arcade()
        envs = a.get_environments()
        target = [e for e in envs if e.game_id.startswith(self.game_id)]
        if not target: return False
        self.wrapper = a.make(target[0].game_id, seed=self.seed, save_recording=True)
        self.total_levels = getattr(self.wrapper.step(GameAction.RESET), 'win_levels', 6)
        return True
    
    def run(self):
        if not self.init(): return {'error': 'Falha ao inicializar'}
        print(f"\n{'='*60}\n  V61 Solver — {self.game_id}\n{'='*60}")
        analyzer = GameAnalyzer(self.wrapper)
        catalog = analyzer.analyze()
        
        start_time = time.time()
        for level_idx in range(self.total_levels):
            print(f"\n  --- Nível {level_idx+1}/{self.total_levels} ---")
            bfs = ArchiveExploreSearch(self.wrapper, catalog)
            solution = bfs.search(max_depth=400)
            if solution:
                self.solutions[level_idx] = solution
                self.solved_levels.add(level_idx)
            else:
                break
                
        elapsed = time.time() - start_time
        result = {'game_id': self.game_id, 'levels_solved': len(self.solved_levels), 'levels_total': self.total_levels, 'solutions': {str(k): v for k, v in self.solutions.items()}, 'time_seconds': round(elapsed, 2), 'success': len(self.solved_levels) == self.total_levels}
        print(f"\n{'='*60}\n  RESULTADO V61 — {self.game_id}\n  ✅ Resolvidos: {len(self.solved_levels)}/{self.total_levels}\n  ⏱ Tempo: {elapsed:.1f}s\n{'='*60}")
        return result

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or '--help' in args:
        print("Uso: python v61.py <game_id> ou --all")
        sys.exit(0)
        
    if '--all' in args:
        a = Arcade()
        results = {}
        for env in a.get_environments():
            game_id = env.game_id.split('-')[0]
            results[game_id] = V61Solver(game_id).run()
            with open(f'v61_{game_id}_result.json', 'w') as f: json.dump(results[game_id], f, indent=2, default=str)
        with open('v61_benchmark_results.json', 'w') as f: json.dump(results, f, indent=2, default=str)
    else:
        game_id = args[0]
        result = V61Solver(game_id).run()
        with open(f'v61_{game_id}_result.json', 'w') as f: json.dump(result, f, indent=2, default=str)
