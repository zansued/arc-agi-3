import sys, numpy as np
from collections import deque
sys.path.insert(0, 'environment_files/ls20/9607627b')
from ls20 import Ls20, GameAction
from arcengine import ActionInput

# ============================================================
# V54 HypothesisGenerator
# ============================================================
class HypothesisGenerator:
    def observe(self, frame_3d, game):
        """Analisa frame 3D (1×64×64) e extrai informações."""
        f = np.array(frame_3d[0])  # frame é lista 3D: [slices][y][x]
        hypothesis = {
            'goals': list(zip(*np.where(f == 9))),
            'transformers': list(zip(*np.where(f == 12))),
            'player_cells': list(zip(*np.where((f == 0) | (f == 1) | (f == -1)))),
            'block_properties': {'shape': -1, 'color': -1, 'rotation': -1},
            'strategy': 'explore_left',
            'steps_left': 42
        }
        return hypothesis, f

# ============================================================
# V60 ActionExecutor + Feedback
# ============================================================
class ActionExecutor:
    def __init__(self):
        self.last_frame = None
    
    def execute(self, game, action):
        act = ActionInput(id=action)
        result = game.perform_action(act)
        
        # FrameData é Pydantic object, acessar atributos diretamente
        frame_after = np.array(result.frame[0]) if result.frame else None
        changed = True  # assume que mudou
        if self.last_frame is not None and frame_after is not None:
            changed = not np.array_equal(self.last_frame, frame_after)
        
        feedback = {
            'action': action.name,
            'changed': changed,
            'state': result.state.value if hasattr(result.state, 'value') else str(result.state),
            'levels_completed': result.levels_completed,
            'win_levels': result.win_levels
        }
        self.last_frame = frame_after
        return feedback, frame_after, result

# ============================================================
# MetacognitionLayer
# ============================================================
class MetacognitionLayer:
    def __init__(self):
        self.consecutive_no_change = 0
        self.action_cycle = [GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION1, GameAction.ACTION2]
        self.index = 0
    
    def next_action(self, feedback):
        if feedback['changed']:
            self.consecutive_no_change = 0
        else:
            self.consecutive_no_change += 1
            if self.consecutive_no_change >= 3:
                self.index = (self.index + 1) % 4
                self.consecutive_no_change = 0
        
        action = self.action_cycle[self.index]
        return action

# ============================================================
# LOOP PRINCIPAL
# ============================================================
def main():
    game = Ls20()
    generator = HypothesisGenerator()
    executor = ActionExecutor()
    meta = MetacognitionLayer()
    
    MAX_STEPS = 42
    actions_taken = []
    
    print("Iniciando loop V54→V60 para LS20 Level 1")
    print("="*50)
    
    for step in range(MAX_STEPS):
        # V54: Observar
        frame = game.get_pixels(0, 0, 64, 64)
        hypothesis, f = generator.observe([frame.tolist()], game)
        
        # V60: Escolher ação (via metacognição ou estratégia)
        if step == 0:
            action = GameAction.ACTION1  # UP
        else:
            action = meta.next_action(feedback)
        
        # Executar 1 passo
        feedback, frame_after, result = executor.execute(game, action)
        actions_taken.append(action.name)
        
        # Feedback visual
        goals = len(hypothesis['goals'])
        print(f"Step {step+1:2d}: {action.name:8s} | changed={feedback['changed']:5} | state={feedback['state']:15s} | goals={goals} | strategy={hypothesis['strategy']:15s}")
        
        # WIN?
        if result.levels_completed > 0 or result.state.value == 'COMPLETED':
            print(f"\n🏆 LEVEL COMPLETED! Actions: {' → '.join(actions_taken)}")
            return actions_taken
        
        # Perdeu?
        if feedback['state'] == 'LOST' or feedback['state'] == 'GAME_OVER':
            print(f"\n💀 GAME OVER no step {step+1}")
            return actions_taken
    
    print(f"\n📊 Fim dos {MAX_STEPS} steps. Nível não vencido.")
    print(f"Ações: {' → '.join(actions_taken)}")
    return actions_taken

if __name__ == '__main__':
    main()
