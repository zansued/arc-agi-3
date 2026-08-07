from arc_agi import Arcade
from arcengine import GameAction
a = Arcade()
g = a.make("tn36")
fd = g.reset()
d = [x for x in dir(fd) if not x.startswith("_")]
print("FrameDataRaw attrs:", d)
print("levels_completed:", fd.levels_completed)
print("state:", fd.state)