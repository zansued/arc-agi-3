"""
Planner: Encontra sequência de interações (sinapses) que leva à vitória.
"""
from typing import List, Tuple, Dict
from arc_oop.core import World, Direction, GameObject, Player, Block, Transformer, Goal, Wall, SynapticSignal

def find_winning_sequence(world: World) -> List[Direction]:
    """Encontra sequência de ações que leva à vitória"""
    player_pos = world.objects['player'].position
    block = world.objects['block']
    transformer = world.objects.get('transformer_1')
    goal = world.objects.get('goal_1')
    
    if not transformer or not goal:
        return []
    
    actions = []
    # Fase 1: Player e bloco para o transformer
    dx_t = transformer.position[0] - player_pos[0]
    dy_t = transformer.position[1] - player_pos[1]
    
    if dx_t < 0:
        actions.extend([Direction.UP] * abs(dx_t))
    elif dx_t > 0:
        actions.extend([Direction.DOWN] * dx_t)
    
    if dy_t < 0:
        actions.extend([Direction.LEFT] * abs(dy_t))
    elif dy_t > 0:
        actions.extend([Direction.RIGHT] * dy_t)
    
    # Fase 2: Para o goal
    dx_g = goal.position[0] - transformer.position[0]
    dy_g = goal.position[1] - transformer.position[1]
    
    if dx_g < 0:
        actions.extend([Direction.UP] * abs(dx_g))
    elif dx_g > 0:
        actions.extend([Direction.DOWN] * dx_g)
    
    if dy_g < 0:
        actions.extend([Direction.LEFT] * abs(dy_g))
    elif dy_g > 0:
        actions.extend([Direction.RIGHT] * dy_g)
    
    return actions[:world.max_steps]
