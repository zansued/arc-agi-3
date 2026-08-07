#!/usr/bin/env python3
"""
v28_verbose_cn04_diagnostic.py — Instrumented v28 archive/bandit solver for cn04.

Run with verbose=true capturing every step: action selection, state transition,
archive updates, replay attempts, and progress events.

This script imports v28_level_reward_shaping.py's core functions and instruments
the solve_from_scratch loop with detailed logging.
"""

import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Import v28's core functions
sys.path.insert(0, '/a0/usr/workdir')

# ── Configuration ──────────────────────────────────────────────────────────
MAX_STEPS = 500
OUT_DIR = 'arc_runs'

# Verbose log
VERBOSE_LOG = []

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def vlog(event_type, **kwargs):
    entry = {
        't': now_iso(),
        'step': len(VERBOSE_LOG),
        'event': event_type,
    }
    entry.update(kwargs)
    VERBOSE_LOG.append(entry)

# Re-implement v28's core solver functions to add verbosity
from arc_agi import Arcade
from arcengine import GameAction

ACTION_NAMES = {
    0: 'RESET', 1: 'ROTATE_CW', 2: 'ROTATE_CCW',
    3: 'FLIP_H', 4: 'FLIP_V', 5: 'TRANSLATE', 6: 'ACTION6/CROP_PASTE',
}

def to_game_action(action):
    if isinstance(action, GameAction):
        return action
    if isinstance(action, str):
        name = action.split('.')[-1]
        if name in GameAction.__members__:
            return GameAction[name]
        return GameAction.RESET
    try:
        value = int(getattr(action, 'value', action))
        return GameAction.from_id(value)
    except:
        return GameAction.RESET

def action_name(action):
    if hasattr(action, 'name'):
        return action.name
    return str(action)

def frame_hash(arr):
    if arr is None:
        return ''
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def extract_frame(raw):
    if raw is None:
        return None
    if isinstance(raw, np.ndarray):
        return raw.squeeze() if raw.ndim > 2 else raw
    if hasattr(raw, 'frame'):
        arr = np.asarray(raw.frame, dtype=np.int32)
        if arr.ndim == 3:
            arr = arr[0]
        return arr
    if hasattr(raw, 'grid'):
        return np.asarray(raw.grid, dtype=np.int32)
    return None

def safe_state(raw):
    s = getattr(raw, 'state', None)
    return str(s) if s is not None else 'UNKNOWN'

def safe_levels(raw):
    return int(getattr(raw, 'levels_completed', 0) or 0)

def safe_win(raw):
    return int(getattr(raw, 'win_levels', 0) or 0)

def progress_ratio(levels_completed, win_levels):
    return levels_completed / max(1, win_levels)

def is_fail(state_str):
    return 'FAIL' in state_str.upper()

def is_win(state_str):
    return 'WIN' in state_str.upper()

def count_changed_pixels(prev, curr):
    if prev is None or curr is None:
        return 0
    try:
        a = np.asarray(prev, dtype=np.int32)
        b = np.asarray(curr, dtype=np.int32)
        if a.shape != b.shape:
            return -1
        return int(np.sum(a != b))
    except:
        return -1

def safe_info(game):
    info = getattr(game, 'info', {})
    if hasattr(info, 'model_dump'):
        info = info.model_dump()
    return info or {}

def get_available_actions(game, info):
    actions = None
    if isinstance(info, dict):
        actions = info.get('available_actions')
    if actions is None:
        raw = getattr(game, 'observation_space', None)
        if raw is not None and hasattr(raw, 'available_actions'):
            raw_actions = raw.available_actions
            if raw_actions:
                actions = raw_actions
    if actions is None:
        aspace = getattr(game, 'action_space', None)
        if hasattr(aspace, 'n'):
            actions = list(range(aspace.n))
        elif isinstance(aspace, (list, tuple, set)):
            actions = list(aspace)
    if actions is None:
        actions = list(range(1, 8))
    safe = []
    for raw_action in list(actions):
        ga = to_game_action(raw_action)
        if action_name(ga) == 'ACTION6':
            continue
        safe.append(ga)
    return safe or [GameAction.RESET]

def get_raw_available_actions(game, info):
    actions = None
    if isinstance(info, dict):
        actions = info.get('available_actions')
    if actions is None:
        raw = getattr(game, 'observation_space', None)
        if raw is not None and hasattr(raw, 'available_actions'):
            raw_actions = raw.available_actions
            if raw_actions:
                actions = raw_actions
    if actions is None:
        aspace = getattr(game, 'action_space', None)
        if hasattr(aspace, 'n'):
            actions = list(range(aspace.n))
        elif isinstance(aspace, (list, tuple, set)):
            actions = list(aspace)
    if actions is None:
        actions = list(range(1, 8))
    raw_actions = [to_game_action(raw_action) for raw_action in list(actions)]
    return raw_actions or [GameAction.RESET]

def step_game(game, action, data=None, reasoning=None):
    raw_before = getattr(game, 'observation_space', None)
    frame_before = extract_frame(raw_before)
    try:
        if data is not None:
            raw_after = game.step(action, data=data, reasoning=reasoning)
        else:
            raw_after = game.step(action, reasoning=reasoning)
        crashed = False
        error = None
    except Exception as exc:
        raw_after = getattr(game, 'observation_space', None)
        crashed = True
        error = f'{type(exc).__name__}: {exc}'
    if raw_after is None:
        raw_after = getattr(game, 'observation_space', None)
    frame_after = extract_frame(raw_after)
    levels_before = safe_levels(raw_before)
    levels_after = safe_levels(raw_after)
    win_lvls = safe_win(raw_after) or safe_win(raw_before)
    state_str = safe_state(raw_after)
    return {
        'raw': raw_after,
        'frame': frame_after,
        'state': state_str,
        'levels_completed': levels_after,
        'win_levels': win_lvls,
        'progress_ratio': progress_ratio(levels_after, win_lvls),
        'delta_levels': max(0, levels_after - levels_before),
        'delta_progress_ratio': progress_ratio(levels_after, win_lvls) - progress_ratio(levels_before, win_lvls),
        'changed_pixels': count_changed_pixels(frame_before, frame_after),
        'available_actions': list(getattr(raw_after, 'available_actions', [])) if raw_after is not None else [],
        'crashed': crashed,
        'error': error,
    }

class SimpleArchive:
    """Simplified version of v28's archive for tracking states."""
    def __init__(self):
        self.cells = {}  # hash -> {frame, visits}
        self.sequences = {}  # hash -> action_seq
        self.replay_record = []
    
    def add_or_update(self, hsh, frame, seq, parent_hash=None, levels=0, step=0, policy='debug'):
        if hsh not in self.cells:
            self.cells[hsh] = {'visits': 0, 'levels': levels, 'first_seen_step': step}
        self.cells[hsh]['visits'] += 1
        self.sequences[hsh] = seq
    
    def record_visit(self, hsh):
        if hsh in self.cells:
            self.cells[hsh]['visits'] += 1
    
    def record_reset(self):
        pass
    
    def record_replay(self, success):
        self.replay_record.append(success)
    
    def select_cell(self, game_id, policy, stagnated):
        if not self.cells:
            return None
        best_hash = max(self.cells, key=lambda h: self.cells[h]['levels'] * 1000 + self.cells[h]['visits'])
        class Cell:
            pass
        cell = Cell()
        cell.state_hash = best_hash
        cell.sequence = [{'action_id': a, 'data': None} for a in (1,)]  # placeholder
        return cell

class SimpleBandit:
    """Simplified bandit for random action selection."""
    def __init__(self):
        self.unique_states = set()
        self.current_hash = None
        self.action_stats = {}
        self.steps_since_new_state = 0
    
    def is_stagnated(self):
        return self.steps_since_new_state > 24
    
    def choose_action(self, avail):
        import random
        return random.choice(avail)
    
    def observe(self, action, changed, hsh, levels, count_action=True, forced_boost=None):
        if hsh not in self.unique_states:
            self.unique_states.add(hsh)
            self.steps_since_new_state = 0
        else:
            self.steps_since_new_state += 1


def v28_verbose_solve_cn04(game_id='cn04', max_steps=MAX_STEPS):
    """v28-style solver with full verbosity."""
    global VERBOSE_LOG
    VERBOSE_LOG = []

    vlog('start', game_id=game_id, max_steps=max_steps, solver='v28-style archive/bandit')

    arcade = Arcade()
    game = arcade.make(game_id)
    if game is None:
        vlog('error', error='Arcade.make returned None')
        return {'game': game_id, 'status': 'ERROR'}

    raw = game.reset()
    frame = extract_frame(raw)
    state_hash = frame_hash(frame)
    init_levels = safe_levels(raw)
    win_levels = safe_win(raw)

    vlog('init',
         init_hash=state_hash,
         init_levels=init_levels,
         win_levels=win_levels,
         state=safe_state(raw),
         frame_shape=list(frame.shape) if frame is not None else None)

    # v28 uses an archive, bandit, but for debugging we do simple stochastic search
    archive = SimpleArchive()
    bandit = SimpleBandit()
    bandit.current_hash = state_hash

    archive.add_or_update(state_hash, frame, [], levels=init_levels, step=0)

    total_steps = 0
    best_levels = init_levels
    current_sequence = []
    forced_probe_count = 0
    crashes = 0
    zero_delta_count = 0

    # Action 6 filter is OFF for cn04 (v28 re-enables it for some games)
    include_action6 = True  # cn04 needs action 6

    while total_steps < max_steps:
        info = safe_info(game)
        raw = getattr(game, 'observation_space', None)
        frame = extract_frame(raw)
        state_hash = frame_hash(frame)
        levels_completed = safe_levels(raw)
        state_str = safe_state(raw)
        
        avail = get_available_actions(game, info)
        raw_avail = get_raw_available_actions(game, info)
        
        # Include action 6 for cn04 if available
        if include_action6:
            for ra in raw_avail:
                if action_name(ra) in ('ACTION6', 'CROP_PASTE'):
                    if ra not in avail:
                        avail.append(ra)

        stagnated = bandit.is_stagnated()
        
        vlog('step_start',
             step=total_steps,
             hash=state_hash,
             levels=levels_completed,
             state=state_str,
             avail_actions=[action_name(a) for a in avail],
             stagnated=stagnated,
             archive_size=len(archive.cells),
             unique_states=len(bandit.unique_states))

        # Select action (random from available)
        import random
        action = random.choice(avail)
        action_id = int(getattr(action, 'value', 0))

        vlog('action_selected',
             action=action_name(action),
             action_id=action_id,
             step=total_steps)

        # Some actions may need data payload
        data = None
        if action_name(action) == 'ACTION6':
            # For cn04, try crop_paste at center
            data = {'x': 32, 'y': 32}

        result = step_game(game, action, data=data, reasoning='v28_diagnostic')
        total_steps += 1

        if result['crashed']:
            crashes += 1
            vlog('crash', action=action_name(action), error=result['error'], step=total_steps)
            continue

        new_frame = result['frame']
        new_hash = frame_hash(new_frame)
        new_levels = result['levels_completed']
        new_state_str = result['state']
        changed = result['changed_pixels']
        zero_delta_count += 1 if changed == 0 else 0

        is_new = new_hash not in archive.cells
        current_sequence.append({'action_id': action_id, 'action_name': action_name(action), 'data': data})

        if is_new:
            archive.add_or_update(new_hash, new_frame, list(current_sequence), 
                                  levels=new_levels, step=total_steps)
        else:
            archive.record_visit(new_hash)

        bandit.observe(action, changed, new_hash, new_levels, count_action=True)

        level_improved = new_levels > best_levels
        if level_improved:
            best_levels = new_levels
            vlog('level_progress',
                 new_levels=new_levels,
                 seq=str(current_sequence),
                 hash=new_hash,
                 state=new_state_str,
                 step=total_steps)

        vlog('step_result',
             step=total_steps,
             action=action_name(action),
             action_id=action_id,
             prev_hash=state_hash,
             new_hash=new_hash,
             changed_pixels=changed,
             new_levels=new_levels,
             new_state=new_state_str,
             is_new_state=is_new,
             archive_size=len(archive.cells),
             unique_states=len(bandit.unique_states),
             zero_delta_rate=round(zero_delta_count / max(1, total_steps), 4))

        if is_win(new_state_str) or is_fail(new_state_str):
            vlog('terminal_state', state=new_state_str, step=total_steps)
            break

    result = {
        'game': game_id,
        'levels_completed': int(best_levels),
        'unique_states': int(len(bandit.unique_states)),
        'archive_size': int(len(archive.cells)),
        'steps': int(total_steps),
        'crashes': int(crashes),
        'zero_delta_rate': round(zero_delta_count / max(1, total_steps), 4),
        'status': 'OK',
    }

    vlog('complete', result=result)
    return result


if __name__ == '__main__':
    print("=" * 70)
    print("v28 VERBOSE DIAGNOSTIC — cn04 Archive/Bandit Solver")
    print("=" * 70)
    print(f"Start: {now_iso()}")
    print(f"Max steps: {MAX_STEPS}")
    print()

    start = time.time()
    result = v28_verbose_solve_cn04()
    elapsed = time.time() - start
    result['elapsed_seconds'] = round(elapsed, 2)

    print(f"\nResult: {json.dumps(result, indent=2)}")
    print(f"\nElapsed: {elapsed:.2f}s")
    print(f"Verbose log entries: {len(VERBOSE_LOG)}")

    # Save outputs
    log_path = '/a0/usr/workdir/arc_runs/v28_cn04_verbose_log.jsonl'
    os.makedirs(Path(log_path).parent, exist_ok=True)
    with open(log_path, 'w') as f:
        for entry in VERBOSE_LOG:
            f.write(json.dumps(entry) + '\n')
    print(f"Verbose log saved: {log_path} ({len(VERBOSE_LOG)} entries)")

    summary_path = '/a0/usr/workdir/arc_runs/v28_cn04_verbose_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"Summary saved: {summary_path}")

    # Print key findings
    print("\n" + "=" * 70)
    print("KEY FINDINGS (v28 cn04 verbose)")
    print("=" * 70)
    print(f"Levels completed: {result['levels_completed']}")
    print(f"Unique states discovered: {result['unique_states']}")
    print(f"Archive size: {result['archive_size']}")
    print(f"Steps: {result['steps']}")
    print(f"Crashes: {result['crashes']}")
    print(f"Zero-delta rate: {result['zero_delta_rate']}")

    # Count event types
    event_counts = Counter(e['event'] for e in VERBOSE_LOG)
    print(f"\nEvent type breakdown:")
    for evt, cnt in sorted(event_counts.items()):
        print(f"  {evt}: {cnt}")

    print(f"\n[{now_iso()}] Done.")
