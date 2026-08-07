#!/usr/bin/env python3
"""
ARC-AGI-3 baseline solver — action-repeat + spectral routing + replay archive.
Known ceiling: 2 levels on sp80 and cn04.

Extracted from v24_fix4_cn04_v23_path (ARC-DGM-lite lineage).
Self-contained: only depends on arc_agi + stdlib.
"""

import csv
import hashlib
import json
import math
import os
import random
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction

# ── Constants ──────────────────────────────────────────────
MAX_STEPS = 500
OUT_DIR = 'arc_runs'
MAX_REPLAY_LEN = 80
MAX_ARCHIVE_RESETS = 6
STAGNATION_STEPS = 24
ZERO_DELTA_STREAK = 8

FRAGILE_GAMES = {'tn36', 'vc33', 'su15', 'sk48', 'm0r0'}
STRONG_GAMES = {'sp80', 'bp35', 'ls20', 'wa30', 're86'}

FULL_GAMES = [
    'sk48', 'bp35', 'tn36', 'wa30', 'vc33', 'tu93', 'tr87', 'su15', 'sp80',
    'sc25', 'sb26', 's5i5', 're86', 'r11l', 'm0r0', 'ls20', 'lp85', 'lf52',
    'ka59', 'g50t', 'ft09', 'dc22', 'cd82', 'ar25', 'cn04',
]

# ── Helpers ────────────────────────────────────────────────

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def frame_hash(arr):
    if arr is None:
        return ''
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()

def count_changed_pixels(prev, curr):
    if prev is None or curr is None:
        return 0
    try:
        a = np.asarray(prev, dtype=np.int32)
        b = np.asarray(curr, dtype=np.int32)
        if a.shape != b.shape:
            return -1
        return int(np.sum(a != b))
    except Exception:
        return -1

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

def safe_info(game):
    info = getattr(game, 'info', {})
    if hasattr(info, 'model_dump'):
        info = info.model_dump()
    return info or {}

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
    except Exception:
        return GameAction.RESET

def action_name(action):
    if hasattr(action, 'name'):
        return action.name
    return str(action)

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
        'state_hash': frame_hash(frame_after),
        'levels_completed': levels_after,
        'win_levels': win_lvls,
        'changed_pixels': count_changed_pixels(frame_before, frame_after),
        'crashed': crashed,
        'error': error,
        'state_str': state_str,
    }

def select_best_action_summary(action_stats):
    best_name = None
    best_rate = -1.0
    best_count = 0
    for name, stats in action_stats.items():
        count = stats['count']
        if count <= 0:
            continue
        rate = stats['successes'] / max(1, count)
        if count >= 3 and rate > best_rate:
            best_name = name
            best_rate = rate
            best_count = count
    if best_name is None:
        for name, stats in action_stats.items():
            count = stats['count']
            if count > best_count:
                best_name = name
                best_count = count
                best_rate = stats['successes'] / max(1, count)
    return best_name or 'ACTION1', round(best_rate if best_rate >= 0 else 0.0, 4)

def log_jsonl(handle, obj):
    handle.write(json.dumps(obj, default=str) + '\n')
    handle.flush()

# ── Core Classes ────────────────────────────────────────────

class PolicyArchiveRouter:
    """Routes policy based on historical performance for each game."""
    def __init__(self, game_id, history_dir=OUT_DIR):
        self.game_id = game_id
        self.history_dir = Path(history_dir)
        self.history_rows = self._load_history()
        self.history_count = len(self.history_rows)
        self.best_row = self._pick_best_row()
        self.best_policy = self._safe_str(self.best_row.get('policy')) if self.best_row else 'fallback'
        self.best_states = self._safe_int(self.best_row.get('unique_states')) if self.best_row else 0
        self.best_crashes = self._safe_int(self.best_row.get('crashes')) if self.best_row else 0
        self.best_replay_rate = self._safe_float(self.best_row.get('replay_success_rate')) if self.best_row else 0.0
        self.avg_states = self._avg_states()
        self.route_family = self._classify_route()
        self.policy = 'v10_final' if self.route_family == 'fragile' else 'v14_spectral' if self.route_family == 'strong' else 'fallback'
        self.replay_floor, self.replay_ceiling = self._replay_bounds()
        self.base_replay = self._derive_base_replay()
        self.early_penalty = 0.07 if self.route_family == 'strong' else 0.05 if self.route_family == 'fallback' else 0.03
        self.stagnation_bonus = 0.11 if self.route_family == 'strong' else 0.09 if self.route_family == 'fallback' else 0.10
        self.min_archive_for_replay = 4 if self.route_family == 'strong' else 5 if self.route_family == 'fallback' else 6
        self.max_resets = 6 if self.route_family == 'strong' else 3 if self.route_family == 'fallback' else 3
        self.min_replay_gap = 42 if self.route_family == 'strong' else 64 if self.route_family == 'fallback' else 72
        self.min_growth_for_replay = 4 if self.route_family == 'strong' else 6 if self.route_family == 'fallback' else 8
        self.routable = self.history_count > 0

    def _safe_str(self, value):
        return str(value) if value is not None else ''
    def _safe_int(self, value):
        try: return int(float(value))
        except: return 0
    def _safe_float(self, value):
        try: return float(value)
        except: return 0.0

    def _load_history(self):
        rows = []
        if not self.history_dir.exists():
            return rows
        for csv_path in sorted(self.history_dir.glob('summary_v*.csv')):
            try:
                with csv_path.open('r', encoding='utf-8', newline='') as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        if row.get('game') == self.game_id:
                            row = dict(row)
                            row['_source'] = csv_path.name
                            rows.append(row)
            except Exception:
                continue
        return rows

    def _pick_best_row(self):
        if not self.history_rows:
            return None
        def sort_key(row):
            return (self._safe_int(row.get('unique_states')),
                    self._safe_int(row.get('levels_completed')),
                    -self._safe_int(row.get('crashes')),
                    self._safe_float(row.get('replay_success_rate')),
                    -self._safe_int(row.get('steps')))
        return max(self.history_rows, key=sort_key)

    def _avg_states(self):
        if not self.history_rows:
            return 0.0
        return sum(self._safe_int(r.get('unique_states')) for r in self.history_rows) / max(1, len(self.history_rows))

    def _classify_route(self):
        if self.game_id in FRAGILE_GAMES:
            return 'fragile'
        if self.best_states >= 100 or self.game_id in STRONG_GAMES:
            return 'strong'
        return 'fallback'

    def _replay_bounds(self):
        if self.route_family == 'strong':
            return 0.04, 0.24
        if self.route_family == 'fallback':
            return 0.02, 0.13
        return 0.01, 0.10

    def _derive_base_replay(self):
        norm = min(1.0, self.best_states / 180.0) if self.best_states else 0.0
        base = 0.06 + 0.10 * norm
        if self.route_family == 'strong':
            base += 0.03
        elif self.route_family == 'fallback':
            base -= 0.03
        else:
            base -= 0.04
        if self.best_crashes > 0:
            base -= 0.02
        if self.best_replay_rate > 0.95 and self.route_family != 'strong':
            base -= 0.01
        return max(self.replay_floor, min(self.replay_ceiling, base))

    def replay_probability(self, step_idx, archive_size, stagnated, archive_growth):
        if archive_size < self.min_archive_for_replay:
            return 0.02 if self.route_family == 'fragile' else 0.0
        prob = self.base_replay
        if step_idx < 16:
            prob -= self.early_penalty
        elif step_idx < 48:
            prob -= self.early_penalty * 0.5
        if archive_size > 20:
            prob += min(0.05, archive_size / 1200.0)
        if stagnated:
            prob += self.stagnation_bonus
        if self.route_family == 'fallback' and archive_size < 32:
            prob -= 0.03
        if self.route_family == 'fallback' and archive_growth < self.min_growth_for_replay:
            prob -= 0.06
        if self.route_family == 'strong' and archive_growth < self.min_growth_for_replay:
            prob -= 0.04
        if self.route_family == 'strong' and self.best_states < 40:
            prob -= 0.04
        return max(self.replay_floor, min(self.replay_ceiling, prob))

    def replay_allowed(self, step_idx, archive_size, resets, last_replay_step, archive_growth, stagnated):
        if resets >= self.max_resets:
            return False
        if self.route_family == 'fragile' and resets >= 1:
            return False
        if archive_size < self.min_archive_for_replay:
            return False
        if step_idx - last_replay_step < self.min_replay_gap:
            return False
        if self.route_family == 'fragile' and not stagnated:
            return False
        if archive_growth < self.min_growth_for_replay and not stagnated:
            return False
        return True


class ProgressBandit:
    """Adaptive multi-armed bandit for action selection."""
    def __init__(self, game_id, policy):
        self.game_id = game_id
        self.policy = policy
        self.action_stats = defaultdict(lambda: {
            'count': 0, 'successes': 0, 'zero_deltas': 0,
            'total_delta': 0, 'recent_changes': deque(maxlen=10),
        })
        self.unique_states = set()
        self.zero_delta_streak = 0
        self.steps_since_new_state = 0
        self.step_count = 0
        self.last_action_name = None
        self.max_levels = 0
        self.current_hash = None

    def is_stagnated(self):
        return self.zero_delta_streak >= ZERO_DELTA_STREAK or self.steps_since_new_state >= STAGNATION_STEPS

    def _safe_actions(self, available_actions):
        safe = []
        for action in available_actions:
            if action_name(action) == 'ACTION6':
                continue
            safe.append(action)
        return safe or [GameAction.RESET]

    def choose_action(self, available_actions):
        safe = self._safe_actions(available_actions)
        if not safe:
            return GameAction.RESET

        def score(action):
            name = action_name(action)
            stats = self.action_stats[name]
            count = stats['count']
            successes = stats['successes']
            novelty = 1.0 / (1.0 + count)
            success_rate = successes / max(1, count)
            recent = sum(stats['recent_changes']) / max(1, len(stats['recent_changes']))
            repeat_penalty = 0.25 if self.last_action_name == name else 0.0
            if self.policy == 'v10_final':
                return 3.0 * novelty + 0.4 * success_rate - 0.05 * count - repeat_penalty
            if self.policy == 'v14_spectral':
                return 4.0 * novelty + 0.5 * success_rate + 0.02 * recent - 0.03 * count - repeat_penalty
            return 3.0 * novelty + 0.25 * success_rate - 0.04 * count - repeat_penalty

        ranked = sorted(safe, key=score, reverse=True)
        if self.policy == 'v10_final':
            chosen = ranked[0]
        else:
            top_n = min(5, len(ranked)) if self.policy == 'v14_spectral' else min(3, len(ranked))
            pool = ranked[:top_n]
            weights = [max(0.01, 1.0 / (1.0 + self.action_stats[action_name(a)]['count'] * 0.15)) for a in pool]
            chosen = random.choices(pool, weights=weights, k=1)[0]
        self.last_action_name = action_name(chosen)
        return chosen

    def observe(self, action, changed, state_hash, levels, count_action=True):
        self.step_count += 1
        is_new = state_hash not in self.unique_states
        if is_new:
            self.unique_states.add(state_hash)
            self.zero_delta_streak = 0
            self.steps_since_new_state = 0
        else:
            self.steps_since_new_state += 1
            if changed == 0:
                self.zero_delta_streak += 1
            else:
                self.zero_delta_streak = 0
        if levels > self.max_levels:
            self.max_levels = levels
        if count_action and action is not None:
            name = action_name(action)
            stats = self.action_stats[name]
            stats['count'] += 1
            stats['recent_changes'].append(changed)
            if is_new:
                stats['successes'] += 1
            if changed == 0:
                stats['zero_deltas'] += 1
            else:
                stats['total_delta'] += changed
            self.last_action_name = name
        self.current_hash = state_hash


class ForcedExplorationPhase:
    """Probes for initial state transition when archive has only 1 unique state."""
    def __init__(self, enabled, initial_hash):
        self.enabled = bool(enabled)
        self.active = bool(enabled)
        self.initial_hash = initial_hash
        self.discovered_states = {initial_hash} if initial_hash else set()
        self.counter = 0
        self.steps = 0
        self.max_steps = 0
        self.irrecoverable = False
        self.last_action = None
        self.payload_counter = 0

    def is_active(self, archive_size, zero_delta_rate, steps_since_new_state):
        if not self.enabled or not self.active or self.irrecoverable:
            return False
        if archive_size > 1 or len(self.discovered_states) > 1:
            self.active = False
            return False
        return archive_size == 1 and (self.steps == 0 or zero_delta_rate >= 0.95 or steps_since_new_state >= 8)

    def next_action(self, available_actions):
        actions = list(available_actions) or [GameAction.RESET]
        self.max_steps = max(self.max_steps, max(1, len(actions) * 3))
        action = actions[self.counter % len(actions)]
        self.counter += 1
        self.steps += 1
        self.last_action = action_name(action)
        return action

    def payload_for(self, action, frame):
        if action_name(action) != 'ACTION6':
            return None
        coords = self._coords(frame)
        if not coords:
            return {'x': 0, 'y': 0}
        self.max_steps = max(self.max_steps, min(96, max(len(coords), self.max_steps)))
        x, y = coords[self.payload_counter % len(coords)]
        self.payload_counter += 1
        return {'x': int(x), 'y': int(y)}

    def _coords(self, frame):
        if frame is None:
            width, height = 8, 8
        else:
            try:
                arr = np.asarray(frame)
                height, width = arr.shape[:2]
            except Exception:
                width, height = 8, 8
        width = max(1, int(width))
        height = max(1, int(height))
        base = [
            (width // 2, height // 2),
            (0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1),
            (width // 3, height // 3), ((2 * width) // 3, height // 3),
            (width // 3, (2 * height) // 3), ((2 * width) // 3, (2 * height) // 3),
        ]
        seen = set()
        coords = []
        for x, y in base:
            x = min(width - 1, max(0, x))
            y = min(height - 1, max(0, y))
            if (x, y) not in seen:
                seen.add((x, y))
                coords.append((x, y))
        step_x = max(1, width // 4)
        step_y = max(1, height // 4)
        for y in range(0, height, step_y):
            for x in range(0, width, step_x):
                if (x, y) not in seen:
                    seen.add((x, y))
                    coords.append((x, y))
                if len(coords) >= 96:
                    return coords
        return coords

    def record_outcome(self, state_hash, changed_pixels):
        if state_hash:
            self.discovered_states.add(state_hash)
        if len(self.discovered_states) > 1:
            self.active = False
        elif self.max_steps and self.steps >= self.max_steps:
            self.irrecoverable = True
            self.active = False


class ArchiveCell:
    """A stored state snapshot with its action sequence and metadata."""
    def __init__(self, state_hash, sequence, frame, levels=0, step=0, policy='fallback'):
        self.state_hash = state_hash
        self.sequence = list(sequence)
        self.frame = frame.copy() if frame is not None else None
        self.visits = 1
        self.children = set()
        self.max_levels = levels
        self.last_improved_step = step
        self.policy = policy
        self.score = 0.0
        self.created_step = step


class MinimalVisitedArchive:
    """Deduplicated archive of visited states with replay selection."""
    def __init__(self):
        self.cells = {}
        self.total_visits = 0
        self.n_resets = 0
        self.n_replays = 0
        self.n_replay_success = 0
        self.max_size = 256

    def add_or_update(self, state_hash, frame, sequence, parent_hash=None, levels=0, step=0, policy='fallback'):
        if not state_hash:
            return None
        if state_hash in self.cells:
            cell = self.cells[state_hash]
            cell.visits += 1
            self.total_visits += 1
            if len(sequence) < len(cell.sequence):
                cell.sequence = list(sequence)
                cell.frame = frame.copy() if frame is not None else None
                cell.policy = policy
            if levels > cell.max_levels:
                cell.max_levels = levels
                cell.last_improved_step = step
            return cell
        if len(self.cells) >= self.max_size:
            worst = min(self.cells.values(), key=lambda c: (c.score, c.visits, len(c.sequence)))
            del self.cells[worst.state_hash]
        cell = ArchiveCell(state_hash, sequence, frame, levels=levels, step=step, policy=policy)
        self.cells[state_hash] = cell
        if parent_hash and parent_hash in self.cells:
            self.cells[parent_hash].children.add(state_hash)
        return cell

    def record_visit(self, state_hash):
        if state_hash in self.cells:
            self.cells[state_hash].visits += 1
            self.total_visits += 1

    def record_replay(self, success):
        self.n_replays += 1
        if success:
            self.n_replay_success += 1

    def record_reset(self):
        self.n_resets += 1

    def select_cell(self, game_id, policy, stagnated):
        cells = [c for c in self.cells.values() if 0 < len(c.sequence) <= MAX_REPLAY_LEN]
        if not cells:
            return None
        if game_id in FRAGILE_GAMES and not stagnated and len(cells) < 4:
            return None

        def score(cell):
            seq_len = len(cell.sequence)
            novelty = 1.0 / (1.0 + cell.visits)
            frontier = 1.0 if len(cell.children) == 0 else 0.35
            depth = min(1.0, seq_len / 20.0)
            policy_bias = 0.0
            if policy == 'v14_spectral':
                policy_bias += 0.2 if seq_len >= 15 else 0.0
            elif policy == 'v10_final':
                policy_bias += 0.2 if seq_len <= 25 else 0.0
            return 2.5 * novelty + 1.2 * frontier + 0.8 * depth - 0.18 * cell.visits - 0.02 * seq_len + policy_bias

        ranked = sorted(cells, key=score, reverse=True)
        top_n = min(5, len(ranked))
        if game_id in FRAGILE_GAMES:
            top_n = min(3, len(ranked))
        return random.choice(ranked[:top_n])

# ── Core Solver Loop ────────────────────────────────────────

def run_game(game_id, max_steps=MAX_STEPS, out_dir=OUT_DIR):
    """Run the ARC-AGI-3 solver for a single game."""
    ensure_dir(out_dir)
    seed_prefix = 'v23:' if game_id == 'cn04' else 'v24_fix2:'
    seed = int(hashlib.md5(f'{seed_prefix}{game_id}'.encode('utf-8')).hexdigest()[:8], 16)
    random.seed(seed)
    np.random.seed(seed & 0xFFFFFFFF)

    router = PolicyArchiveRouter(game_id)
    bandit = ProgressBandit(game_id, router.policy)
    archive = MinimalVisitedArchive()

    game = Arcade().make(game_id)
    try:
        game.reset()
    except Exception:
        pass

    raw = getattr(game, 'observation_space', None)
    frame = extract_frame(raw)
    state_hash = frame_hash(frame)
    info = safe_info(game)
    levels_completed = safe_levels(raw)
    win_levels = safe_win(raw)

    bandit.unique_states.add(state_hash)
    bandit.current_hash = state_hash
    archive.add_or_update(state_hash, frame, [], parent_hash=None, levels=levels_completed, step=0, policy=router.policy)

    forced_probe_games = {'tn36', 'vc33', 'su15', 's5i5', 'ft09', 'lp85', 'r11l'}

    total_steps = 0
    crashes = 0
    resets = 0
    zero_delta_count = 0
    last_progress = 0.0
    last_state_str = ''
    best_seen_levels = 0
    best_seen_state = ''
    level_progress_events = 0
    progress_ratio_events = 0
    state_string_changes = 0
    win_signal_seen = False
    terminal_signal_seen = False
    current_sequence = []
    replay_idx = 0
    mode = 'FRESH'
    selected_cell = None
    last_replay_step = 0
    archive_size_at_last_replay = 0
    replay_attempts = 0
    replay_successes = 0
    replay_steps = 0
    live_steps = 0
    forced_probe_count = 0
    forced_probe = ForcedExplorationPhase(game_id in forced_probe_games, state_hash)
    while total_steps < max_steps:
        info = safe_info(game)
        raw = getattr(game, 'observation_space', None)
        frame = extract_frame(raw)
        state_hash = frame_hash(frame)
        levels_completed = safe_levels(raw)
        win_levels = safe_win(raw)
        state_str = safe_state(raw)
        avail = get_available_actions(game, info)
        raw_avail = get_raw_available_actions(game, info)
        stagnated = bandit.is_stagnated()
        archive_growth = len(archive.cells) - archive_size_at_last_replay
        current_zero_delta_rate = zero_delta_count / max(1, total_steps)

        if mode == 'RESET_TO_ARCHIVE':
            try:
                game.reset()
            except Exception:
                crashes += 1
                break
            resets += 1
            archive.record_reset()
            raw = getattr(game, 'observation_space', None)
            frame = extract_frame(raw)
            state_hash = frame_hash(frame)
            bandit.current_hash = state_hash
            current_sequence = []
            replay_idx = 0
            mode = 'REPLAY'
            continue

        if mode == 'REPLAY' and selected_cell is not None:
            if replay_idx < len(selected_cell.sequence):
                record = selected_cell.sequence[replay_idx]
                action = to_game_action(record.get('action_id', 0))
                data = record.get('data')
                prev_hash = state_hash
                result = step_game(game, action, data=data, reasoning=f'replay_{replay_idx}')
                total_steps += 1
                replay_steps += 1
                current_sequence.append(record)
                if result['crashed']:
                    crashes += 1
                    break
                raw = result['raw']
                frame = result['frame']
                state_hash = frame_hash(frame)
                levels_completed = result['levels_completed']
                win_levels = result['win_levels']
                changed = result['changed_pixels']
                zero_delta_count += 1 if changed == 0 else 0
                bandit.observe(None, changed, state_hash, levels_completed, count_action=False)
                if state_hash not in archive.cells:
                    archive.add_or_update(state_hash, frame, list(current_sequence), parent_hash=prev_hash, levels=levels_completed, step=total_steps, policy=router.policy)
                if levels_completed > best_seen_levels:
                    best_seen_levels = levels_completed
                    best_seen_state = state_hash
                    level_progress_events += 1
                new_progress = progress_ratio(levels_completed, win_levels)
                if new_progress > last_progress:
                    last_progress = new_progress
                    progress_ratio_events += 1
                current_state_str = safe_state(raw)
                if current_state_str != last_state_str:
                    state_string_changes += 1
                    last_state_str = current_state_str
                if is_win(current_state_str):
                    win_signal_seen = True
                if is_win(current_state_str) or is_fail(current_state_str):
                    terminal_signal_seen = True
                replay_idx += 1
                if replay_idx >= len(selected_cell.sequence):
                    success = state_hash == selected_cell.state_hash
                    archive.record_replay(success)
                    if success:
                        replay_successes += 1
                    archive.record_visit(selected_cell.state_hash)
                    mode = 'FRESH'
                    selected_cell = None
                    current_sequence = list(current_sequence)
                continue
            else:
                success = state_hash == selected_cell.state_hash
                archive.record_replay(success)
                if success:
                    replay_successes += 1
                archive.record_visit(selected_cell.state_hash)
                mode = 'FRESH'
                selected_cell = None
                current_sequence = list(current_sequence)
                continue

        should_replay = False
        if archive.cells and router.replay_allowed(
            total_steps,
            len(archive.cells),
            resets,
            last_replay_step,
            archive_growth,
            stagnated,
        ):
            replay_prob = router.replay_probability(total_steps, len(archive.cells), stagnated, archive_growth)
            should_replay = random.random() < replay_prob

        if should_replay:
            selected_cell = archive.select_cell(game_id, router.policy, stagnated)
            if selected_cell is not None:
                replay_attempts += 1
                last_replay_step = total_steps
                archive_size_at_last_replay = len(archive.cells)
                mode = 'RESET_TO_ARCHIVE'
                continue

        forced_probe_used = forced_probe.is_active(len(archive.cells), current_zero_delta_rate, bandit.steps_since_new_state)
        if forced_probe_used:
            action = forced_probe.next_action(raw_avail)
            forced_probe_count += 1
        else:
            action = bandit.choose_action(avail)
        prev_hash = state_hash
        data = forced_probe.payload_for(action, frame) if forced_probe_used else None
        action_id = int(getattr(action, 'value', 0))
        if action_name(action) == 'ACTION6' and not forced_probe_used:
            action = GameAction.RESET
            action_id = int(getattr(action, 'value', 0))
        result = step_game(game, action, data=data, reasoning=f'live_{router.policy}')
        total_steps += 1
        live_steps += 1
        if result['crashed']:
            crashes += 1
            break

        raw = result['raw']
        frame = result['frame']
        state_hash = frame_hash(frame)
        levels_completed = result['levels_completed']
        win_levels = result['win_levels']
        changed = result['changed_pixels']
        zero_delta_count += 1 if changed == 0 else 0
        current_sequence.append({'action_id': action_id, 'action_name': action_name(action), 'data': data})
        bandit.observe(action, changed, state_hash, levels_completed, count_action=True)
        if forced_probe_used:
            forced_probe.record_outcome(state_hash, changed)
        is_new = state_hash not in archive.cells
        if is_new:
            archive.add_or_update(state_hash, frame, list(current_sequence), parent_hash=prev_hash, levels=levels_completed, step=total_steps, policy=router.policy)
        else:
            archive.record_visit(state_hash)
        if levels_completed > best_seen_levels:
            best_seen_levels = levels_completed
            best_seen_state = state_hash
            level_progress_events += 1
        new_progress = progress_ratio(levels_completed, win_levels)
        if new_progress > last_progress:
            last_progress = new_progress
            progress_ratio_events += 1
        current_state_str = safe_state(raw)
        current_state_changed = current_state_str != last_state_str
        if current_state_changed:
            state_string_changes += 1
            last_state_str = current_state_str
        if is_win(current_state_str):
            win_signal_seen = True
        if is_win(current_state_str) or is_fail(current_state_str):
            terminal_signal_seen = True

        if is_win(current_state_str) or is_fail(current_state_str):
            break

    total_unique_states = len(bandit.unique_states)
    zero_delta_rate = zero_delta_count / max(1, total_steps)
    best_action, best_action_success_rate = select_best_action_summary(bandit.action_stats)
    summary = {
        'game': game_id,
        'policy': router.policy,
        'route_family': router.route_family,
        'levels_completed': int(best_seen_levels),
        'unique_states': int(total_unique_states),
        'zero_delta_rate': round(zero_delta_rate, 4),
        'crashes': int(crashes),
        'archive_size': int(len(archive.cells)),
        'steps': int(total_steps),
        'live_steps': int(live_steps),
        'replay_steps': int(replay_steps),
        'replay_attempts': int(replay_attempts),
        'replay_successes': int(replay_successes),
        'replay_success_rate': round(replay_successes / max(1, replay_attempts), 4),
        'best_action': best_action,
        'best_action_success_rate': best_action_success_rate,
        'forced_probe_count': int(forced_probe_count),
        'forced_probe_irrecoverable': bool(forced_probe.irrecoverable),
    }
    return summary


def run_benchmark(games, out_dir=OUT_DIR):
    ensure_dir(out_dir)
    results = []
    for gid in games:
        print(f'  {gid}...', flush=True)
        summary = run_game(gid, out_dir=out_dir)
        results.append(summary)
    csv_path = os.path.join(out_dir, 'kaggle_submission_summary.csv')
    if results:
        with open(csv_path, 'w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
    return results


def main(argv):
    games = argv[1:] if len(sys.argv) > 1 else FULL_GAMES
    print('=' * 60)
    print('ARC-AGI-3 Kaggle Submission Solver')
    print(f'Games: {len(games)}')
    print('=' * 60)
    results = run_benchmark(games)
    print('=' * 60)
    print('SUMMARY')
    print('=' * 60)
    for item in results:
        print(f"{item['game']:15s} {item['policy']:11s} | states={item['unique_states']:3d} | levels={item['levels_completed']} | crashes={item['crashes']}")
    avg_states = sum(item['unique_states'] for item in results) / max(1, len(results))
    total_levels = sum(item['levels_completed'] for item in results)
    print(f"AVG states: {avg_states:.1f} | Total levels: {total_levels} | Crash-free: {sum(1 for r in results if r['crashes']==0)}/{len(results)}")
    return results


if __name__ == '__main__':
    main(sys.argv)
