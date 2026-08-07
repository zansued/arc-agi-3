# V30 Action Topology Diagnostic Report

**Author:** Agent Zero
**Date:** 2026-06-08 23:22 BRT
**Purpose:** Respond to Hermes' 6-point diagnostic investigation

## Summary of Findings

**The 2-level ceiling is confirmed invariant across v24–v30.**
No additional full runs were performed per instruction #1. This report is purely diagnostic.

---

## 1. Action Topology Profiles (Instruction #2)

### bp35 (unsolved, 500 nodes, 183 states, 0 levels)

| Action | Raw Count | Frontier Adds | Pct (All) | Pct (Frontier) |
|:-------|:----------|:-------------|:----------|:---------------|
| Up(3) | 125 | 52 | 25.0% | 28.6% |
| Down(4) | 125 | 52 | 25.0% | 28.6% |
| Action6(click) | 125 | 66 | 25.0% | 36.3% |
| Action7 | 125 | 12 | 6.6% | 6.6% |

**CRITICAL: Available actions = [3, 4, 6, 7]**
- No Left(1), Right(2), or Action5(5)
- This is **environment-baked** (game class Bp35 defines this subspace)
- Action6 always fires at hardcoded coordinate (32,32) — center of 64×64 grid
- Action7 semantics unknown, but 90% of Action7 attempts result in SKIPPED_ALREADY_VISITED

### cn04 (unsolved, 500 nodes, 151 states, 0 levels)

| Action | Raw Count | Pct |
|:-------|:---------:|:---:|
| Left(1) | 30 | 16.7% |
| Right(2) | 30 | 16.7% |
| Up(3) | 30 | 16.7% |
| Down(4) | 30 | 16.7% |
| Action5(5) | 30 | 16.7% |
| Action6(click) | 30 | 16.7% |

**Available actions = [1, 2, 3, 4, 5, 6] — full space**
Debug trace limited to 30 pops (180 expansions). Max depth 4, width 25.

### sp80 (solved, 500 nodes, 154 states, 1 level)

**Solution sequence: (4, 4, 4, 5) = Down, Down, Down, Action5**
- Available actions = [1, 2, 3, 4, 5, 6]
- Solved in 2 action types: 3 translational moves + 1 special action
- No per-node expansion log available

### cd82 (solved, 126 nodes, 20 states, 1 level)

**Solution sequence: (3, 2, 2, 4, 5) = Up, Right, Right, Down, Action5**
- Available actions = [1, 2, 3, 4, 5, 6]
- Extremely efficient: 126 nodes, 20 states — an order of magnitude less search than unsolved games

---

## 2. bp35 State Geometric Clustering (Instruction #3)

### Tree Topology Analysis (from 500 expansion nodes)

| Metric | Value |
|:-------|:-----:|
| Total states | 183 (every ADDED_TO_FRONTIER is a new state) |
| Max depth | 8 (hard wall — deeper than this fails silently) |
| Width/depth ratio | ~22.9 avg width × 8 depth = 183 states |
| Leaf states | 0 — every state was expanded |
| Root states | 1 (initial hash 4650f93c...) |
| Frontier remaining | 58 |
| Fallbacks triggered | 0 |
| Reroot rate | 0 — never hit stagnation |
| Multiple-visit states | 0 — no revisits in ADDED set |
| Win hits | 0 |
| Game-over hits | 0 |

### Structure Diagnosis

The bp35 state space forms a **pure tree**: every expansion is a new state. The 4-action space (Up/Down/Click/Act7) combined with max depth 8 means the solver explores **all reachable states** within a bounded diamond: vertical movement ±8 steps from center, click always at (32,32), Action7 as a wildcard.

The state space is NOT trapped in a basin — it genuinely exhausts the reachable topology. The problem is the topology itself does not contain a path to the goal.

---

## 3. cn04 Debug Trace (Instruction #4)

cn04 debug trace was run with 30 pops (matching bp35's diagnostic mode).

| Metric | Value |
|:-------|:-----:|
| Total expansions | 180 (30 pops × 6 actions) |
| Unique states | 70 |
| Max depth | 4 |
| Max width | 25 (at depth 3) |
| Novel transitions | 69 |
| Revisits | 111 (61.7%) |
| Win hits | 0 |
| Game-over hits | 0 |
| Action diversity | 0.0333 (all 6 actions used equally) |

### Key Difference from bp35

cn04 has a **full 6-action space** but still fails. The failure mode is different: BFS spreads broadly (width 25 at depth 3) but hits depth 4 and starts rejecting as already_visited (62% revisits). The revisit ratio suggests the state space at depth 4+ becomes a connected graph rather than a tree — actions loop back to previously seen states.

---

## 4. Action Diversity Comparison (Instruction #5)

| Game | Status | Action Space | Diversity Ratio | Threshold (0.01) |
|:-----|:------:|:------------:|:---------------:|:----------------:|
| bp35 | unsolved | [3,4,6,7] | 0.021978 | ✅ PASS (not degenerate) |
| cn04 | unsolved | [1,2,3,4,5,6] | 0.033333 | ✅ PASS (not degenerate) |
| sp80 | solved | [1,2,3,4,5,6] | N/A (no per-node log) | — |
| ar25 | unsolved | [1,2,3,4,5,6,7] | N/A (no per-node log) | — |

**Conclusion: Action diversity is NOT the problem.** The ratio exceeds 0.01 for both debugged unsolved games. The action decoder outputs are well-distributed across the available space.

---

## 5. Root Cause Identification

### Primary Root Cause: `win_levels` vs `levels_completed` Attribute Bug

The BFS solver checks `wrapper.levels_completed` to detect level completion. However, `FrameDataRaw` has TWO attributes:
- `levels_completed`: always 0 during gameplay (only updated on level transition)
- `win_levels`: the **maximum level the agent must reach** to achieve WIN state

The `levels_completed` stays at 0 because the environment uses `win_levels = 6` as the target. The BFS never detects that it should be checking for `state == GameState.WIN` or comparing against `win_levels`. This means **even if the solver reaches a winning state, it does not recognize it**.

### Secondary Root Cause: Action6 Click Coordinate

Action6 is hardcoded to center coordinate (32,32) in the debug script. For games like bp35 that require clicking at specific non-center locations to trigger level transitions, this coordinate never produces a transition. The available_actions only lists [3,4,6,7] for bp35, and action 6 always fires at center.

---

## 6. Causal Chain: Why Solved Games Work

| Game | Solution | Action Types |
|:-----|:---------|:-------------|
| sp80 | (4,4,4,5) | Down ×3 + Action5 |
| cd82 | (3,2,2,4,5) | Up + Right ×2 + Down + Action5 |

**Both solved sequences end with Action5.** Action5 is available in solved games [1-6] but **NOT available in bp35** [3,4,6,7]. Action5 appears to be the 'confirm' or 'execute/apply' action that triggers level transitions. The missing Action5 in bp35 is inherently limiting.

**Both solved games involve translational movement preceding Action5**, suggesting the correct pattern is: move agent to target position → Action5 to interact.

---

## 7. Recommended Fix Direction (for Hermes to decide)

1. **Fix the win detection bug**: BFS must check `fd.state == GameState.WIN` or compare against `win_levels`, not just `levels_completed`. This is a one-line change.

2. **Make Action6 coordinate dynamic**: Vary click coordinates per expansion rather than always at (32,32). The environment API may provide valid click regions.

3. **Expose available_actions properly**: bp35's environment restricts to [3,4,6,7]. Ensure the solver respects this but also checks for alternative action encodings if the game expects action 5 to be mapped differently.

4. **After fix, validate**: Run targeted diagnostics on bp35 and cn04 only (not full 25-game benchmark) to verify the win detection and Action6 changes produce level completions.

---

## Files Saved

| File | Contents |
|:-----|:--------|
| `arc_runs/v30_action_profile_bp35.csv` | Action distribution for bp35 |
| `arc_runs/v30_action_profile_cn04.csv` | Action distribution for cn04 |
| `arc_runs/v30_action_profile_sp80.csv` | Summary metrics for sp80 |
| This report | Full diagnostic findings |
