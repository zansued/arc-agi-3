
import warnings
warnings.filterwarnings("ignore")
from arc_agi import Arcade
a = Arcade()
envs = a.get_environments()
for e in envs:
    print(f"{e.game_id:20s} local_dir={e.local_dir}")
