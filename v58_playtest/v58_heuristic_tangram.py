"""
v58_heuristic_tangram.py — Heurística de Tangram/Encaixe Expansível

Baseada no playtest manual de Senhor no cn04:
- ACTION5 = girar 90° (na maioria das peças)
- ACTION5 = CRESCER (na peça roxa — EXCEÇÃO!)
- ACTION6 = selecionar peça + crescer (amarela do meio)
- Até 5 cliques na mesma peça para crescer progressivamente
- Pontas vermelhas = pontos de conexão
- Sombra cinza oculta pontas em níveis avançados
- Formas: U, E, L, pequeno (tangram)

Extraído de:
https://github.com/niclas349/ARC-AGI-3
"""

import json
from typing import Dict, List, Optional, Tuple, Set
from arc_agi import Arcade


class TangramHeuristic:
    """
    Heurística específica para jogos de TANGRAM EXPANSÍVEL (cn04-style).
    
    Detecta o padrão de encaixe com peças que crescem progressivamente
    e precisam ser giradas para encaixar pontas vermelhas.
    """
    
    # Padrão cn04: ACTION6 com efeito, cliques múltiplos possíveis
    # Peças podem ter ACTION5 = girar ou ACTION5 = crescer
    TANGRAM_PATTERN = {
        'has_pecas_expansiveis': True,
        'action6_func': 'select_or_grow',
        'max_cliques': 5,
    }
    
    def __init__(self, game_id: str, arcade: Arcade, catalog: Dict = None):
        self.game_id = game_id
        self.arcade = arcade
        self.catalog = catalog or {}
        self.is_tangram_game = False
        self.solution_sequence = []
        self.pieces_info = []
    
    def matches_pattern(self) -> bool:
        """Verifica se o jogo corresponde ao padrão tangram."""
        if not self.catalog:
            return False
        
        acts = self.catalog.get('actions', {})
        
        # cn04: ACTION6 tem efeito principal
        act6_has = acts.get(6, {}).get('has_effect', False)
        
        # Detectar peças expansíveis
        has_expand = self.catalog.get('has_pecas_expansiveis', False)
        max_cliques = self.catalog.get('max_cliques', 1)
        
        if act6_has and max_cliques > 1:
            self.is_tangram_game = True
            return True
        
        if act6_has:
            # Pode ser tangram sem expansão ou encaixe simples
            self.is_tangram_game = True
            return True
        
        return False
    
    def analyze_pieces(self) -> List[Dict]:
        """
        Analisa as peças disponíveis no nível atual.
        
        Retorna:
        - Cada peça com nome, cor, posição, tamanho
        - Identifica qual peça cresce com clique vs com ACTION5
        - Detecta pontas vermelhas (conexões)
        - Detecta sombra cinza
        """
        state = self.arcade.get_state()
        sprites = state.get('sprites', [])
        grid = state.get('grid', [])
        
        pieces = []
        for sprite in sprites:
            name = sprite.get('name', '')
            color = sprite.get('color', 0)
            pos = sprite.get('position', {})
            size = sprite.get('size', {})
            tags = sprite.get('tags', [])
            
            piece = {
                'name': name,
                'color': color,
                'position': pos,
                'size': size,
                'tags': tags,
                'grows_with_click': False,
                'grows_with_space': False,
                'rotates_with_space': True,  # default
                'has_red_tips': False,
                'shape': self._classify_shape(name, size),
            }
            
            # Detectar se a peça tem pontas vermelhas
            piece['has_red_tips'] = self._detect_red_tips(sprite, grid)
            
            pieces.append(piece)
        
        self.pieces_info = pieces
        return pieces
    
    def _detect_red_tips(self, sprite: Dict, grid: List) -> bool:
        """
        Detecta se uma peça tem pontas vermelhas (conexões).
        
        No cn04, as pontas vermelhas (cor 2) indicam pontos de conexão.
        Em níveis avançados, sombra cinza (cor 12/13) pode ocultá-las.
        """
        pos = sprite.get('position', {})
        size = sprite.get('size', {})
        
        x, y = pos.get('x', 0), pos.get('y', 0)
        w, h = size.get('width', 1), size.get('height', 1)
        
        # Verificar pixels ao redor da peça
        for dx in range(-1, w + 1):
            for dy in range(-1, h + 1):
                px, py = x + dx, y + dy
                if 0 <= py < len(grid) and 0 <= px < len(grid[0]):
                    color = grid[py][px]
                    if color == 2:  # Vermelho = ponta de conexão
                        return True
                    if color in [12, 13]:  # Cinza = sombra (oculta ponta)
                        # Sombra pode indicar ponta oculta
                        pass
        
        return False
    
    def _classify_shape(self, name: str, size: Dict) -> str:
        """
        Classifica a forma da peça baseado em nome e tamanho.
        
        Senhor descreveu formas: 'E', 'jtinha', 'U', 'L', 'pequeno'
        """
        w = size.get('width', 0)
        h = size.get('height', 0)
        
        # Heurística simples baseada em proporções
        if 'tuvkdkhdokr' in name or w <= 1 or h <= 1:
            return 'small_pin'
        if w >= 4 and h >= 3:
            return 'big_shape'  # 'E' - forma grande
        if w >= 3 and h >= 2:
            return 'medium_shape'  # 'U' - forma média
        if w >= 2 and h >= 2:
            return 'L_shape'  # L - forma menor
        return 'unknown'
    
    def generate_solution(self) -> List[Dict]:
        """
        Gera sequência de ações para resolver puzzle de tangram.
        
        Baseado na descoberta de Senhor:
        1. Identificar todas as peças
        2. Para cada peça que cresce:
           - ACTION6 repetido N vezes (até max_cliques)
        3. Para cada peça que gira:
           - ACTION1-4 para posicionar
           - ACTION5 para girar até encaixar
        4. Encaixar pontas vermelhas
        """
        if not self.is_tangram_game:
            return []
        
        pieces = self.analyze_pieces()
        
        solution = []
        
        # Estratégia genérica de tangram:
        # Para cada peça, tentar expandir e encaixar
        for i, piece in enumerate(pieces):
            piece_solution = {
                'piece': piece['name'],
                'color': piece['color'],
                'shape': piece['shape'],
                'steps': []
            }
            
            # Passo 1: Selecionar a peça (ACTION6)
            piece_solution['steps'].append({
                'action': 6,
                'target': piece['position'],
                'desc': f'Selecionar peça {piece["name"]}'
            })
            
            # Passo 2: Se cresce com clique, repetir ACTION6
            if piece.get('grows_with_click'):
                max_cliques = self.catalog.get('max_cliques', 3)
                for _ in range(max_cliques - 1):
                    piece_solution['steps'].append({
                        'action': 6,
                        'target': piece['position'],
                        'desc': f'Crescer peça {piece["name"]} (clique extra)'
                    })
            
            # Passo 3: Se cresce com ACTION5, usar espaço
            if piece.get('grows_with_space'):
                piece_solution['steps'].append({
                    'action': 5,
                    'desc': f'Crescer peça {piece["name"]} com ACTION5'
                })
            
            # Passo 4: Mover em direção a outras peças
            piece_solution['steps'].append({
                'action': 'move_toward_center',
                'desc': f'Mover peça {piece["name"]} para centro'
            })
            
            # Passo 5: Tentar ACTION5 para girar
            if piece.get('rotates_with_space'):
                piece_solution['steps'].append({
                    'action': 5,
                    'desc': f'Girar peça {piece["name"]}'
                })
            
            solution.append(piece_solution)
        
        self.solution_sequence = solution
        return solution
    
    def execute_solution(self) -> bool:
        """
        Executa a solução gerada.
        
        Para cada peça:
        1. ACTION6 para selecionar
        2. Se cresce com clique: repetir ACTION6 (2-5x)
        3. ACTION1-4 para mover
        4. ACTION5 para girar
        5. Repetir até encaixar
        """
        if not self.solution_sequence:
            print("[TANGRAM] Nenhuma solução gerada.")
            return False
        
        print(f"[TANGRAM] Executando solução com {len(self.solution_sequence)} peças...")
        
        for piece_solution in self.solution_sequence:
            print(f"  Processando peça: {piece_solution['piece']}")
            
            for step in piece_solution['steps']:
                try:
                    action = step['action']
                    if action in [1, 2, 3, 4, 5]:
                        self.arcade.execute_action(action)
                    elif action == 6:
                        target = step.get('target', {})
                        if target and isinstance(target, dict):
                            self.arcade.execute_action(6, x=target.get('x', 0), y=target.get('y', 0))
                        else:
                            self.arcade.execute_action(6)
                    elif action == 'move_toward_center':
                        # Mover em direção ao centro por alguns passos
                        for _ in range(3):
                            self.arcade.execute_action(2)  # default: direita
                            self.arcade.execute_action(4)  # default: baixo
                except Exception as e:
                    print(f"    Erro: {e}")
                    return False
        
        # Verificar resultado
        state = self.arcade.get_state()
        if state.get('level', 0) > 1:
            print(f"[TANGRAM] ✅ Nível completado!")
            return True
        
        print(f"[TANGRAM] ❌ Peças posicionadas mas nível não completou.")
        return False
    
    def save_pattern_memory(self) -> Dict:
        """Salva o padrão tangram para memória."""
        return {
            'game_id': self.game_id,
            'pattern': 'tangram',
            'is_tangram_game': self.is_tangram_game,
            'pieces_analyzed': self.pieces_info,
            'solution_sequence': self.solution_sequence,
            'catalog_snapshot': self.catalog,
        }


if __name__ == '__main__':
    print("Módulo v58_heuristic_tangram carregado com sucesso.")
    print("Heurística de Tangram Expansível (cn04-style) disponível.")
