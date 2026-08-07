"""
v62_8_bfs_estado.py — BFS com estados reais via deepcopy wrapper

Cada nó guarda um deepcopy do wrapper inteiro.
Step() direto no wrapper copiado.
Hash do grid renderizado para dedup.
Verifica _next_level e _state após cada step.

Uso: python3 v62_8_bfs_estado.py <game_id> [max_expansions] [max_levels]
"""
import sys
import json
import copy
import time
import numpy as np
from pathlib import Path
from collections import deque

sys.path.insert(0, '.')
from arc_agi import Arcade
from arcengine.enums import GameAction, GameState

ACTION_MAP = {1: GameAction.ACTION1, 2: GameAction.ACTION2,
              3: GameAction.ACTION3, 4: GameAction.ACTION4,
              5: GameAction.ACTION5, 6: GameAction.ACTION6, 7: GameAction.ACTION7}


def render_grid_hash(wrapper) -> bytes:
    """Renderiza grid e retorna hash para dedup."""
    try:
        game = wrapper._game
        level = game.current_level
        sprites = level.get_sprites()
        grid = game.camera.render(sprites)
        return grid.tobytes()
    except Exception as e:
        return b'err:' + str(e).encode()[:64]


def check_win(wrapper) -> bool:
    """Verifica vitória após step."""
    try:
        g = wrapper._game
        if getattr(g, '_next_level', False):
            return True
        st = getattr(g, '_state', None)
        if st == GameState.WIN or str(st) == 'GameState.WIN':
            return True
        # Some games may use different win indicators
        return False
    except:
        return False


def solve_level(wrapper, actions: list, max_expansions: int):
    """
    BFS incremental sobre deepcopy de wrapper.
    actions: ações disponíveis para este jogo.
    """
    initial_hash = render_grid_hash(wrapper)
    visited = {initial_hash}
    
    # BFS queue: (wrapper_copy, sequence_list)
    queue = deque()
    w0 = copy.deepcopy(wrapper)
    queue.append((w0, []))
    
    expansions = 0
    while queue and expansions < max_expansions:
        cur_w, seq = queue.popleft()
        
        for act_id in actions:
            expansions += 1
            
            # Clone
            w_clone = copy.deepcopy(cur_w)
            
            # Step
            try:
                act = ACTION_MAP[act_id]
                _ = w_clone.step(act)
            except Exception as e:
                continue
            
            # Check win
            if check_win(w_clone):
                new_seq = seq + [act_id]
                return new_seq, expansions
            
            # Hash
            h = render_grid_hash(w_clone)
            if h not in visited:
                visited.add(h)
                new_seq = seq + [act_id]
                queue.append((w_clone, new_seq))
                
                if len(visited) % 100 == 0:
                    print(f"      {len(visited)} estados, fila={len(queue)}, seq_len={len(new_seq)}", flush=True)
            
            if expansions >= max_expansions:
                break
    
    return None, expansions


def solve(game_id: str, max_exp=5000, max_levels=9):
    print(f"\n{'='*60}", flush=True)
    print(f"  V62.8 BFS Estado — {game_id}", flush=True)
    print(f"  Limite: {max_exp} expansoes/nivel", flush=True)
    print(f"{'='*60}", flush=True)
    
    start = time.time()
    
    a = Arcade()
    wrapper = a.make(game_id, seed=0, save_recording=False)
    wrapper.step(GameAction.RESET)
    game = wrapper._game
    
    total_levels = min(len(getattr(game, '_levels', [])), max_levels)
    acts = list(getattr(game, '_available_actions', [1, 2, 3, 4]))
    print(f"  Levels: {total_levels}, Actions: {acts}", flush=True)
    
    results = {
        'game_id': game_id,
        'solver': 'v62_8_bfs_estado',
        'levels': [],
        'solved': 0,
        'total': total_levels,
        'actions': acts,
        'time': 0,
        'expansions': 0,
    }
    
    # BFS benchmark: primeiro nível com contagem de tempo
    for level_idx in range(total_levels):
        print(f"\n  [{level_idx+1}/{total_levels}] Level {level_idx+1}...", flush=True)
        wrapper.step(GameAction.RESET)
        
        t0 = time.time()
        solution, exp_count = solve_level(wrapper, acts, max_exp)
        dt = time.time() - t0
        
        results['expansions'] += exp_count
        
        level_res = {
            'level': level_idx + 1,
            'solved': solution is not None,
            'steps': len(solution) if solution else 0,
            'expansions': exp_count,
            'time_s': round(dt, 1),
        }
        results['levels'].append(level_res)
        
        if solution:
            results['solved'] += 1
            print(f"    >> Level {level_idx+1} SOLVED! {len(solution)} steps, {exp_count} exp, {dt:.1f}s", flush=True)
            
            # Execute solution on real wrapper to advance state
            wrapper.step(GameAction.RESET)
            for a in solution:
                wrapper.step(ACTION_MAP[a])
        else:
            print(f"    >> Level {level_idx+1} FAILED ({exp_count} exp, {dt:.1f}s)", flush=True)
    
    results['time'] = round(time.time() - start, 1)
    
    print(f"\n{'='*60}", flush=True)
    print(f"  RESULTADO: {results['solved']}/{results['total']}", flush=True)
    print(f"  Tempo total: {results['time']}s", flush=True)
    print(f"  Expansões totais: {results['expansions']}", flush=True)
    print(f"{'='*60}", flush=True)
    
    out = Path(f"v62_8_{game_id}_result.json")
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"  Salvo: {out.name}", flush=True)
    
    return results


if __name__ == '__main__':
    args = sys.argv[1:]
    gid = args[0] if args else 'tu93'
    me = int(args[1]) if len(args) > 1 else 5000
    ml = int(args[2]) if len(args) > 2 else 9
    solve(gid, me, ml)
