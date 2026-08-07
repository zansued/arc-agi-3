#!/usr/bin/env python3
"""
# SPECTRAL SMART RANDOM SOLVER — ARC-AGI-3
#
# Inspired by StochasticGoose (1st place, 12.58%, 30-day ARC Challenge):
#   "A CNN-based Smart Random that learns which actions cause frame changes"
#
# Our twist: Replace the CNN with OSCAR-inspired Spectral Analysis.
#   - Capture N random frames via game.step()
#   - Convert frames to numerical embeddings
#   - spectral_importance_ranking() finds which action dimensions matter
#   - Prioritize actions that maximize frame change
#
# Keys to beating the benchmark:
#   1. 0 crashes like V55/V56 (done)
#   2. Action efficiency (rank_importance replaces CNN)
#   3. State graph pruning via KG (when available)
#   4. Archive replay (from V48)
"""

import numpy as np
import json, os, sys, time, argparse
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Set TOKENIZERS_PARALLELISM to false to avoid warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Import arc_agi
sys.path.insert(0, '/opt/venv/lib/python3.13/site-packages')

try:
    import arc_agi
    from arc_agi.arcade import Arcade, Action, ActionSet
    HAS_ARCADE = True
except ImportError:
    HAS_ARCADE = False
    print("WARNING: arc_agi not importable")

# Import Spectral Atomizer
try:
    from spectral_atomizer.core import spectral_importance_ranking, compress_via_projection
except ImportError:
    print("WARNING: spectral_atomizer not importable")
    spectral_importance_ranking = None


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

N_RANDOM_FRAMES = 500       # frames to sample for spectral analysis
MAX_STEPS = 800              # max steps per game (same as V55/V56)
MIN_ACTIONS = 4              # min actions per game

GAME_IDS = [
    'ar25', 'bp35', 'cd82', 'cn04', 'ft09', 'g50t', 'ka59', 'lf52',
    'lp85', 'ls20', 'm0r0', 'r11l', 're86', 's5i5', 'sb26', 'sc25',
    'sk48', 'sp80', 'su15', 'tn36', 'tr87', 'tu93', 'vc33', 'wa30'
]

# ---------------------------------------------------------------------------
# UTILITY: convert arcade environment frame to vector
# ---------------------------------------------------------------------------

def frame_to_vector(frames_dict: dict) -> np.ndarray:
    """Convert arcade frame output to a 1D numerical vector."""
    vec_parts = []
    for key in sorted(frames_dict.keys()):
        val = frames_dict[key]
        # Handle arrays / lists
        if isinstance(val, (np.ndarray, list)):
            if isinstance(val, np.ndarray):
                vec_parts.append(val.flatten().astype(np.float32))
            else:
                vec_parts.append(np.array(val, dtype=np.float32).flatten())
        # Handle scalars
        elif isinstance(val, (int, float, bool)):
            vec_parts.append(np.array([float(val)], dtype=np.float32))
        # Handle strings — encode as hash
        elif isinstance(val, str):
            h = hash(val) % 1000
            vec_parts.append(np.array([float(h)], dtype=np.float32))
    if not vec_parts:
        return np.zeros(64, dtype=np.float32)
    result = np.concatenate(vec_parts)
    if len(result) == 0:
        return np.zeros(64, dtype=np.float32)
    return result


# ---------------------------------------------------------------------------
# SPECTRAL ACTION RANKER
# ---------------------------------------------------------------------------

def rank_actions_by_spectral_importance(
    actions: List[str],
    game_env
) -> List[Dict[str, Any]]:
    """
    Sample random frames, convert to embeddings, run spectral analysis,
    return actions ranked by spectral importance.
    """
    print(f"  Ranking {len(actions)} actions via spectral analysis...")
    
    # Collect embeddings per action
    action_embeddings = {a: [] for a in actions}
    
    for _ in range(min(N_RANDOM_FRAMES // len(actions), 100)):
        # Take random action
        action = np.random.choice(actions)
        try:
            result = game_env.step(action=Action(action))
            if isinstance(result, dict):
                vec = frame_to_vector(result)
                action_embeddings[action].append(vec)
        except Exception:
            pass
        # Reset occasionally to avoid terminal states
        if np.random.random() < 0.05:
            try:
                game_env.reset()
            except Exception:
                pass
    
    # Build embedding matrix (n_tokens, d_model)
    all_vecs = []
    action_labels = []
    for act, vecs in action_embeddings.items():
        for v in vecs[-20:]:  # max 20 per action
            all_vecs.append(v)
            action_labels.append(act)
    
    if len(all_vecs) < 5:
        # Fallback: uniform priority
        return [{'action': a, 'importance': 1.0/len(actions), 'method': 'fallback'} for a in actions]
    
    embeddings = np.stack(all_vecs)
    
    try:
        result = spectral_importance_ranking(embeddings, method='variance_weighted', variance_ratio=0.95)
        # Compute importance per action by grouping
        unique_actions = list(set(action_labels))
        action_scores = []
        for act in unique_actions:
            indices = [i for i, l in enumerate(action_labels) if l == act]
            if indices and len(indices) > 0:
                # Use importance_per_token from spectral analysis
                importance = float(np.mean(result['importance_per_token'][indices])) if 'importance_per_token' in result else 1.0
            else:
                importance = 1.0
            action_scores.append({'action': act, 'importance': importance})
        
        # Sort by importance descending
        action_scores.sort(key=lambda x: x['importance'], reverse=True)
        return action_scores
    except Exception as e:
        print(f"  Spectral ranking failed: {e}")
        return [{'action': a, 'importance': 1.0/len(actions)} for a in actions]


# ---------------------------------------------------------------------------
# SPECTRAL SMART RANDOM SOLVER (per game)
# ---------------------------------------------------------------------------

def solve_game_with_smart_random(
    game_id: str,
    arcade
) -> Dict[str, Any]:
    """Run Spectral Smart Random on one game."""
    print(f"\n{'='*60}")
    print(f"🎮 GAME: {game_id}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    # Open game
    try:
        game_env = arcade.open_game(game_id)
    except Exception as e:
        return {'game_id': game_id, 'error': str(e), 'states': 0, 'levels': 0, 'crashes': 0}
    
    # Get available actions
    try:
        action_set = game_env.action_set()
        actions = [a.name for a in action_set.actions]
    except Exception:
        actions = [f'ACTION{i}' for i in range(1, 7)]  # fallback
    
    print(f"  Actions available: {actions}")
    
    # Phase 1: Spectral Analysis — rank actions
    ranked_actions = rank_actions_by_spectral_importance(actions, game_env)
    print(f"  Ranked actions (top-3): {[a['action'] for a in ranked_actions[:3]]}")
    
    # Phase 2: Smart Random with spectral prior
    n_states = 0
    n_levels = 0
    n_crashes = 0
    n_steps = 0
    
    # Reset game to start fresh
    try:
        game_env.reset()
    except Exception:
        pass
    
    # Build prior weights from spectral ranking
    prior_weights = {}
    for r in ranked_actions:
        prior_weights[r['action']] = r['importance']
    
    for step in range(MAX_STEPS):
        if n_levels > 0:
            break  # level complete
        
        # Choose action: sample from spectral prior
        action_probs = np.array([prior_weights.get(a, 1.0) for a in actions])
        action_probs = action_probs / action_probs.sum()
        chosen_action = np.random.choice(actions, p=action_probs)
        
        try:
            result = game_env.step(action=Action(chosen_action))
            n_steps += 1
            n_states += 1
            
            # Check for level complete
            if isinstance(result, dict):
                score = result.get('score', 0)
                if score > 0:
                    n_levels += 1
                    print(f"  ⭐ LEVEL {n_levels} found! (step {step+1}, action: {chosen_action})")
        except Exception as e:
            n_crashes += 1
            if n_crashes > 3:
                break
            try:
                game_env.reset()
            except Exception:
                pass
    
    elapsed = time.time() - start_time
    
    result = {
        'game_id': game_id,
        'states': n_states,
        'levels': n_levels,
        'crashes': n_crashes,
        'steps': n_steps,
        'time': round(elapsed, 1),
        'actions_tried': len(set(actions)),
        'strategy': 'spectral_smart_random'
    }
    
    print(f"  Result: {n_states} states, {n_levels} levels, {n_crashes} crashes, {round(elapsed, 1)}s")
    return result


# ---------------------------------------------------------------------------
# BENCHMARK RUNNER
# ---------------------------------------------------------------------------

def run_benchmark(
    game_ids: List[str],
    num_workers: int = 1,
    output_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Run Spectral Smart Random on all games."""
    print(f"\n🔥 SPECTRAL SMART RANDOM BENCHMARK")
    print(f"   Games: {len(game_ids)} | Workers: {num_workers}")
    print(f"   Spectral rank: active | Frames: {N_RANDOM_FRAMES}/game")
    print(f"   Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Initialize arcade
    try:
        arcade = Arcade()
        print(f"✅ Arcade initialized")
    except Exception as e:
        print(f"❌ Arcade failed: {e}")
        return []
    
    all_results = []
    for i, game_id in enumerate(game_ids):
        print(f"\n--- Game {i+1}/{len(game_ids)}")
        result = solve_game_with_smart_random(game_id, arcade)
        all_results.append(result)
        
        # Save intermediate
        if output_path:
            with open(output_path.replace('.json', '_partial.json'), 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
    
    # Summary
    total_states = sum(r.get('states', 0) for r in all_results)
    total_levels = sum(r.get('levels', 0) for r in all_results)
    total_crashes = sum(r.get('crashes', 0) for r in all_results)
    total_steps = sum(r.get('steps', 0) for r in all_results)
    
    print(f"\n{'='*60}")
    print(f"📊 BENCHMARK COMPLETE")
    print(f"   Total states: {total_states}")
    print(f"   Total levels: {total_levels}")
    print(f"   Total crashes: {total_crashes}")
    print(f"   Total steps: {total_steps}")
    print(f"{'='*60}")
    
    return all_results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Spectral Smart Random Solver')
    parser.add_argument('--games', nargs='+', default=None, help='Game IDs to run')
    parser.add_argument('--workers', type=int, default=1, help='Number of workers')
    parser.add_argument('--output', type=str, default='spectral_smart_random_results.json', help='Output path')
    args = parser.parse_args()
    
    game_list = args.games or GAME_IDS
    results = run_benchmark(game_list, args.workers, args.output)
    
    if args.output and results:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n✅ Results saved to {args.output}")
