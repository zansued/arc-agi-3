import arcengine, inspect, numpy as np

print("=== GameState enum ===")
for gs in arcengine.GameState:
    print(f"  {gs.name} = {gs.value}")

print()
print("=== Arcade methods ===")
import sys
sys.path.insert(0, ".")
from arc_agi import Arcade
methods = [x for x in dir(Arcade) if not x.startswith("_")]
for m in methods:
    obj = getattr(Arcade, m)
    if callable(obj):
        try:
            sig = inspect.signature(obj)
            print(f"  {m}{sig}")
        except:
            print(f"  {m}(...)")
    else:
        print(f"  {m} = {repr(obj)}")

print()
print("=== step a specific environment ===")
a = Arcade()
# list environment names
envs = a.get_all_environment_ids()
print(f"  environments: {envs[:5]}...")
env = a.load_environment(envs[0])
print(f"  loaded: {type(env).__name__}")
# try step
fd = env.step(0)
print(f"  step(0) -> {type(fd).__name__}")
for name, field in fd.model_fields.items():
    val = getattr(fd, name)
    if isinstance(val, list) and val and isinstance(val[0], list):
        arr = np.array(val)
        print(f"    .{name}: list -> ndarray shape={arr.shape} dtype={arr.dtype}")
    elif isinstance(val, list):
        print(f"    .{name}: list len={len(val)} first={val[0] if val else None}")
    elif isinstance(val, arcengine.GameState):
        print(f"    .{name}: GameState.{val.name}")
    else:
        print(f"    .{name}: {repr(val)}")
