#!/usr/bin/env python3
"""Testar todos os jogos via Arcade.make() - metodo do v31."""
import warnings, logging, uuid, json
warnings.filterwarnings('ignore')
from arc_agi import Arcade
from arc_agi.local_wrapper import LocalEnvironmentWrapper
from arcengine import GameAction, GameState

a = Arcade()
envs = a.get_environments()
logger = logging.getLogger('mass_test')

print(f"Total: {len(envs)} environments")

# Testar cada jogo
results = {}
for e in envs:
    gid = e.game_id
    ba = [int(x) for x in e.baseline_actions]
    print(f"\n{'='*50}")
    print(f"  {gid}")
    print(f"  Baseline: {ba[:5]}... ({len(ba)} actions)")
    print('='*50)

    try:
        wrapper = LocalEnvironmentWrapper(e, logger, str(uuid.uuid4()))
        action_space = wrapper.action_space
        print(f"  Action space: {[str(a) for a in action_space]}")

        game_results = {"levels_completed": 0, "actions_tried": 0, "states": []}

        # Testar cada acao disponivel no action space
        for action in action_space:
            wrapper.reset()
            try:
                obs = wrapper.step(action)
                lc = obs.levels_completed
                state = str(obs.state)
                print(f"  {action}: levels={lc} state={state}")
                game_results["actions_tried"] += 1
                if lc > 0:
                    game_results["levels_completed"] = max(game_results["levels_completed"], lc)
                    game_results["states"].append({str(action): {"levels": lc, "state": state}})
            except Exception as ex:
                print(f"  {action}: ERROR - {str(ex)[:80]}")

        results[gid] = game_results

        # Se action_space vazio, tentar com ints
        if not action_space:
            print(f"  Action space vazio - tentando actions 1-7")
            for act_val in range(1, 8):
                wrapper.reset()
                try:
                    obs = wrapper.step(act_val)
                    lc = obs.levels_completed
                    print(f"  step({act_val}): levels={lc} state={obs.state}")
                except Exception as ex:
                    print(f"  step({act_val}): ERROR - {str(ex)[:60]}")

    except Exception as ex:
        print(f"  WRAPPER ERROR: {str(ex)[:200]}")
        results[gid] = {"error": str(ex)[:200]}

print("\n\n=== RESUMO ===")
solved = [(gid, r) for gid, r in results.items() if r.get("levels_completed", 0) > 0]
print(f"Jogos com progresso: {len(solved)}/{len(results)}")
for gid, r in sorted(results.items()):
    if "error" in r:
        print(f"  {gid}: ERRO - {r['error']}")
    else:
        print(f"  {gid}: {r.get('levels_completed', 0)} levels, {r.get('actions_tried', 0)} acoes testadas")
