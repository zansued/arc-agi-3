from arc_agi import Arcade
import os, inspect
os.environ["ARC_AGI_ENV_DIR"] = "/a0/usr/workdir/environment_files"
a = Arcade()
g = a.make("sp80")

# inspect step signature
sig = inspect.signature(g.step)
print("step signature:", sig)

h = g.reset()
print("frame has name?", hasattr(h, "name"), getattr(h, "name", "N/A"))
print("frame has game_id?", hasattr(h, "game_id"), getattr(h, "game_id", "N/A"))

# Try step without passing the action as frame (maybe step(game_action) is the API?)
try:
    r = g.step(g.action_space[0])
    print("step(just action):", type(r), r)
except Exception as e:
    print("step(just action) ERROR:", e)

# Try with explicit GameAction enum value
try:
    r = g.step(h, 1)  # just the int
    print("step(frame, 1):", type(r))
except Exception as e:
    print("step(frame, 1) ERROR:", e)
