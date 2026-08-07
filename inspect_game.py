import arcengine, inspect, numpy as np

print("=== GameState enum ===")
for gs in arcengine.GameState:
    print(f"  {gs.name} = {gs.value}")

print()
print("=== ActionInput enum ===")
for ai in arcengine.ActionInput:
    print(f"  {ai.name} = {ai.value}")

print()
print("=== FrameData frame detail ===")
fd_cls = arcengine.FrameData
frame_field = fd_cls.model_fields.get("frame")
print(f"  frame annotation: {frame_field.annotation}")
print(f"  frame default: {frame_field.default}")

print()
print("=== Attempting Arcade import ===")
import sys
sys.path.insert(0, "/a0/usr/workdir")
try:
    from arc_agi import Arcade
    print("  Arcade imported OK")
    print(f"  Arcade init: {inspect.signature(Arcade.__init__)}")
    a = Arcade()
    print(f"  Arcade() created OK")
    fd = a.step(0)
    print(f"  step(0) type: {type(fd).__name__}")
    for name in fd.model_fields:
        val = getattr(fd, name)
        if isinstance(val, np.ndarray):
            print(f"    .{name}: ndarray shape={val.shape} dtype={val.dtype}")
        elif isinstance(val, list):
            if val and isinstance(val[0], list):
                arr = np.array(val)
                print(f"    .{name}: list -> ndarray shape={arr.shape} dtype={arr.dtype}")
            else:
                print(f"    .{name}: list len={len(val)}")
        elif isinstance(val, arcengine.GameState):
            print(f"    .{name}: GameState.{val.name}")
        else:
            print(f"    .{name}: {repr(val)}")
except Exception as e:
    print(f"  Error: {e}")
    import traceback
    traceback.print_exc()
