import arcengine, inspect, numpy as np

print("=== arcengine contents ===")
for name in dir(arcengine):
    if not name.startswith("_"):
        obj = getattr(arcengine, name)
        if isinstance(obj, type):
            print(f"  {name} (class)")
        else:
            print(f"  {name} ({type(obj).__name__})")

print()
print("=== inspect arcengine.FrameData ===")
fd_cls = arcengine.FrameData
for attr in dir(fd_cls):
    if not attr.startswith("_"):
        obj = getattr(fd_cls, attr)
        if isinstance(obj, type):
            print(f"  .{attr}: class {obj}")
        elif callable(obj):
            print(f"  .{attr}: method")
        else:
            print(f"  .{attr}: {type(obj).__name__}")

print()
print("=== Create first + second instance, inspect FrameData object ===")
# Try to create a game instance - look at base_game or Level
print("Checking base_game:", dir(arcengine.base_game))

# Try building a game
game = arcengine.base_game.ARCBaseGame()
print()
print("game created:", type(game).__name__)
print("dir(game):", [x for x in dir(game) if not x.startswith("_")])

# Try step
fd = game.step(0)
print()
print("=== step(0) via ARCBaseGame ===")
print(f"  type(fd): {type(fd)}")
attrs = [x for x in dir(fd) if not x.startswith("_")]
print(f"  dir(fd): {attrs}")
for attr in attrs:
    try:
        val = getattr(fd, attr)
        if isinstance(val, np.ndarray):
            print(f"  .{attr}: ndarray shape={val.shape} dtype={val.dtype}")
        elif isinstance(val, (list, tuple)):
            print(f"  .{attr}: {type(val).__name__} len={len(val)}")
        else:
            print(f"  .{attr}: {repr(val)}")
    except Exception as e:
        print(f"  .{attr}: <error: {e}>")

print()
# Check levels_completed
print("=== Levels ===")
print(f"  game.levels type: {type(getattr(game, 'levels', None))}")
levels = getattr(game, 'levels', None)
if levels:
    print(f"  len={len(levels)}")

print()
print("=== API: Arcade import check ===")
try:
    from arc_agi import Arcade
    print("  Arcade imported successfully!")
    a = Arcade()
    print(f"  Arcade() type: {type(a)}")
    fd2 = a.step(0)
    print(f"  step(0) type: {type(fd2)}")
    for attr in [x for x in dir(fd2) if not x.startswith("_")]:
        try:
            val = getattr(fd2, attr)
            if isinstance(val, np.ndarray):
                print(f"  .{attr}: ndarray shape={val.shape} dtype={val.dtype}")
            elif isinstance(val, (list, tuple)):
                print(f"  .{attr}: {type(val).__name__} len={len(val)}")
            else:
                print(f"  .{attr}: {repr(val)}")
        except Exception as e:
            print(f"  .{attr}: <error: {e}>")
except Exception as e:
    print(f"  Error: {e}")
