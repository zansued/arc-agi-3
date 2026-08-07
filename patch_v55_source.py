#!/usr/bin/env python3
"""Patch v55.py hardcoded NEURAL_WEIGHTS defaults to favor BFS for hard games."""
with open('/a0/usr/workdir/v55.py', 'r') as f:
    src = f.read()

# Replace the specific weight lines
replacements = [
    ("'bp35': [0.6, 0.2, 0.1, 0.1],   # Poucas cores -> deducao", 
     "'bp35': [0.1, 0.1, 0.7, 0.1],   # BFS-heavy (deducao falha)"),
    ("'cn04': [0.3, 0.5, 0.1, 0.1],   # Archive forte (V28 resolveu)",
     "'cn04': [0.1, 0.1, 0.7, 0.1],   # BFS-heavy (archive falhou)"),
    ("'sp80': [0.4, 0.3, 0.2, 0.1],   # Sparse + archive",
     "'sp80': [0.1, 0.1, 0.7, 0.1],   # BFS-heavy (archive falhou)"),
]

count = 0
for old, new in replacements:
    if old in src:
        src = src.replace(old, new)
        count += 1
        print(f"Patched: {old[:30]}...")
    else:
        print(f"NOT FOUND: {old[:50]}...")

with open('/a0/usr/workdir/v55.py', 'w') as f:
    f.write(src)

print(f"\n{count} replacements made")

# Also update the JSON to the target values directly (load_neural_weights will blend, 
# but since defaults are now correct the blend will converge towards them)
# Actually, with defaults matching targets, blend = 0.7*target + 0.3*target = target. Perfect.
import json
with open('/a0/usr/workdir/arc_runs/v55_neural_weights.json', 'r') as f:
    nw = json.load(f)
for g in ['cn04', 'bp35', 'sp80']:
    nw[g] = [0.05, 0.05, 0.85, 0.05]  # Even more aggressive BFS for JSON
with open('/a0/usr/workdir/arc_runs/v55_neural_weights.json', 'w') as f:
    json.dump(nw, f, indent=2)
print("JSON also updated")
