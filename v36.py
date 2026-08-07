#!/usr/bin/env python3
"""
v36: Deepcopy BFS + Análise Estrutural + Grafo em Memória + Priorização de Ações
Baseado no v30 (deepcopy wrapper) + features do v35 + fallback router

Arquitetura:
  1. FASE DE ANÁLISE: extrair features do frame (cores, objetos, simetria)
  2. FASE DE BUSCA: BFS com deepcopy do wrapper, ações priorizadas pelas features
  3. GRAFO EM MEMÓRIA: objetos detectados em cada frame, padrões de movimento
"""

import copy
import hashlib
import json
import sys
import time
import traceback
from collections import defaultdict, deque
from multiprocessing import Pool, cpu_count

import numpy as np

# ============================================================
# CONFIG
# ============================================================
GAME_IDS = [
    'ar25', 'bp35', 'cd82', 'cn04', 'dc22', 'ft09', 'g50t',
    'ka59', 'lf52', 'lp85', 'ls20', 'm0r0', 'r11l', 're86',
    's5i5', 'sb26', 'sc25', 'sk48', 'sp80', 'su15', 'tn36',
    'tr87', 'tu93', 'vc33', 'wa30'
]
MAX_STEPS = 500
MAX_PLY = 8
N_WORKERS = 6


# ============================================================
# FEATURE EXTRACTION
# ============================================================
def extract_features(frame_list):
    """
    Extrai features estruturais de um frame (lista de arrays numpy 64x64).
    Retorna dict com:
      - color_hist: contagem de pixels por cor (0-9)
      - n_objects: número aproximado de objetos (componentes conectados)
      - symmetry_h: simetria horizontal (bool)
      - symmetry_v: simetria vertical (bool)
      - grid_hash: hash determinístico do grid principal
    """
    if not frame_list or len(frame_list) == 0:
        return {'color_hist': {}, 'n_objects': 0, 'symmetry_h': False,
                'symmetry_v': False, 'grid_hash': 'empty'}

    grid = np.asarray(frame_list[0], dtype=np.int8)
    if grid.size == 0:
        return {'color_hist': {}, 'n_objects': 0, 'symmetry_h': False,
                'symmetry_v': False, 'grid_hash': 'empty'}

    h, w = grid.shape

    # Histograma de cores (0-9)
    colors, counts = np.unique(grid, return_counts=True)
    color_hist = dict(zip((int(c) for c in colors), (int(v) for v in counts)))

    # Simetria horizontal
    if h >= 2:
        mid = h // 2
        top = grid[:mid, :]
        bottom = grid[h - mid:, :]
        symmetry_h = np.array_equal(top, bottom[::-1, :])
    else:
        symmetry_h = False

    # Simetria vertical
    if w >= 2:
        mid = w // 2
        left = grid[:, :mid]
        right = grid[:, w - mid:]
        symmetry_v = np.array_equal(left, right[:, ::-1])
    else:
        symmetry_v = False

    # Componentes conectados (contagem aproximada de objetos)
    # Usando flood-fill simples, ignorando cor 0 (fundo)
    grid_bin = (grid > 0).astype(np.int8)
    visited = np.zeros_like(grid_bin, dtype=bool)
    n_objects = 0
    stack = []
    for y in range(h):
        for x in range(w):
            if grid_bin[y, x] and not visited[y, x]:
                n_objects += 1
                # Preencher componente
                stack.append((y, x))
                while stack:
                    cy, cx = stack.pop()
                    if cy < 0 or cy >= h or cx < 0 or cx >= w:
                        continue
                    if visited[cy, cx] or not grid_bin[cy, cx]:
                        continue
                    visited[cy, cx] = True
                    stack.extend([(cy - 1, cx), (cy + 1, cx),
                                  (cy, cx - 1), (cy, cx + 1)])

    # Hash do grid
    grid_hash = hashlib.md5(grid.tobytes()).hexdigest()[:12]

    return {
        'color_hist': color_hist,
        'n_objects': n_objects,
        'symmetry_h': bool(symmetry_h),
        'symmetry_v': bool(symmetry_v),
        'grid_hash': grid_hash,
    }


def features_to_state_key(features):
    """Gera uma chave de estado única baseada nas features estruturais."""
    if features is None or features.get('grid_hash') == 'empty':
        return 'empty'
    return features['grid_hash']


def compute_delta_features(f1, f2):
    """Compara features entre dois frames e retorna o delta."""
    if f1 is None or f2 is None:
        return {}
    delta = {}
    if f1['n_objects'] != f2['n_objects']:
        delta['n_objects'] = f2['n_objects'] - f1['n_objects']
    if f1['symmetry_h'] != f2['symmetry_h']:
        delta['symmetry_h'] = f2['symmetry_h']
    if f1['symmetry_v'] != f2['symmetry_v']:
        delta['symmetry_v'] = f2['symmetry_v']
    # Mudança de cores: cores que apareceram ou sumiram
    delta['colors_added'] = set(f2['color_hist'].keys()) - set(f1['color_hist'].keys())
    delta['colors_removed'] = set(f1['color_hist'].keys()) - set(f2['color_hist'].keys())
    return delta


# ============================================================
# GRAPH MEMORY
# ============================================================
class GraphMemory:
    """
    Grafo em memória que armazena:
      - Nós: cada frame único (identificado por grid_hash)
      - Arestas: transições entre frames por ação
      - Metadados: features de cada nó, deltas entre nós
      - Padrões: movimentos recorrentes detectados
    """

    def __init__(self):
        self.nodes = {}          # grid_hash -> features
        self.edges = []          # [(from_hash, action_id, to_hash, step_count)]
        self.game_metadata = {}  # info global do jogo
        self.action_probs = defaultdict(lambda: defaultdict(float))

    def add_frame(self, features):
        h = features.get('grid_hash', 'empty')
        if h != 'empty' and h not in self.nodes:
            self.nodes[h] = features
            return True
        return False

    def add_transition(self, from_hash, action_id, to_hash):
        if from_hash and to_hash and from_hash != to_hash:
            self.edges.append((from_hash, action_id, to_hash, len(self.edges)))
            # Atualizar probabilidades de ação
            self.action_probs[from_hash][action_id] += 1.0

    def get_action_priorities(self, current_features):
        """
        Retorna lista de ações prioritárias baseadas no grafo.
        Se o frame atual é similar a um frame já visitado, 
        prioriza ações que geraram mudanças naquele frame.
        """
        if current_features is None:
            return list(range(1, 7))

        current_hash = current_features.get('grid_hash', '')
        if not current_hash:
            return list(range(1, 7))

        # Ações mais bem-sucedidas a partir deste hash
        if current_hash in self.action_probs:
            probs = self.action_probs[current_hash]
            sorted_actions = sorted(probs.keys(),
                                    key=lambda a: probs[a],
                                    reverse=True)
            # Completar com ações não testadas
            remaining = [a for a in range(1, 7) if a not in sorted_actions]
            return sorted_actions + remaining

        # Fallback: priorizar ACTION1 (mais segura)
        # ACTION1 é pixel/movimento, nunca crasha
        return [1, 2, 3, 4, 5, 6]

    def has_pattern(self, current_hash):
        """Verifica se este hash já foi explorado suficientemente."""
        if current_hash in self.action_probs:
            # Se já testou 4+ ações a partir daqui, está explorado
            return len(self.action_probs[current_hash]) >= 4
        return False

    def summary(self):
        return {
            'nodes': len(self.nodes),
            'edges': len(self.edges),
            'action_probs': sum(len(v) for v in self.action_probs.values()),
        }


# ============================================================
# PRE-ANALYSIS PHASE
# ============================================================
def analyze_game(wrapper):
    """
    FASE 1: Análise estrutural do jogo antes do BFS.
    Extrai features do frame inicial e constrói o grafo base.
    """
    graph = GraphMemory()

    try:
        f0 = wrapper.reset()
        if f0 is None:
            return graph, {'initial_state': 'dead'}

        features = extract_features(f0.frame)
        graph.add_frame(features)

        # Testar cada ação uma vez pra ver o que muda
        action_results = {}
        for a in range(1, 7):
            try:
                w_clone = copy.deepcopy(wrapper)
                fa = w_clone.step(GameAction.from_id(a))
                if fa is not None:
                    feat_a = extract_features(fa.frame)
                    action_results[a] = {
                        'new_hash': feat_a.get('grid_hash', ''),
                        'changed': feat_a.get('grid_hash', '') != features.get('grid_hash', ''),
                        'level_up': fa.levels_completed > 0,
                    }
                    if feat_a.get('grid_hash', '') != features.get('grid_hash', ''):
                        graph.add_frame(feat_a)
                        graph.add_transition(features['grid_hash'], a, feat_a['grid_hash'])
                else:
                    action_results[a] = {'new_hash': '', 'changed': False, 'level_up': False, 'none': True}
            except Exception:
                action_results[a] = {'new_hash': '', 'changed': False, 'level_up': False, 'crash': True}

        graph.game_metadata = {
            'action_results': action_results,
            'initial_features': features,
            'win_levels': f0.win_levels,
        }

        return graph, action_results
    except Exception as e:
        print(f'  [ANALYZE] crash: {e}')
        return graph, {'initial_state': 'crash'}


# ============================================================
# BFS WITH DEEPCOPY + GRAPH
# ============================================================
def solve_game(game_id):
    """
    FASE 2: BFS informado pelo grafo de features.
    """
    from arc_agi import Arcade
    from arcengine.enums import GameAction, GameState

    start = time.time()
    result = {
        'game': game_id,
        'states': 0,
        'levels': 0,
        'steps': 0,
        'crashes': 0,
        'stagnated': False,
    }

    try:
        wrapper = Arcade().make(game_id)
        root = wrapper.reset()
        if root is None:
            return result

        # FASE 1: Análise
        features_root = extract_features(root.frame)
        graph = GraphMemory()
        graph.add_frame(features_root)

        # Análise de ações
        for a in range(1, 7):
            try:
                wc = copy.deepcopy(wrapper)
                fa = wc.step(GameAction.from_id(a))
                if fa is not None:
                    feat = extract_features(fa.frame)
                    fh = feat.get('grid_hash', '')
                    rh = features_root.get('grid_hash', '')
                    if fh and fh != rh:
                        graph.add_frame(feat)
                        graph.add_transition(rh, a, fh)
            except Exception:
                pass

        # FASE 2: BFS
        visited = set()
        queue = deque()
        level_steps_remaining = MAX_STEPS

        # Inicializar
        root_key = features_to_state_key(features_root)
        visited.add(root_key)
        queue.append((wrapper, [], features_root))

        ply = 0
        states_count = 1
        levels_found = 0
        crashes = 0
        steps_used = 0

        while queue and level_steps_remaining > 0 and ply < MAX_PLY:
            # Beam: processar este nível da BFS
            level_size = len(queue)
            new_states = 0

            for _ in range(level_size):
                if level_steps_remaining <= 0:
                    break

                w, path, feat = queue.popleft()

                # Priorizar ações baseadas no grafo
                action_order = graph.get_action_priorities(feat)

                for action_id in action_order:
                    if level_steps_remaining <= 0:
                        break

                    try:
                        w_clone = copy.deepcopy(w)
                        fa = w_clone.step(GameAction.from_id(action_id))
                        steps_used += 1
                        level_steps_remaining -= 1

                        if fa is None:
                            crashes += 1
                            continue

                        feat_a = extract_features(fa.frame)
                        state_key = features_to_state_key(feat_a)

                        # Verificar se completou nível
                        lv = fa.levels_completed
                        if lv > levels_found:
                            levels_found = lv
                            # Resetar stagnação
                            new_states = max(new_states, 1)

                        if state_key not in visited and state_key != 'empty':
                            visited.add(state_key)
                            graph.add_frame(feat_a)
                            if feat:
                                graph.add_transition(feat.get('grid_hash', ''),
                                                     action_id,
                                                     feat_a.get('grid_hash', ''))
                            queue.append((w_clone, path + [action_id], feat_a))
                            new_states += 1
                            states_count += 1

                    except Exception as e:
                        crashes += 1
                        level_steps_remaining -= 1

                # Limitar deepcopies: se já exploramos o suficiente
                # deste estado, pular
                if graph.has_pattern(feat.get('grid_hash', '')):
                    continue

            ply += 1

            # Stagnação guard: se nenhum estado novo, pular profundo
            if new_states == 0 and ply > 3:
                break

            if new_states == 0:
                # Um ply sem novidades não é stagnation se ainda
                # temos profundidade
                pass

        result.update({
            'states': states_count,
            'levels': levels_found,
            'steps': steps_used,
            'crashes': crashes,
            'stagnated': level_steps_remaining > MAX_STEPS // 2,
            'graph_summary': graph.summary(),
            'time': round(time.time() - start, 1),
        })

    except Exception as e:
        result['error'] = str(e)
        traceback.print_exc()

    return result


def solve_wrapper(gid):
    """Wrapper pra Pool.map"""
    try:
        r = solve_game(gid)
        print(f'[v36] {gid}: {r["states"]} estados, {r["levels"]} níveis, '
              f'{r["steps"]} steps, {r["crashes"]} cr, {r["time"]}s')
        return r
    except Exception as e:
        print(f'[v36] {gid}: CRASH {e}')
        return {'game': gid, 'error': str(e)}


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print(f'===== V36 DEEPCOPY BFS + GRAPH MEMORY =====')
    print(f'Games: {len(GAME_IDS)} | Workers: {N_WORKERS} | Steps: {MAX_STEPS} | Ply: {MAX_PLY}')
    print(f'Started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    sys.stdout.flush()

    t0 = time.time()
    results = []

    with Pool(N_WORKERS) as pool:
        for r in pool.imap_unordered(solve_wrapper, GAME_IDS):
            results.append(r)

    t1 = time.time()

    # Compilar
    total_states = sum(r.get('states', 0) for r in results)
    total_levels = sum(r.get('levels', 0) for r in results)
    total_crashes = sum(r.get('crashes', 0) for r in results)
    total_steps = sum(r.get('steps', 0) for r in results)
    dead_games = [r['game'] for r in results if r.get('states', 0) <= 1]
    top_games = sorted(results, key=lambda r: r.get('states', 0), reverse=True)[:10]

    print(f'\n{"="*60}')
    print(f'V36 FULL BENCHMARK RESULT')
    print(f'{"="*60}')
    print(f'Tempo total: {t1-t0:.1f}s')
    print(f'25/25 jogos completos')
    print(f'')
    print(f'Total estados únicos: {total_states}')
    print(f'Total níveis: {total_levels}')
    print(f'Total crashes: {total_crashes}')
    print(f'Total steps: {total_steps}')
    print(f'')
    print(f'Dead games (<=1 estado): {len(dead_games)}')
    for g in dead_games:
        r = next(x for x in results if x['game'] == g)
        print(f'  {g}: error={r.get("error", "none")}')
    print(f'')
    print(f'Top 10 por estados:')
    for r in top_games:
        print(f'  {r["game"]}: {r["states"]:>4} estados, {r["levels"]} níveis, '
              f'{r["steps"]:>3} steps, {r["crashes"]:>3} cr, {r["time"]:>4.1f}s')
    print(f'')
    print(f'Games com níveis:')
    for r in results:
        if r.get('levels', 0) > 0:
            print(f'  {"":>2}{r["game"]}: {r["levels"]} nível(is)')

    # Salvar resultados
    out = {
        'version': 'v36',
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'total_states': total_states,
        'total_levels': total_levels,
        'total_crashes': total_crashes,
        'total_steps': total_steps,
        'results': {r['game']: {
            'states': r.get('states', 0),
            'levels': r.get('levels', 0),
            'steps': r.get('steps', 0),
            'crashes': r.get('crashes', 0),
            'time': r.get('time', 0),
            'error': r.get('error', None),
            'graph': r.get('graph_summary', {}),
        } for r in results},
    }

    with open(f'/tmp/v36_results.json', 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f'\nResultados salvos em /tmp/v36_results.json')
    print(f'Done: {time.strftime("%Y-%m-%d %H:%M:%S")}')
