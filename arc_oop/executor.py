"""
Executor: Executa sequência de ações no arcengine ou browser.
"""
from typing import List, Dict, Optional
from arc_oop.core import Direction, World, Player, Block, Goal

def execute_on_arcengine(world: World, actions: List[Direction], game_obj) -> Dict:
    """Executa ações no arcengine"""
    from arcengine import ActionInput, GameAction
    
    results = []
    action_map = {
        Direction.UP: GameAction.ACTION1,
        Direction.DOWN: GameAction.ACTION2,
        Direction.LEFT: GameAction.ACTION3,
        Direction.RIGHT: GameAction.ACTION4
    }
    
    for direction in actions:
        action_id = action_map[direction]
        result = game_obj.perform_action(ActionInput(id=action_id))
        results.append({'action': direction.name, 'action_id': action_id, 'result': result})
        
        if hasattr(result, 'levels_completed') and result.levels_completed > 0:
            return {'status': 'WIN', 'steps': len(results), 'results': results}
    
    return {'status': 'NOT_FINISHED', 'steps': len(results), 'results': results}

def execute_on_browser(actions: List[Direction], focus_func, send_key_func, screenshot_func):
    """Executa ações no browser tool"""
    results = []
    for direction in actions:
        # Focar canvas
        focus_func()
        # Enviar tecla
        send_key_func(direction.to_keyboard())
        # Screenshot pós-ação
        screenshot_path = screenshot_func()
        results.append({'direction': direction.name, 'screenshot': screenshot_path})
    return {'status': 'EXECUTED', 'actions': len(results)}
