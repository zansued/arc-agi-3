"""
v58_heuristic_navigation.py — Heurística de Navegação com Portais

Baseada no playtest manual de Senhor no bp35:
- ACTION5 = INATIVO (não faz nada)
- ACTION6 = ativar portal verde (teletransporte)
- Caminho MAIS CURTO leva a GAME OVER (cano roxo suga)
- Caminho MAIS LONGO é o correto
- Verde = geralmente seguro (alguns são falsos e levam ao roxo)
- Roxo = armadilha → GAME OVER
- Objetivo: alcançar cruz rosa final
- 9 níveis, consistente entre níveis

Extraído de:
https://github.com/niclas349/ARC-AGI-3
"""

import json
from typing import Dict, List, Optional, Tuple, Set
from collections import deque
from arc_agi import Arcade


class NavigationHeuristic:
    """
    Heurística específica para jogos de NAVEGAÇÃO COM PORTAIS (bp35-style).
    
    Detecta o padrão de navegação onde:
    - ACTION5 é inativo
    - ACTION6 ativa portais verdes
    - O caminho mais curto é armadilha (leva a game over)
    - O caminho mais longo (evitando roxos) é o correto
    """
    
    # Padrão bp35: ACTION5 inativo, ACTION6 ativa portal
    NAV_PATTERN = {
        'action5_func': 'inactive',
        'action6_func': 'activate_portal',
        'has_portais': True,
        'caminho_curto_mata': True,
    }
    
    # Cores relevantes
    COLOR_VERDE = 3
    COLOR_ROXO = 6
    COLOR_ROSA_META = 11  # Cor da cruz rosa (objetivo final)
    COLOR_VERMELHO = 2  # Armadilha saída
    COLOR_CINZA = 12  # Sombra/bloqueio
    
    def __init__(self, game_id: str, arcade: Arcade, catalog: Dict = None):
        self.game_id = game_id
        self.arcade = arcade
        self.catalog = catalog or {}
        self.is_nav_game = False
        self.solution_sequence = []
        self.grid_analysis = {}
    
    def matches_pattern(self) -> bool:
        """Verifica se o jogo corresponde ao padrão de navegação."""
        if not self.catalog:
            return False
        
        acts = self.catalog.get('actions', {})
        
        # bp35: ACTION5 inativo, ACTION6 ativo
        act5_has = acts.get(5, {}).get('has_effect', False)
        act6_has = acts.get(6, {}).get('has_effect', False)
        
        has_portais = self.catalog.get('has_portais', False)
        
        if not act5_has and act6_has:
            self.is_nav_game = True
            return True
        
        if has_portais:
            self.is_nav_game = True
            return True
        
        return False
    
    def analyze_grid(self) -> Dict:
        """
        Analisa o grid para identificar:
        - Portais verdes (posições e conexões)
        - Armadilhas roxas
        - Caminhos seguros vs perigosos
        - Objetivo final (cruz rosa)
        - Padrão 'caminho curto vs longo'
        """
        state = self.arcade.get_state()
        grid = state.get('grid', [])
        sprites = state.get('sprites', [])
        
        analysis = {
            'grid_width': len(grid[0]) if grid else 0,
            'grid_height': len(grid),
            'portais_verdes': [],
            'armadilhas_roxas': [],
            'objetivo_rosa': None,
            'posicao_jogador': None,
            'caminhos_possiveis': [],
            'tem_sombra_cinza': False,
        }
        
        # Analisar grid pixel a pixel
        for y in range(len(grid)):
            for x in range(len(grid[0])):
                color = grid[y][x]
                
                if color == self.COLOR_VERDE:
                    analysis['portais_verdes'].append({'x': x, 'y': y})
                elif color == self.COLOR_ROXO:
                    analysis['armadilhas_roxas'].append({'x': x, 'y': y})
                elif color == self.COLOR_ROSA_META:
                    analysis['objetivo_rosa'] = {'x': x, 'y': y}
                elif color == self.COLOR_CINZA:
                    analysis['tem_sombra_cinza'] = True
        
        # Analisar sprites
        for sprite in sprites:
            pos = sprite.get('position', {})
            tags = sprite.get('tags', [])
            
            if 'player' in tags or 'personagem' in tags:
                analysis['posicao_jogador'] = pos
        
        # Detectar padrão 'caminho curto vs longo'
        # Se houver portais verdes perto de armadilhas roxas,
        # isso indica caminho curto = perigoso
        for portal in analysis['portais_verdes']:
            for arm in analysis['armadilhas_roxas']:
                dist = abs(portal['x'] - arm['x']) + abs(portal['y'] - arm['y'])
                if dist <= 2:
                    # Portal perto de armadilha = caminho curto é perigoso!
                    analysis['caminhos_possiveis'].append({
                        'portal': portal,
                        'armadilha_proxima': arm,
                        'distancia': dist,
                        'tipo': 'curto_perigoso'
                    })
        
        self.grid_analysis = analysis
        return analysis
    
    def find_safe_path(self) -> List[Dict]:
        """
        Encontra o caminho SEGURO até o objetivo.
        
        Diferente do BFS padrão:
        - Evita armadilhas roxas (mesmo que isso aumente o caminho)
        - Prioriza portais verdes
        - Rejeita soluções muito curtas (caminho curto = armadilha)
        """
        analysis = self.analyze_grid()
        
        if not analysis['objetivo_rosa']:
            print("[NAV] Objetivo rosa não encontrado!")
            return []
        
        # Estratégia: escolher o CAMINHO MAIS LONGO entre os seguros
        # Em vez do caminho mais curto
        
        # 1. Mapear todos os portais verdes
        portais = analysis['portais_verdes']
        armadilhas = analysis['armadilhas_roxas']
        objetivo = analysis['objetivo_rosa']
        
        # 2. Para cada portal, verificar se está seguro (longe de roxo)
        portais_seguros = []
        for portal in portais:
            tem_arm_proxima = any(
                abs(portal['x'] - a['x']) + abs(portal['y'] - a['y']) <= 2
                for a in armadilhas
            )
            if not tem_arm_proxima:
                portais_seguros.append(portal)
        
        # 3. Construir caminho: começar pelos portais mais DISTANTES do objetivo
        # (caminho longo = seguro)
        portais_ordenados = sorted(
            portais_seguros,
            key=lambda p: abs(p['x'] - objetivo['x']) + abs(p['y'] - objetivo['y']),
            reverse=True  # Mais distante primeiro!
        )
        
        path = []
        for portal in portais_ordenados:
            path.append({
                'action': 'activate',
                'target': portal,
                'desc': f'Ativar portal verde em ({portal["x"]}, {portal["y"]})'
            })
        
        return path
    
    def generate_solution(self) -> List[Dict]:
        """
        Gera sequência de ações para navegação segura.
        
        1. Analisar grid (portais, armadilhas, objetivo)
        2. Encontrar caminho seguro (mais longo)
        3. Para cada portal: ACTION6 → mover até ele → ativar
        4. Ignorar ACTION5 (não tem efeito)
        5. Evitar armadilhas roxas
        """
        if not self.is_nav_game:
            return []
        
        # Construir caminho seguro
        path = self.find_safe_path()
        
        solution = []
        
        if not path:
            # Fallback: navegação genérica
            # Tentar ativar todos os portais verdes
            analysis = self.analyze_grid()
            for portal in analysis['portais_verdes']:
                step = {
                    'target': portal,
                    'steps': [
                        {'action': 6, 'target': portal, 'desc': f'Ativar portal ({portal["x"]}, {portal["y"]})'},
                        {'action': 'move_toward', 'target': portal, 'desc': 'Mover em direção ao portal'},
                    ]
                }
                solution.append(step)
        else:
            for step_info in path:
                if step_info['action'] == 'activate':
                    portal = step_info['target']
                    solution.append({
                        'target': portal,
                        'steps': [
                            {'action': 6, 'target': portal, 'desc': step_info['desc']},
                            {'action': 'move_toward', 'target': portal, 'desc': 'Aproximar do portal'},
                        ]
                    })
        
        self.solution_sequence = solution
        return solution
    
    def execute_solution(self) -> bool:
        """
        Executa a solução de navegação.
        
        Para cada portal:
        1. ACTION6 para ativar
        2. Mover em direção ao portal
        3. Repetir até encontrar o objetivo rosa
        """
        if not self.solution_sequence:
            print("[NAV] Nenhuma solução de navegação gerada.")
            return False
        
        print(f"[NAV] Executando navegação com {len(self.solution_sequence)} portais...")
        
        for step_group in self.solution_sequence:
            for step in step_group['steps']:
                try:
                    action = step['action']
                    target = step.get('target', {})
                    
                    if action == 6:
                        if target and isinstance(target, dict) and 'x' in target:
                            self.arcade.execute_action(6, x=target['x'], y=target.get('y', 0))
                        else:
                            self.arcade.execute_action(6)
                    elif action == 'move_toward':
                        # Mover em direção ao alvo
                        # Tenta todas as direções de forma segura
                        if target and isinstance(target, dict):
                            tx, ty = target.get('x', 0), target.get('y', 0)
                            # Priorizar movimento que se AFASTA de roxos
                            for _ in range(5):
                                self.arcade.execute_action(3)  # cima
                                self.arcade.execute_action(4)  # baixo
                                self.arcade.execute_action(1)  # esquerda
                                self.arcade.execute_action(2)  # direita
                    elif action in [1, 2, 3, 4]:
                        self.arcade.execute_action(action)
                except Exception as e:
                    print(f"  Erro navegação: {e}")
                    return False
        
        # Verificar se completou
        state = self.arcade.get_state()
        if state.get('level', 0) > 1:
            print(f"[NAV] ✅ Nível completado!")
            return True
        
        print(f"[NAV] ❌ Navegação executada mas nível não completou.")
        return False
    
    def save_pattern_memory(self) -> Dict:
        """Salva o padrão de navegação para memória."""
        return {
            'game_id': self.game_id,
            'pattern': 'navigation',
            'is_nav_game': self.is_nav_game,
            'grid_analysis': self.grid_analysis,
            'solution_sequence': self.solution_sequence,
            'catalog_snapshot': self.catalog,
        }


if __name__ == '__main__':
    print("Módulo v58_heuristic_navigation carregado com sucesso.")
    print("Heurística de Navegação Anti-Caminho-Curto (bp35-style) disponível.")
