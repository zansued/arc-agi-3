#!/bin/bash
# Run v55 on specific game IDs with corrected weights
cd /a0/usr/workdir
source .venv/bin/activate

GAMES=("cn04" "bp35" "sp80")

echo "============================================"
echo "v55 Re-run with BFS-heavy weights"
echo "Date: $(date -u)"
echo "============================================"

for game in "${GAMES[@]}"; do
    echo ""
    echo "=== ${game} ==="
    timeout 300 python3 -c "
import sys, time, json
sys.path.insert(0, '.')
from v55 import solve_game, NEURAL_WEIGHTS
print('  Weights for ${game}:', NEURAL_WEIGHTS.get('${game}', 'MISSING'))
start = time.time()
try:
    result = solve_game('${game}', is_smoke=True)
    elapsed = time.time() - start
    print('  RESULT: levels={}, states={}, steps={}, strategy={}, time={:.1f}s'.format(
        result['levels'], result['states'], result['steps'], result['strategy'], elapsed))
    print('  FULL:', json.dumps(result, indent=2))
except Exception as e:
    elapsed = time.time() - start
    print('  ERROR [{:.1f}s]: {}'.format(elapsed, e))
    import traceback; traceback.print_exc()
"
    echo "--- ${game} done ---"
done

echo ""
echo "All 3 games complete at $(date -u)"
