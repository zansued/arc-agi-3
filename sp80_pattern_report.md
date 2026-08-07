# sp80 Pattern Report — Archive Effect Breakthrough

## Metadata
- Game: sp80
- Total steps: 500
- States visited: 84
- Zero-delta rate: 83.2%
- Archive size at end: 83
- Levels completed: 1/6
- Win levels: 6

## Breakthrough event
- Step: 71
- Mode: EXPLORE_FROM_CELL
- Action: 5
- Changed pixels: 82
- State hash (before): d6e416871b
- State hash (after): 4e99bf15f4

## Causal chain
1. Archive selected cell `d862bb27` (sequence_len=67, steps ~41-42)
2. RESET + REPLAY_SEQUENCE (2 steps, step 41-42)
3. EXPLORE_FROM_CELL starting step 43:
   - Steps 43-70: 28 steps discovering 29 new states
   - Average delta/step: ~60 pixels
   - Step 71: ACTION 5 triggered level-up
4. Post-level-up: step 72 had 1168 changed pixels (new level loaded)

## Action distribution (30 steps before level-up)
- ACTION 1: 5
- ACTION 2: 4
- ACTION 3: 4
- ACTION 4: 7
- ACTION 5: 3 (level-up!)
- ACTION 6: 5
- RESET: 2

## Key insight
The breakthrough did NOT happen immediately after replay.
It happened after 30 steps of diverse exploration from the replayed cell.
This validates: archive → return to promising region → explore → progress.

## Recommended heuristic for v9.1
- If a cell leads to high delta region after replay, explore longer before next reset
- Track "exploration freshness" per cell (states discovered since last reset)
- Suppress archive reset for 50 steps after any level completion
