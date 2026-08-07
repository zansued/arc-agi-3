import arcengine, inspect, numpy as np

print("=== GameState enum ===")
for gs in arcengine.GameState:
    print(f"  {gs.name} = {gs.value}")

print()
print("=== Arcade via arc_agi ===")
import sys
sys.path.insert(0, ".")
try:
    from arc_agi import Arcade
    print(f"  Arcade init: {inspect.signature(Arcade.__init__)}")
    a = Arcade()
    fd = a.step(0)
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
except Exception as e:
    print(f"  Error: {e}")
