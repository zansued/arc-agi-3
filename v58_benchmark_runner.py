#!/usr/bin/env python3
"""
v58_benchmark_runner.py — Executa V58 solver em todos os 25 jogos
"""
import sys, os, json, time
sys.path.insert(0, '/a0/usr/workdir/v58_playtest')
os.chdir('/a0/usr/workdir/v58_playtest')

from v58 import V58Solver
from arc_agi import Arcade  # Arcade() core

GAMES = ["ar25","bp35","cn04","ft09","g50t","ka59","lf52","lp85",
         "ls20","m0r0","r11l","re86","s5i5","sb26","sc25","sk48",
         "sp80","su15","tn36","tr87","tu93","vc33","wa30"]

results = {}
for gid in GAMES:
    print(f"\n{'='*60}")
    print(f"JOGO: {gid}")
    print(f"{'='*60}")
    try:
        sol = V58Solver(gid, Arcade())
        r = sol.run()
        results[gid] = r
        print(f"Result: success={r.get('success')}, lv={r.get('levels_completed')}, err={r.get('error')}")
    except Exception as e:
        import traceback
        results[gid] = {'game_id': gid, 'error': str(e), 'traceback': traceback.format_exc()}
        print(f"CRASH: {e}")

# Salvar resultados
out = '/a0/usr/workdir/arc_runs/v58_results.json'
with open(out, 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResultados salvos em {out}")

# Sumário
solved = sum(1 for r in results.values() if r.get('success'))
print(f"\n{'='*60}")
print(f"V58 BENCHMARK COMPLETO")
print(f"Jogos: {len(results)} | Resolvidos: {solved} | Falhas: {len(results)-solved}")
print(f"{'='*60}")
