"""
v62_5_incremental_bfs.py — BFS Incremental com Deepcopy do Wrapper

Descoberta chave: deepcopy(wrapper) funciona!
- copy wrapper → step on copy → check win → enfileirar
- SEM RESET+replay = 100x mais rápido

Uso:
  python3 v62_5_incremental_bfs.py <game_id> [max_states] [max_levels]
"""
import sys
import copy
import json
import time
import numpy as np
from pathlib import Path
from collections import deque
from typing import Optional, List, Set, Tuple

sys.path.insert(0, '.')

from arc_agi import Arcade
from arcengine.enums import GameAction, GameState


# Mapeamento action_id → GameAction
ACTION_MAP = {i: GameAction[f'ACTION{i}'] for i in range(1, 8)}


class IncrementalBFS:
    """
    BFS incremental usando deepcopy do wrapper.
    
    Cada nó guarda deepcopy do wrapper (contém game state completo).
    Expande step(action) diretamente no wrapper copiado.
    SEM RESET+replay = ~300 expansões/segundo.
    """
    
    def __init__(self, game_id: str, max_states: int = 5000, max_levels: int = 9):
        self.game_id = game_id
        self.max_states = max_states
        self.max_levels = max_levels
        self.results = {
            'game_id': game_id,
            'solver': 'v62_5_incremental_bfs',
            'total_levels': 0,
            'solved_levels': 0,
            'levels': [],
            'total_expansions': 0,
            'duration_seconds': 0,
        }
    
    def _hash_state(self, wrapper) -> bytes:
        """Hash do grid renderizado para dedup."""
        try:
            game = wrapper._game
            sprites = game.current_level.get_sprites()
            grid = game.camera.render(sprites)
            return grid.tobytes()
        except:
            return b'error'
    
    def _check_win(self, wrapper) -> bool:
        """Verifica se o jogo venceu após último step."""
        game = wrapper._game
        if getattr(game, '_next_level', False):
            return True
        if getattr(game, '_state', None) == GameState.WIN:
            return True
        # Verificar se estado de jogo mudou para vitorioso
        state = getattr(game, '_state', None)
        if state and str(state) in ('WIN', 'GameState.WIN', 'COMPLETE'):
            return True
        return False
    
    def _get_available_actions(self, wrapper) -> List[int]:
        """Ações disponíveis para este jogo."""
        game = wrapper._game
        acts = getattr(game, '_available_actions', None)
        if acts is not None:
            return list(acts)
        return [1, 2, 3, 4]
    
    def solve_level(self, wrapper, level_index: int) -> Optional[List[int]]:
        """
        Resolve um nível usando BFS incremental.
        wrapper já deve estar no nível correto.
        """
        # Hash inicial
        initial_hash = self._hash_state(wrapper)
        initial_actions = self._get_available_actions(wrapper)
        
        # BFS queue: lista de (wrapper_copy, sequence)
        queue = deque()
        wrapper_copy = copy.deepcopy(wrapper)
        queue.append((wrapper_copy, []))
        
        visited: Set[bytes] = {initial_hash}
        expansions = 0
        
        while queue and expansions < self.max_states:
            current_wrapper, seq = queue.popleft()
            
            for act_id in initial_actions:
                expansions += 1
                
                # Clone wrapper
                w_clone = copy.deepcopy(current_wrapper)
                
                # Step diretamente no clone
                try:
                    act = ACTION_MAP[act_id]
                    _ = w_clone.step(act)
                except Exception as e:
                    continue
                
                # Check win
                if self._check_win(w_clone):
                    new_seq = seq + [act_id]
                    print(f"      SOLUCAO! {len(new_seq)} passos, {expansions} expansoes", flush=True)
                    return new_seq
                
                # Hash
                new_hash = self._hash_state(w_clone)
                
                # Dedup
                if new_hash not in visited and new_hash != initial_hash:
                    visited.add(new_hash)
                    new_seq = seq + [act_id]
                    queue.append((w_clone, new_seq))
                    
                    if len(visited) % 200 == 0:
                        print(f"      {len(visited)} estados, fila={len(queue)}, seq_len={len(new_seq)}", flush=True)
            
            if expansions % 1000 == 0:
                print(f"      {expansions} expansoes, {len(visited)} estados unicos", flush=True)
                if expansions >= self.max_states:
                    break
        
        print(f"      Fim: {expansions} expansoes, {len(visited)} unicos, SEM SOLUCAO", flush=True)
        return None
    
    def solve(self):
        """Resolve todos os níveis."""
        print(f"\n{'='*60}", flush=True)
        print(f"  V62.5 Incremental BFS — {self.game_id}", flush=True)
        print(f"  Limite: {self.max_states} estados/nivel", flush=True)
        print(f"{'='*60}", flush=True)
        
        start = time.time()
        
        a = Arcade()
        wrapper = a.make(self.game_id, seed=0, save_recording=False)
        wrapper.step(GameAction.RESET)
        game = wrapper._game
        
        total_levels = min(
            len(getattr(game, '_levels', [])),
            self.max_levels
        )
        self.results['total_levels'] = total_levels
        print(f"  Total levels: {total_levels}", flush=True)
        
        for level_idx in range(total_levels):
            print(f"\n  Nivel {level_idx+1}/{total_levels}...", flush=True)
            
            # Reset wrapper to ensure we're at this level
            wrapper.step(GameAction.RESET)
            
            solution = self.solve_level(wrapper, level_idx)
            
            level_result = {
                'level_index': level_idx,
                'solved': solution is not None,
                'steps': len(solution) if solution else 0,
                'solution': solution,
            }
            self.results['levels'].append(level_result)
            
            if solution:
                self.results['solved_levels'] += 1
                print(f"    >> Nivel {level_idx+1} resolvido! {len(solution)} passos", flush=True)
            else:
                print(f"    >> Nivel {level_idx+1} falhou", flush=True)
        
        self.results['duration_seconds'] = time.time() - start
        
        print(f"\n{'='*60}", flush=True)
        print(f"  RESULTADO: {self.results['solved_levels']}/{total_levels}", flush=True)
        print(f"  Duracao: {self.results['duration_seconds']:.1f}s", flush=True)
        print(f"  Expansoes totais: {self.results.get('total_expansions', 'N/A')}", flush=True)
        print(f"{'='*60}", flush=True)
        
        # Salvar
        out_path = Path(f"v62_5_{self.game_id}_result.json")
        out_path.write_text(json.dumps(self.results, indent=2, default=str))
        print(f"Resultado salvo em {out_path.name}", flush=True)
        
        return self.results


if __name__ == '__main__':
    args = sys.argv[1:]
    game_id = args[0] if len(args) > 0 else 'tu93'
    max_states = int(args[1]) if len(args) > 1 else 5000
    max_levels = int(args[2]) if len(args) > 2 else 9
    
    solver = IncrementalBFS(game_id, max_states=max_states, max_levels=max_levels)
    solver.solve()
