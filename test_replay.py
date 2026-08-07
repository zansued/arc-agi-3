from arc_agi import Arcade
from arcengine.enums import GameAction
import os
os.environ["ARC_AGI_ENV_DIR"] = "/a0/usr/workdir/environment_files"
a = Arcade()
g = a.make("sp80")

# Test replay path
path = [GameAction.ACTION4, GameAction.ACTION4, GameAction.ACTION4, GameAction.ACTION5]
print("Path:", [str(a) for a in path])

g.reset()
print("After reset", end="")
for step_num, act in enumerate(path):
    result = g.step(act)
    if result is None:
        print(f"  Step {step_num}: {act} returned None!")
        break
    else:
        print(f"  Step {step_num}: {act} -> state={result.state}")
else:
    print("  Path completed successfully!")
    
# Test with single step replay
print("\n--- Single step after reset ---")
g.reset()
r1 = g.step(GameAction.ACTION4)
print(f"Step1: {r1 is not None} state={r1.state if r1 else None}")
r2 = g.step(GameAction.ACTION4)
print(f"Step2: {r2 is not None} state={r2.state if r2 else None}")

# Now test: reset -> step -> step (not reset+step each time)
print("\n--- What happens if we DON'T reset between? ---")
g.reset()
r1 = g.step(GameAction.ACTION4)
print(f"Step1: {r1 is not None}")
r2 = g.step(GameAction.ACTION4)
print(f"Step2: {r2 is not None}")

# And a fresh reset between
print("\n--- Fresh reset between each ---")
g.reset()
r1 = g.step(GameAction.ACTION4)
print(f"A: {r1 is not None}")
g.reset()
r2 = g.step(GameAction.ACTION4)
print(f"B: {r2 is not None}")
