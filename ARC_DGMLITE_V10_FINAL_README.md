# ARC-DGM-lite v10 Final — ACTION6 Router

## Stable Version

**v10_final = `arc_dgmlite_v10a4_action6_router.py`**

## File Location

`/a0/usr/workdir/arc_dgmlite_v10a4_action6_router.py`

## How to Run

### Single Game

```bash
cd /a0/usr/workdir
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('router', 'arc_dgmlite_v10a4_action6_router.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
result = mod.run_benchmark(['tn36'])
print(result)
"
```

### Full 25-Game Benchmark

```bash
cd /a0/usr/workdir
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('router', 'arc_dgmlite_v10a4_action6_router.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from arc_agi import Arcade
arcade = Arcade()
envs = arcade.get_environments()
games = sorted([e.game_id.split('-')[0] for e in envs], key=str.lower)

for g in games:
    r = mod.run_benchmark([g])[0]
    print(f'{g}: {r["unique_states"]} states | {r["zero_delta_rate"]:.3f} zd')
"
```

## Expected Metrics

| Metric | Value |
|:-------|:-----:|
| Mean states (25 games) | **129.84** |
| Zero crashes | **25/25** |
| ACTION6-only games unlocked | **4/4** (tn36, su15, ft09, lp85) |
| Mean states (8 controls, 48 runs) | **98.5** |
| sp80 progress rate | **1/3 runs** |

## Key Results

| Game | Before (v10a4) | v10_final | Gain |
|:-----|:--------------:|:---------:|:----:|
| tn36 | 1 | **69** | +68 |
| su15 | 1 | **69** | +68 |
| ft09 | 1 | **34** | +33 |
| lp85 | 1 | **15** | +14 |
| sp80 | 63 | 62 | −1 |
| m0r0 | 235 | 165+ | −70 |

## Architecture

- **Two modes**: NORMAL_MODE (v10a4 stable) and ACTION6_MODE
- **Router decision**: `should_enable_action6()` checks whitelist + available actions
- **ACTION6 whitelist**: tn36, su15, ft09, lp85
- **Coordinates**: 22 preset click points on a 64×64 grid, cycled by step
- **Routed step**: `step_game()` delegates to `step_action6()` when action is ACTION6
- **Archive**: Saves `data` parameter; replay reapplies it

## Final Classification

| Version | Role |
|:--------|:-----|
| **v10a4_action6_router** | **v10_final / stable** |
| v10a4_coliseu_delta | Baseline without ACTION6 |
| v10b/v10b2/v10c | Archived |
| v11/v11b | Archived |
| v12 | Archived research line |

## Known Limitations

- Currently identical code runs in both modes (only the ACTION6 call differs)
- RouterBandit subclass of ProgressBandit with action6_mode flag
- sp80/m0r0 progress not consistently reproducible (stochastic)
- No graph memory integration
- Single-run benchmark (not portfolio)

## Related Files

- `/a0/usr/workdir/ARC_DGMLITE_RESEARCH_REPORT.md` — Full research history v1→v12
- `/a0/usr/workdir/arc_dgmlite_v10a4_coliseu_delta.py` — Historical baseline
- `/a0/usr/workdir/arc_runs/comparison_control_20260530_215807.csv` — 48-run control comparison
- `/a0/usr/workdir/arc_runs/summary_router.csv` — 25-game benchmark results

*Generated: 2026-05-30 23:30 BRT*
*Stable version: v10a4_action6_router*
