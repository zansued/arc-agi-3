"""
v62_nav_solver.py — Pure Symbolic Navigation Solver (A*)

Categorias suportadas:
- A_NAV: Navegação pura (ls20, tr87, tu93)
- B_NAV+CLICK: Navegação com clique (dc22, ka59, sc25)

Arquitetura:
1. Render grid do jogo
2. Identificar walkable cells (não-parede, não-borda)
3. A* pathfinding do player ao goal
4. Mapear caminho → sequência de ACTIONS [1,2,3,4]
5. Executar e verificar progresso
"""

import json
import sys
import heapq
import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Set
from arc_agi import Arcade
from arcengine.enums import GameAction, GameState

# Direction mapping: 0=down(0,1), 1=right(1,0), 2=up(0,-1), 3=left(-1,0)
DIR_TO_VEC = {0: (0, 1), 1: (1, 0), 2: (0, -1), 3: (-1, 0)}
VEC_TO_DIR = {(0, 1): 0, (1, 0): 1, (0, -1): 2, (-1, 0): 3}

# Action ID → internal direction (for step())
# ACTION1=dir0(down), ACTION2=dir1(right), ACTION3=dir2(up), ACTION4=dir3(left)
ACTION_TO_DIR = {1: 0, 2: 1, 3: 2, 4: 3}


class NavSolver:
    """
    V62.4 — Pure Symbolic Navigation Solver
    """

    def __init__(self, game_id: str, max_steps_per_level: int = 500):
        self.game_id = game_id
        self.max_steps_per_level = max_steps_per_level
        self.arcade = Arcade()
        self.wrapper = None
        self.game = None
        self.results = {
            'game_id': game_id,
            'total_levels': 0,
            'solved_levels': 0,
            'levels': [],
            'success': False,
            'duration_seconds': 0,
        }

    def _init_game(self):
        """Initialize the game wrapper."""
        self.wrapper = self.arcade.make(self.game_id, seed=0, save_recording=False)
        self.game = self.wrapper._game
        self.results['total_levels'] = len(getattr(self.game, '_levels', []))

    def _get_grid(self) -> np.ndarray:
        """Render current grid."""
        sprites = self.game.current_level.get_sprites()
        return self.game.camera.render(sprites)

    def _find_player_pos(self, grid: np.ndarray) -> Optional[Tuple[int, int]]:
        """Find player position in grid (unique non-wall value that moves).
        Strategy: player is the sprite tagged eqatonpohu (for ls20).
        For other games, find the unique animated value.
        """
        sprites = self.game.current_level.get_sprites()
        # Look for player by known tag patterns
        for s in sprites:
            if s.tags and s.tags[0] in ['eqatonpohu', 'kvynsvxbpi'] and s.is_visible:
                if 'ihdgageizm' not in s.tags:
                    return (s.x // 5, s.y // 5)  # Convert pixel to cell
        # Fallback: return None - let subclass handle
        return None

    def _build_walkability_map(self, grid: np.ndarray) -> np.ndarray:
        """
        Build walkability map from grid render.
        Walls are high-layer (low value) collidable background.
        """
        # Get all collidable sprites positions
        sprites = self.game.current_level.get_sprites()
        h, w = grid.shape
        walkable = np.ones((h, w), dtype=bool)

        # Block positions of wall sprites (ihdgageizm tag)
        for s in sprites:
            if 'ihdgageizm' in s.tags:
                # Wall sprite occupies cells
                x_start = s.x // 5
                y_start = s.y // 5
                sprite_render = s.render()
                sh, sw = sprite_render.shape[:2]
                for dy in range(0, sh, 5):
                    for dx in range(0, sw, 5):
                        cx = x_start + dx // 5
                        cy = y_start + dy // 5
                        if 0 <= cx < w and 0 <= cy < h:
                            walkable[cy, cx] = False

        return walkable

    def _a_star(self, walkable: np.ndarray, start: Tuple[int, int], goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
        """
        A* pathfinding on walkability map.
        Returns path as list of (x, y) positions from start to goal.
        """
        h, w = walkable.shape

        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        start_node = (start[0], start[1])
        goal_node = (goal[0], goal[1])

        # Early exit if start or goal is blocked
        if not (0 <= start_node[0] < w and 0 <= start_node[1] < h):
            return None
        if not (0 <= goal_node[0] < w and 0 <= goal_node[1] < h):
            return None
        if not walkable[start_node[1], start_node[0]]:
            return None
        if not walkable[goal_node[1], goal_node[0]]:
            return None

        open_set = [(0, start_node)]
        came_from = {}
        g_score = {start_node: 0}
        f_score = {start_node: heuristic(start_node, goal_node)}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal_node:
                # Reconstruct path
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start_node)
                path.reverse()
                return path

            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                nx, ny = current[0] + dx, current[1] + dy
                neighbor = (nx, ny)

                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                if not walkable[ny, nx]:
                    continue

                tentative_g = g_score[current] + 1
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(neighbor, goal_node)
                    f_score[neighbor] = f
                    heapq.heappush(open_set, (f, neighbor))

        return None  # No path found

    def _path_to_actions(self, path: List[Tuple[int, int]]) -> List[int]:
        """Convert path to sequence of action IDs."""
        actions = []
        for i in range(len(path) - 1):
            dx = path[i+1][0] - path[i][0]
            dy = path[i+1][1] - path[i][1]
            vec = (dx, dy)
            if vec in VEC_TO_DIR:
                dir_id = VEC_TO_DIR[vec]
                # ACTION1=dir0, ACTION2=dir1, ACTION3=dir2, ACTION4=dir3
                action_id = dir_id + 1
                actions.append(action_id)
        return actions

    def _execute_and_check(self, actions: List[int]) -> bool:
        """Execute action sequence and check if level completed."""
        if not actions:
            return False

        # Reset before execution
        self.wrapper.step(GameAction.RESET)

        # Execute each action
        for action_id in actions:
            act = GameAction(f'ACTION{action_id}')
            fd = self.wrapper.step(act)

            # Check game state after each step
            state = getattr(fd, '_game_state', getattr(self.game, '_state', None))
            if state == GameState.WIN:
                return True
            if state == GameState.GAME_OVER:
                return False

        # After full sequence, check win
        state = getattr(self.game, '_state', None)
        if state == GameState.WIN or getattr(self.game, '_next_level', False):
            return True

        # Also check level index change
        level_idx_before = getattr(self.game, '_current_level_index', 0)
        self.wrapper.step(GameAction.RESET)
        level_idx_after = getattr(self.game, '_current_level_index', 0)
        if level_idx_after > level_idx_before:
            return True

        return False

    def solve_level(self, level_index: int) -> bool:
        """Solve single level using A* pathfinding."""
        # TODO: Implement per-level solving
        # This is the base class - subclasses will override for game-specific mechanics
        return False

    def solve_all(self):
        """Solve all levels."""
        print(f"
{'='*60}")
        print(f"  V62.4 NAV Solver — {self.game_id}")
        print(f"{'='*60}")

        self._init_game()
        total_levels = self.results['total_levels']

        start_time = time.time()

        for level_idx in range(total_levels):
            print(f"
  Level {level_idx + 1}/{total_levels}...")
            solved = self.solve_level(level_idx)
            self.results['levels'].append({
                'level_index': level_idx,
                'solved': solved,
            })
            if solved:
                self.results['solved_levels'] += 1
                print(f"    ✅ SOLVED")
            else:
                print(f"    ❌ FAILED")

        self.results['duration_seconds'] = time.time() - start_time
        self.results['success'] = self.results['solved_levels'] > 0

        print(f"
{'='*60}")
        print(f"  RESULTADO: {self.results['solved_levels']}/{total_levels} níveis resolvidos")
        print(f"  Duração: {self.results['duration_seconds']:.1f}s")
        print(f"{'='*60}")

        return self.results

