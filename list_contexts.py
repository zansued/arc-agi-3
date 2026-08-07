
import sys
sys.path.append("/a0")

import initialize
from agent import AgentContext

initialize.initialize_migration()
contexts = AgentContext.all()
print("TOTAL CONTEXTS:", len(contexts))
for ctx in contexts:
    print(f" - ID: {ctx.id} | Name: {ctx.name}")
