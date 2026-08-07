#!/usr/bin/env python3
"""tn36 - test actions via ActionInput."""
import sys
sys.path.insert(0, '/a0/usr/workdir')
from arcengine import GameAction, ActionInput
from environment_files.tn36.ef4dde99.tn36 import Tn36

def run(g, n=50):
    for _ in range(n):
        g.step()
        if g.nyhaiggftp: return True
        if g.pgualuszrs: return False
    return g.nyhaiggftp

baseline = [32, 72, 26, 40, 30, 55, 62]

g = Tn36()
total = len(g._levels)
print(f"tn36 - {total} levels")

for li in range(total):
    print(f"Level {li}: ", end="", flush=True)
    solved = False

    # Test each baseline action as ActionInput
    for ba in baseline:
        g.set_level(li)
        run(g, 5)
        inp = ActionInput(id=ba, data={'x': 0, 'y': 0})
        g.perform_action(inp)
        if run(g, 50):
            print(f"BASELINE{ba} OK ", end="", flush=True)
            solved = True
            break

    # Test ACTION6 at various camera positions
    if not solved:
        for pos in [(160,120), (100,100), (200,180), (300,200), (50,50), (400,300)]:
            g.set_level(li)
            run(g, 5)
            inp = ActionInput(id=GameAction.ACTION6, data={'x': pos[0], 'y': pos[1]})
            g.perform_action(inp)
            if run(g, 100):
                print(f"CLICK{pos} OK ", end="", flush=True)
                solved = True
                break

    # Try step() with action set directly
    if not solved:
        for ba in baseline:
            g.set_level(li)
            run(g, 5)
            g.action = ActionInput(id=ba, data={'x': 0, 'y': 0})
            g.step()
            if run(g, 50):
                print(f"ACTION{ba} OK ", end="", flush=True)
                solved = True
                break

    print("OK" if solved else "FAIL")

print()
