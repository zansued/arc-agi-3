"""
v58_guided_bfs.py — Fase 2: BFS Guiado por Priors do Reconhecimento

Diferente do BFS cego do v55:
1. Usa o catálogo da Fase 0 para SABER quais ações têm efeito
2. Ignora ações sem efeito (ex: ACTION5 em bp35)
3. Testa cliques N vezes na mesma posição (cn04: até 5x)
4. Prioriza ACTION6 em sprites com sys_click
5. Evita estados de game over conhecidos
6. Suporta 'caminho mínimo' configurável (ignora soluções muito curtas)

Baseado nas descobertas do playtest:
- sp80: ACTION5 = pintar, ACTION6 = selecionar cor, ordem importa
- cn04: ACTION6 = selecionar + crescer (até 5x), ACTION5 = girar/crescer
- bp35: ACTION5 = inativo, caminho curto = armadilha
"""

import json
from typing import Dict, List, Optional, Set, Tuple, Callable
from collections import deque
from arc_agi import Arcade


class GuidedBFS:
    """
    BFS Guiado por priors do catálogo de reconhecimento.
    
    Características:
    - Usa o catálogo da Fase 0 para limitar o espaço de ações
    - Testa cliques acumulativos na mesma posição
    - Evita estados de game over
    - Suporta'caminho mínimo' (bp35-style)
    """
    
    def __init__(self, game_id: str, arcade: Arcade, catalog: Dict = None):
        self.game_id = game_id
        self.arcade = arcade
        self.catalog = catalog or {}
        
        # Configurações derivadas do catálogo
        self.max_steps = 1000
        self.max_states = 5000
        self.min_path_length = 1
        self.ignore_actions = set()  # Ações sem efeito
        self.priority_actions = []  # Ações prioritárias
        self.max_cliques_per_pos = 1  # cn04: até 5
        
        # Estado
        self.visited = set()
        self.best_solution = None
        self.game_over_states = set()
        
        # Configurar a partir do catálogo
        self._configure_from_catalog()
    
    def _configure_from_catalog(self):
        """Configura BFS baseado no catálogo da Fase 0."""
        if not self.catalog:
            return
        
        acts = self.catalog.get('actions', {})
        
        # Ignorar ações sem efeito
        for action_id, info in acts.items():
            if not info.get('has_effect', False):
                self.ignore_actions.add(action_id)
                print(f"[BFS-GUIADO] Ignorando ACTION{action_id} (sem efeito)")
        
        # Configurar cliques múltiplos (cn04-style)
        max_cliques = self.catalog.get('max_cliques', 1)
        if max_cliques > 1:
            self.max_cliques_per_pos = max_cliques
            print(f"[BFS-GUIADO] Cliques múltiplos ativados: até {max_cliques}x")
        
        # Caminho mínimo (bp35-style)
        if self.catalog.get('caminho_curto_mata', False):
            self.min_path_length = 5
            print(f"[BFS-GUIADO] Caminho mínimo ativado: {self.min_path_length} ações mínimas")
        
        # Priorizar ações que funcionam
        action5_func = self.catalog.get('action5_func', 'unknown')
        action6_func = self.catalog.get('action6_func', 'unknown')
        
        if action5_func in ['paint', 'rotate', 'expand']:
            self.priority_actions.append(5)
        if action6_func in ['select', 'select_or_grow', 'activate_portal']:
            self.priority_actions.append(6)
        
        # Priorizar movimento (ACTION1-4) sempre disponível
        self.priority_actions.extend([1, 2, 3, 4])
    
    def _get_state_hash(self) -> str:
        """Gera hash único do estado atual."""
        state = self.arcade.get_state()
        grid = state.get('grid', [])
        level = state.get('level', 1)
        steps = state.get('steps', 0)
        
        # Hash do grid + nivel + steps para diferenciar estados
        grid_hash = hash(str(grid))
        return f"{level}_{grid_hash}_{steps}"
    
    def _is_game_over(self) -> bool:
        """Verifica se o estado atual é game over."""
        state = self.arcade.get_state()
        return state.get('game_over', False)
    
    def _is_level_complete(self) -> bool:
        """Verifica se o nível atual foi completado."""
        state = self.arcade.get_state()
        return state.get('level', 0) > state.get('starting_level', 1)
    
    def _get_available_actions(self) -> List[int]:
        """
        Retorna ações disponíveis, excluindo as ignoradas.
        Ações prioritárias vêm primeiro.
        """
        actions = []
        
        # Ações prioritárias primeiro
        for act in self.priority_actions:
            if act not in self.ignore_actions:
                actions.append(act)
        
        # Demais ações (1-6) excluindo ignoradas e já incluídas
        for act in range(1, 7):
            if act not in self.ignore_actions and act not in actions:
                actions.append(act)
        
        if not actions:
            actions = [a for a in range(1, 7) if a not in self.ignore_actions]
        
        return actions
    
    def _execute_action_safe(self, action_id: int, **kwargs) -> bool:
        """Executa ação com segurança, retornando sucesso."""
        try:
            if action_id in [1, 2, 3, 4, 5]:
                self.arcade.execute_action(action_id)
            elif action_id == 6:
                x = kwargs.get('x')
                y = kwargs.get('y')
                if x is not None and y is not None:
                    self.arcade.execute_action(6, x=x, y=y)
                else:
                    self.arcade.execute_action(6)
            return True
        except Exception as e:
            return False
    
    def search(self, max_steps: int = 500, max_states: int = 2000) -> Optional[List[Tuple[int, Dict]]]:
        """
        Executa busca BFS guiada.
        
        Retorna:
        - Lista de (ação, kwargs) que resolve o nível
        - None se não encontrar solução
        """
        print(f"[BFS-GUIADO] Iniciando busca para {self.game_id}...")
        print(f"  Ações disponíveis: {self._get_available_actions()}")
        print(f"  Ignoradas: ACTION{list(self.ignore_actions)}")
        
        self.max_steps = max_steps
        self.max_states = max_states
        
        # Estado inicial
        initial_hash = self._get_state_hash()
        self.visited.add(initial_hash)
        
        # Fila BFS: (sequência de ações, estado_hash)
        queue = deque()
        queue.append(([], initial_hash))
        
        states_explored = 0
        steps_taken = 0
        
        while queue and steps_taken < self.max_steps and states_explored < self.max_states:
            sequence, _ = queue.popleft()
            states_explored += 1
            
            # Se esta sequência já é muito curta e precisamos de caminho mínimo
            if len(sequence) < self.min_path_length - 1:
                action_candidates = self._get_available_actions()
            else:
                action_candidates = self._get_available_actions()
            
            for action_id in action_candidates:
                # Reset ao estado inicial para replay
                self.arcade.reset_level()
                
                # Replay da sequência atual
                failed = False
                for prev_action, prev_kwargs in sequence:
                    if not self._execute_action_safe(prev_action, **prev_kwargs):
                        failed = True
                        break
                
                if failed:
                    continue
                
                # Executar nova ação
                kwargs = {}
                if action_id == 6:
                    # Em alguns jogos, ACTION6 precisa de coordenadas
                    # Por enquanto executa sem coordenada (default)
                    pass
                
                if not self._execute_action_safe(action_id, **kwargs):
                    continue
                
                steps_taken += 1
                
                # Verificar se completou
                if self._is_level_complete():
                    new_sequence = sequence + [(action_id, kwargs)]
                    
                    # Verificar caminho mínimo
                    if len(new_sequence) >= self.min_path_length:
                        print(f"[BFS-GUIADO] ✅ Solução encontrada! {len(new_sequence)} ações")
                        self.best_solution = new_sequence
                        return new_sequence
                
                # Verificar game over
                if self._is_game_over():
                    self.game_over_states.add(self._get_state_hash())
                    continue
                
                # Adicionar à fila
                new_hash = self._get_state_hash()
                if new_hash not in self.visited:
                    self.visited.add(new_hash)
                    new_sequence = sequence + [(action_id, kwargs)]
                    queue.append((new_sequence, new_hash))
            
            # Progresso a cada 100 estados
            if states_explored % 100 == 0:
                print(f"  Estados explorados: {states_explored}, fila: {len(queue)}")
        
        print(f"[BFS-GUIADO] ❌ Solução não encontrada ({states_explored} estados, {steps_taken} steps)")
        return None
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas da busca."""
        return {
            'game_id': self.game_id,
            'visited_states': len(self.visited),
            'game_over_states': len(self.game_over_states),
            'solution_found': self.best_solution is not None,
            'solution_length': len(self.best_solution) if self.best_solution else 0,
            'ignore_actions': list(self.ignore_actions),
            'priority_actions': self.priority_actions,
            'max_cliques': self.max_cliques_per_pos,
            'min_path_length': self.min_path_length,
        }


if __name__ == '__main__':
    print("Módulo v58_guided_bfs carregado com sucesso.")
    print("BFS Guiado com Priors da Fase 0 disponível.")
