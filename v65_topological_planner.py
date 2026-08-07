import sys, numpy as np
from collections import deque
sys.path.insert(0, 'environment_files/ls20/9607627b')
from ls20 import Ls20, GameAction
from arcengine import ActionInput

# ============================================================
# TOPOLOGICAL MAPPER - Parse 64x64 grid into pathfinding graph
# ============================================================
# Grid values from ls20.py analysis:
# 5 = wall/boundary (impassable)
# 4 = walkable floor (corridors)
# 3 = walkable tunnel (interior)
# 0,1 = player/small objects
# 9 = goal (rjlbuycveu)
# 12 = transformer station
# 8 = unknown (observed in bottom)
# 11 = unknown (observed area)

ACTION_MAP = {
    (0, -1): GameAction.ACTION1,  # UP
    (0, 1): GameAction.ACTION2,   # DOWN
    (-1, 0): GameAction.ACTION3,  # LEFT
    (1, 0): GameAction.ACTION4    # RIGHT
}

TRAVERSABLE = {3, 4, 0, 1, 9, 12, 8}

class TopologicalPlanner:
    def __init__(self, grid):
        """grid: np.array 64x64 com valores do arcengine"""
        self.grid = grid
        self.height, self.width = grid.shape
    
    def is_traversable(self, y, x):
        if y < 0 or y >= self.height or x < 0 or x >= self.width:
            return False
        return int(self.grid[y, x]) in TRAVERSABLE
    
    def find_path(self, start, goal):
        """BFS: encontra caminho de (sy,sx) até (gy,gx). Retorna lista de (y,x)."""
        if start == goal:
            return []
        q = deque()
        q.append((start[0], start[1], []))
        visited = {start}
        while q:
            y, x, path = q.popleft()
            for dy, dx in [(0,1),(0,-1),(1,0),(-1,0)]:
                ny, nx = y + dy, x + dx
                if (ny, nx) == goal:
                    return path + [(ny, nx)]
                if (ny, nx) not in visited and self.is_traversable(ny, nx):
                    visited.add((ny, nx))
                    q.append((ny, nx, path + [(ny, nx)]))
        return None
    
    def path_to_actions(self, path):
        """Converte caminho de coordenadas para lista de GameAction."""
        actions = []
        for i in range(1, len(path)):
            dy = path[i][0] - path[i-1][0]
            dx = path[i][1] - path[i-1][1]
            action = ACTION_MAP.get((dx, dy))
            if action:
                actions.append(action)
        return actions
    
    def find_targets(self, value):
        """Encontra todas as células com um valor específico."""
        ys, xs = np.where(self.grid == value)
        return list(zip(ys.tolist(), xs.tolist()))
    
    def find_player(self):
        """Encontra posição do player (values 0 ou 1)."""
        ys, xs = np.where((self.grid == 0) | (self.grid == 1))
        if len(ys) > 0:
            # Pega o centro do grupo de pixels do player
            mid = len(ys) // 2
            return (int(ys[mid]), int(xs[mid]))
        return None

# ============================================================
# EXECUTE PATH ON ARCENGINE
# ============================================================
class ArcEngineRunner:
    def __init__(self, game):
        self.game = game
    
    def execute_actions(self, actions, max_steps=200):
        """Executa sequência de ações e retorna resultado."""
        steps_used = []
        for i, action in enumerate(actions):
            act = ActionInput(id=action)
            result = self.game.perform_action(act)
            steps_used.append({
                'step': i+1,
                'action': action.name,
                'state': result.state.value if hasattr(result.state, 'value') else str(result.state),
                'levels_completed': result.levels_completed
            })
            if result.levels_completed > 0:
                return steps_used, 'WIN'
            if i >= max_steps:
                break
        return steps_used, 'NOT_FINISHED'
    
    def scan_grid(self):
        return self.game.get_pixels(0, 0, 64, 64)

# ============================================================
# MAIN: Planejamento Topológico para LS20 Level 1
# ============================================================
def main():
    game = Ls20()
    runner = ArcEngineRunner(game)
    grid = runner.scan_grid()
    
    planner = TopologicalPlanner(grid)
    
    print("="*60)
    print("ANÁLISE TOPOLÓGICA DO LS20 LEVEL 1")
    print("="*60)
    
    # 1. Identificar features
    goals = planner.find_targets(9)
    transformers = planner.find_targets(12)
    player_pos = planner.find_player()
    
    print(f"\n📌 Player position: {player_pos}")
    print(f"🎯 Goals (value 9): {len(goals)} tiles")
    if goals:
        # Mostrar bounding box
        ys = [g[0] for g in goals]
        xs = [g[1] for g in goals]
        print(f"   Y range: {min(ys)}-{max(ys)}, X range: {min(xs)}-{max(xs)}")
        print(f"   First 5: {goals[:5]}")
    print(f"🔧 Transformers (value 12): {len(transformers)} tiles")
    if transformers:
        print(f"   Positions: {transformers}")
    
    # 2. Mapear paredes
    walls = planner.find_targets(5)
    floor_3 = planner.find_targets(3)
    floor_4 = planner.find_targets(4)
    print(f"🧱 Walls (value 5): {len(walls)} tiles")
    print(f"🚶 Walkable (value 3): {len(floor_3)} tiles")
    print(f"🚶 Walkable (value 4): {len(floor_4)} tiles")
    
    # 3. BFS: Player → primeiro goal
    if player_pos and goals:
        goal_center = (goals[0][0], goals[0][1])
        print(f"\n🔍 BFS: Player {player_pos} → Goal {goal_center}")
        path = planner.find_path(player_pos, goal_center)
        if path:
            print(f"   ✅ Path found! Length: {len(path)} steps")
            actions = planner.path_to_actions(path)
            print(f"   Action sequence ({len(actions)} steps): {' → '.join(a.name for a in actions[:10])}...")
            
            # Executar no arcengine
            print(f"\n⚡ Executing on arcengine...")
            results, final_state = runner.execute_actions(actions)
            print(f"   Final state: {final_state}")
            
            # Scannear grid pós-movimento
            grid2 = runner.scan_grid()
            new_goals = len(np.where(grid2 == 9)[0])
            print(f"   Goals remaining: {new_goals}")
            
            # Primeiro passo detalhado
            if results:
                r = results[0]
                print(f"   Step 1: {r['action']} → state={r['state']}, completed={r['levels_completed']}")
            
            # Se não chegou, tentar rota alternativa
            if final_state != 'WIN':
                print(f"\n⚠️  Direto não funcionou. Tentando rota alternativa...")
                # Precisa desviar do bloqueio
        else:
            print(f"   ❌ No path found! Paredes bloqueiam.")
    
    print(f"\n{'='*60}")
    print(f"Nível atual: {game.level_index}, Goals detectados: {len(goals)}, Steps totais: 42")

if __name__ == '__main__':
    main()
