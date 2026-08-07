import json
import sys
import os
import types
from typing import Any, Optional, Dict, List, Tuple

import numpy as np
np.set_printoptions(linewidth=200, threshold=100)

# Caminhos
sys.path.insert(0, "/a0/usr/workdir")

from arcengine import ActionInput, GameAction, GameState

# --- Monkey-patch no step() ---
call_count = 0
debug_log = []

def sprite_info(s):
    if s is None:
        return "None"
    return f"{s.name} pos=({s.x},{s.y}) w={s.width} h={s.height} layer={s.layer}"

def log_state(game, label: str):
    global call_count
    d = {}
    for attr in ["dkvpswzsjg","vsoxmtrhqt","kfdcqkodyy","lybfalkrdl",
                 "avangppqui","yqejjfwwh","zlhbnhpcq","lyremoheq",
                 "trhynadhiz","fahhoimkk"]:
        val = getattr(game, attr, "<MISSING>")
        if isinstance(val, bool):
            d[attr] = val
        elif isinstance(val, (int, float)):
            d[attr] = val
        elif val is None:
            d[attr] = "None"
        elif hasattr(val, "name"):
            d[attr] = f"Sprite({val.name}) at ({val.x},{val.y})"
        else:
            d[attr] = str(val)[:60]
    
    # Estado base
    d["_state"] = str(game._state)
    d["_score"] = game._score
    d["_action_count"] = game._action_count
    d["_next_level"] = game._next_level
    d["_current_level_index"] = game._current_level_index
    
    # Número de sprites relevantes
    d["n_palettes"] = len(game.fbrwmvzsym())
    d["n_buckets"] = len(game.mxdlffpzkc())
    d["n_droplets"] = len(game.qbsoyazkhk())
    d["n_walls"] = len(game.vgpoqzieha())
    
    # Set sizes
    d["|cevwbinfgl|"] = len(game.cevwbinfgl)
    d["|onoqwewztl|"] = len(game.onoqwewztl)
    d["|hmxltcipkc|"] = len(game.hmxltcipkc)
    d["|xpcxocsmmq|"] = len(game.xpcxocsmmq)
    
    debug_log.append({"call": call_count, "label": label, "state": d})
    return d

# --- Carregar sp80 ---
os.chdir("/a0/usr/workdir/environment_files/sp80/589a99af")

import importlib.util
spec = importlib.util.spec_from_file_location("sp80_module", "sp80.py")
sp80_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp80_module)

# Instanciar jogo
game = sp80_module.Sp80()
game._debug = True

# Go to Level 2 (index 1)
game.set_level(1)
print(f"=== SP80 DEBUG HOOK ===")
print(f"Level 2 loaded")
print(f"Game ID: {game.game_id}")
print(f"Level index: {game.level_index}")
print(f"Level name: {game.current_level.name}")
print(f"Grid size: {game.current_level.grid_size}")
print(f"k (rotação): {game.fahhoimkk}")
print(f"Steps: {game.zlhbnhpcq}")
print(f"Win condition (yqejjfwwh): {game.yqejjfwwh}")
print(f"")

print("Sprites clicáveis (palettes + sys_click) no nível 2:")
for s in game.fbrwmvzsym():
    print(f"  [{s.name}] pos=({s.x},{s.y}) w={s.width} h={s.height} tags={s.tags}")
print(f"")

print("Sprites balde (repwkzbkhxl):")
for s in game.mxdlffpzkc():
    print(f"  [{s.name}] pos=({s.x},{s.y})")
print(f"")

print("Sprites parede (waoewejnqzc):")
for s in game.vgpoqzieha():
    print(f"  [{s.name}] pos=({s.x},{s.y})")
print(f"")

print("Gotas iniciais (liolfvkveqg):")
for s in game.qbsoyazkhk():
    print(f"  [{s.name}] pos=({s.x},{s.y})")
print(f"")

# --- TESTE 1: Estado inicial ---
log_state(game, "INITIAL")

# --- TESTE 2: Tentar ACTION6 em coordenadas calculadas manualmente ---
# Palette na pos game (6,9) = plzwjbfyfli-3 (tamanho 1x3)
# display_to_grid(39,27) -> (24,36) -> k=2 -> oijydygjkdb rotaciona para (39,27)
# VAMOS TESTAR 64 COORDENADAS VARRENDO O GRID DE 4 EM 4

print("\n=== VARREDURA ACTION6 no Level 2 ===")
print("Testando 64 coordenadas display (step=8 em 64x64)...")

found_palette = False
for dy in range(0, 64, 8):
    for dx in range(0, 64, 8):
        call_count += 1
        
        # Tentar ACTION6
        action = ActionInput(id=GameAction.ACTION6, data={"x": dx, "y": dy})
        r = game.perform_action(action)
        
        if r.levels_completed > 0:
            print(f"*** VITÓRIA! ACTION6({dx},{dy}) - levels={r.levels_completed} ***")
        
        # Verificar se algo mudou
        d = log_state(game, f"AFTER ACTION6({dx},{dy})")
        
        if game.vsoxmtrhqt is not None:
            print(f">>> ACTION6({dx},{dy}) SELECIONOU {sprite_info(game.vsoxmtrhqt)}")
            pr = game.vsoxmtrhqt
            # Tentar mover o palette selecionado em 4 direções
            for mv_id, mv_name, mv_key in [(GameAction.ACTION1, "ACIMA", (0,-1)), 
                                            (GameAction.ACTION2, "ABAIXO", (0,1)),
                                            (GameAction.ACTION3, "ESQUERDA", (-1,0)),
                                            (GameAction.ACTION4, "DIREITA", (1,0))]:
                call_count += 1
                action_move = ActionInput(id=mv_id)
                r_move = game.perform_action(action_move)
                d2 = log_state(game, f"AFTER {mv_name} (ACTION{mv_id.value})")
                print(f"    {mv_name}: vsoxmtrhqt={sprite_info(game.vsoxmtrhqt)}, levels={r_move.levels_completed}")
                if r_move.levels_completed > 0:
                    print(f"    *** VITÓRIA! ***")
                    found_palette = True
                    break
            if found_palette:
                break

print(f"\n=== RESUMO ===")
print(f"Total de calls: {call_count}")
print(f"Palette encontrado: {game.vsoxmtrhqt.name if game.vsoxmtrhqt else 'NÃO'}")
print(f"Levels completed: {r.levels_completed}")
print(f"Estado: {r.state}")
print(f"")

# --- Mostrar debug log compacto ---
print("=== DEBUG LOG COMPACTO ===")
for entry in debug_log[:5]:
    print(f"Call #{entry['call']}: {entry['label']}")
    for k, v in entry['state'].items():
        if isinstance(v, bool):
            print(f"  {k}={v}")
        elif isinstance(v, int):
            print(f"  {k}={v}")
        else:
            print(f"  {k}={str(v)[:50]}")
    print()
