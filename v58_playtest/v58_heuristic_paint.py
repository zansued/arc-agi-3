"""
v58_heuristic_paint.py — Heurística de Pintura em Camadas

Baseada no playtest manual de Senhor no sp80:
- ACTION5 = pintar (aplica cor no centro do grid)
- ACTION6 = selecionar cor do tanque de tinta
- Ordem importa (roxo→laranja→azul→amarelo = camadas da base ao topo)
- Meia esfera (tuvkdkhdokr) = pintura localizada com ACTION6
- Referência no canto superior esquerdo = cor alvo

Extraído de:
https://github.com/niclas349/ARC-AGI-3
"""

import json
from typing import Dict, List, Optional, Tuple
from arc_agi import Arcade


class PaintHeuristic:
    """
    Heurística específica para jogos de PINTURA EM CAMADAS (sp80-style).
    
    Detecta se o jogo atual é de pintura comparando o catálogo de
    comportamentos com o padrão conhecido.
    """
    
    # Padrão sp80 conhecido do playtest
    PAINT_PATTERN = {
        'action5_func': 'paint',
        'action6_func': 'select',
        'has_tanque_cores': True,
        'sprites_with_sys_click': True,
    }
    
    # Ordem de pintura descoberta por Senhor:
    # 1º Roxo (base) → 2º Laranja (diagonal) → 3º Azul → 4º Amarelo (topo)
    PAINT_ORDER = ['roxo', 'laranja', 'azul', 'amarelo', 'verde', 'vermelho', 'branco', 'preto']
    
    def __init__(self, game_id: str, arcade: Arcade, catalog: Dict = None):
        self.game_id = game_id
        self.arcade = arcade
        self.catalog = catalog or {}
        self.is_paint_game = False
        self.solution_sequence = []
    
    def matches_pattern(self) -> bool:
        """Verifica se o jogo atual corresponde ao padrão de pintura."""
        if not self.catalog:
            return False
        
        acts = self.catalog.get('actions', {})
        
        # Padrão sp80: ambas ACTION5 e ACTION6 têm efeito
        act5_has = acts.get(5, {}).get('has_effect', False)
        act6_has = acts.get(6, {}).get('has_effect', False)
        
        if act5_has and act6_has:
            self.is_paint_game = True
            return True
        
        return False
    
    def analyze_paint_setup(self) -> Dict:
        """
        Analisa a configuração de pintura do nível atual.
        
        Retorna:
        - colors_available: cores disponíveis no tanque
        - target_reference: cor alvo (canto superior esquerdo)
        - has_meia_esfera: se tem a ferramenta pequena
        - border_color: cor da moldura
        """
        state = self.arcade.get_state()
        sprites = state.get('sprites', [])
        grid = state.get('grid', [])
        
        info = {
            'colors_available': [],
            'target_reference': None,
            'has_meia_esfera': False,
            'border_color': None,
            'grid_size': state.get('grid_size'),
        }
        
        # Método 1: se houver sprites, usar como antes
        if sprites:
            for sprite in sprites:
                tags = sprite.get('tags', [])
                name = sprite.get('name', '')
                color = sprite.get('color')
                pos = sprite.get('position', {})
                if 'sys_click' in tags:
                    info['colors_available'].append({
                        'name': name,
                        'color': color,
                        'position': pos
                    })
                if 'tuvkdkhdokr' in name or ('sys_click' in tags and self._is_meia_esfera(sprite)):
                    info['has_meia_esfera'] = True
                if 'bodekplurlf' in name or 'moldura' in name:
                    info['border_color'] = color
        
        # Método 2: escanear grid se não houver sprites
        if not info['colors_available'] and grid and len(grid) > 0:
            try:
                import numpy as np
                arr = np.array(grid, dtype=np.int8)
                unique_vals, _ = np.unique(arr, return_counts=True)
                color_map = {3:'roxo',4:'laranja',5:'azul',6:'amarelo',7:'verde',
                             8:'vermelho',9:'branco',10:'preto',11:'cinza',12:'marrom'}
                for val in unique_vals:
                    v = int(val)
                    if v not in (-1, 0, 1):  # ignorar vazio/fundo/borda
                        name = color_map.get(v, f'cor_{v}')
                        info['colors_available'].append({
                            'name': name,
                            'color': name,
                            'position': {'x': 0, 'y': 0}
                        })
            except Exception as e:
                pass  # fallback silencioso
        
        return info
    
    def _is_meia_esfera(self, sprite: Dict) -> bool:
        """Detecta se um sprite é a meia esfera (ferramenta pequena)."""
        # No sp80, a meia esfera é tuvkdkhdokr
        # Ela é pequena, clicável, e pinta localmente quando clicada
        name = sprite.get('name', '')
        size = sprite.get('size', {})
        
        if 'tuvkdkhdokr' in name:
            return True
        if 'sys_click' in sprite.get('tags', []) and size.get('width', 0) <= 2:
            return True
        return False
    
    def generate_solution(self) -> List[Dict]:
        """
        Gera a sequência de ações para resolver o puzzle de pintura.
        
        Baseado na descoberta de Senhor:
        1. Identificar cores disponíveis
        2. Ordenar por camada (base → topo)
        3. Para cada cor: ACTION6(selecionar) → ACTION1-4(posicionar) → ACTION5(pintar)
        4. Se tiver meia esfera: ACTION6 nela no momento certo
        """
        if not self.is_paint_game:
            return []
        
        # Garantir que o wrapper tenha um grid real antes de analisar
        # (apenas se analyze_paint_setup puder scanear grid vazio)
        setup = self.analyze_paint_setup()
        
        # Se não encontrou cores (grid vazio), tentar step inicial
        if not setup['colors_available']:
            try:
                self.arcade.execute_action(1)
                setup = self.analyze_paint_setup()
            except:
                pass
        
        # Estratégia genérica de pintura:
        # Para cada cor disponível, tentar pintar
        solution = []
        
        for color_info in setup['colors_available']:
            color_name = color_info['color']
            
            # Se for meia esfera, usar ACTION6 no lugar de ACTION5
            if color_info.get('is_meia_esfera') or 'tuvkdkhdokr' in color_info.get('name', ''):
                color_entry = {
                    'action': 'select_and_paint_small',
                    'color': color_name,
                    'sequence': [
                        {'action': 6, 'target': color_info['position'], 'desc': f'Clicar na meia esfera {color_name}'},
                        {'action': 6, 'target': 'center', 'desc': f'Pintar pequeno com {color_name}'},
                    ]
                }
            else:
                # Tanque grande: selecionar com ACTION6, pintar com ACTION5
                color_entry = {
                    'action': 'select_and_paint',
                    'color': color_name,
                    'sequence': [
                        {'action': 6, 'target': color_info['position'], 'desc': f'Selecionar cor {color_name}'},
                        {'action': 5, 'target': 'center', 'desc': f'Pintar centro com {color_name}'},
                    ]
                }
            
            solution.append(color_entry)
        
        self.solution_sequence = solution
        return solution
    
    def execute_solution(self) -> bool:
        """Executa a solução gerada e retorna True se bem-sucedida."""
        if not self.solution_sequence:
            print("Nenhuma solução de pintura gerada.")
            return False
        
        print(f"[PAINT] Executando {len(self.solution_sequence)} ações de pintura...")
        
        for step in self.solution_sequence:
            for action in step['sequence']:
                try:
                    target = action.get('target')
                    # ACTION1-4: movimento direcional
                    if action['action'] in [1, 2, 3, 4]:
                        self.arcade.execute_action(action['action'])
                    # ACTION5: ação especial
                    elif action['action'] == 5:
                        self.arcade.execute_action(5)
                    # ACTION6: clique
                    elif action['action'] == 6:
                        if isinstance(target, tuple):
                            self.arcade.execute_action(6, x=target[0], y=target[1])
                        else:
                            self.arcade.execute_action(6)
                except Exception as e:
                    print(f"  Erro executando ação {action}: {e}")
                    return False
        
        # Verificar se o nível foi completado
        state = self.arcade.get_state()
        if state.get('level', 0) > 1:
            print(f"[PAINT] ✅ Nível completado!")
            return True
        
        print(f"[PAINT] ❌ Pintura executada mas nível não completou.")
        return False
    
    def save_pattern_memory(self) -> Dict:
        """Salva o padrão de pintura para memória."""
        return {
            'game_id': self.game_id,
            'pattern': 'paint',
            'is_paint_game': self.is_paint_game,
            'solution_sequence': self.solution_sequence,
            'catalog_snapshot': self.catalog,
        }


if __name__ == '__main__':
    print("Módulo v58_heuristic_paint carregado com sucesso.")
    print("Heurística de Pintura em Camadas (sp80-style) disponível.")
