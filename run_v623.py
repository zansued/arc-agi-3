import importlib.util, sys, json, time
from pathlib import Path
sys.path.insert(0, '.')
from arcengine import ActionInput, GameAction, GameState

GAMES_DIR = Path('/a0/usr/workdir/environment_files')
RESULTS_DIR = Path('/a0/usr/workdir/arc_runs')
RESULTS_DIR.mkdir(exist_ok=True)

def load(gid):
    d = GAMES_DIR / gid
    sd = list(d.iterdir())[0]
    pyf = sd / f'{gid}.py'
    spec = importlib.util.spec_from_file_location(gid, pyf)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for n, o in m.__dict__.items():
        if isinstance(o, type) and hasattr(o, '__bases__'):
            for b in o.__bases__:
                if 'ARCBaseGame' in str(b):
                    return o
    return None

def analyze(gid):
    res = {'id': gid, 'levels': 0, 'solved': 0, 'level_results': [], 'tags': [], 'err': None}
    try:
        GC = load(gid)
        if not GC:
            res['err'] = 'no class'
            return res
        g = GC()
        res['levels'] = len(g._levels)
        cam = g.camera
        res['cam'] = f'Cam({cam.x},{cam.y},{cam.width},{cam.height})'
        l0 = g._levels[0]
        tgs = l0.get_all_tags()
        res['tags'] = sorted(list(tgs)) if tgs else []
        if hasattr(l0, '_data'):
            res['data'] = {str(k): str(v)[:80] for k,v in l0._data.items()}
        # Get sprites
        sprites = list(l0._sprites)[:15]
        s_info = []
        for s in sprites:
            s_info.append({'n': s.name, 'pos': (s.x,s.y), 'tags': list(s.tags or []), 'wh': (s.w,s.h)})
        res['sprites'] = s_info
        # Click attempts
        attempts = []
        for s in sprites[:10]:
            sx, sy = s.x, s.y
            for m in [2, 4]:
                dx, dy = sx*m, sy*m
                try:
                    fg = GC()
                    act = ActionInput(id=GameAction.ACTION6, data={'x': dx, 'y': dy})
                    fr = fg.perform_action(act)
                    st = str(fr.state) if fr else 'NONE'
                    adv = fg.level_index > 0
                    grid = fg.camera.display_to_grid(dx, dy)
                    attempts.append({'sp': s.name, 'gpos': (sx,sy), 'c': (dx,dy), 'grid': str(grid), 'st': st, 'adv': adv})
                    if adv:
                        res['solved'] += 1
                except Exception as e:
                    attempts.append({'sp': s.name, 'gpos': (sx,sy), 'c': (dx,dy), 'err': str(e)[:50]})
        res['attempts'] = attempts
        del g
    except Exception as e:
        res['err'] = f'{type(e).__name__}: {e}'
    return res

games = ['ft09', 'lp85', 'r11l', 's5i5', 'tn36', 'vc33']
results = {}
for gid in games:
    print(f'  {gid}...', end=' ', flush=True)
    t0 = time.time()
    results[gid] = analyze(gid)
    print(f'{results[gid]["solved"]}/{results[gid]["levels"]} solved, {time.time()-t0:.1f}s')

results['_summary'] = {
    'timestamp': time.strftime('%Y%m%d_%H%M%S'),
    'solver': 'v62.3',
    'games': {gid: {'levels': r['levels'], 'solved': r['solved'], 'err': str(r.get('err',''))[:60], 'tags': r.get('tags',[])[:6]}
              for gid, r in results.items() if gid != '_summary'}
}

ts = time.strftime('%Y%m%d_%H%M%S')
out = RESULTS_DIR / f'v62_3_results_{ts}.json'
with open(out, 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f'\nSaved to {out}')
