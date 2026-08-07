from arc_agi import Arcade
from arcengine import GameAction
import random
a = Arcade()
g = a.make("tn36")
fd = g.reset()
print("Initial levels:", fd.levels_completed)
actions = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION5]
for i in range(500):
    act = random.choice(actions)
    fd = g.step(act)
    if fd.levels_completed > 0:
        print("Level advanced at step {}! levels={}".format(i, fd.levels_completed))
        break
else:
    print("No level advanced after 500 random steps")
    print("Final levels:", fd.levels_completed)