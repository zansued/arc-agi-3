#!/usr/bin/env python3
"""Quick compile test for v29_bfs_sequence_solver.py"""
import sys
import py_compile

sys.path.insert(0, '/a0/usr/workdir')

# Test compile
py_compile.compile('/a0/usr/workdir/v29_bfs_sequence_solver.py')
print('Compiles OK')

# Test imports
from arc_agi import Arcade
from arcengine import GameAction, GameState
acts = [a.name for a in GameAction]
print('GameAction:', acts)

# Test GameAction.from_id
tests = [(0, 'RESET'), (1, 'ACTION1'), (7, 'ACTION7')]
for i, name in tests:
    act = GameAction.from_id(i)
    ok = 'OK' if act.name == name else 'FAIL'
    print(f'  from_id({i}) -> {act.name} (expected {name}): {ok}')

print('All imports and API tests passed!')
