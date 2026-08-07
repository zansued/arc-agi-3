"""
v59 — Teste direto heurísticas v58 + arc_agi REAL v2.
Usa arcade.make() + step(GameAction) consistentemente.
Estratégias multi-step para cada heurística.
"""
import sys, json, os, time, numpy as np
sys.path.insert(0, '/a0/usr/workdir/arcengine_pkg')
sys.path.insert(0, '/a0/usr/workdir/arc_agi_pkg')
from arc_agi import Arcade
from arcengine import GameAction, GameState

OUT_DIR = '/a0/usr/workdir/arc_runs'

GA_MAP = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
          4: GameAction.ACTION4, 5: GameAction.ACTION5, 6: GameAction.ACTION6, 7: GameAction.ACTION7}

def safe_step(game, action_id, **kw):
    ga = GA_MAP.get(action_id, GameAction.ACTION1)
    try:
        if action_id == 6:
            x = kw.get('x', 32)
            y = kw.get('y', 32)
            return game.step(ga, data={'x': x, 'y': y})
        return game.step(ga)
    except KeyError as e:
        if 'x' in str(e):
            return game.step(ga, data={'x': 32, 'y': 32})
        return None
    except Exception:
        return None

def probe_actions(game):
    catalog = {'actions': {}}
    fd = game._last_response
    initial_frame = None
    if fd and hasattr(fd, 'frame') and fd.frame is not None:
        g = np.asarray(fd.frame)
        initial_frame = g.copy()
        catalog['initial_shape'] = list(g.shape)
        catalog['initial_colors'] = int(len(np.unique(g)))
    for aid in range(1, 8):
        game.reset()
        fd = safe_step(game, aid)
        eff = {'has_effect': False, 'levels_completed': 0}
        if fd:
            lc = getattr(fd, 'levels_completed', 0)
            av = getattr(fd, 'available_actions', [])
            eff['levels_completed'] = int(lc)
            eff['available_actions'] = [int(a) for a in av]
            if hasattr(fd, 'frame') and fd.frame is not None:
                g = np.asarray(fd.frame)
                eff['colors'] = int(len(np.unique(g)))
                eff['sum'] = int(np.sum(g))
                if initial_frame is not None:
                    diff = np.sum(g != initial_frame)
                    eff['has_effect'] = bool(diff > 0)
                    eff['pixels_changed'] = int(diff)
        catalog['actions'][aid] = eff
    return catalog

def diagnose(catalog):
    acts = catalog.get('actions', {})
    has5 = acts.get(5, {}).get('has_effect', False)
    has6 = acts.get(6, {}).get('has_effect', False)
    has1 = acts.get(1, {}).get('has_effect', False)
    if has5 and has6: return 'paint'
    if has6 and not has5: return 'tangram'
    if has1: return 'navigation'
    return 'unknown'

def run_game(game_id):
    print(f"\n{'='*55}")
    print(f"  🎮 {game_id}")
    print(f"{'='*55}")
    try:
        game = Arcade().make(game_id)
    except Exception as e:
        return {'game': game_id, 'error': str(e), 'levels_completed': 0}
    catalog = probe_actions(game)
    heur = diagnose(catalog)
    print(f"  Heurística: {heur}")
    for aid, info in catalog['actions'].items():
        eff = '✅' if info.get('has_effect') else '❌'
        lc = info.get('levels_completed', 0)
        pc = info.get('pixels_changed', 0)
        print(f"    ACT{aid}: {eff} levels={lc} pixels={pc} colors={info.get('colors','?')}"  )
    max_levels = 0
    strategy = 'none'
    if heur == 'paint':
        strategy = 'paint_multi'
        print(f"  ▶ Estratégia: paint multi-step (sequential ACT5 with color picks)"  )
        for pos in [[(16,16)], [(32,32)], [(48,48)], [(8,8)], [(40,40)]]:
            for trial in range(5):
                game.reset()
                # Paint sequence: pick color then paint
                for px, py in pos:
                    safe_step(game, 6, x=px, y=py)
                for _ in range(100):
                    fd = safe_step(game, 5)
                    lc = getattr(fd, 'levels_completed', 0) if fd else 0
                    if lc > max_levels:
                        max_levels = lc
                        print(f"      PROGRESS: levels={lc} at step {_} ✅")
    if heur == 'navigation':
        strategy = 'nav_sequence'
        print(f"  ▶ Estratégia: navigation com movimentos sequenciais"  )
        for trial in range(10):
            for seq_len in range(1, 20):
                game.reset()
                # Try long sequences of same direction
                for a in [4, 3]:  # LEFT then RIGHT
                    for _ in range(seq_len):
                        fd = safe_step(game, a)
                        lc = getattr(fd, 'levels_completed', 0) if fd else 0
                        if lc > max_levels:
                            max_levels = lc
                            print(f"      PROGRESS: ACT{a} x{seq_len}: levels={lc} ✅")
    if max_levels == 0:
        strategy = 'bfs_go_explore'
        print(f"  ▶ BFS Go-Explore: archive + random walks"  )
        archive = set()
        for _ in range(200):
            game.reset()
            fd = game._last_response
            if fd and hasattr(fd, 'frame') and fd.frame is not None:
                key = hash(np.asarray(fd.frame).tobytes())
                archive.add(key)
            for a in range(1, 8):
                fd = safe_step(game, a)
                lc = getattr(fd, 'levels_completed', 0) if fd else 0
                if lc > max_levels:
                    max_levels = lc
                    print(f"      PROGRESS BFS: ACT{a}: levels={lc} ✅")
    status = '✅' if max_levels > 0 else '❌'
    print(f"  {status} Resultado: {max_levels} levels ({strategy})")
    return {'game': game_id, 'heuristic': heur, 'strategy': strategy,
            'levels_completed': max_levels, 'catalog': {k:{'has_effect':v.get('has_effect'),'pixels_changed':v.get('pixels_changed',0)} for k,v in catalog.get('actions',{}).items()}}

def main():
    games = ['sp80', 'cn04', 'wa30', 'bp35', 'tn36', 'sk48']
    print(f"{'='*55}")"  print(f"  V59v2 — TESTE DIRETO ARC_AGI REAL")"  print(f"  Estratégias: paint multi-step, nav sequence, BFS Go-Explore")"  print(f"  {len(games)} jogos")"  print(f"{'='*55}")"  all_results = []
    for g in games:
        try:
            r = run_game(g)
        except Exception as e:
            r = {'game': g, 'error': str(e)[:100], 'levels_completed': 0}
        all_results.append(r)
    print(f"\n\n{'='*55}")"  print(f"  RESUMO FINAL")"  print(f"{'='*55}")"  total = sum(r.get('levels_completed', 0) for r in all_results)
    for r in all_results:
        s = '✅' if r.get('levels_completed', 0) > 0 else '❌'
        print(f"  {s} {r['game']}: {r['levels_completed']} ({r.get('heuristic','?')})")"  print(f"  \n  Total: {total} levels em {len(all_results)} jogos")"  summary = {
        'run_key': f"v59v2-{time.strftime('%Y-%m-%dT%H-%M-%S')}",
        'version': 'v59v2_direct_arcade',
        'games_benchmarked': len(all_results),
        'levels_completed': total,
        'results': all_results,
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(f'{OUT_DIR}/v59v2_results.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSalvo: {OUT_DIR}/v59v2_results.json")

if __name__ == '__main__':
    main()
