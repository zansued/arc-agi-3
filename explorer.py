#!/usr/bin/env python3
"""ARC-AGI-3 Game Explorer - testa todos os 25 jogos."""
import warnings, json, sys
warnings.filterwarnings('ignore')
from arc_agi import Arcade

a = Arcade()
envs = a.get_environments()
print(f"Total: {len(envs)} environments\n")

games = []
for e in envs:
    ba = [int(x) for x in e.baseline_actions]
    games.append({"id": e.game_id, "baseline": ba, "n_baseline": len(ba)})
    print(f"  {e.game_id:20s}  baseline_actions={len(ba):2d}  {str(ba)[:60]}")

print("\n---JSON---")
print(json.dumps(games, indent=2))
