#!/usr/bin/env python3
"""Investigar como carregar jogos via arcengine."""
import sys
sys.path.insert(0, '/a0/usr/workdir')

# 1. Testar import direto do tn36 (que funcionava antes)
print("=== TESTE 1: Import direto Tn36 ===")
try:
    from environment_files.tn36.ef4dde99.tn36 import Tn36
    g = Tn36()
    print(f"Tn36() OK: {len(g._levels)} levels")
    g.set_level(0)
    for _ in range(10): g.step()
    print(f"  win={g.nyhaiggftp}")
except Exception as e:
    print(f"ERRO: {e}")

# 2. Ver como arcengine registra os jogos
print("\n=== TESTE 2: arcengine internals ===")
import arcengine
print(f"arcengine: {arcengine.__file__}")
print(f"dir: {[x for x in dir(arcengine) if not x.startswith('_')][:20]}")

# 3. Ver estrutura do Tn36
print("\n=== TESTE 3: Tn36 class structure ===")
import inspect
from environment_files.tn36.ef4dde99.tn36 import Tn36
print(f"Bases: {Tn36.__bases__}")
print(f"Init sig: {inspect.signature(Tn36.__init__)}")

# 4. Ver o que ARCBaseGame precisa
print("\n=== TESTE 4: ARCBaseGame ===")
from arcengine import ARCBaseGame
print(f"Init sig: {inspect.signature(ARCBaseGame.__init__)}")

# 5. Tentar com sp80
print("\n=== TESTE 5: sp80 ===")
try:
    from environment_files.sp80.589a99af.sp80 import Sp80
    g = Sp80()
    print(f"Sp80() OK: {len(g._levels)} levels")
    g.set_level(0)
    for _ in range(10): g.step()
    print(f"  win={g.nyhaiggftp}")
except Exception as e:
    print(f"ERRO: {e}")

# 6. Ver todas as classes de jogos
print("\n=== TESTE 6: Nomes de classes em cada jogo ===")
import os, importlib.util
env_dir = '/a0/usr/workdir/environment_files/'
for d in sorted(os.listdir(env_dir)):
    dpath = os.path.join(env_dir, d)
    if not os.path.isdir(dpath): continue
    subdirs = os.listdir(dpath)
    for sd in subdirs:
        module_path = os.path.join(dpath, sd, f'{d}.py')
        if not os.path.exists(module_path): continue
        try:
            spec = importlib.util.spec_from_file_location(f'_{d}', module_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            classes = [x for x in dir(mod) if x[0].isupper() and x not in ('GameAction', 'ActionInput', 'ARCBaseGame', 'ABC')]
            print(f"  {d}: {classes}")
        except Exception as e:
            print(f"  {d}: ERRO - {str(e)[:60]}")
