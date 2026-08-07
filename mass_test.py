#!/usr/bin/env python3
"""Teste em massa: 25 jogos, acoes baseline + ACTION6 + random."""
import sys, os, importlib.util, warnings, json
warnings.filterwarnings('ignore')
sys.path.insert(0, '/a0/usr/workdir')

from arcengine import GameAction, ActionInput

# Mapear jogos
env_dir = '/a0/usr/workdir/environment_files/'
game_classes = {}
for d in sorted(os.listdir(env_dir)):
    dpath = os.path.join(env_dir, d)
    if not os.path.isdir(dpath): continue
    for sd in os.listdir(dpath):
        mp = os.path.join(dpath, sd, f'{d}.py')
        if not os.path.exists(mp): continue
        try:
            spec = importlib.util.spec_from_file_location(f'g_{d}_{sd}', mp)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for attr in dir(mod):
                if attr[0].isupper() and attr not in ('GameAction','ActionInput','ARCBaseGame','ABC',
                    'Any','Callable','ClassVar','Dict','Enum','Final','Iterator','List','Literal',
                    'NamedTuple','Optional','Set','T','Tuple','TypedDict','TypeAlias','TypeVar','Union',
                    'BACKGROUND_COLOR','PADDING_COLOR','Camera','Level','Sprite','RenderableUserDisplay',
                    'BlockingMode','InteractionMode','UndoState','CSPOIQWER','STPQNMET',
                    'GRAPH_BUILDER','BLACK','BLUE','DARK_GRAY','GRAY','GREEN','LIGHT_BLUE','MAGENTA',
                    'MAROON','OFF_BLACK','OFF_WHITE','ORANGE','PINK','PURPLE','RED','WHITE','YELLOW',
                    'STORES_UNDO'):
                    game_classes[d] = getattr(mod, attr)
                    break
        except Exception:
            pass

print(f"Jogos carregados: {len(game_classes)}")
for gid, cls in sorted(game_classes.items()):
    print(f"  {gid}: {cls.__name__}")

# Testar cada jogo
results = {}
for gid, cls in sorted(game_classes.items()):
    print(f"\n{'='*50}")
    print(f"  {gid} ({cls.__name__})")
    print('='*50)

    try:
        g = cls()
        n_levels = len(g._levels) if hasattr(g, '_levels') else '?'
        print(f"  Levels: {n_levels}")
        results[gid] = {"levels": n_levels, "solved": 0, "total": n_levels}

        # Testar todos os levels
        for li in range(n_levels if isinstance(n_levels, int) else 3):
            g.set_level(li)
            for _ in range(15): g.step()
            print(f"  L{li}: init_win={g.nyhaiggftp}", end="")

            # Strategy 1: ACTION6 em grid 5x5
            won = False
            for x in range(0, 641, 160):
                if won: break
                for y in range(0, 481, 160):
                    g.set_level(li)
                    for _ in range(10): g.step()
                    try:
                        g.perform_action(ActionInput(id=GameAction.ACTION6, data={'x': x, 'y': y}))
                        for _ in range(100):
                            g.step()
                            if g.nyhaiggftp: break
                        if g.nyhaiggftp:
                            print(f" CLICK({x},{y})", end="")
                            won = True
                            break
                    except Exception:
                        pass

            # Strategy 2: todas as outras acoes
            for aid in [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3,
                        GameAction.ACTION4, GameAction.ACTION5, GameAction.ACTION7]:
                if won: break
                g.set_level(li)
                for _ in range(10): g.step()
                try:
                    g.perform_action(ActionInput(id=aid, data={}))
                    for _ in range(100):
                        g.step()
                        if g.nyhaiggftp: break
                    if g.nyhaiggftp:
                        print(f" {aid}", end="")
                        won = True
                except Exception:
                    pass

            if won:
                results[gid]["solved"] += 1
                print(" WIN!")
            else:
                print(" FAIL")

    except Exception as e:
        print(f"  ERRO: {str(e)[:100]}")
        results[gid] = {"error": str(e)[:100]}

print("\n\n=== RESUMO ===")
solved_any = [(g, r) for g, r in results.items() if r.get("solved", 0) > 0]
print(f"Jogos com pelo menos 1 level solucionavel: {len(solved_any)}/{len(results)}")
for gid, r in sorted(results.items()):
    if "error" in r:
        print(f"  {gid}: ERRO - {r['error']}")
    else:
        print(f"  {gid}: {r['solved']}/{r['total']} levels")
