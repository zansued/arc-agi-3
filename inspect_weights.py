#!/usr/bin/env python3
"""Inspect the exact formatting of NEURAL_WEIGHTS in v55.py."""
with open('/a0/usr/workdir/v55.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    stripped = line.rstrip()
    if any(g in stripped for g in ['"cn04"', '"bp35"', '"sp80"', '"ar25"']) and '[' in stripped:
        print(f"Line {i:5d}: {repr(stripped)}")
    elif 'NEURAL_WEIGHTS' in stripped:
        print(f"Line {i:5d}: {repr(stripped)}")
