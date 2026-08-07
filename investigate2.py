#!/usr/bin/env python3
"""Investigar como carregar jogos via importlib (bypass nome de modulo)."""
import sys, os, importlib.util
sys.path.insert(0, '/a0/usr/workdir')

# 1. Testar import direto do tn36 (hash comeca com letra - funciona)
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

# 2. Ver o que ARCBaseGame precisa
print("\n=== TESTE 2: ARCBaseGame init ===")
import inspect
from arcengine import ARCBaseGame
print(f"ARCBaseGame init: {inspect.signature(ARCBaseGame.__init__)}")

# 3. Carregar sp80 via importlib (hash comeca com 5)
print("\n=== TESTE 3: sp80 via importlib ===")
try:
    spec = importlib.util.spec_from_file_location(
        'sp80_mod',
        '/a0/usr/workdir/environment_files/sp80/589a99af/sp80.py'
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    classes = [x for x in dir(mod) if x[0].isupper() and x not in ('GameAction', 'ActionInput', 'ARCBaseGame', 'ABC')]
    print(f"Classes: {classes}")
    if classes:
        cls = getattr(mod, classes[0])
        print(f"Classe: {cls}")
        print(f"Bases: {cls.__bases__}")

        # Tentar criar instancia
        try:
            g = cls()
            print(f"  {classes[0]}() OK")
            if hasattr(g, '_levels'):
                print(f"  Levels: {len(g._levels)}")
            g.set_level(0)
            for _ in range(10): g.step()
            print(f"  win={g.nyhaiggftp}")
        except Exception as e2:
            print(f"  ERRO init: {e2}")
except Exception as e:
    print(f"ERRO: {e}")

# 4. Carregar TODOS os jogos e listar classes
print("\n=== TESTE 4: Todos os jogos ===")
env_dir = '/a0/usr/workdir/environment_files/'
for d in sorted(os.listdir(env_dir)):
    dpath = os.path.join(env_dir, d)
    if not os.path.isdir(dpath): continue
    for sd in os.listdir(dpath):
        module_path = os.path.join(dpath, sd, f'{d}.py')
        if not os.path.exists(module_path): continue
        try:
            spec = importlib.util.spec_from_file_location(f'_{d}_{sd}', module_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            classes = [x for x in dir(mod) if x[0].isupper() and x not in ('GameAction', 'ActionInput', 'ARCBaseGame', 'ABC')]
            print(f"  {d}: {classes}")
        except Exception as e:
            print(f"  {d}: ERRO - {str(e)[:60]}")
