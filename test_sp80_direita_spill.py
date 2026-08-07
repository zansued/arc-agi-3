#!/a0/usr/workdir/.venv/bin/python3
"""Teste: ACTION3 (DIREITA, k=2) + ACTION5 (SPILL) - baseado no histórico"""
import sys, os
sys.path.insert(0, '/a0/usr/workdir')

from arcengine import ActionInput, GameAction, GameState
os.chdir('/a0/usr/workdir/environment_files/sp80/589a99af')

import importlib.util
spec = importlib.util.spec_from_file_location('sp80_module', 'sp80.py')
sp80_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp80_module)

import json

print('='*60)
print('SP80 LEVEL 2 - Teste ACTION3 + ACTION5')
print('='*60)

game = sp80_module.Sp80()
game.set_level(1)

snapshots = []

def snapshot(label):
    snapshots.append({
        'label': label,
        'vsoxmtrhqt': f'{game.vsoxmtrhqt.name if game.vsoxmtrhqt else "None"} ({game.vsoxmtrhqt.x},{game.vsoxmtrhqt.y}) w={game.vsoxmtrhqt.width}' if game.vsoxmtrhqt else 'None',
        'avangppqui': game.avangppqui,
        'yqejjfwwh': game.yqejjfwwh,
        'zlhbnhpcq': game.zlhbnhpcq,
        'lyremoheq': game.lyremoheq,
        'cevwbinfgl': len(game.cevwbinfgl),
        'levels': game._current_level_index,
        'state': game._state.name,
        'gotas': [(s.x, s.y) for s in game.fbrwmvzsym() if 'liolfvkveqg' in s.tags],
        'baldes': [(s.x, s.y) for s in game.mxdlffpzkc()],
    })

snapshot('INICIO')
print(f'\n1. INICIO: vsoxmtrhqt={snapshots[-1]["vsoxmtrhqt"]}')
print(f'   avangppqui={snapshots[-1]["avangppqui"]} k={game.fahhoimkk}')
print(f'   Gotas inicial: {snapshots[-1]["gotas"]}')

# Testar 5 combinacoes diferentes
combinacoes = [
    [('ACTION3', 1), ('ACTION5', 1)],           # 1 direita + spill
    [('ACTION3', 3), ('ACTION5', 1)],           # 3 direita + spill
    [('ACTION3', 1), ('ACTION2', 1), ('ACTION5', 1)], # direita + cima + spill
    [('ACTION2', 1), ('ACTION5', 1)],           # cima + spill
    [('ACTION5', 1)],                            # spill direto
]

for idx, combo in enumerate(combinacoes):
    print(f'\n{"="*60}')
    print(f'COMBO {idx+1}: {" → ".join([f"{a}×{n}" for a,n in combo])}')
    print('='*60)
    
    game2 = sp80_module.Sp80()
    game2.set_level(1)
    
    for action_name, count in combo:
        for i in range(count):
            action = ActionInput(id=GameAction[action_name])
            r = game2.perform_action(action)
            px, py = game2.vsoxmtrhqt.x, game2.vsoxmtrhqt.y
            pw = game2.vsoxmtrhqt.width
            print(f'  {action_name} #{i+1}: pos=({px},{py}) w={pw} '
                  f'steps={game2.zlhbnhpcq} levels={r.levels_completed} '
                  f'state={r.state.name} yqej={game2.yqejjfwwh}')
            if r.levels_completed > 0:
                print(f'  *** VITORIA! Nivel completado! ***')
                break
        if r.levels_completed > 0:
            break
    
    if r.levels_completed == 0:
        baldes = [(s.x, s.y) for s in game2.mxdlffpzkc()]
        gotas = [(s.x, s.y) for s in game2.fbrwmvzsym() if 'liolfvkveqg' in s.tags]
        print(f'  RESULTADO: palette=({game2.vsoxmtrhqt.x},{game2.vsoxmtrhqt.y}) '
              f'baldes_cheios={len(game2.cevwbinfgl)} gotas={gotas} lyremoheq={game2.lyremoheq}')

print(f'\n{"="*60}')
print('FIM DOS TESTES')
print('='*60)

# Salvar JSON de diagnostico
with open('/a0/usr/workdir/sp80_level2_diagnosis.json', 'w') as f:
    json.dump(snapshots, f, indent=2, default=str)
print(f'Snapshots salvos em sp80_level2_diagnosis.json')
