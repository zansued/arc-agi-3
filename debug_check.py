from arc_agi import Arcade
from arcengine import GameAction
a = Arcade()
g = a.make("tn36")
fd = g.reset()
print("levels_completed:", fd.levels_completed)
print("has state():", hasattr(g, "state"))
if hasattr(g, "state"):
    s = g.state()
    print("state type:", type(s).__name__)
else:
    print("NO state() method")
print("step returns type:", type(fd).__name__)
print("step returns has levels_completed:", hasattr(fd, "levels_completed"))
# Test a step
fd2 = g.step(GameAction.ACTION1)
print("After step:", fd2.levels_completed)
