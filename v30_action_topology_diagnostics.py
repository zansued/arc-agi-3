#!/usr/bin/env python3
"""
v30_action_topology_diagnostics — action-space profiling for ARC-AGI-3 games.

Phase: v30_action_topology_diagnostics
Purpose: Map action diversity for 4 games (bp35, cn04, sp80, ls20) at 30-step cutoffs.
Outputs: Markdown profiles + cn04 debug trace JSON.
"""

import copy
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction
from arcengine.enums import GameState

# ── Configuration ──────────────────────────────────────────────────────────
TARGET_GAMES = ['bp35', 'cn04', 'sp80', 'ls20']
DIAG_STEPS = 30          # Total actions across all expansions
OUT_DIR = Path('arc_runs/v30_action_topology')

# ── Utilities ──────────────────────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def frame_from_fd(fd):
    if hasattr(fd, 'frame') and fd.frame is not None and len(fd.frame) > 0:
        return np.asarray(fd.frame[0])
    return None

def frame_hash(arr):
    if arr is None:
        return ''
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def fd_action_list(fd):
    avail = getattr(fd, 'available_actions', None)
    if avail is not None and len(avail) > 0:
        return [int(a) for a in avail]
    return [0, 1, 2, 3, 4, 5, 6]

def is_win(state_val):
    return state_val in (GameState.WIN, 'WIN')

def is_game_over(state_val):
    return state_val in (GameState.GAME_OVER, 'GAME_OVER')

def wrapper_state_str(fd):
    st = getattr(fd, 'state', None)
    return str(st) if st is not None else 'UNKNOWN'

def safe_wrapper_levels(fd):
    return int(getattr(fd, 'levels_completed', 0) or 0)

ACTION_NAMES = {
    0: 'noop', 1: 'rotate_cw', 2: 'rotate_ccw',
    3: 'flip_h', 4: 'flip_v', 5: 'translate',
    6: 'crop_paste', 7: 'color_swap'
}

def action_name(aid):
    return ACTION_NAMES.get(aid, f'unknown_{aid}')

# ── Wrapper helpers (from v30) ─────────────────────────────────────────────

def snapshot_wrapper(wrapper):
    return copy.deepcopy(wrapper)

def step_and_fetch(wrapper, action_id):
    try:
        action = GameAction.from_id(action_id)
        if action_id == 6:
            fd = wrapper.step(action, data={'x': 32, 'y': 32})
        else:
            fd = wrapper.step(action)
    except Exception as e:
        return None, None, f'STEP_ERR: {e}', 0
    if fd is None:
        return None, None, 'FD_NONE', 0
    frame = frame_from_fd(fd)
    st = wrapper_state_str(fd)
    lvl = safe_wrapper_levels(fd)
    return fd, frame, st, lvl


# ── Diagnostic BFS (capped at DIAG_STEPS, logs per-step) ────────────────────

def diagnostic_bfs(game_id: str) -> dict:
    """Run BFS capped at DIAG_STEPS total actions, logging per-step details."""
    arcade = Arcade()
    wrapper = arcade.make(game_id)
    if wrapper is None:
        return {'game_id': game_id, 'status': 'ERROR', 'error': 'Arcade.make returned None'}

    fd_init = wrapper.reset()
    init_frame = frame_from_fd(fd_init)
    init_hash = frame_hash(init_frame)
    avail_actions = fd_action_list(fd_init)

    # ── Action-tracking structures ──
    action_log: list[dict] = []      # Per-step log
    action_histogram: dict[str, int] = defaultdict(int)  # Action type counts
    unique_states: set[str] = {init_hash}
    revisit_count = 0
    frontier_peak = 0

    # Frontier init
    frontier = [{'wrapper': snapshot_wrapper(wrapper), 'state_hash': init_hash,
                 'action_seq': (), 'depth': 0, 'levels_completed': 0}]
    safe_stash = [frontier[0]]

    total_actions_consumed = 0
    nodes_expanded = 0
    expansions_without_new_state = 0
    best_levels = 0
    levels_progress_events = []

    print(f"  [{game_id}] Starting diagnostic BFS, max_steps={DIAG_STEPS}, avail_actions={avail_actions}")

    while frontier and total_actions_consumed < DIAG_STEPS:
        node = frontier.pop(0)
        frontier_peak = max(frontier_peak, len(frontier) + 1)

        for act in avail_actions:
            if total_actions_consumed >= DIAG_STEPS:
                break

            clone = snapshot_wrapper(node['wrapper'])
            fd, frame, state_str, levels = step_and_fetch(clone, act)
            total_actions_consumed += 1
            nodes_expanded += 1

            if frame is None:
                continue

            h = frame_hash(frame)
            is_novel = h not in unique_states
            if is_novel:
                unique_states.add(h)
                expansions_without_new_state = 0
            else:
                revisit_count += 1
                expansions_without_new_state += 1

            # Track best levels
            if levels > best_levels:
                best_levels = levels
                levels_progress_events.append({
                    'step': total_actions_consumed,
                    'levels': levels,
                    'hash': h,
                    'action': int(act),
                })

            # Log this step
            step_entry = {
                'step': total_actions_consumed,
                'node_depth': node['depth'],
                'action': int(act),
                'action_name': action_name(act),
                'state_hash': h,
                'is_novel': is_novel,
                'levels': levels,
                'frontier_size': len(frontier),
                'visited_count': len(unique_states),
            }
            action_log.append(step_entry)
            action_histogram[action_name(act)] += 1

            # Push to frontier if novel and not terminal
            if is_novel and not is_game_over(state_str) and node['depth'] + 1 < 100:
                new_node = {
                    'wrapper': clone,
                    'state_hash': h,
                    'action_seq': node['action_seq'] + (act,),
                    'depth': node['depth'] + 1,
                    'levels_completed': levels,
                }
                frontier.append(new_node)
                safe_stash.append(new_node)

    # Compute revisit ratio
    revisit_ratio = round(revisit_count / max(total_actions_consumed, 1), 3)

    return {
        'game_id': game_id,
        'status': 'OK',
        'actions_total': total_actions_consumed,
        'nodes_expanded': nodes_expanded,
        'unique_states': len(unique_states),
        'unique_actions': len(action_histogram),
        'action_histogram': dict(action_histogram),
        'revisit_count': revisit_count,
        'revisit_ratio': revisit_ratio,
        'frontier_peak': frontier_peak,
        'best_levels': best_levels,
        'levels_progress': levels_progress_events,
        'action_log': action_log,
        'avail_actions': [int(a) for a in avail_actions],
    }


# ── Profile writers ─────────────────────────────────────────────────────────

def write_action_profile(game_id: str, result: dict, out_dir: Path):
    """Write markdown action profile for one game."""
    out_path = out_dir / f'{game_id}_action_profile.md'
    hist = result.get('action_histogram', {})
    total = result.get('actions_total', 0)
    unique = result.get('unique_actions', 0)

    sorted_actions = sorted(hist.items(), key=lambda x: -x[1])

    lines = [
        f'# Action Topology Profile: {game_id}',
        f'',
        f'**Phase:** v30_action_topology_diagnostics',
        f'**Timestamp:** {time.strftime("%Y-%m-%d %H:%M:%S")}',
        f'**Max Steps:** {DIAG_STEPS}',
        f'',
        f'## Summary',
        f'',
        f'| Metric | Value |',
        f'|--------|-------|',
        f'| Total Actions Attempted | {total} |',
        f'| Nodes Expanded | {result.get("nodes_expanded", 0)} |',
        f'| Unique States Discovered | {result.get("unique_states", 0)} |',
        f'| Unique Action Types Used | {unique} |',
        f'| Revisit Count | {result.get("revisit_count", 0)} |',
        f'| Revisit Ratio | {result.get("revisit_ratio", 0):.3f} |',
        f'| Frontier Peak Size | {result.get("frontier_peak", 0)} |',
        f'| Best Levels Completed | {result.get("best_levels", 0)} |',
        f'| Available Actions | {result.get("avail_actions", [])} |',
        f'',
        f'## Action Type Histogram',
        f'',
        f'| Action | Count | % |',
        f'|--------|------:|--:|',
    ]
    for act_name, cnt in sorted_actions:
        pct = round(100 * cnt / max(total, 1), 1)
        lines.append(f'| {act_name} | {cnt} | {pct}% |')

    lines.extend([
        f'',
        f'## Step-by-Step Action Log',
        f'',
        f'| Step | Depth | Action | Novel? | Levels | Frontier | Visited |',
        f'|-----:|------:|:-------|:------:|:------:|:--------:|:-------:|',
    ])
    for entry in result.get('action_log', []):
        lines.append(
            f'| {entry["step"]} | {entry["node_depth"]} '
            f'| {entry["action_name"]} '
            f'| {"✅" if entry["is_novel"] else "🔄"} '
            f'| {entry["levels"]} | {entry["frontier_size"]} | {entry["visited_count"]} |'
        )

    lines.append(f'')

    if result.get('levels_progress'):
        lines.append(f'## Levels Progress Events')
        lines.append(f'')
        for ev in result['levels_progress']:
            lines.append(f'- Step {ev["step"]}: reached level {ev["levels"]} via action {ev["action"]}')

    text = '\n'.join(lines)
    ensure_dir(out_dir)
    with open(out_path, 'w') as f:
        f.write(text)
    print(f'  ✓ Profile written: {out_path}')


def write_cn04_debug_trace(result: dict, out_dir: Path):
    """Write cn04 debug trace as JSON."""
    if result.get('game_id') != 'cn04':
        return
    out_path = out_dir / 'cn04_debug_trace.json'
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f'  ✓ Debug trace written: {out_path}')


# ── Main ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    ensure_dir(OUT_DIR)

    # Determine which games to run
    if '--game' in sys.argv:
        idx = sys.argv.index('--game')
        games = [sys.argv[idx + 1]] if idx + 1 < len(sys.argv) else TARGET_GAMES
    else:
        games = TARGET_GAMES

    print(f'v30 Action Topology Diagnostics')
    print(f'Target games: {" ".join(games)}')
    print(f'Max steps per game: {DIAG_STEPS}')
    print(f'Output dir: {OUT_DIR}')
    print()

    all_results = {}

    for gid in games:
        print(f'[{gid}] Running diagnostic BFS...')
        start = time.time()
        try:
            result = diagnostic_bfs(gid)
            elapsed = time.time() - start
            result['elapsed_seconds'] = round(elapsed, 2)
            all_results[gid] = result

            print(f'  Status: {result["status"]}')
            print(f'  Actions: {result["actions_total"]}, Unique: {result["unique_states"]}, '
                  f'Revisit%: {result["revisit_ratio"]:.1%}')
            print(f'  Histogram: {result["action_histogram"]}')
            print(f'  Elapsed: {elapsed:.1f}s')
            print()

            write_action_profile(gid, result, OUT_DIR)
            write_cn04_debug_trace(result, OUT_DIR)

        except Exception as e:
            import traceback
            traceback.print_exc()
            all_results[gid] = {
                'game_id': gid,
                'status': 'ERROR',
                'error': str(e),
            }
            print(f'  ✗ CRASHED: {e}')
            print()

    # Write comparison table
    comparison_lines = [
        f'# v30 Action Topology Comparison',
        f'',
        f'**Phase:** v30_action_topology_diagnostics',
        f'**Timestamp:** {time.strftime("%Y-%m-%d %H:%M:%S")}',
        f'**Max Steps Per Game:** {DIAG_STEPS}',
        f'',
        f'## Comparison Table',
        f'',
        f'| Game | Total Actions | Unique Actions | Unique States | Revisit Ratio | Frontier Peak | Best Levels | Solved? | Notes |',
        f'|:----|:------------:|:--------------:|:-------------:|:-------------:|:-------------:|:-----------:|:------:|:------|',
    ]
    solved_lookup = {'bp35': True, 'cn04': False, 'sp80': True, 'ls20': False}

    for gid in TARGET_GAMES:
        r = all_results.get(gid, {})
        if r.get('status') == 'ERROR':
            comparison_lines.append(f'| {gid} | — | — | — | — | — | — | — | CRASHED: {r.get("error", "")} |')
        else:
            hist = r.get('action_histogram', {})
            comparison_lines.append(
                f'| {gid} | {r.get("actions_total", "?")} | {r.get("unique_actions", "?")} '
                f'| {r.get("unique_states", "?")} | {r.get("revisit_ratio", "?")} '
                f'| {r.get("frontier_peak", "?")} | {r.get("best_levels", 0)} '
                f'| {"✅" if solved_lookup.get(gid) else "❌"} '
                f'| Actions: {dict(sorted(hist.items(), key=lambda x:-x[1]))} |'
            )

    comparison_lines.extend([
        f'',
        f'## Action Diversity Analysis',
        f'',
        f'### Solved vs Unsolved Comparison',
        f'',
    ])

    # Compute aggregate
    solved_hist: dict[str, int] = defaultdict(int)
    unsolved_hist: dict[str, int] = defaultdict(int)
    for gid in TARGET_GAMES:
        r = all_results.get(gid, {})
        hist = r.get('action_histogram', {})
        if solved_lookup.get(gid):
            for k, v in hist.items():
                solved_hist[k] += v
        else:
            for k, v in hist.items():
                unsolved_hist[k] += v

    comparison_lines.extend([
        f'**Solved games (bp35, sp80) action pool:** {dict(sorted(solved_hist.items(), key=lambda x:-x[1]))}',
        f'',
        f'**Unsolved games (cn04, ls20) action pool:** {dict(sorted(unsolved_hist.items(), key=lambda x:-x[1]))}',
        f'',
    ])

    # Gap analysis
    solved_keys = set(solved_hist.keys())
    unsolved_keys = set(unsolved_hist.keys())
    only_solved = solved_keys - unsolved_keys
    only_unsolved = unsolved_keys - solved_keys

    if only_solved:
        comparison_lines.append(f'- Actions used ONLY in solved games: {only_solved}')
    if only_unsolved:
        comparison_lines.append(f'- Actions used ONLY in unsolved games: {only_unsolved}')
    if not only_solved and not only_unsolved:
        comparison_lines.append(f'- No exclusive action types — all actions appear in both solved and unsolved.')

    comparison_lines.append(f'')
    comparison_lines.append(f'### Interpretation')
    comparison_lines.append(f'')
    comparison_lines.append(f'If revisit ratio is significantly higher in unsolved games, the solver is '
                            f'cycling rather than exploring — action vocabulary is not the bottleneck; '
                            f'heuristic/state evaluation is.')
    comparison_lines.append(f'')
    comparison_lines.append(f'If action histogram shows unsolved games MISSING key actions that solved games '
                            f'use, the action vocabulary IS the bottleneck for those games.')

    comp_text = '\n'.join(comparison_lines)
    comp_path = OUT_DIR / 'action_diversity_comparison.md'
    with open(comp_path, 'w') as f:
        f.write(comp_text)
    print(f'✓ Comparison table written: {comp_path}')
    print()

    # Print final summary
    print('=' * 60)
    print('PHASE COMPLETE: v30_action_topology_diagnostics')
    print(f'Games processed: {len(games)}')
    print(f'Artifacts in: {OUT_DIR}')
    for gid in TARGET_GAMES:
        r = all_results.get(gid, {})
        status = '✅' if r.get('status') == 'OK' else '❌'
        print(f'  {status} {gid}')
    print('=' * 60)
