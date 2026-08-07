import arcengine, inspect, numpy as np

fd_cls = arcengine.FrameData
print("=== FrameData Fields ===")
for name, field in fd_cls.model_fields.items():
    print(f"  {name}: {field.annotation} (default={field.default})")

print()
print("=== FrameDataRaw Fields ===")
fd_raw = arcengine.FrameDataRaw
for name, field in fd_raw.model_fields.items():
    print(f"  {name}: {field.annotation} (default={field.default})")

print()
print("=== Level Fields ===")
lvl = arcengine.Level
for name, field in lvl.model_fields.items():
    print(f"  {name}: {field.annotation} (default={field.default})")

print()
print("=== GameState Fields ===")
gs = arcengine.GameState
for name, field in gs.model_fields.items():
    print(f"  {name}: {field.annotation} (default={field.default})")

print()
print("=== Trying to import Arcade from arc_agi ===")
try:
    from arc_agi import Arcade
    print("  Arcade imported!")
    sig = inspect.signature(Arcade.__init__)
    print(f"  Arcade.__init__{sig}")
    print(f"  Arcade class attrs:")
    arcade_attrs = [x for x in dir(Arcade) if not x.startswith("_") and not callable(getattr(Arcade, x, None))]
    for attr in arcade_attrs:
        print(f"    .{attr}: {getattr(Arcade, attr, None)}")
except Exception as e:
    print(f"  Error importing Arcade: {e}")
    import traceback
    traceback.print_exc()
