#!/a0/usr/workdir/.venv/bin/python3
"""Teste focado: mover palette selecionado ate balde e spill (k=2)"""
import sys, os, json
sys.path.insert(0, '/a0/usr/workdir')

from arcengine import ActionInput, GameAction, GameState
os.chdir('/a0/usr/workdir/environment_files/sp80/589a99af')

import importlib.util
spec = importlib.util.spec_from_file_location('sp80_module', 'sp80.py')
sp80_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp80_module)

game = sp80_module.Sp80()
game.set_level(1)  # Level 2 (0-indexed)

print('='*60)
print(f'SP80 LEVEL 2 - k={game.fahhoimkk}')
print(f'Palette selecionado: {game.vsoxmtrhqt.name if game.vsoxmtrhqt else "None"}')
print(f'Posicao: ({game.vsoxmtrhqt.x},{game.vsoxmtrhqt.y})')
print(f'Largura: {game.vsoxmtrhqt.width}')
print(f'avangppqui (modo selecao): {game.avangppqui}')
print(f'Steps restantes: {game.zlhbnhpcq}')

baldes = [(s.x, s.y) for s in game.mxdlffpzkc()]
print(f'Baldes: {baldes}')
print(f'Balde alvo (6,13): {"encontrado" if (6,13) in baldes else "NAO encontrado"}')
print('='*60)

# Sequencia: 7x ACTION1 (k=2 = BAIXO) + 1x ACTION5 (SPILL)
actions = [f'ACTION1']*7 + ['ACTION5']

for i, a in enumerate(actions):
    game._state = GameState.NOT_FINISHED  # ensure not game over
    action = ActionInput(id=GameAction[actions[i]])
    r = game.perform_action(action)
    print(f'  {i+1}. {a}: palette=({game.vsoxmtrhqt.x},{game.vsoxmtrhqt.y}) '
          f'levels={r.levels_completed} steps_left={game.zlhbnhpcq} '
          f'state={r.state.name} yqejjfwwh={game.yqejjfwwh}')

print('='*60)
print(f'RESULTADO FINAL:')
print(f'  Palette em: ({game.vsoxmtrhqt.x},{game.vsoxmtrhqt.y})')
print(f'  yqejjfwwh (win cond): {game.yqejjfwwh}')
print(f'  levels_completed: {r.levels_completed if "r" in dir() else "N/A"}')
print(f'  cevwbinfgl (baldes cheios): {len(game.cevwbinfgl)}')

# Tentar niveis seguintes
if r.levels_completed > 0:
    print(f'\n*** VITORIA! Proximo nivel: {game._current_level_index} ***')
else:
    print(f'\nFalhou. lyremoheq (tentativas SPILL): {game.lyremoheq}')
    print(f'Estado final: {game._state.name}')
    
    # Diagnostic: check if palette is over a bucket
    px, py = game.vsoxmtrhqt.x, game.vsoxmtrhqt.y
    pwidth = game.vsoxmtrhqt.width
    baldes_now = [(s.x, s.y) for s in game.mxdlffpzkc()]
    covering = [(bx, by) for bx, by in baldes_now if bx >= px and bx < px+pwidth and by == py]
    print(f'Palette ({px},{py}) w={pwidth} cobre baldes: {covering}')
