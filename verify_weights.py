import sys
sys.path.insert(0, '/a0/usr/workdir')
import v55
print('Module loaded OK')
for g in ['cn04', 'bp35', 'sp80']:
    w = v55.NEURAL_WEIGHTS.get(g, 'MISSING')
    print(f'  {g}: {w}')
print('Defaults now BFS-heavy')
