#!/usr/bin/env python3
"""Testar todos os jogos com suporte local via arcengine."""
import sys, os
sys.path.insert(0, '/a0/usr/workdir')

from arcengine import GameAction, ActionInput

# Mapear jogos locais
env_dir = '/a0/usr/workdir/environment_files/'
games = {}
for d in os.listdir(env_dir):
    dpath = os.path.join(env_dir, d)
    if os.path.isdir(dpath):
        subdirs = os.listdir(dpath)
        for sd in subdirs:
            module_path = os.path.join(dpath, sd, f'{d}.py')
            if os.path.exists(module_path):
                games[d] = module_path

print(f"Jogos locais encontrados: {len(games)}")
for gid, path in games.items():
    print(f"  {gid}: {path}")

# Testar cada jogo
for gid, path in games.items():
    print(f"\n{'='*50}")
    print(f"TESTANDO: {gid}")
    print('='*50)
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(gid, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Pegar a classe do jogo
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and attr_name[0].isupper() and attr_name not in ('GameAction', 'ActionInput'):
                game_class = attr
                break

        g = game_class()
        total_levels = len(g._levels) if hasattr(g, '_levels') else '?'
        print(f"  Classe: {game_class.__name__}")
        print(f"  Levels: {total_levels}")

        # Testar win/lose flags
        g.set_level(0)
        for _ in range(20): g.step()
        print(f"  nyhaiggftp (win): {g.nyhaiggftp}")
        print(f"  pgualuszrs (lose): {g.pgualuszrs}")

        # Testar ACTION6 em posicoes variadas
        won = False
        for x in [0, 160, 320, 480, 640]:
            if won: break
            for y in [0, 120, 240, 360, 480]:
                g.set_level(0)
                for _ in range(10): g.step()
                g.perform_action(ActionInput(id=GameAction.ACTION6, data={'x': x, 'y': y}))
                for _ in range(50):
                    g.step()
                    if g.nyhaiggftp: break
                if g.nyhaiggftp:
                    print(f"  ACTION6({x},{y}) -> WIN!")
                    won = True
                    break
        if not won:
            print(f"  ACTION6: nenhum click venceu")

        # Testar outras acoes
        for action_id in [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3,
                          GameAction.ACTION4, GameAction.ACTION5, GameAction.ACTION7]:
            g.set_level(0)
            for _ in range(10): g.step()
            try:
                g.perform_action(ActionInput(id=action_id, data={}))
                for _ in range(50):
                    g.step()
                    if g.nyhaiggftp: break
                if g.nyhaiggftp:
                    print(f"  {action_id} -> WIN!")
                else:
                    print(f"  {action_id}: no win")
            except Exception as ex:
                print(f"  {action_id}: ERROR - {str(ex)[:80]}")

    except Exception as ex:
        print(f"  ERRO: {str(ex)[:200]}")
