import arcengine, inspect, numpy as np

import sys
sys.path.insert(0, ".")
from arc_agi import Arcade

a = Arcade()
envs = a.get_environments()
print(f"=== Environments ({len(envs)}) ===")
for e in envs[:3]:
    print(f"  id={e.id}, name={e.name}")

print()
env_id = envs[0].id
print(f"=== Making env: {env_id} ===")
wrapper = a.make(env_id, seed=0)
print(f"  wrapper type: {type(wrapper).__name__}")
print(f"  wrapper dir (non-underscore): {[x for x in dir(wrapper) if not x.startswith('_')]}")
# step via wrapper
fd = wrapper.step(0)
print(f"  step(0) -> {type(fd).__name__}")
for name, field in fd.model_fields.items():
    val = getattr(fd, name)
    if isinstance(val, list) and val and isinstance(val[0], list):
        arr = np.array(val)
        print(f"    .{name}: list -> ndarray shape={arr.shape} dtype={arr.dtype}")
    elif isinstance(val, list):
        print(f"    .{name}: list len={len(val)} first={str(val[0])[:80] if val else None}")
    elif isinstance(val, arcengine.GameState):
        print(f"    .{name}: GameState.{val.name}")
    else:
        print(f"    .{name}: {repr(val)}")

print()
# Try a few more steps
for i in range(1, 5):
    fd2 = wrapper.step(i)
    levels = getattr(fd2, "levels_completed", None)
    state = getattr(fd2, "state", None)
    print(f"  step({i}): levels_completed={levels}, state={state}")
