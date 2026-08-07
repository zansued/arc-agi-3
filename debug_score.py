from arc_agi import Arcade
from arcengine import GameAction
import random
a = Arcade()
g = a.make("tn36")
fd = g.reset()
print("Initial levels: {} score: {} state: {}".format(fd.levels_completed, fd.score, fd.state))
actions = [GameAction.ACTION1, GameAction.ACTION2, GameAction.ACTION3, GameAction.ACTION4, GameAction.ACTION5]
max_score = fd.score
for i in range(200):
    act = random.choice(actions)
    fd = g.step(act)
    if fd.score > max_score:
        max_score = fd.score
        print("Step {}: levels={} score={} state={}".format(i, fd.levels_completed, fd.score, fd.state))
    if fd.levels_completed > 0:
        print("LEVEL UP at step {}!".format(i))
        break
print("Final: levels={} score={}".format(fd.levels_completed, fd.score))