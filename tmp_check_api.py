#!/usr/bin/env python3
"""Check the arc_agi environment wrapper API."""
import inspect
from arc_agi import Arcade
from arc_agi.wrapper import EnvironmentWrapper

# Find where LocalEnvironmentWrapper is defined
import arc_agi as a
src = inspect.getsource(a)
for line in src.split('\n'):
    if 'Local' in line or 'local' in line or 'Wrapper' in line:
        print(line.strip()[:200])

print("=== EnvironmentWrapper step ===")
src = inspect.getsource(EnvironmentWrapper.step)
for line in src.split('\n'):
    print(line)

print("=== EnvironmentWrapper reset ===")
src = inspect.getsource(EnvironmentWrapper.reset)
for line in src.split('\n'):
    print(line)
