"""
v60.py — ARC-AGI-3 Solver com API arc_agi 0.1.0

Arquitetura:
- Fase 0: Reconhecimento (grid + actions → catálogo)
- Fase 1: Archive Replay BFS com GameAction correto
- Fase 2: Heurísticas por padrão (paint/tangram/navigation)

API arc_agi:
- Arcade.make(game_id, seed, save_recording=True)
- wrapper.step(GameAction.ACTIONn)
- wrapper._game.camera.render(sprites) → grid (H,W) int8
- wrapper._game.current_level.get_sprites()

Diferenças da API antiga:
- NÃO existe Arcade.get_state()
- NÃO existe arcade.open_game(id)
- NÃO existe step(-1)
- GameAction é Enum (não IntEnum) — usar GameAction.ACTION1
"""

import json
import sys
import os
import time
import numpy as np
from typing import Dict, List, Optional
from collections import deque

from arc_agi import Arcade
from arcengine.enums import GameAction, GameState


# ========== UTILITIES ==========

def get_grid(wrapper) -> np.ndarray:
    """
    Obtém grid atual via Camera.render().
    Retorna ndarray (H, W) dtype=int8.
    """
    sprites = wrapper._game.current_level.get_sprites()
    return wrapper._game.camera.render(sprites)


def observe(wrapper) -> Dict:
    """
    Observa estado atual sem modificar nada.
    Não precisa de step() — apenas lê o estado interno.
    """
    game = wrapper._game
    grid = get_grid(wrapper)
    return {
        'grid': grid,
        'grid_hash': hash(grid.tobytes()),
        'level_index': getattr(game, 'level_index', 0),
        'steps': getattr(game, 'steps', 0),
        'game_over': getattr(game, '_game_over', getattr(game, 'game_over', False)),
    }


def get_fd(wrapper) -> Optional[Dict]:
    """
    Obtém FrameDataRaw após um step RESET.
    Útil para verificar levels_completed, state, available_actions.
    """
    try:
        fd = wrapper.step(GameAction.RESET)
        return {
            'state': fd.state.name if hasattr(fd.state, 'name') else str(fd.state),
            'levels_completed': getattr(fd, 'levels_completed', 0),
            'win_levels': getattr(fd, 'win_levels', 0),
            'available_actions': getattr(fd, 'available_actions', []),
        }
    except Exception as e:
        return {'error': str(e)}


# Map int to GameAction
ACTION_MAP = {i: GameAction[f'ACTION{i}'] for i in range(1, 8)}


def grid_diff(g1: np.ndarray, g2: np.ndarray) -> int:
    """Conta pixels diferentes entre grids."""
    return int(np.sum(g1 != g2))


# ========== PHASE 0: RECONNHECIMENTO ==========

class GameAnalyzer:
    """
    Fase 0: Analisa o jogo sem conhecimento prévio.
    Testa cada ação, mapeia efeitos, identifica padrões.
    """
    
    def __init__(self, wrapper):
        self.wrapper = wrapper
        self.catalog = {
            'actions': {},
            'grid_size': None,
            'grid_unique_colors': [],
            'action_effects': {},
            'game_type': 'unknown',
            'has_paint': False,
            'has_tangram': False,
            'has_navigation': False,
        }
    
    def analyze(self) -> Dict:
        """Executa análise completa."""
        print(f"[V60] FASE 0: Analisando jogo...")
        
        # Grid inicial
        grid0 = get_grid(self.wrapper)
        self.catalog['grid_size'] = grid0.shape
        self.catalog['grid_unique_colors'] = sorted(np.unique(grid0).tolist())
        print(f"  Grid: {grid0.shape}, cores: {self.catalog['grid_unique_colors']}")
        
        # Testar cada ação (1-6)
        available = self._get_available()
        print(f"  Ações disponíveis: {available}")
        
        for action_id in available:
            self._test_action(action_id, grid0)
        
        # Diagnóstico
        self._diagnose_game_type()
        
        return self.catalog
    
    def _get_available(self) -> List[int]:
        try:
            fd = self.wrapper.step(GameAction.RESET)
            return getattr(fd, 'available_actions', [1, 2, 3, 4, 5, 6])
        except:
            return [1, 2, 3, 4, 5, 6]
    
    def _test_action(self, action_id: int, grid0: np.ndarray):
        """Testa efeito de uma ação."""
        try:
            # Reset ao estado inicial primeiro
            self.wrapper.step(GameAction.RESET)
            grid_before = get_grid(self.wrapper)
            
            # Executar ação
            act = ACTION_MAP.get(action_id)
            if act is None:
                return
            fd = self.wrapper.step(act)
            
            grid_after = get_grid(self.wrapper)
            diff = grid_diff(grid_before, grid_after)
            
            state = fd.state.name if hasattr(fd.state, 'name') else str(fd.state)
            levels = getattr(fd, 'levels_completed', 0)
            
            effect = {
                'has_effect': diff > 0 or 'WIN' in str(state),
                'delta_pixels': diff,
                'state_after': state,
                'levels_after': levels,
            }
            self.catalog['actions'][action_id] = effect
            self.catalog['action_effects'][action_id] = diff
            
            print(f"  ACTION{action_id}: diff={diff} pixels, state={state}, levels={levels}")
            
        except Exception as e:
            self.catalog['actions'][action_id] = {'has_effect': False, 'error': str(e)}
            self.catalog['action_effects'][action_id] = 0
            print(f"  ACTION{action_id}: ERRO {e}")
    
    def _diagnose_game_type(self):
        """Diagnostica tipo do jogo baseado nos efeitos."""
        acts = self.catalog['actions']
        
        # sp80-style: ACTION5=move/paint, ACTION6=select
        has_5 = acts.get(5, {}).get('has_effect', False)
        has_6 = acts.get(6, {}).get('has_effect', False)
        
        if has_5 and has_6:
            self.catalog['has_paint'] = True
            self.catalog['game_type'] = 'paint'
        elif has_6:
            # Check if it's tangram or navigation
            if acts.get(5, {}).get('delta_pixels', 0) > 0:
                self.catalog['has_tangram'] = True
                self.catalog['game_type'] = 'tangram'
            else:
                self.catalog['has_navigation'] = True
                self.catalog['game_type'] = 'navigation'
        
        print(f"  Diagnóstico: {self.catalog['game_type']}")


# ========== PHASE 1: ARCHIVE REPLAY BFS ==========

class ArchiveReplayBFS:
    """
    BFS com archive replay e grid hashing.
    
    Estratégia:
    - Usa hash do grid como chave de estado
    - Archive de estados promissores
    - Backtracking quando game over
    - Beam search com limiar de expansão
    """
    
    def __init__(self, wrapper, catalog: Dict, max_states: int = 5000):
        self.wrapper = wrapper
        self.catalog = catalog
        self.max_states = max_states
        self.visited = set()
        self.archive = []
        self.best_solution = None
        self.best_score = 0
        self.stats = {'expanded': 0, 'game_overs': 0, 'archive_resets': 0}
    
    def search(self, max_depth: int = 200) -> Optional[List[int]]:
        """
        Busca BFS com archive replay.
        Retorna sequência de ações que resolve o nível ou None.
        """
        print(f"[V60] FASE 1: BFS Archive Replay (max_states={self.max_states})")
        
        # Estado inicial
        self.wrapper.step(GameAction.RESET)
        initial_grid = get_grid(self.wrapper)
        initial_hash = hash(initial_grid.tobytes())
        
        queue = deque()
        queue.append((initial_hash, []))  # (state_hash, action_sequence)
        self.visited.add(initial_hash)
        self.archive.append({'hash': initial_hash, 'grid': initial_grid, 'sequence': [], 'score': 0})
        
        available_actions = [a for a in range(1, 7) if self.catalog['actions'].get(a, {}).get('has_effect', False)]
        if not available_actions:
            available_actions = list(range(1, 7))  # fallback: all actions
        
        print(f"  Available actions (with effect): {available_actions}")
        
        while queue and self.stats['expanded'] < self.max_states:
            state_hash, sequence = queue.popleft()
            
            if len(sequence) >= max_depth:
                continue
            
            # Try each action
            improved = False
            for action_id in available_actions:
                # Restore state from archive
                archive_entry = None
                for entry in reversed(self.archive):
                    if entry['hash'] == state_hash:
                        archive_entry = entry
                        break
                
                if archive_entry is None:
                    continue
                
                # Execute from archived state
                self._restore_state(archive_entry)
                
                # Apply action
                act = ACTION_MAP.get(action_id)
                if act is None:
                    continue
                
                try:
                    fd = self.wrapper.step(act)
                except Exception as e:
                    self.stats['game_overs'] += 1
                    continue
                
                new_grid = get_grid(self.wrapper)
                new_hash = hash(new_grid.tobytes())
                new_sequence = sequence + [action_id]
                
                state_str = getattr(fd, 'state', None)
                state_name = state_str.name if hasattr(state_str, 'name') else str(state_str)
                levels_before = self._get_levels()
                levels_after = getattr(fd, 'levels_completed', 0)
                
                # Hit game over?
                if 'GAME_OVER' in state_name:
                    self.stats['game_overs'] += 1
                    continue
                
                # Won the level?
                if levels_after > levels_before or 'WIN' in state_name:
                    self.best_solution = new_sequence
                    self.best_score = levels_after
                    print(f"  ✅ LEVEL WON! {len(new_sequence)} steps, levels={levels_after}")
                    return new_sequence
                
                # New state or better?
                if new_hash not in self.visited:
                    self.visited.add(new_hash)
                    score = int(np.sum(new_grid != initial_grid))
                    self.archive.append({'hash': new_hash, 'grid': new_grid.copy(), 'sequence': new_sequence, 'score': score})
                    queue.append((new_hash, new_sequence))
                    
                    if score > self.best_score:
                        self.best_score = score
                    improved = True
                    self.stats['expanded'] += 1
                
                if self.stats['expanded'] >= self.max_states:
                    break
            
            if self.stats['expanded'] % 500 == 0 and self.stats['expanded'] > 0:
                print(f"  ... {self.stats['expanded']} estados, {len(queue)} fila, best_score={self.best_score}")
        
        print(f"  ❌ Nível não resolvido. {self.stats['expanded']} estados explorados.")
        return None
    
    def _restore_state(self, archive_entry: Dict):
        """Restaura estado a partir do archive."""
        self.wrapper.step(GameAction.RESET)
        for action_id in archive_entry['sequence']:
            act = ACTION_MAP.get(action_id)
            if act:
                try:
                    self.wrapper.step(act)
                except:
                    break
    
    def _get_levels(self) -> int:
        """Obtém níveis completados atuais."""
        try:
            fd = self.wrapper.step(GameAction.RESET)
            return getattr(fd, 'levels_completed', 0)
        except:
            return 0


# ========== V60 SOLVER ==========

class V60Solver:
    """
    Solver completo V60 para ARC-AGI-3.
    
    Fases:
    0 — Reconhecimento de jogo (GameAnalyzer)
    1 — Archive Replay BFS (com heurísticas)
    """
    
    def __init__(self, game_id: str, seed: int = 0):
        self.game_id = game_id
        self.seed = seed
        self.wrapper = None
        self.catalog = None
        self.solutions = {}  # level_index -> solution_sequence
        self.total_levels = 0
        self.solved_levels = set()
    
    def init(self):
        """Inicializa ambiente."""
        a = Arcade()
        envs = a.get_environments()
        target = [e for e in envs if e.game_id.startswith(self.game_id)]
        if not target:
            print(f"[V60] ERRO: Jogo {self.game_id} não encontrado!")
            return False
        
        self.wrapper = a.make(target[0].game_id, seed=self.seed, save_recording=True)
        self.info = target[0]
        
        # Descobrir total de níveis
        fd = self.wrapper.step(GameAction.RESET)
        self.total_levels = getattr(fd, 'win_levels', 6)
        print(f"[V60] Jogo: {self.game_id}, níveis: {self.total_levels}")
        return True
    
    def run(self):
        """Executa solver completo."""
        if not self.init():
            return {'error': 'Falha ao inicializar'}
        
        print(f"\n{'='*60}")
        print(f"  V60 Solver — {self.game_id}")
        print(f"{'='*60}")
        
        # FASE 0: Reconhecimento
        print(f"\n{'─'*40}")
        print("  FASE 0: RECONHECIMENTO")
        print(f"{'─'*40}")
        
        analyzer = GameAnalyzer(self.wrapper)
        self.catalog = analyzer.analyze()
        
        # FASE 1: BFS para cada nível
        print(f"\n{'─'*40}")
        print("  FASE 1: BFS ARCHIVE REPLAY")
        print(f"{'─'*40}")
        
        start_time = time.time()
        for level_idx in range(self.total_levels):
            print(f"\n  --- Nível {level_idx+1}/{self.total_levels} ---")
            
            bfs = ArchiveReplayBFS(self.wrapper, self.catalog)
            solution = bfs.search(max_depth=200)
            
            if solution:
                self.solutions[level_idx] = solution
                self.solved_levels.add(level_idx)
                print(f"  ✅ Nível {level_idx+1} resolvido! {len(solution)} ações: {solution[:10]}...")
            else:
                print(f"  ❌ Nível {level_idx+1} falhou.")
                break  # BFS falhou, próximo nível pode precisar de reset global
        
        elapsed = time.time() - start_time
        
        result = {
            'game_id': self.game_id,
            'levels_solved': len(self.solved_levels),
            'levels_total': self.total_levels,
            'solutions': {str(k): v for k, v in self.solutions.items()},
            'time_seconds': round(elapsed, 2),
            'success': len(self.solved_levels) == self.total_levels,
        }
        
        print(f"\n{'='*60}")
        print(f"  RESULTADO V60 — {self.game_id}")
        print(f"  ✅ Níveis resolvidos: {len(self.solved_levels)}/{self.total_levels}")
        print(f"  ⏱ Tempo: {elapsed:.1f}s")
        if len(self.solved_levels) > 0:
            print(f"  🔍 Soluções: {len(self.solutions)} níveis")
            for k, v in self.solutions.items():
                print(f"     Nível {k+1}: {len(v)} ações: {str(v[:15])}...")
        print(f"{'='*60}")
        
        return result


def main():
    """
    Ponto de entrada.
    
    Uso:
        python v60.py [game_id]
        python v60.py --all
    """
    print(f"\n{'='*60}")
    print("  V60 — ARC-AGI-3 Solver (API arc_agi 0.1.0)")
    print(f"{'='*60}")
    
    args = sys.argv[1:]
    
    if not args or '--help' in args:
        print(f"\n  Uso: python v60.py <game_id>")
        print(f"  Ex:  python v60.py sp80")
        print(f"       python v60.py cn04")
        print(f"       python v60.py --all")
        return
    
    if '--all' in args:
        a = Arcade()
        envs = a.get_environments()
        results = {}
        for env in envs:
            game_id = env.game_id.split('-')[0]
            solver = V60Solver(game_id)
            result = solver.run()
            results[game_id] = result
            with open(f'v60_{game_id}_result.json', 'w') as f:
                json.dump(result, f, indent=2, default=str)
        
        total_wins = sum(1 for r in results.values() if r.get('success'))
        print(f"\n{'='*60}")
        print(f"  BENCHMARK V60 COMPLETO")
        print(f"  Jogos resolvidos: {total_wins}/{len(envs)}")
        print(f"{'='*60}")
        
        with open('v60_benchmark_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
    else:
        game_id = args[0]
        solver = V60Solver(game_id)
        result = solver.run()
        
        # Salvar resultado
        with open(f'v60_{game_id}_result.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nResultado salvo em v60_{game_id}_result.json")


if __name__ == '__main__':
    main()
