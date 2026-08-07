import arcengine, inspect, numpy as np

import sys
sys.path.insert(0, ".")
from arc_agi import Arcade

a = Arcade()
envs = a.get_environments()
print(f"=== Environments ({len(envs)}) ===")
for e in envs[:3]:
    print(f"  fields: {list(e.model_fields.keys())}")
    for f in e.model_fields:
        print(f"    {f}: {getattr(e, f)}")
    print()

print("=== Wrapping first env ===")
env_id = envs[0].game_id
print(f"  game_id: {env_id}")
wrapper = a.make(env_id, seed=0)
print(f"  wrapper type: {type(wrapper).__name__}")
wrapper_dir = [x for x in dir(wrapper) if not x.startswith("_")]
print(f"  wrapper dir: {wrapper_dir}")

fd = wrapper.step(0)
print(f"\n  step(0) -> {type(fd).__name__}")
for name, field in fd.model_fields.items():
    val = getattr(fd, name)
    if isinstance(val, list) and val and isinstance(val[0], list):
        arr = np.array(val)
        print(f"    .{name}: list -> ndarray shape={arr.shape} dtype={arr.dtype}")
    elif isinstance(val, list):
        print(f"    .{name}: list len={len(val)} first={str(val[0])[:80] if val else None}")
    elif isinstance(val, arcengine.GameState):
        print(f"    .{name}: GameState.{val.name}")
    elif isinstance(val, arcengine.ActionInput):
        print(f"    .{name}: ActionInput.{val}")
    else:
        print(f"    .{name}: {repr(val)}")
