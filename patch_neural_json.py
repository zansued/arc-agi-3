#!/usr/bin/env python3
"""Patch v55 neural weights JSON file to favor BFS for hard games."""
import json

path = '/a0/usr/workdir/arc_runs/v55_neural_weights.json'
with open(path, 'r') as f:
    weights = json.load(f)

print("=== Current weights for target games ===")
for g in ['cn04', 'bp35', 'sp80']:
    w = weights.get(g, 'MISSING')
    print(f"  {g}: {w}")

# Strategy ordering: [deduction, archive, bfs, random]
# For hard games that deduction/archive fail on, shift to BFS-heavy
new_weights = {
    'cn04': [0.05, 0.05, 0.85, 0.05],   # BFS=85%, almost no deduction/archive
    'bp35': [0.05, 0.05, 0.85, 0.05],
    'sp80': [0.05, 0.05, 0.85, 0.05],
}

for g, w in new_weights.items():
    weights[g] = w
    print(f"  {g}: SET TO {w}")

with open(path, 'w') as f:
    json.dump(weights, f, indent=2)

print(f"\nSaved to {path}")
# Verify
with open(path, 'r') as f:
    v = json.load(f)
for g in ['cn04', 'bp35', 'sp80']:
    print(f"  Verified {g}: {v[g]}")
