from arc_agi import Arcade
import os
os.environ["ARC_AGI_ENV_DIR"] = "/a0/usr/workdir/environment_files"
a = Arcade()
g = a.make("sp80")

print("game type:", type(g))
print("game attrs:", [x for x in dir(g) if not x.startswith("_")][:30])
print()

h = g.reset()
print("frame type:", type(h))
print("Has levels_completed:", hasattr(h, "levels_completed"), getattr(h, "levels_completed", None))
print("Has win_levels:", hasattr(h, "win_levels"), getattr(h, "win_levels", None))
print()

# Try step on game
try:
    result = g.step(h, g.action_space[0])
    print("step result type:", type(result))
    print("step result dir:", [x for x in dir(result) if not x.startswith("_")][:20])
except Exception as e:
    print("ERROR step:", e)
