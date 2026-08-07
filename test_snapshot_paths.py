
import sys
sys.path.append("/a0")
sys.path.append("/a0/plugins/_time_travel/helpers")

from time_travel import resolve_workspace, iter_snapshot_paths
from pathlib import Path

workspace = resolve_workspace()
print("Workspace real path:", workspace.real_path)
print("Workspace display path:", workspace.display_path)

paths = list(iter_snapshot_paths(workspace.real_path, display_path=workspace.display_path))
print("TOTAL FILES TO SNAPSHOT:", len(paths))
print("First 100 files:")
for p in paths[:100]:
    print(" -", p)
