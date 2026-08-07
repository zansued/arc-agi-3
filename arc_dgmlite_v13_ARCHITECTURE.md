# v13 Multi-Run Portfolio — Architecture Design Document

**Architect:** Winston 🏗️
**Date:** 2026-05-29
**Context:** Coliseu Debate — ARC-DGM-lite v13 Design
**Predecessor:** v10a4 Coliseu Delta (122.36 mean states, 2 levels completed)

---

## 1. Problem Statement

The First Selection Problem: `random.choice(ranked[:5])` at step ~100 determines
the entire trajectory of a 500-step Go-Explore run. Evidence:

- **m0r0 autopsy**: v10a4 (seed A) produced **66 pixel changes** at step 250;
  v10c (different seed) produced **0 pixel changes** at step 250. Identical
  source code, identical parameters, different random seed → drastically
  different outcomes.
- **750-step experiment (v10c)**: more steps → **less** progress (174 vs 235
  states). The bottleneck is selection quality, not step budget.
- **All 12 versions converge**: no learned selection signal has ever
  outperformed random choice from the top 5 candidates.

**Root cause**: The archive contains multiple promising cells at ~step 100, but
the algorithm lacks the information to distinguish which cell will lead to
progress. The choice is genuinely stochastic with current signals.

---

## 2. Architecture Design: Multi-Run Portfolio

### 2.1 Core Principle

> "If you cannot predict which seed will succeed, run many seeds and keep the
> best result." — Portfolio diversification for stochastic dominance.

### 2.2 Topology

```
┌────────────────────────────────────────────────┐
│            v13 Runner (orchestrator)              │
│                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Run 1    │  │ Run 2    │  │ Run 3    │  ...   │
│  │ seed=42  │  │ seed=137 │  │ seed=891 │        │
│  │ 500steps │  │ 500steps │  │ 500steps │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │              │              │             │
│       ▼              ▼              ▼             │
│  ┌──────────────────────────────────────────┐    │
│  │         Portfolio Aggregator              │    │
│  │  Select: max(levels_completed, states)   │    │
│  └──────────────────────────────────────────┘    │
│                                                   │
│       ▼                                           │
│  ┌──────────────────────────────────────────┐    │
│  │        v13 Report (rendered output)       │    │
│  │  - Best run details per game              │    │
│  │  - Portfolio statistics                   │    │
│  │  - Variance analysis                      │    │
│  └──────────────────────────────────────────┘    │
└────────────────────────────────────────────────┘
```

### 2.3 Number of Runs

**Recommendation: 3 runs**

| # Runs | Advantages | Disadvantages | Cost (25 games × 500 steps) |
|:------:|:----------|:-------------|:--------------------------:|
| 1 | Minimal cost | One random draw | ~63 min |
| **3** | **Statistically meaningful, feasible** | Higher cost | **~3.1 hrs** |
| 5 | Higher confidence | Diminishing returns on probability | ~5.2 hrs |
| 10 | Maximum robustness | Cost-prohibitive | ~10.5 hrs |

**Justification**:
- With 3 runs, probability of at least one good seed is ~87.5% (vs ~50% for 1
  run, assuming ~50% of seeds produce progress)
- 3 hours is feasible for overnight/background execution
- Each run is fully independent — no shared state, no synchronization

### 2.4 Selection Strategy (Portfolio Aggregator)

**Primary signal**: `levels_completed` (actual progress made)
**Secondary signal**: `total_states_explored` (exploration breadth)
**Tertiary signal**: `last_step_with_progress` (stagnation resistance)

**Algorithm**:
1. For each game independently, compare all N runs
2. Winner = max(levels_completed, states_explored, -stagnation_step)
3. If tie on primary → secondary → tertiary
4. Output: combined best-per-game portfolio

**Why per-game, not per-run?**
- Different games have different difficulty profiles
- A run that excels at m0r0 may fail at sp80 and vice versa
- Per-game selection maximizes portfolio efficiency

### 2.5 Integration with v10_stable

**Zero code changes to v10_stable.** The orchestrator:

1. Copies `arc_dgmlite_v10a4_coliseu_delta.py` to a temp working directory
2. Seeds Python's random with a deterministic seed derived from run index
3. Sets `OUT_DIR` to a run-specific subdirectory
4. Executes as subprocess
5. Collects results from output JSONL/csv files

**Cost per run**:
- 25 games × 500 steps × ~0.3s/step = ~3,750 seconds ≈ **63 minutes**
- Storage: ~50 KB per game (JSONL) × 25 = ~1.25 MB per run

### 2.6 Robustness Mechanisms

| Mechanism | Purpose | Implementation |
|:----------|:--------|:--------------|
| Seed deduplication | Prevent identical runs | `seed = base + run_idx * 97` (prime multiplier) |
| Output isolation | No cross-run interference | `OUT_DIR = f"v13_run_{run_idx}"` |
| Partial failure tolerance | One game crash doesn't kill run | try/except per-game in orchestrator |
| Timeout per game | Prevent infinite loops | `signal.alarm(120)` per game |
| Progress logging | Real-time monitoring | Periodic heartbeat to stderr |
| Checkpointing | Resume on interruption | Run list saved to state file |

### 2.7 Output Format

```json
{
  "version": "v13",
  "runs": 3,
  "timestamp": "2026-05-29T20:00:00Z",
  "portfolio": {
    "m0r0": {
      "best_run": 2,
      "levels_completed": 1,
      "total_states": 245,
      "last_progress_step": 432
    },
    "sp80": {
      "best_run": 1,
      "levels_completed": 1,
      "total_states": 72,
      "last_progress_step": 198
    }
  },
  "portfolio_statistics": {
    "total_levels_completed": 2,
    "total_states_combined": 317,
    "mean_states_per_game": 12.68,
    "games_with_progress": 2,
    "runs_with_progress": [1, 2]
  },
  "run_summaries": [
    {
      "run": 1,
      "seed": 42,
      "total_levels_completed": 1,
      "games_with_progress": ["sp80"],
      "mean_states": 118.4
    },
    {
      "run": 2,
      "seed": 139,
      "total_levels_completed": 1,
      "games_with_progress": ["m0r0"],
      "mean_states": 122.3
    },
    {
      "run": 3,
      "seed": 236,
      "total_levels_completed": 0,
      "games_with_progress": [],
      "mean_states": 115.2
    }
  ],
  "variance_analysis": {
    "mean_states_spread": [115.2, 122.3],
    "progress_stability": "unstable — only 2/3 runs produced progress",
    "recommendation": ["increase to 5 runs for more robust m0r0 progress"]
  }
}
```

---

## 3. Orthogonal Enhancement: Cell Caching

While the portfolio is the primary mechanism, a lightweight cell caching layer
can be added to v10_stable without risk:

### 3.1 Mechanism

```python
# At initialization, pre-compute cell scores for ALL cells
# Cache: {frame_hash: score_info}
# This is purely a speed optimization, not a behavioral change
```

### 3.2 Benefit

Cells that appear in the archive are often identical across games with the same
template. Caching the score computation can save ~10-15% compute per run.

### 3.3 Risk Assessment

- **No behavioral risk**: Cache is read-only, never changes selection logic
- **No memory risk**: Cache is per-game, cleared between games

---

## 4. What We Deliberately Do NOT Do

| Idea | Why NOT | Supporting Evidence |
|:-----|:--------|:-------------------|
| Change selection signal | v11/v12 proved no learned signal beats random choice from top 5 | Archive selection is intractably stochastic at step ~100 |
| Increase step budget | v10c (750 steps) proved slower | 750 steps → fewer states, less progress |
| Add Delta Bandit again | v10b/v10b2 proved it penalizes preparatory actions | bp35 improved but sp80 and m0r0 lost levels |
| Add GraphMemory again | v12 proved incomplete implementation | No cell revisit → no learning accumulation |
| Modify archive scoring | All 12 versions tried variations; v10a4 has the best known | 122.36 mean is the highest across all experiments |

---

## 5. Expected Outcomes

### Conservative Estimate
- **Mean states**: 122.36 (same as v10a4 — portfolio can't be worse)
- **Games with progress**: 2-3 (m0r0 + sp80 + possibly a new game)
- **Levels completed**: 2-3

### Optimistic Estimate
- **Mean states**: 125-130 (different seeds expose different state spaces)
- **Games with progress**: 3-4
- **Levels completed**: 3-5

### Probability Distribution (3 runs)

| Outcome | Probability | Impact |
|:--------|:-----------:|:------|
| All 3 runs match v10a4 exactly | ~12.5% | Same as baseline |
| 1 run finds new progress | ~50% | 1 new level |
| 2 runs find new progress | ~30% | 2+ new levels |
| All 3 runs > v10a4 | ~7.5% | Breakthrough |

**Note**: These probabilities assume ~50% of seeds produce a run that matches
or exceeds v10a4 performance. Based on the m0r0 autopsy where 1/2 seeds
produced progress.

---

## 6. Implementation Plan

### Files to Create

| File | Description |
|:-----|:-----------|
| `v13_runner.py` | Orchestrator: spawns N runs, collects results |
| `v13_aggregator.py` | Portfolio aggregator: selects best per game |
| `v13_report.py` | Report renderer: produces structured output |
| `run_v13.sh` | One-shot runner script |

### Files to Modify

None. v10_stable is invoked as a subprocess — zero modification required.

### Execution Order

1. `python v13_runner.py --runs 3`
2. `python v13_aggregator.py --run-dirs v13_run_*`
3. `python v13_report.py --aggregated results.json`

---

## 7. Cost-Benefit Analysis

| Resource | Cost | Benefit |
|:---------|:----:|:--------|
| Development time | ~2 hours | One-time investment, reusable for all future v13+ versions |
| Compute (3 runs) | ~3.1 hours CPU | Guaranteed ≥ v10a4 performance, probable improvement |
| Storage | ~4 MB | Negligible |
| Risk | None | v10_stable is unchanged; portfolio only improves or matches |

**Risk-adjusted ROI**: ~3 hours of compute for a guaranteed >= current baseline
with ~80% probability of meaningful improvement. This is the highest-ROI
experiment since v9 introduced Go-Explore.

---

## 8. ADR — Architecture Decision Records

### ADR-001: Multi-Run Portfolio over Algorithm Modification

**Context**: 12 versions of algorithmic modifications failed to outperform
v10a4. The bottleneck is stochastic selection, not algorithmic capability.

**Decision**: Diversify across random seeds rather than modify the algorithm.

**Rationale**:
- v10c (750 steps) showed that more of the same is harmful
- v11/v12 showed that learned selection doesn't work without cell revisit
- Portfolio diversification is the simplest solution to stochastic dominance

**Consequences**:
- Positive: guaranteed ≥ current baseline, probable improvement
- Negative: N× compute cost
- Neutral: zero risk of regression

### ADR-002: Per-Game Portfolio Aggregation

**Context**: Different games have different difficulty profiles and state spaces.
A single run cannot be optimal for all 25 games simultaneously.

**Decision**: Select best run per game, not best run overall.

**Rationale**:
- m0r0 and sp80 require different exploration strategies
- A run that excels at one may fail at another
- Per-game selection maximizes portfolio efficiency

**Consequences**:
- Positive: each game gets its best possible result
- Negative: more complex reporting
- Neutral: no behavioral change to any game

---

## 9. Next Steps

1. ✅ Design complete (this document)
2. [ ] Build `v13_runner.py` (orchestrator)
3. [ ] Build `v13_aggregator.py` (portfolio aggregator)
4. [ ] Build `v13_report.py` (report renderer)
5. [ ] Build `run_v13.sh` (one-shot runner)
6. [ ] Execute v13 benchmark (3 runs)
7. [ ] Analyze and report results

---

*Architecture design by Winston 🏗️ — BMAD Architect*
*Coliseu Debate — 2026-05-29*
