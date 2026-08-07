from arc_agi import Arcade
from arcengine.enums import GameAction
import os, json
os.environ["ARC_AGI_ENV_DIR"] = "/a0/usr/workdir/environment_files"
a = Arcade()
g = a.make("sp80")

# Check if different actions produce different frames
results = {}
for act in g.action_space:
    g.reset()
    frame = g.step(act)
    frame_json = json.loads(frame.json())
    results[str(act)] = {
        "state": str(frame.state),
        "levels_completed": frame.levels_completed,
        "win_levels": frame.win_levels,
        "guid": frame.guid,
        "action_input": frame.action_input,
        "full_reset": frame.full_reset,
        "available_actions": frame.available_actions,
    }

for act, d in results.items():
    print(f"{act:20s}: state={d['state']:15s} lv={d['levels_completed']} guid={d['guid'][:8]}... action_input={d['action_input']}")

print("\nNumber of unique (state, lv, win) combos:", len(set((r["state"], r["levels_completed"], r["win_levels"]) for r in results.values())))
print("Number of unique guids:", len(set(r["guid"] for r in results.values())))

# The key insight: all frames are structurally identical!
# BUT: the game's internal state IS different after each step.
# The FrameDataRaw doesn't capture the full game state.
# We need to use the FRAME itself as state identifier, not just its scalar attributes.

# Try: does the same sequence of actions produce the same guids?
g.reset()
f1 = g.step(GameAction.ACTION4)
print(f"\nPath (4,4,4,5):")
print(f"  {f1.guid[:16]}... step0")
f2 = g.step(GameAction.ACTION4)
print(f"  {f2.guid[:16]}... step1")
f3 = g.step(GameAction.ACTION4)
print(f"  {f3.guid[:16]}... step2")
f4 = g.step(GameAction.ACTION5)
print(f"  {f4.guid[:16]}... step3")

# Re-do the same sequence
g.reset()
f1b = g.step(GameAction.ACTION4)
print(f"\nSame path again:")
print(f"  {f1b.guid[:16]}... step0")
f2b = g.step(GameAction.ACTION4)
print(f"  {f2b.guid[:16]}... step1")

# Different path
g.reset()
fr1 = g.step(GameAction.ACTION1)
print(f"\nPath (1,1,1,2):")
print(f"  {fr1.guid[:16]}... step0")
