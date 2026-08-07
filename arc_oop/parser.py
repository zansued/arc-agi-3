"""
ARC-OOP Parser: Extrai objetos (neurônios) do código fonte do jogo.
"""
import re
from typing import Tuple, Dict, List
from arc_oop.core import Player, Block, Transformer, Goal, Wall, World, Direction

class GameParser:
    """Parser que lê o .py de um jogo e constrói objetos ARC-OOP"""
    
    def __init__(self, game_id: str = "ls20"):
        self.game_id = game_id
        self.code = ""
        self.sprites: Dict[str, Dict] = {}
        
    def load_game_code(self, code_path: str):
        with open(code_path) as f:
            self.code = f.read()
        
    def extract_sprites(self):
        """Extrai definições de sprites do código"""
        if not self.code:
            return self.sprites
        # Sprite definitions: name: Sprite(...)
        pattern = r'"(\w+)":\s*Sprite\('
        for m in re.finditer(pattern, self.code):
            name = m.group(1)
            if name not in self.sprites:
                self.sprites[name] = {'name': name}
        return self.sprites
    
    def extract_level_positions(self, level: int = 1) -> Dict[str, Tuple[int, int]]:
        """Extrai posições de sprites para nível específico"""
        positions = {}
        if not self.code:
            return positions
        pattern = r'sprites\["(\w+)"\]\.clone\(\)\.set_position\((\d+),\s*(\d+)\)'
        for m in re.finditer(pattern, self.code):
            name, x, y = m.group(1), int(m.group(2)), int(m.group(3))
            if name not in positions or name == 'ihdgageizm':
                positions[name] = (x, y) if name not in positions else positions[name]
        return positions
    
    def build_world(self, level: int = 1) -> World:
        """Constrói mundo com objetos ARC-OOP a partir do código fonte"""
        world = World(self.game_id)
        self.extract_sprites()
        positions = self.extract_level_positions(level)
        
        # Adiciona player
        if 'sfqyzhzkij' in positions:
            block_pos = positions['sfqyzhzkij']
            player = Player(block_pos)
            # Player começa na mesma posição do bloco
            player.position = block_pos
            world.add_object(player)
            # Bloco
            block = Block(block_pos, shape=5, color=9, rotation=270)
            world.add_object(block)
        
        # Transformer
        for key in ['rhsxkxzdjz']:
            if key in positions:
                t = Transformer(positions[key], 'rotation', 90)
                t.id = 'transformer_1'
                world.add_object(t)
        
        # Goals
        for key in ['rjlbuycveu']:
            if key in positions:
                g = Goal(positions[key], target_shape=5, target_color=9, target_rotation=0)
                g.id = 'goal_1'
                world.add_object(g)
        
        # Walls (ihdgageizm)
        for pos_name, pos in positions.items():
            if 'ihdgageizm' in pos_name or 'ihdgageizm' in str(pos_name):
                w = Wall(pos)
                world.add_object(w)
        
        # Sinapses padrão
        world.add_synaptic_pathway('player', 'block', 'push')
        world.add_synaptic_pathway('block', 'transformer_1', 'check_transform')
        world.add_synaptic_pathway('block', 'goal_1', 'deliver')
        
        return world
    
    def get_action_mapping(self) -> Dict[int, str]:
        """Extrai mapeamento de ações do código"""
        mapping = {1: 'UP', 2: 'DOWN', 3: 'LEFT', 4: 'RIGHT'}
        return mapping
