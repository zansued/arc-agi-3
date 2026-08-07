# cn04 Regression Diagnosis Report — v30 vs v28

## Summary
cn04 is solved to level 1 by v28 (archive/bandit solver) but NOT by v30 (stateful deepcopy BFS). This is the critical blocker preventing v30 from receiving full 25-game benchmark authorization.

## Methodology
Both v30 and v28 solvers were run on cn04 with full verbose logging:
- **v30**: 588 event entries capturing every node pop, transition, and pruning decision
- **v28**: 508 event entries from the actual v28_level_reward_shaping.py solver run (not simplified)
- Comparison identifies exact divergence points and root cause

## Key Data

### v30 BFS Results
| Metric | Value |
|--------|-------|
| Status | OK |
| Nodes expanded | 500 (maxed out) |
| Unique states discovered | 151 |
| Best levels completed | **0** |
| Max depth reached | **4** |
| Frontier remaining | 67 |
| Fallbacks triggered | 0 |
| Progress events | 0 |
| Duplicate rate | 350/500 = 70% |
| Best state hash | `5a832116ac9e3bae65e4f9a189e6a1e0` (initial state) |
| Depth 5 states | Only 24 new, 176 duplicates |

### v28 Solver Results
| Metric | Value |
|--------|-------|
| Status | OK |
| Steps | 500 (342 live + 158 replay) |
| Unique states discovered | **234** |
| Best levels completed | **1** (✅) |
| Replay attempts | 6 |
| Replay successes | 4 (66.7%) |
| Progress events | 2 (level + progress ratio) |
| Zero-delta rate | 28.8% |

## Divergence Analysis

### (a) At what BFS depth do the paths diverge?

The v30 BFS reaches a **hard wall at depth 4-5**:
- Depth 0: 1 node (initial)
- Depth 1: 5 nodes (6 actions → 5 unique states)
- Depth 2: 19 nodes
- Depth 3: 25 nodes
- Depth 4: 34 nodes (peak exploration — 77 new states at this depth)
- Depth 5: **Exploration collapse** — only 24 new states, 176 duplicate attempts

v28 found the level-1 state (hash `8a6577d9b7eca29d039cac29164e27da`) via: ACTION2 (ROTATE_CCW) at step ~209, after exploring an archive of 220+ states through replay and bandit-guided exploration. The exact path uses 342 live steps + 158 replay steps.

**The BFS diverges from v28's path at depth 3-4.** v30's BFS explores action order [1,2,3,4,5,6] deterministically from each node. v28 uses stochastic action selection (bandit with UCB-like stats) + archive replay to explore alternative branches that the deterministic BFS never reaches.

### (b) What state/action was pruned in v30 but accepted in v28?

The v30 BFS deduplicates states using MD5 hash of the full (64,64) frame. 70% of all actions produce duplicates. The critical issue is **not a specific state being pruned**, but rather the BFS **hitting a local plateau where most transitions cycle back to visited states**.

v28 overcomes this plateau through:
1. **Archive persistence**: States are stored with their full action sequences
2. **Reset-to-archive**: When stagnation hits, v28 resets the game and replays from a chosen archive cell (6 replay attempts in this run)
3. **Stochastic bandit**: Action selection is randomized with UCB-style reward tracking, not deterministic FIFO
4. **Zero replay steps**: 158/500 steps (31.6%) are replay steps from archive cells

The v30 BFS has NO equivalent mechanism. Its fallback system (random node from safe_stash after 50 consecutive visited duplicates) was NEVER triggered because new states trickle in at depth 4, resetting the stagnation counter.

### (c) Frontier size limit, symmetry detection false positive, or reward threshold issue?

**Root cause: Frontier exhaustion + duplicate rate saturation — not a specific detection false positive.**

1. **Not a frontier size limit**: 67 nodes remained in the frontier when the step limit hit
2. **Not a symmetry detection false positive**: The frame_hash MD5 is accurate
3. **Not a reward threshold issue**: v30 uses levels_completed for progress detection (0/6) — no partial-progress reward shaping

**The real mechanism is BFS topological lock-in:**
- The BFS pops nodes FIFO (depth-first-per-action-order)
- Actions are iterated [1,2,3,4,5,6] from each node
- Many transitions at depth 4-5 lead back to previously visited states (frame identical after cycle of transforms)
- The action 6 (crop/paste) with fixed data `{'x':32, 'y':32}` never produces a novel state that breaks the plateau
- Without a replay mechanism, the BFS cannot "skip" the plateau to explore deeper branches
- v30's safe_stash fallback requires 50+ consecutive duplicates to trigger — but new states trickle in at depth 4, resetting the counter

## v28's Winning Insight
v28 solved cn04 using a **heterogeneous search strategy**:
- 342 live steps with bandit-guided action selection
- 158 replay steps from archive cells (6 separate replay attempts)
- **No ACTION6 needed** — level 1 was achieved using only ACTION1-5
- The level-1 state was reached through the combination of stochastic exploration + targeted replay from promising archive states
- PolicyArchiveRouter classified cn04 as "strong" route (v14_spectral) with 11 historical samples averaging 444 states

## v30's Structural Limitation

The v30 BFS is a **pure FIFO deepcopy BFS with deterministic action ordering**. It cannot:
- Escalate from archive-stored promising states (no replay mechanism)
- Use stochastic exploration to break out of plateaus
- Benefit from historical data (PolicyArchiveRouter)
- Apply forced probing or targeted reset-and-replay

For cn04 specifically, the BFS topology means the solution path requires either:
1. A non-deterministic action order that happens to hit the right state at depth >4
2. A replay mechanism that returns the agent to a promising state at depth 3-4 and then tries different actions
3. A larger step budget (>500) and expanded frontier to brute-force through the plateau

## Is the Regression Fixable?

**Partially — with caveats.**

**Short-term fix (v30_fix1):**
1. Increase MAX_STEPS from 500 to 1500 for cn04 and bottleneck games
2. Add stochastic action ordering (randomize action iteration order per node) to break plateaus
3. Lower stagnation threshold from 50 to 20 to trigger fallsack earlier

**Medium-term fix (v31):**
- Add archive replay mechanism: store visited states and their action sequences, periodically reset to promising archive cells
- This is the core v28 mechanism that enables broader exploration

**Long-term fix (v32+):**
- Combine deepcopy BFS with archive replay: use BFS for local exploration + archive replay for global restart
- Add bandit-guided action selection with UCB or spectral reward tracking

## Action Recommendation
1. ⚡ Create v30_fix1 with the three short-term fixes above
2. Run smoke test on cn04, sp80, cd82, tn36, bp35
3. If cn04 passes on v30_fix1, proceed to full 25-game benchmark
4. If cn04 still fails, archive v30's approach and pivot to v30/v28 hybrid (v31)

## Files
- `/a0/usr/workdir/v30_verbose_cn04_diagnostic.py` — v30 verbose diagnostic
- `/a0/usr/workdir/arc_runs/v30_cn04_verbose_log.jsonl` — 588 entries
- `/a0/usr/workdir/arc_runs/v30_cn04_verbose_summary.json` — summary
- `/a0/usr/workdir/arc_runs/v28_cn04_verbose_log.jsonl` — v28 verbose log
- `/a0/usr/workdir/arc_runs/v28_cn04_verbose_summary.json` — v28 summary
- `/a0/usr/workdir/v28_level_reward_shaping.py` — v28 source (1131 lines)
- `/a0/usr/workdir/v30_stateful_bfs_solver.py` — v30 source (479 lines)

## Timestamp
2026-06-09 02:10 BRT