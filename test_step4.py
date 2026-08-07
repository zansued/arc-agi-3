from arc_agi import Arcade
import os
os.environ["ARC_AGI_ENV_DIR"] = "/a0/usr/workdir/environment_files"
a = Arcade()
g = a.make("sp80")

print("=== Trying step directly after reset ===")
for attempt in range(3):
    frame = g.reset()
    print(f"\nAttempt {attempt}:")
    print(f"  state={frame.state} lv_completed={frame.levels_completed} win={frame.win_levels}")
    for act in g.action_space:
        # reset each time for clean state
        g.reset()
        result = g.step(act)
        if result is not None:
            print(f"  {act}: OK state={result.state} lv={result.levels_completed} win={result.win_levels}")
        else:
            print(f"  {act}: None")
