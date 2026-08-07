#!/usr/bin/env python3
"""Patch v55.py neural weights for hard games and save."""
import sys, json, re

sys.path.insert(0, '/a0/usr/workdir')

# Read the source
with open('/a0/usr/workdir/v55.py', 'r') as f:
    src = f.read()

# Find NEURAL_WEIGHTS dict
print("NEURAL_WEIGHTS dict location:", src.find('NEURAL_WEIGHTS'))

# Load the module to get current weights, but we need to do it without triggering execution
# Better approach: patch the file directly
# Strategy: [deduction, archive, bfs, random]
# For cn04, bp35, sp80: we want BFS to dominate

old_cn04 = '"cn04": [0.3, 0.5, 0.1, 0.1]'
new_cn04 = '"cn04": [0.1, 0.1, 0.7, 0.1]'

old_bp35 = '"bp35": [0.6, 0.2, 0.1, 0.1]'
new_bp35 = '"bp35": [0.1, 0.1, 0.7, 0.1]'

old_sp80 = '"sp80": [0.4, 0.3, 0.2, 0.1]'
new_sp80 = '"sp80": [0.1, 0.1, 0.7, 0.1]'

# Also checking if NEURAL_WEIGHTS is defined inline or loaded from file
# Look for NEURAL_STATE_PATH
import ast
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == 'NEURAL_STATE_PATH':
                print("NEURAL_STATE_PATH found in source")
                val = ast.literal_eval(node.value)
                print(f"  Path: {val}")
            if isinstance(target, ast.Name) and target.id == 'NEURAL_WEIGHTS':
                print("NEURAL_WEIGHTS found in source (inline dict)")
                # Check if it's a direct dict literal
                if isinstance(node.value, ast.Dict):
                    print("  Inline dict literal - will patch source directly")

# Count occurrences
for old, name in [(old_cn04, 'cn04'), (old_bp35, 'bp35'), (old_sp80, 'sp80')]:
    count = src.count(old)
    print(f"{name}: found {count} occurrences of old value")

# Replace
src = src.replace(old_cn04, new_cn04)
src = src.replace(old_bp35, new_bp35)
src = src.replace(old_sp80, new_sp80)

# Verify
for new, name in [(new_cn04, 'cn04'), (new_bp35, 'bp35'), (new_sp80, 'sp80')]:
    count = src.count(new)
    print(f"{name}: found {count} occurrences of new value")

# Write back
with open('/a0/usr/workdir/v55.py', 'w') as f:
    f.write(src)

print("\nWeight patch applied successfully")
