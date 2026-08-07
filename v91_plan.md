# v9.1 Incremental Changes

## Changes from v9
1. Add cn04 to game list (25 games total)
2. Three-level replay success metric:
   - exact_success: hash matches exactly
   - near_success: hamming_distance <= 25 pixels
   - useful_success: new visited states after replay
3. MAX_ARCHIVE_RESETS = 5
4. MAX_REPLAY_BUDGET = 150 (steps allocated for replay)
5. Frontier score for archive cells:
   score = 4*untried_actions + 3*children + 10*progress - 1.5*visits - 0.05*len(seq)
6. Suppress reset for 50 steps after levels_completed increases
7. Skip cells with sequence > MAX_REPLAY_LEN

## Preserved from v9
- v6 diversity bandit as exploration policy
- Archive save/select/reset/replay mechanism (the successful ARCHIVE EFFECT)
- ACTION6 filtered out (disabled)
- EXPLORE_FROM_CELL as main progress mode
- Single game structure (500 steps, logging to JSONL)

## Sentinel conditions
- sp80: must attempt ARCHIVE EFFECT (levels_completed should appear)
- sk48: maintain high exploration (>200 states expected)
- bp35: robust exploration
- tn36: must not crash (ACTION6-only, fallback to RESET)

## Target metrics (compared to v9)
- Mean states: >= 120
- Zero-delta: <= 72%
- Early stagnation: <= 4/25
- Progress games: >= 1
- Crashes: 0

## Build order
1. Copy v9 to v9.1
2. Apply each change above
3. Test sentinels
4. Run full benchmark
5. Compare against v9 metrics
