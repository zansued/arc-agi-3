#!/usr/bin/env python3
"""
Clone-step sanity test for sp80.

Tests:
1. Instantiate sp80 game via Arcade
2. Deepcopy the game state (wrapper)
3. Step the clone forward by one action
4. Verify the original game state is UNMODIFIED
5. Step the clone a few more times and confirm observation space consistency
6. Log results to arc_runs/clone_step_sanity_sp80.json
"""

import copy
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from arc_agi import Arcade
from arcengine import GameAction
from arcengine.enums import GameState

GAME_ID = 'sp80'
OUT_DIR = Path('arc_runs')
OUT_FILE = OUT_DIR / 'clone_step_sanity_sp80.json'


def frame_from_fd(fd):
    """Extract numpy frame array from FrameDataRaw."""
    if hasattr(fd, 'frame') and fd.frame is not None and len(fd.frame) > 0:
        return np.asarray(fd.frame[0])
    return None


def frame_hash(arr):
    """Hash a frame for comparison."""
    if arr is None:
        return 'NONE'
    import hashlib
    return hashlib.md5(np.asarray(arr, dtype=np.int32).tobytes()).hexdigest()


def fd_describe(fd, label="fd"):
    """Return a dict describing the key fields of a FrameDataRaw."""
    desc = {}
    desc[f'{label}_levels_completed'] = int(getattr(fd, 'levels_completed', -1) or -1)
    desc[f'{label}_state'] = str(getattr(fd, 'state', 'N/A'))
    state_val = getattr(fd, 'state', None)
    # Store state as string: GameState is a string enum (e.g. 'NOT_FINISHED'), not numeric
    if state_val is not None:
        desc[f'{label}_state_val'] = str(state_val.value) if hasattr(state_val, 'value') else str(state_val)
    else:
        desc[f'{label}_state_val'] = 'NONE'
    
    # Frame info
    frame = frame_from_fd(fd)
    desc[f'{label}_frame_shape'] = str(frame.shape) if frame is not None else 'NONE'
    desc[f'{label}_frame_hash'] = frame_hash(frame)
    desc[f'{label}_frame_sum'] = int(np.sum(frame)) if frame is not None else -1
    
    # Available actions
    avail = getattr(fd, 'available_actions', None)
    desc[f'{label}_available_actions'] = [int(a) for a in avail] if avail is not None and len(avail) > 0 else []
    
    return desc


def run_sanity_test() -> dict:
    """Run the full clone-step sanity test."""
    results = {
        'game_id': GAME_ID,
        'start_time': time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime()),
        'tests': [],
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    
    # ── Test 0: Instantiation ──
    test0 = {'name': 'instantiate', 'status': 'running'}
    try:
        arcade = Arcade()
        wrapper = arcade.make(GAME_ID)
        if wrapper is None:
            test0['status'] = 'FAIL'
            test0['error'] = 'arcade.make() returned None'
            results['tests'].append(test0)
            results['overall_status'] = 'FAIL'
            return results
        test0['status'] = 'PASS'
        test0['wrapper_type'] = type(wrapper).__name__
    except Exception as e:
        test0['status'] = 'ERROR'
        test0['error'] = str(e)
        results['tests'].append(test0)
        results['overall_status'] = 'ERROR'
        return results
    results['tests'].append(test0)
    
    # ── Test 1: Reset + deepcopy ──
    test1 = {'name': 'deepcopy_reset_state', 'status': 'running'}
    try:
        fd_orig = wrapper.reset()
        wrapper_copy = copy.deepcopy(wrapper)
        
        # Describe both states
        fd_copy = wrapper_copy.reset()
        desc_orig = fd_describe(fd_orig, 'orig')
        desc_copy = fd_describe(fd_copy, 'copy')
        test1['orig'] = desc_orig
        test1['copy'] = desc_copy
        
        # Check equality
        match = (
            desc_orig['orig_levels_completed'] == desc_copy['copy_levels_completed']
            and desc_orig['orig_state_val'] == desc_copy['copy_state_val']
            and desc_orig['orig_frame_hash'] == desc_copy['copy_frame_hash']
        )
        test1['states_match'] = match
        test1['status'] = 'PASS' if match else 'FAIL_MISMATCH'
    except Exception as e:
        test1['status'] = 'ERROR'
        test1['error'] = str(e)
    results['tests'].append(test1)
    
    # ── Test 2: Step original forward, verify clone unchanged ──
    test2 = {'name': 'step_original_preserves_clone', 'status': 'running'}
    try:
        # Recreate fresh states
        wrapper_a = arcade.make(GAME_ID)
        fd_a = wrapper_a.reset()
        wrapper_b = copy.deepcopy(wrapper_a)
        fd_b = wrapper_b.reset()  # Reset clone to match
        
        # Snapshot clone state
        desc_b_before = fd_describe(fd_b, 'clone_before')
        
        # Step original forward by 3 actions
        actions_taken = []
        for step_i in range(3):
            avail = getattr(fd_a, 'available_actions', None)
            action_list = [int(a) for a in avail] if avail is not None and len(avail) > 0 else [0, 1, 2, 3, 4, 5, 6]
            action_id = action_list[0]  # Take first available action
            try:
                action = GameAction.from_id(action_id)
                if action_id == 6:
                    fd_a = wrapper_a.step(action, data={'x': 32, 'y': 32})
                else:
                    fd_a = wrapper_a.step(action)
                actions_taken.append({'step': step_i, 'action_id': action_id})
            except Exception as e_step:
                actions_taken.append({'step': step_i, 'action_id': action_id, 'error': str(e_step)})
                break
        
        test2['actions_taken_on_original'] = actions_taken
        
        # Now check clone is unchanged
        fd_b_after = wrapper_b.reset()
        desc_b_after = fd_describe(fd_b_after, 'clone_after')
        
        test2['clone_before_reset'] = desc_b_before
        test2['clone_after_reset'] = desc_b_after
        
        # Verify clone state is preserved (same hash after reset)
        clone_preserved = desc_b_before['clone_before_frame_hash'] == desc_b_after['clone_after_frame_hash']
        test2['clone_preserved'] = clone_preserved
        test2['status'] = 'PASS' if clone_preserved else 'FAIL_CLONE_MODIFIED'
    except Exception as e:
        test2['status'] = 'ERROR'
        test2['error'] = str(e)
    results['tests'].append(test2)
    
    # ── Test 3: Step clone independently, verify no cross-contamination ──
    test3 = {'name': 'independent_clone_steps', 'status': 'running'}
    try:
        wrapper_x = arcade.make(GAME_ID)
        fd_x = wrapper_x.reset()
        wrapper_y = copy.deepcopy(wrapper_x)
        fd_y = wrapper_y.reset()
        
        # Step clone y forward by 5 actions
        y_actions = []
        for step_i in range(5):
            avail = getattr(fd_y, 'available_actions', None)
            action_list = [int(a) for a in avail] if avail is not None and len(avail) > 0 else [0, 1, 2, 3, 4, 5, 6]
            action_id = action_list[-1] if len(action_list) > 1 else action_list[0]  # Last available (diverse from test2)
            try:
                action = GameAction.from_id(action_id)
                if action_id == 6:
                    fd_y = wrapper_y.step(action, data={'x': 32, 'y': 32})
                else:
                    fd_y = wrapper_y.step(action)
                y_actions.append({'step': step_i, 'action_id': action_id})
            except Exception as e_step:
                y_actions.append({'step': step_i, 'action_id': action_id, 'error': str(e_step)})
                break
        
        test3['clone_y_actions'] = y_actions
        
        # Verify original x is unchanged
        fd_x_after = wrapper_x.reset()
        desc_x_after = fd_describe(fd_x_after, 'orig_x_after')
        test3['orig_x_after_reset'] = desc_x_after
        
        # Verify y has progressed (different state than reset)
        fd_y_final = wrapper_y.reset() if getattr(fd_y, 'state', None) is not None else fd_y
        fd_y_after = wrapper_y.reset()
        desc_y_after = fd_describe(fd_y_after, 'clone_y_after')
        test3['clone_y_after_reset'] = desc_y_after
        
        # Cross-contamination check: x unchanged
        x_unmodified = desc_x_after['orig_x_after_frame_hash'] == desc_b_before['clone_before_frame_hash']
        test3['x_unmodified'] = x_unmodified
        test3['y_has_different_state'] = desc_y_after['clone_y_after_frame_hash'] != desc_x_after['orig_x_after_frame_hash']
        test3['status'] = 'PASS' if (x_unmodified and test3['y_has_different_state']) else 'FAIL'
    except Exception as e:
        test3['status'] = 'ERROR'
        test3['error'] = str(e)
    results['tests'].append(test3)
    
    # ── Test 4: Observation space consistency across clone steps ──
    test4 = {'name': 'observation_consistency', 'status': 'running'}
    try:
        wrapper_z = arcade.make(GAME_ID)
        fd_z = wrapper_z.reset()
        wrapper_z_copy = copy.deepcopy(wrapper_z)
        fd_z_copy = wrapper_z_copy.reset()
        
        shapes_consistent = True
        frames_valid = True
        
        for step_i in range(3):
            avail = getattr(fd_z_copy, 'available_actions', None)
            action_list = [int(a) for a in avail] if avail is not None and len(avail) > 0 else [0, 1, 2, 3, 4, 5, 6]
            action_id = action_list[0] if action_list else 1
            try:
                action = GameAction.from_id(action_id)
                if action_id == 6:
                    fd_z_copy = wrapper_z_copy.step(action, data={'x': 32, 'y': 32})
                else:
                    fd_z_copy = wrapper_z_copy.step(action)
            except Exception:
                pass
            
            frame = frame_from_fd(fd_z_copy)
            if frame is not None:
                if frame.shape != (64, 64):
                    shapes_consistent = False
            else:
                frames_valid = False
        
        test4['shapes_consistent'] = shapes_consistent
        test4['frames_valid'] = frames_valid
        test4['status'] = 'PASS' if (shapes_consistent and frames_valid) else 'FAIL'
    except Exception as e:
        test4['status'] = 'ERROR'
        test4['error'] = str(e)
    results['tests'].append(test4)
    
    # ── Overall ──
    all_pass = all(t.get('status') == 'PASS' for t in results['tests'])
    results['overall_status'] = 'PASS' if all_pass else 'FAIL'
    results['end_time'] = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
    results['duration_seconds'] = time.time() - time.mktime(time.strptime(results['start_time'], '%Y-%m-%dT%H:%M:%S'))
    
    return results


if __name__ == '__main__':
    print(f"🚀 Running clone-step sanity test for {GAME_ID}...")
    results = run_sanity_test()
    
    # Write output
    with open(OUT_FILE, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {results['overall_status']}")
    print(f"Output: {OUT_FILE}")
    print(f"{'='*60}")
    for t in results.get('tests', []):
        status = t.get('status', '?')
        name = t.get('name', '?')
        print(f"  [{status}] {name}")
        if t.get('error'):
            print(f"         Error: {t['error']}")
    print(f"{'='*60}")
