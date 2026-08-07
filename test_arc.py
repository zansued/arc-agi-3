#!/a0/usr/workdir/.venv/bin/python3
from arc_agi import Arcade
import os
os.environ["ARC_AGI_ENV_DIR"] = "/a0/usr/workdir/environment_files"
a = Arcade()
g = a.make("sp80")
print("OK:", type(g).__name__)
print("levels:", g.levels if hasattr(g, "levels") else "N/A")
print("action_space:", g.action_space if hasattr(g, "action_space") else "N/A")
if hasattr(g, "action_space") and g.action_space:
    print("sample actions:", [str(a)[:80] for a in g.action_space[:3]])
