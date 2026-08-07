#!/usr/bin/env python3
"""Teste de sequencias de acoes nos 5 jogos com suporte local."""
import sys, os, importlib.util, warnings, json
warnings.filterwarnings('ignore')
sys.path.insert(0, '/a0/usr/workdir')

from arcengine import GameAction, ActionInput

# Mapear os 5 jogos com suporte local
GAMES = {
    'bp35': ('bp35', '0a0ad940', 'Bp35'),
    'cd82': ('cd82', 'fb555c5d', 'Cd82'),
    'cn04': ('cn04', '2fe56bfb', 'Cn04'),
    'tn36': ('tn36', 'ef4dde99', 'Tn36'),
    'sp80': ('sp80', '589a99af', 'Sp80'),
}

ACTIONS = {
    'ACTION1': GameAction.ACTION1,
    'ACTION2': GameAction.ACTION2,
    'ACTION3': GameAction.ACTION3,
    'ACTION4': GameAction.ACTION4,
    'ACTION5': GameAction.ACTION5,
    'ACTION6': GameAction.ACTION6,
    'ACTION7': GameAction.ACTION7,
}

def load_game(gid, hash_val, class_name):
    path = f'/a0/usr/workdir/environment_files/{gid}/{hash_val}/{gid}.py'
    spec = importlib.util.spec_from_file_location(f'g_{gid}', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, class_name)()

def click(game, x, y):
    game.perform_action(ActionInput(id=GameAction.ACTION6, data={'x': x, 'y': y}))

def run_steps(game, n=50):
    for _ in range(n):
        game.step()
        if hasattr(game, 'nyhaiggftp') and game.nyhaiggftp:
            return True
        if hasattr(game, 'pgualuszrs') and game.pgualuszrs:
            return False
    return False

def do_action(game, action_id, data=None):
    try:
        if data:
            game.perform_action(ActionInput(id=action_id, data=data))
        else:
            game.perform_action(ActionInput(id=action_id, data={}))
        return run_steps(game, 100)
    except Exception as e:
        return False

for gid, (_, _, cls_name) in GAMES.items():
    print(f"\n{'='*60}")
    print(f"  {gid} ({cls_name})")
    print('='*60)

    try:
        g = load_game(gid, GAMES[gid][1], cls_name)
        n_levels = len(g._levels) if hasattr(g, '_levels') else '?'
        print(f"  Levels: {n_levels}")

        for li in range(n_levels if isinstance(n_levels, int) else 3):
            print(f"\n  --- Level {li} ---")
            won = False

            # Test 1: All non-ACTION6 actions
            for name, aid in ACTIONS.items():
                if aid == GameAction.ACTION6:
                    continue
                g.set_level(li)
                for _ in range(10): g.step()
                if do_action(g, aid):
                    print(f"  [{name}] -> WIN!")
                    won = True
                    break
                else:
                    print(f"  [{name}] -> no win", end=" ")

                # Test 2: Same action twice
                g.set_level(li)
                for _ in range(10): g.step()
                do_action(g, aid)
                if do_action(g, aid):
                    print(f"  [{name}x2] -> WIN!")
                    won = True
                    break

            if won:
                continue

            # Test 3: ACTION6 clicks at grid points
            for x in range(0, 641, 80):
                if won: break
                for y in range(0, 481, 80):
                    g.set_level(li)
                    for _ in range(10): g.step()
                    try:
                        click(g, x, y)
                        if run_steps(g, 100):
                            print(f"  [CLICK({x},{y})] -> WIN!")
                            won = True
                            break
                    except Exception:
                        pass

            if won:
                continue

            # Test 4: Two-action sequences
            for a1_name, a1_id in ACTIONS.items():
                if won: break
                if a1_id == GameAction.ACTION6:
                    continue
                for a2_name, a2_id in ACTIONS.items():
                    if won: break
                    if a2_id == GameAction.ACTION6:
                        continue
                    g.set_level(li)
                    for _ in range(10): g.step()
                    do_action(g, a1_id)
                    if do_action(g, a2_id):
                        print(f"  [{a1_name}+{a2_name}] -> WIN!")
                        won = True

            if not won:
                print(f"  Level {li}: NENHUMA SEQUENCIA FUNCIONOU")

    except Exception as e:
        print(f"  ERRO: {str(e)[:200]}")

print("\n\n=== TESTE CONCLUIDO ===")
