"""
v58_game_analyzer.py — Fase 0: Reconhecimento de Jogo

Executa cada ação 1x em diferentes sprites e observa o resultado
para construir um Catálogo de Comportamentos.

Descobriu (playtest manual):
- sp80: ACTION5 = pintar, ACTION6 = selecionar cor do tanque
- cn04: ACTION5 = girar/crescer, ACTION6 = selecionar peça + crescer (cliques múltiplos)
- bp35: ACTION5 = inativo, ACTION6 = ativar portal, evitar caminho curto
"""

import json
import time
from typing import Dict, List, Optional, Any
from arc_agi import Arcade


class GameAnalyzer:
    """
    Fase 0: Reconhecimento de Jogo
    
    Estratégia:
    1. Resetar jogo
    2. Para cada ação (1-6), executar em sprite neutro
    3. Observar se o grid mudou
    4. Identificar sprites especiais (sys_click, cores, tags)
    5. Construir Catálogo de Comportamentos
    """
    
    def __init__(self, game_id: str, arcade: Arcade):
        self.game_id = game_id
        self.arcade = arcade
        self.catalog = {
            'game_id': game_id,
            'actions': {},  # action_id -> {has_effect: bool, effect_type: str}
            'sprites': [],  # sprites especiais identificados
            'has_tanque_cores': False,  # sp80-style paint tank
            'has_pecas_expansiveis': False,  # cn04-style expandable pieces
            'has_portais': False,  # bp35-style portals
            'action5_func': 'unknown',  # paint | rotate | expand | inactive
            'action6_func': 'unknown',  # select | activate | grow
            'caminho_curto_mata': False,  # bp35-style
            'max_cliques': 1,  # cn04: até 5 cliques na mesma peça
        }
        self.grid_history = []
    
    def analyze(self) -> Dict:
        """Executa análise completa do jogo."""
        print(f"[FASE 0] Analisando jogo: {self.game_id}")
        
        # Passo 1: Capturar estado inicial
        self._capture_state('initial')
        
        # Passo 2: Testar cada ação (1-6) em sprite neutro
        for action_id in range(1, 7):
            self._test_action(action_id)
        
        # Passo 3: Identificar sprites especiais
        self._identify_sprites()
        
        # Passo 4: Se ACTION6 tem efeito, testar cliques múltiplos
        if self.catalog['actions'].get(6, {}).get('has_effect', False):
            self._test_multiple_clicks()
        
        # Passo 5: Consolidar diagnóstico
        self._diagnose_game_type()
        
        return self.catalog
    
    def _capture_state(self, label: str) -> Dict:
        """Captura estado atual do jogo."""
        state = self.arcade.get_state()
        if state is None:
            state = {'grid': [], 'sprites': [], 'level': 0, 'steps': 0}
        self.grid_history.append({
            'label': label,
            'grid': state.get('grid'),
            'sprites': state.get('sprites', []),
            'level': state.get('level', 0),
            'steps': state.get('steps', 0),
        })
        return state
    
    def _test_action(self, action_id: int):
        """Testa se uma ação tem efeito no jogo."""
        # Reset para estado inicial antes do teste
        self.arcade.reset_level()
        # Após reset, executar step inicial para wrapper real ter estado
        try:
            self.arcade.execute_action(1)
        except:
            pass
        state_before = self._capture_state(f'before_action_{action_id}')
        
        # Executar ação
        try:
            raw = self.arcade.execute_action(action_id)
            result = {'success': bool(raw), 'error': None}
        except Exception as e:
            result = {'success': False, 'error': str(e)}
        
        state_after = self._capture_state(f'after_action_{action_id}')
        
        # Verificar se o grid mudou
        grid_before = state_before.get('grid', [])
        grid_after = state_after.get('grid', [])
        grid_changed = str(grid_before) != str(grid_after) if len(grid_before) > 0 and len(grid_after) > 0 else False
        level_changed = state_before.get('level') != state_after.get('level')
        # Alguns estados não têm 'steps'; usar a mudança de grid/level como detector de efeito
        has_effect = grid_changed or level_changed
        
        self.catalog['actions'][action_id] = {
            'has_effect': has_effect,
            'grid_changed': grid_changed,
            'level_changed': level_changed,
            'error': result.get('error'),
        }
        
        print(f"  ACTION{action_id}: efeito={grid_changed or level_changed}, "
              f"grid={'sim' if grid_changed else 'não'}, "
              f"level={'sim' if level_changed else 'não'}")
    
    def _identify_sprites(self):
        """Identifica sprites especiais no estado atual."""
        state = self.arcade.get_state()
        sprites = state.get('sprites', [])
        
        special_sprites = []
        for sprite in sprites:
            entry = {
                'name': sprite.get('name', 'unknown'),
                'color': sprite.get('color'),
                'position': sprite.get('position'),
                'tags': sprite.get('tags', []),
                'size': sprite.get('size'),
            }
            
            # Detectar sprites especiais
            if 'sys_click' in sprite.get('tags', []):
                entry['type'] = 'clicavel'
            if sprite.get('color') in ['green', 3]:
                entry['possible_type'] = 'portal'
            if sprite.get('color') in ['purple', 6, 'magenta', 6]:
                entry['possible_type'] = 'armadilha'
            
            special_sprites.append(entry)
        
        self.catalog['sprites'] = special_sprites
    
    def _test_multiple_clicks(self):
        """Testa se cliques múltiplos na mesma posição têm efeito cumulativo.
        
        Descoberta do cn04: até 5 cliques na peça amarela do meio
        fazem ela crescer progressivamente.
        """
        for n_cliques in [2, 3, 4, 5, 6]:
            self.arcade.reset_level()
            
            # Executar ACTION6 N vezes na mesma posição
            for _ in range(n_cliques):
                result = self.arcade.execute_action(6)
            
            state = self._capture_state(f'after_{n_cliques}x_clique')
            
            # Se o grid mudou significativamente, cliques múltiplos têm efeito
            if state['grid'] != self.grid_history[0]['grid']:
                self.catalog['max_cliques'] = n_cliques
                self.catalog['has_pecas_expansiveis'] = True
                print(f"  Cliques múltiplos detectados! {n_cliques} cliques modificam o grid")
                break
    
    def _diagnose_game_type(self):
        """Diagnostica o tipo de jogo baseado no catálogo."""
        acts = self.catalog['actions']
        
        # sp80-style: ACTION5 tem efeito (pintar), ACTION6 seleciona
        if acts.get(5, {}).get('has_effect') and acts.get(6, {}).get('has_effect'):
            self.catalog['action5_func'] = 'paint'
            self.catalog['action6_func'] = 'select'
            self.catalog['has_tanque_cores'] = True
            print(f"  ▶ Diagnóstico: PUZZLE DE PINTURA (sp80-style)")
        
        # cn04-style: ACTION6 tem efeito, ACTION5 pode girar
        elif acts.get(6, {}).get('has_effect'):
            if acts.get(5, {}).get('has_effect'):
                self.catalog['action5_func'] = 'rotate'
            else:
                self.catalog['action5_func'] = 'inactive'
            self.catalog['action6_func'] = 'select_or_grow'
            if self.catalog['has_pecas_expansiveis']:
                print(f"  ▶ Diagnóstico: TANGRAM EXPANSÍVEL (cn04-style)")
            else:
                print(f"  ▶ Diagnóstico: ENCAIXE DE FORMAS (cn04-style)")
        
        # bp35-style: ACTION5 inativo, ACTION6 ativa portais
        elif not acts.get(5, {}).get('has_effect') and acts.get(6, {}).get('has_effect'):
            self.catalog['action5_func'] = 'inactive'
            self.catalog['action6_func'] = 'activate_portal'
            self.catalog['has_portais'] = True
            self.catalog['caminho_curto_mata'] = True  # bp35-style
            print(f"  ▶ Diagnóstico: NAVEGAÇÃO COM PORTAIS (bp35-style)")
        
        # Fallback: genérico
        else:
            print(f"  ▶ Diagnóstico: JOGO GENÉRICO")
    
    def get_catalog_json(self) -> str:
        """Retorna catálogo como JSON para salvar."""
        return json.dumps(self.catalog, indent=2)


if __name__ == '__main__':
    # Teste local
    print("Módulo v58_game_analyzer carregado com sucesso.")
    print("Execute via v58.py para testar com jogos reais.")
