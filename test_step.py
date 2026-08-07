from arc_agi import Arcade
import os
os.environ["ARC_AGI_ENV_DIR"] = "/a0/usr/workdir/environment_files"
a = Arcade()
g = a.make("sp80")
h = g.reset()
print("reset type:", type(h))
print("dir:", [x for x in dir(h) if not x.startswith("_")][:40])
print()
print("Has step?", hasattr(h, "step"))
print("action_space:", g.action_space)
# Try step with different action formats
for act in [g.action_space[0], int(g.action_space[0].value), 1, "ACTION1"]:
    try:
        h2 = g.reset()
        r = h2.step(act)
        print(f"  step({act}): result={r}, type={type(r).__name__ if r is not None else None}")
    except Exception as e:
        print(f"  step({act}): ERROR {e}")
