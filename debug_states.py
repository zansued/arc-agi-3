#!/opt/venv/bin/python3
"""Debug: understand ARC-AGI-3 state transitions."""
import sys
sys.path.insert(0, '/a0/usr/workdir')
from arc_agi import Arcade
from arcengine import GameAction, GameState

arcade = Arcade()
game = arcade.make('sp80')

# Reset and observe
fd = game.reset()
print(f'Initial state: {fd.state}')
print(f'Initial levels: {fd.levels_completed}')
print(f'Frame type: {type(fd)}')
print(f'Frame dir: {[x for x in dir(fd) if not x.startswith("_")]}')
print()

# Try actions and observe
for i in range(5):
    fd = game.step(GameAction.ACTION1)
    print(f'Step {i}: state={fd.state}, levels={fd.levels_completed}, score={getattr(fd, "score", "N/A")}')

# Check if levels_completed changes after more steps
print()
print('Trying more actions...')
for i in range(20):
    fd = game.step(GameAction.ACTION1)
    if fd.levels_completed > 0:
        print(f'Step {i+5}: levels={fd.levels_completed}, state={fd.state}')
        break
else:
    print(f'After 25 steps: levels={fd.levels_completed}, state={fd.state}')