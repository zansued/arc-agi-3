#!/opt/venv/bin/python3
"""Debug: understand ARC-AGI-3 win mechanics."""
import sys
sys.path.insert(0, '/a0/usr/workdir')
from arc_agi import Arcade
from arcengine import GameAction, GameState

# Test multiple games
for game_id in ['sp80', 'tn36', 'bp35', 'cn04']:
    print(f'=== {game_id} ===')
    arcade = Arcade()
    game = arcade.make(game_id)
    game.reset()

    # Try each action type
    for action in [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3,
                   GameAction.ACTION4, GameAction.ACTION5, GameAction.ACTION6,
                   GameAction.ACTION7, GameAction.RESET]:
        # Skip actions that require data
        if action in [GameAction.ACTION6, GameAction.ACTION7, GameAction.RESET]:
            continue

        game.reset()
        for i in range(30):
            fd = game.step(action)
            if fd.levels_completed > 0 or fd.win_levels > 0 or fd.state == GameState.WIN:
                print(f'  {action.name} step {i}: levels={fd.levels_completed}, win_levels={fd.win_levels}, state={fd.state}')
                break

    # Try ACTION6 with various data params
    for x in [0, 16, 32, 48]:
        for y in [0, 16, 32, 48]:
            game.reset()
            fd = game.step(GameAction.ACTION6, data={'x': x, 'y': y})
            if fd.levels_completed > 0 or fd.win_levels > 0:
                print(f'  ACTION6(x={x},y={y}) step 0: levels={fd.levels_completed}, win_levels={fd.win_levels}, state={fd.state}')

    print()