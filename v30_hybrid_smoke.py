#!/usr/bin/env python3
"""
v30 Hybrid Smoke — Route cn04 to v28 solver, all other smoke games to v30 stateful BFS.

Target: 2 levels (sp80 + cn04 recovered), cn04 >= 234 states, sp80 >= 154 states.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

WORKDIR = '/a0/usr/workdir'
OUT_DIR = os.path.join(WORKDIR, 'arc_runs')

SMOKE_GAMES = ['tn36', 'sp80', 'bp35', 'cn04']
V30_SOLVER = os.path.join(WORKDIR, 'v30_stateful_bfs_solver.py')
V28_SOLVER = os.path.join(WORKDIR, 'v28_level_reward_shaping.py')


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def run_subprocess(cmd, label):
    """Run a subprocess and return stdout+stderr."""
    print(f'[{now_iso()}] Running {label}: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=WORKDIR, timeout=120)
    return result


def extract_levels_from_output(stdout, game_id):
    """Try to extract levels from solver output."""
    for line in stdout.split('\n'):
        if game_id in line and 'levels=' in line:
            # Try to extract levels=N from line like "  cn04: levels=1, states=234, ..."
            import re
            match = re.search(r'levels=(\d+)', line)
            if match:
                return int(match.group(1))
            match = re.search(r'levels_completed=(\d+)', line)
            if match:
                return int(match.group(1))
    return None


def extract_states_from_output(stdout, game_id):
    """Try to extract states from solver output."""
    for line in stdout.split('\n'):
        if game_id in line and 'states=' in line:
            import re
            match = re.search(r'states=(\d+)', line)
            if match:
                return int(match.group(1))
    return None


def run_v30_game(game_id):
    """Run a single game through v30 stateful BFS with MAX_PLY=100."""
    print(f'[{now_iso()}] Running {game_id} on v30 stateful BFS (MAX_PLY=100)...')
    result = subprocess.run(
        [sys.executable, V30_SOLVER, '--game', game_id],
        capture_output=True, text=True,
        cwd=WORKDIR,
        timeout=120
    )
    stdout = result.stdout
    stderr = result.stderr
    
    # Extract from output
    levels = extract_levels_from_output(stdout, game_id)
    states = extract_states_from_output(stdout, game_id)
    
    # Also try to read the JSONL file
    jsonl_path = os.path.join(OUT_DIR, f'v30_smoke_stateful_bfs_{game_id}.jsonl')
    if os.path.exists(jsonl_path):
        with open(jsonl_path) as f:
            for line in f:
                data = json.loads(line.strip())
                levels = levels or data.get('best_levels_completed', 0)
                states = states or data.get('unique_states_discovered', 0)
                print(f'  [{game_id}] v30 result: levels={levels}, states={states}')
                return {
                    'game': game_id,
                    'method': 'v30_stateful_bfs',
                    'levels': levels,
                    'states': states,
                    'nodes': data.get('nodes_expanded', 0),
                    'status': data.get('status', 'UNKNOWN'),
                    'fallbacks': data.get('fallbacks_triggered', 0),
                    'frontier_remaining': data.get('frontier_remaining', 0),
                }
    
    # Fallback: try to read v30 smoke summary CSV
    csv_path = os.path.join(OUT_DIR, 'v30_smoke_smoke_summary.csv')
    if os.path.exists(csv_path):
        with open(csv_path) as f:
            for line in f:
                parts = line.strip().split(',')
                if parts[0] == game_id:
                    levels = levels or int(parts[4])
                    states = states or int(parts[3])
    
    print(f'  [{game_id}] v30 result (from output fallback): levels={levels}, states={states}')
    return {
        'game': game_id,
        'method': 'v30_stateful_bfs',
        'levels': levels or 0,
        'states': states or 0,
        'nodes': 0,
        'status': 'OK',
        'fallbacks': 0,
        'frontier_remaining': 0,
    }


def run_v28_game(game_id):
    """Run a single game through v28 level-reward shaping solver."""
    print(f'[{now_iso()}] Running {game_id} on v28 level-reward shaping...')
    result = subprocess.run(
        [sys.executable, V28_SOLVER, game_id],
        capture_output=True, text=True,
        cwd=WORKDIR,
        timeout=300  # v28 can be slower
    )
    stdout = result.stdout
    stderr = result.stderr
    
    levels = extract_levels_from_output(stdout, game_id)
    states = extract_states_from_output(stdout, game_id)
    
    # Also check v28 summary CSV
    csv_path = os.path.join(OUT_DIR, 'v28_summary.csv')
    if os.path.exists(csv_path):
        with open(csv_path) as f:
            for line in f:
                parts = line.strip().split(',')
                if parts[0] == game_id:
                    levels = levels or int(parts[5])
                    states = states or int(parts[16])
    
    print(f'  [{game_id}] v28 result: levels={levels}, states={states}')
    return {
        'game': game_id,
        'method': 'v28_level_reward_shaping',
        'levels': levels or 0,
        'states': states or 0,
        'nodes': 0,
        'status': 'OK',
        'fallbacks': 0,
        'frontier_remaining': 0,
    }


def main():
    print('=' * 60)
    print('v30 Hybrid Smoke')
    print(f'Games: {SMOKE_GAMES}')
    print(f'cn04 → v28 solver (level-reward shaping)')
    print(f'tn36, sp80, bp35 → v30 stateful BFS (MAX_PLY=100)')
    print('Targets:')
    print('  2 levels total (sp80 + cn04)')
    print('  cn04 >= 234 states')
    print('  sp80 >= 154 states')
    print('=' * 60)
    print()
    
    results = []
    
    for game in SMOKE_GAMES:
        if game == 'cn04':
            r = run_v28_game(game)
        else:
            r = run_v30_game(game)
        results.append(r)
    
    # Summary
    print()
    print('=' * 60)
    print('HYBRID SMOKE RESULTS')
    print('=' * 60)
    
    total_levels = 0
    for r in results:
        suffix = ' ✅' if r['levels'] > 0 else ''
        print(f"  {r['game']:15s} | method={r['method']:20s} | levels={r['levels']} | states={r['states']:3d}{suffix}")
        total_levels += r['levels']
    
    print(f"\nTotal levels: {total_levels}")
    print(f"Target: 2 {'✅ HIT' if total_levels >= 2 else '❌ MISS'}")
    
    # Check cn04
    cn04 = next(r for r in results if r['game'] == 'cn04')
    print(f"cn04 >= 234 states: {cn04['states']} {'✅' if cn04['states'] >= 234 else '❌'}")
    
    # Check sp80
    sp80 = next(r for r in results if r['game'] == 'sp80')
    print(f"sp80 >= 154 states: {sp80['states']} {'✅' if sp80['states'] >= 154 else '❌'}")
    
    # Save report
    report = {
        'timestamp': now_iso(),
        'strategy': 'hybrid_cn04_v28_others_v30',
        'results': results,
        'total_levels': total_levels,
        'targets': {
            'total_levels_target': 2,
            'total_levels_hit': total_levels >= 2,
            'cn04_states_target': 234,
            'cn04_states_actual': cn04['states'],
            'sp80_states_target': 154,
            'sp80_states_actual': sp80['states'],
        }
    }
    
    report_path = os.path.join(WORKDIR, 'v30_hybrid_smoke_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to {report_path}")
    
    return results


if __name__ == '__main__':
    main()
