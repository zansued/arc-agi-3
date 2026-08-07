import sys, json, numpy as np
from collections import deque
sys.path.insert(0, 'environment_files/ls20/9607627b')
from ls20 import Ls20, GameAction
from arcengine import ActionInput

# ============================================================
# HypothesisGenerator (V54) - cria modelo simbólico do jogo
# ============================================================
class HypothesisGenerator:
    """Gera e mantém hipótese simbólica baseada no frame observado."""
    def __init__(self):
        self.hypothesis = {
            'block_properties': {'shape': -1, 'color': -1, 'rotation': -1},
            'player_pos': None, 'block_pos': None,
            'transformers_visited': {'shape': False, 'color': False, 'rotation': False},
            'goals_delivered': [],
            'strategy': 'explore',  # explore | find_block | push_block | transform | deliver
            'steps_left': 42,
            'world_model': {}
        }
    
    def observe(self, frame, game):
        """Analisa frame 64×64 e extrai informações."""
        # Mapeamento de cores do código fonte
        # Value 3 = walkable corridor, 4 = walkable floor
        # Value 5 = wall/boundary, 9 = goal (rjlbuycveu)
        # Value 12 = transformer (ttfwljgohq?)
        # Value 0/1 = player/small objects
        # Value -1 (255 in signed int8) = transparent
        
        # Detectar goals (value 9)
        goals_y, goals_x = np.where(frame == 9)
        self.hypothesis['goals_detected'] = list(zip(goals_y.tolist(), goals_x.tolist()))
        
        # Detectar transformers (value 12)
        trans_y, trans_x = np.where(frame == 12)
        self.hypothesis['transformers_detected'] = list(zip(trans_y.tolist(), trans_x.tolist()))
        
        # Detectar player (value 0, 1 - small objects)
        player_y, player_x = np.where((frame == 0) | (frame == 1))
        self.hypothesis['player_detected'] = list(zip(player_y.tolist(), player_x.tolist()))
        
        return self.hypothesis
    
    def generate_action_plan(self):
        """Gera sequência de ações baseada na hipótese atual."""
        strategy = self.hypothesis['strategy']
        # Nível 1: explorar → encontrar bloco → empurrar pelos 3 transformers → goal
        if strategy == 'explore':
            return GameAction.ACTION3  # LEFT
        elif strategy == 'find_block':
            return GameAction.ACTION4  # RIGHT
        elif strategy == 'push_block':
            # Precisamos determinar direção para mover o bloco
            return GameAction.ACTION1  # UP
        return GameAction.ACTION3  # LEFT default

# ============================================================
# ActionExecutor (V60) - executa 1 passo e captura feedback
# ============================================================
class ActionExecutor:
    def __init__(self):
        self.history = deque(maxlen=10)
        self.last_frame = None
    
    def execute(self, game, action):
        frame_before = game.get_pixels(0, 0, 64, 64).copy()
        act = ActionInput(id=action)
        result = game.perform_action(act)
        frame_after = game.get_pixels(0, 0, 64, 64).copy()
        
        # Calcular mudanças
        changed = not np.array_equal(frame_before, frame_after)
        diff_count = np.sum(frame_before != frame_after)
        
        feedback = {
            'action': action.name,
            'changed': changed,
            'diff_pixels': int(diff_count),
            'state': result.get('state', 'UNKNOWN'),
            'levels_completed': result.get('levels_completed', 0)
        }
        self.history.append(feedback)
        self.last_frame = frame_after
        return feedback, frame_after, result

# ============================================================
# FeedbackRefiner - atualiza hipótese com base no feedback
# ============================================================
class FeedbackRefiner:
    def refine(self, hypothesis, feedback, frame):
        # Se frame mudou, atualizar observações
        if feedback['changed']:
            hypothesis['strategy'] = 'explore'  # continuar na mesma direção
        else:
            # Se não mudou, tentar outra direção
            if hypothesis['strategy'] == 'explore':
                hypothesis['strategy'] = 'find_block'
            elif hypothesis['strategy'] == 'find_block':
                hypothesis['strategy'] = 'explore'  # alternar
        return hypothesis

# ============================================================
# MetacognitionLayer - detecta estagnação e troca estratégia
# ============================================================
class MetacognitionLayer:
    def __init__(self):
        self.consecutive_no_change = 0
        self.same_action_count = 0
        self.last_action = None
    
    def check(self, feedback, hypothesis):
        stuck = False
        
        if not feedback['changed']:
            self.consecutive_no_change += 1
            if self.consecutive_no_change >= 5:
                hypothesis['strategy'] = 'rotate'  # trocar direção
                self.consecutive_no_change = 0
                stuck = True
        else:
            self.consecutive_no_change = 0
        
        if feedback['state'] == 'GAME_OVER':
            hypothesis['strategy'] = 'reset_needed'
            stuck = True
        
        return stuck, hypothesis

# ============================================================
# LOOP PRINCIPAL V54→V60
# ============================================================
def main():
    game = Ls20()
    generator = HypothesisGenerator()
    executor = ActionExecutor()
    refiner = FeedbackRefiner()
    meta = MetacognitionLayer()
    
    MAX_STEPS = 42
    actions_taken = []
    action_order = [GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION1, GameAction.ACTION2]  # LEFT, RIGHT, UP, DOWN
    
    for step in range(MAX_STEPS):
        frame = game.get_pixels(0, 0, 64, 64)
        hypothesis = generator.observe(frame, game)
        
        action = action_order[step % 4]
        feedback, frame_after, result = executor.execute(game, action)
        actions_taken.append(action.name)
        
        hypothesis = refiner.refine(hypothesis, feedback, frame_after)
        stuck, hypothesis = meta.check(feedback, hypothesis)
        
        print(f"Step {step+1}: {action.name} | changed={feedback['changed']} | diff={feedback['diff_pixels']} | state={feedback['state']} | strategy={hypothesis['strategy']}")
        
        if feedback['state'] == 'COMPLETED' or feedback['levels_completed'] > 0:
            print(f"\n🏆 LEVEL COMPLETED after {step+1} steps!")
            print(f"Actions: {' → '.join(actions_taken)}")
            
            # Tentar próximo nível
            game.set_level(game.level_index + 1)
            print(f"Next level: {game.level_index}")
            break
        
        if stuck:
            # Tenta outra direção
            action_order = [GameAction.ACTION1, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION2]
    
    print(f"\n📊 Summary:")
    print(f"  Total actions: {len(actions_taken)}")
    print(f"  Unique actions: {set(actions_taken)}")
    print(f"  Level 1 state: {feedback['state']}")
    if len(game._levels) > 0:
        print(f"  Total goals: {len(game.plrpelhym)}")

if __name__ == '__main__':
    main()
