#!/usr/bin/env python3
"""Analyze v9_sp80.jsonl for level-up window."""
import json, sys

path = sys.argv[1] if len(sys.argv) > 1 else '/a0/usr/workdir/arc_runs/v9_sp80.jsonl'

logs = []
with open(path) as f:
    for line in f:
        if line.strip():
            logs.append(json.loads(line))

print(f'Total steps logged: {len(logs)}')

# Find level-up steps
level_up = [l for l in logs if l.get('levels_completed', 0) > 0]
print(f'Steps with levels_completed > 0: {len(level_up)}')

if not level_up:
    print("NO LEVELS COMPLETED")
    sys.exit(0)

first_lu = level_up[0]
lu_step = first_lu['step']
print(f'\n=== LEVEL-UP at STEP {lu_step} ===')
print(f'Mode: {first_lu.get("mode", "?")}')
print(f'Action: {first_lu.get("action_name", "?")}')
print(f'Action ID: {first_lu.get("action_id", "?")}')
print(f'State hash: {first_lu.get("state_hash", "")[:16]}')
print(f'Changed pixels: {first_lu.get("changed_pixels", "?")}')
print(f'Unique states: {first_lu.get("unique_states", "?")}')
print(f'Archive size: {first_lu.get("archive_size", "?")}')
print(f'n_resets: {first_lu.get("n_resets", "?")}')
print(f'n_replays: {first_lu.get("n_replays", "?")}')
print(f'Selected cell: {first_lu.get("selected_cell", "none")}')
print(f'Sequence len: {first_lu.get("sequence_len", "?")}')

# Window: 30 before to 10 after
start = max(0, lu_step - 30)
end = min(len(logs), lu_step + 10)
window = logs[start:end]

print(f'\n=== WINDOW [st.{start} -> st.{end}] ({len(window)} steps) ===')
print('-' * 130)
print(f"{'STEP':<6} {'MODE':<22} {'ACTION':<14} {'CHG':<5} {'UNIQ':<5} {'LVL':<4} {'ARC':<5} {'REPOK':<8} {'ZDSTREAK':<9} {'SELC':<12} {'HASH':<10}")
print('-' * 130)

prev_levels = 0
for l in window:
    h = l.get('state_hash', '')[:10]
    sel = str(l.get('selected_cell', ''))[:12] if l.get('selected_cell') else ''
    print(f"{l.get('step',''):<6} {str(l.get('mode',''))[:22]:<22} {str(l.get('action_name',''))[:14]:<14} "
          f"{l.get('changed_pixels',''):<5} {l.get('unique_states',''):<5} "
          f"{l.get('levels_completed',''):<4} {l.get('archive_size',''):<5} "
          f"{l.get('replay_success_rate',''):<8} {l.get('zero_delta_streak',''):<9} {sel:<12} {h:<10}")
    if l.get('levels_completed', 0) > prev_levels:
        print(f"{'^'*60} *** LEVEL-UP!")
    prev_levels = l.get('levels_completed', 0)

# Stats
unique_in_window = set(l.get('state_hash', '') for l in window)
print(f'\n=== WINDOW SUMMARY ===')
print(f'Unique states in window: {len(unique_in_window)}')
print(f'Modes: {sorted(set(l.get("mode","") for l in window))}')
acts = [l.get('action_name','') for l in window]
act_counts = {}
for a in sorted(set(acts)):
    act_counts[a] = acts.count(a)
print(f'Actions: {act_counts}')

# Actions before level-up
before = [l for l in window if l['step'] < lu_step]
acts_before = [l.get('action_name','') for l in before]
print(f'Actions before level-up: {dict((a, acts_before.count(a)) for a in sorted(set(acts_before)))}')

# Classify
print(f'\n=== CLASSIFICATION ===')
has_archive = any(l.get('archive_size', 0) > 0 for l in window)
has_replay = any(l.get('n_replays', 0) > 0 for l in window)
lu_mode = first_lu.get('mode', '?')
is_archive_mode = 'EXPLORE' in str(lu_mode) or 'CELL' in str(lu_mode)
print(f'Level-up mode: {lu_mode}')
print(f'Archive active: {has_archive}')
print(f'Replay happened: {has_replay}')
print(f'Is archive related: {is_archive_mode}')
