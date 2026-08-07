"""
ARC-OOP Core: Framework Orientado a Objetos para ARC-AGI.

Inspirado no sistema nervoso da Aplysia californica (lesma do mar) de Eric Kandel:
- Cada objeto no jogo = neurônio com estado interno e respostas fixas
- Cada interação = sinapse entre neurônios
- Aprendizado = reforço de sequências sinápticas que levam à vitória
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from enum import Enum


class Direction(Enum):
    """Direções de movimento (como estímulos sensoriais)"""
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)
    
    def to_action_id(self) -> int:
        """Mapeia direção para ACTION_ID do arcengine"""
        mapping = {
            Direction.UP: 1,
            Direction.DOWN: 2,
            Direction.LEFT: 3,
            Direction.RIGHT: 4
        }
        return mapping[self]
    
    def to_keyboard(self) -> str:
        """Mapeia direção para tecla"""
        mapping = {
            Direction.UP: "ArrowUp",
            Direction.DOWN: "ArrowDown",
            Direction.LEFT: "ArrowLeft",
            Direction.RIGHT: "ArrowRight"
        }
        return mapping[self]


@dataclass
class SynapticSignal:
    """Sinal sináptico: estímulo que um neurônio envia a outro"""
    source_id: str          # ID do neurônio/objeto de origem
    target_id: str          # ID do neurônio/objeto de destino
    signal_type: str        # 'push', 'transform', 'collect', 'block'
    data: Dict[str, Any] = field(default_factory=dict)
    strength: float = 1.0   # Força sináptica (aprendizado)


class GameObject:
    """
    Classe base para todo objeto no ARC-AGI.
    
    Analogia: NEURÔNIO da lesma.
    - Cada neurônio tem estado interno (potencial de membrana)
    - Resposta FIXA a estímulos específicos
    - Conecta-se a outros neurônios via sinapses
    """
    
    def __init__(self, id: str, position: Tuple[int, int], properties: dict = None):
        self.id = id
        self.position = position  # (x, y) no grid 64×64
        self.properties = properties or {}
        self.active = True
        self.interaction_count = 0  # Habituação: quantas vezes foi estimulado
        
        # Sinapses: conexões com outros objetos (aprendizadas por experiência)
        self.synapses: List[SynapticSignal] = []
    
    def respond(self, signal: SynapticSignal) -> Optional[SynapticSignal]:
        """
        Resposta a um estímulo sináptico.
        Como um neurônio: se o estímulo é forte o suficiente, dispara.
        """
        self.interaction_count += 1
        
        # Habituação: respostas repetidas enfraquecem
        effective_strength = signal.strength * (1.0 / (1.0 + 0.1 * self.interaction_count))
        
        if effective_strength < 0.5:
            return None  # Habituação: não responde mais
        
        return self._execute_response(signal)
    
    def _execute_response(self, signal: SynapticSignal) -> Optional[SynapticSignal]:
        """Executa a resposta específica do tipo de objeto"""
        raise NotImplementedError
    
    def get_state(self) -> dict:
        """Retorna estado interno do neurônio"""
        return {
            'id': self.id,
            'position': self.position,
            'active': self.active,
            'interaction_count': self.interaction_count
        }


class Player(GameObject):
    """
    Player: neurônio sensorial-motor.
    Recebe estímulos do ambiente, emite sinais motores (movimento/push).
    """
    def __init__(self, position: Tuple[int, int]):
        super().__init__('player', position, {
            'type': 'player',
            'color': 1,  # Valor no grid
            'steps_per_action': 1
        })
        self.pushed_object: Optional[str] = None  # Objeto sendo empurrado agora
    
    def _execute_response(self, signal: SynapticSignal) -> Optional[SynapticSignal]:
        if signal.signal_type == 'move':
            direction = signal.data.get('direction')
            if direction:
                dx, dy = direction.value
                self.position = (self.position[0] + dx, self.position[1] + dy)
                return SynapticSignal(
                    source_id=self.id,
                    target_id='block',
                    signal_type='push',
                    data={'direction': direction, 'new_position': self.position}
                )
        return None


class Block(GameObject):
    """
    Bloco empurrável: neurônio de 'veículo'.
    Carrega propriedades (forma, cor, rotação) que são transformadas.
    É o objeto central do puzzle: tudo gira em torno de transformá-lo.
    """
    def __init__(self, position: Tuple[int, int], 
                 shape: int = 5, 
                 color: int = 9,
                 rotation: int = 270):
        super().__init__('block', position, {
            'type': 'block',
            'shape': shape,
            'color': color,
            'rotation': rotation,
            'start_shape': shape,
            'start_color': color,
            'start_rotation': rotation
        })
        self.transformers_passed = 0  # Contador de transformações
    
    def _execute_response(self, signal: SynapticSignal) -> Optional[SynapticSignal]:
        if signal.signal_type == 'push':
            direction = signal.data.get('direction')
            if direction:
                dx, dy = direction.value
                self.position = (self.position[0] + dx, self.position[1] + dy)
                return SynapticSignal(
                    source_id=self.id,
                    target_id='transformer',
                    signal_type='check_transform',
                    data={'position': self.position}
                )
        return None
    
    def apply_transform(self, transform_type: str, value: int):
        """Aplica uma transformação ao bloco (como sinapse que modifica neurônio)"""
        if transform_type == 'rotation':
            self.properties['rotation'] = (self.properties['rotation'] + value) % 360
        elif transform_type == 'shape':
            self.properties['shape'] = value
        elif transform_type == 'color':
            self.properties['color'] = value
        self.transformers_passed += 1
    
    def can_deliver(self, target: dict) -> bool:
        """Verifica se bloco está na configuração para entrega"""
        return (self.properties['shape'] == target.get('shape', self.properties['start_shape']) and
                self.properties['color'] == target.get('color', self.properties['start_color']) and
                self.properties['rotation'] == target.get('rotation', 0))


class Transformer(GameObject):
    """
    Transformador: neurônio de processamento.
    Quando o bloco entra em contato, modifica suas propriedades.
    
    Tipos de transformação:
    - shape: muda forma
    - color: muda cor
    - rotation: muda rotação (90°, 180°, 270°)
    """
    def __init__(self, position: Tuple[int, int], 
                 transform_type: str = 'rotation',
                 effect: int = 90):
        super().__init__('transformer', position, {
            'type': 'transformer',
            'transform_type': transform_type,
            'effect': effect
        })
        self.block_in_contact: Optional[str] = None
    
    def _execute_response(self, signal: SynapticSignal) -> Optional[SynapticSignal]:
        if signal.signal_type == 'check_transform':
            block_pos = signal.data.get('position')
            if block_pos and self._is_block_inside(block_pos):
                return SynapticSignal(
                    source_id=self.id,
                    target_id='block',
                    signal_type='transform',
                    data={
                        'transform_type': self.properties['transform_type'],
                        'effect': self.properties['effect']
                    }
                )
        return None
    
    def _is_block_inside(self, block_pos: Tuple[int, int]) -> bool:
        """Verifica se o bloco está dentro do transformador"""
        # Transformador ocupa tile único: compara posição
        return block_pos == self.position
    
    def can_transform(self) -> bool:
        """Verifica se transformador pode operar (não está em cooldown)"""
        return self.block_in_contact is None


class Goal(GameObject):
    """
    Goal: neurônio receptor final.
    Quando o bloco (na configuração correta) é entregue, ativa vitória.
    """
    def __init__(self, position: Tuple[int, int],
                 target_shape: int = 5,
                 target_color: int = 9,
                 target_rotation: int = 0):
        super().__init__('goal', position, {
            'type': 'goal',
            'target_shape': target_shape,
            'target_color': target_color,
            'target_rotation': target_rotation
        })
        self.completed = False
    
    def _execute_response(self, signal: SynapticSignal) -> Optional[SynapticSignal]:
        if signal.signal_type == 'deliver' and not self.completed:
            block_state = signal.data.get('block_state', {})
            if self._check_delivery(block_state):
                self.completed = True
                return SynapticSignal(
                    source_id=self.id,
                    target_id='world',
                    signal_type='level_complete',
                    data={'goal_id': self.id}
                )
        return None
    
    def _check_delivery(self, block_state: dict) -> bool:
        """Verifica se bloco está na configuração alvo"""
        return (block_state.get('shape') == self.properties['target_shape'] and
                block_state.get('color') == self.properties['target_color'] and
                block_state.get('rotation') == self.properties['target_rotation'])


class Wall(GameObject):
    """
    Parede: neurônio inibidor.
    Bloqueia passagem. Não dispara sinapses.
    """
    def __init__(self, position: Tuple[int, int]):
        super().__init__('wall', position, {'type': 'wall'})
    
    def _execute_response(self, signal: SynapticSignal) -> Optional[SynapticSignal]:
        # Paredes não respondem a estímulos
        return None


class World:
    """
    Mundo: o ecossistema neural completo.
    Contém todos os objetos (neurônios) e gerencia interações (sinapses).
    """
    
    def __init__(self, game_id: str = "ls20"):
        self.game_id = game_id
        self.objects: Dict[str, GameObject] = {}
        self.synaptic_pathways: List[Tuple[str, str, str]] = []  # (source, target, signal_type)
        self.win_condition_met = False
        self.steps_taken = 0
        self.max_steps = 42  # LS20: 42 steps per level
    
    def add_object(self, obj: GameObject):
        """Adiciona um neurônio ao sistema"""
        self.objects[obj.id] = obj
    
    def add_synaptic_pathway(self, source_id: str, target_id: str, signal_type: str):
        """
        Adiciona uma via sináptica entre dois neurônios.
        Exemplo: 'player' → 'block' via 'push'
        """
        self.synaptic_pathways.append((source_id, target_id, signal_type))
    
    def get_object_at(self, position: Tuple[int, int]) -> Optional[GameObject]:
        """Encontra objeto em determinada posição"""
        for obj in self.objects.values():
            if obj.position == position:
                return obj
        return None
    
    def check_collision(self, position: Tuple[int, int]) -> bool:
        """Verifica se posição está ocupada por objeto sólido"""
        obj = self.get_object_at(position)
        if obj and isinstance(obj, Wall):
            return True
        if obj and isinstance(obj, Block):
            return True  # Bloco não pode ocupar mesmo tile que outro bloco
        return False
    
    def simulate_action(self, direction: Direction) -> List[SynapticSignal]:
        """
        Simula uma ação no mundo e retorna as sinapses disparadas.
        
        Fluxo: Player recebe estímulo → move/empurra → bloco responde →
        transformador checa → goal verifica entrega → win?
        """
        signals: List[SynapticSignal] = []
        player = self.objects.get('player')
        new_pos = (player.position[0] + direction.value[0],
                   player.position[1] + direction.value[1])
        
        if self.check_collision(new_pos):
            return signals  # Movimento bloqueado
        
        # Player move e emite sinal de push para objetos adjacentes
        player.position = new_pos
        for obj in self.objects.values():
            if obj.id != 'player' and obj.position == new_pos:
                signals.append(SynapticSignal('player', obj.id, 'interact', {}))
        
        self.steps_taken += 1
        return signals
    
    def get_state_summary(self) -> dict:
        """Resumo completo do estado do mundo"""
        summary = {
            'game_id': self.game_id,
            'steps': self.steps_taken,
            'max_steps': self.max_steps,
            'win_condition': self.win_condition_met,
            'objects': {}
        }
        for obj_id, obj in self.objects.items():
            summary['objects'][obj_id] = obj.get_state()
        return summary
