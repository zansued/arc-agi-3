import sys
with open('/a0/usr/workdir/v55.py', 'r', encoding='utf-8') as f:
    src = f.read()

# Use numeric line-based approach: find the actual lines
lines = src.split('\n')
for i, line in enumerate(lines):
    if i == 90:  # line 91 (0-indexed)
        print(f"Line {i+1} BEFORE: {repr(line)}")
        if 'bp35' in line and '[' in line:
            lines[i] = "    'bp35': [0.1, 0.1, 0.7, 0.1],   # Poucas cores -> BFS-heavy"
            print(f"Line {i+1} AFTER:  {repr(lines[i])}")
    if i == 107:  # line 108
        print(f"Line {i+1} BEFORE: {repr(line)}")
        if 'sp80' in line and '[' in line:
            lines[i] = "    'sp80': [0.1, 0.1, 0.7, 0.1],   # Sparse + BFS-heavy"
            print(f"Line {i+1} AFTER:  {repr(lines[i])}")

with open('/a0/usr/workdir/v55.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))

print("\nDone. Verifying...")
# Read back and check
with open('/a0/usr/workdir/v55.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f.readlines()):
        if i in [90, 107]:
            print(f"Line {i+1} VERIFY: {repr(line.rstrip())}")
