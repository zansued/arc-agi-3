#!/opt/venv/bin/python3
"""Debug: understand ARC-AGI-3 GameState and win mechanics."""
import sys
sys.path.insert(0, '/a0/usr/workdir')
from arc_agi import Arcade
from arcengine import GameAction, GameState, FrameDataRaw

# Print all GameState members
print('=== GameState MEMBERS ===')
for name in dir(GameState):
    if not name.startswith('_'):
        val = getattr(GameState, name)
        print(f'  {name} = {val}')

# Print FrameDataRaw fields
print()
print('=== FrameDataRaw FIELDS ===')
for field in FrameDataRaw.model_fields:
    print(f'  {field}')

# Test sp80 with all actions
print()
print('=== TESTING sp80 ===')
arcade = Arcade()
game = arcade.make('sp80')

# Try each action 30 times
for action in [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3,
               GameAction.ACTION4, GameAction.ACTION5, GameAction.ACTION6]:
    game.reset()
    found = False
    for i in range(30):
        if action == GameAction.ACTION6:
            fd = game.step(action, data={'x': 32, 'y': 32})
        else:
            fd = game.step(action)
        if fd.levels_completed > 0 or (hasattr(fd, 'win_levels') and fd.win_levels > 0):
            print(f'  {action.name} step {i}: levels={fd.levels_completed}, state={fd.state}')
            found = True
            break
    if not found:
        print(f'  {action.name}: no progress after 30 steps')

# Try with data params
print()
print('=== TESTING WITH DATA ===')
for x in [16, 32, 48]:
    for y in [16, 32, 48]:
        game.reset()
        fd = game.step(GameAction.ACTION6, data={'x': x, 'y': y})
        if fd.levels_completed > 0:
            print(f'  ACTION6(x={x},y={y}): levels={fd.levels_completed}, state={fd.state}')
        fd = game.step(GameAction.ACTION7, data={'x': x, 'y': y})
        if fd.levels_completed > 0:
            print(f'  ACTION7(x={x},y={y}): levels={fd.levels_completed}, state={fd.state}')