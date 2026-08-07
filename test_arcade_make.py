
import warnings, logging, uuid
warnings.filterwarnings("ignore")
from arc_agi import Arcade
from arcengine import GameAction, GameState

a = Arcade()
envs = a.get_environments()
logger = logging.getLogger("test")

# Testar apenas jogos com local_dir
for e in envs:
    if e.local_dir is None:
        print(f"{e.game_id}: SKIP (no local_dir)")
        continue
    print(f"\n--- {e.game_id} ---")
    try:
        wrapper = a.make(e.game_id)
        print(f"  Wrapper: {type(wrapper).__name__}")
        obs = wrapper.reset()
        print(f"  Reset: levels={obs.levels_completed} state={obs.state}")
        print(f"  Action space: {wrapper.action_space}")

        # Testar cada acao
        for action in wrapper.action_space:
            wrapper.reset()
            try:
                obs = wrapper.step(action)
                print(f"  {action}: levels={obs.levels_completed} state={obs.state}")
            except Exception as ex:
                print(f"  {action}: ERROR - {str(ex)[:80]}")
    except Exception as ex:
        print(f"  MAKE ERROR: {str(ex)[:200]}")

print("\n\nDONE")
