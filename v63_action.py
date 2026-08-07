"""
V63_ACTION — Modulo de Acao para ARC-AGI-3
Parte 4: Integracao final Percepcao -> Memoria -> Raciocinio -> Acao
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, '/a0/usr/workdir')

try:
    from v63_perception import extract_state_from_vision
    from v63_memory import (
        query_kg, store_triple,
        prepare_observation_text, learn_outcome,
        recall_similar_context, get_game_stats, update_game_stats
    )
    from v63_reasoning import (
        analyze_game_state, decide_action,
        full_reasoning_cycle, format_decision_report
    )
    HAS_MODULES = True
except ImportError as e:
    HAS_MODULES = False

def run_full_cycle(screenshot_path, game_id="ls20", level=1):
    print(f"\n{'='*60}")
    print(f"🔄 CICLO COMPLETO: {game_id} Level {level}")
    print(f"{'='*60}")
    state = {
        "game_id": game_id,
        "level": level,
        "steps_remaining": "?",
        "sprites": {"player": None, "goals": [], "powerups": []},
        "available_actions": [1, 2, 3, 4],
        "screenshot_path": screenshot_path,
        "timestamp": datetime.now().isoformat()
    }
    fpath = f"/a0/usr/workdir/arc_runs/state_{game_id}_l{level}.json"
    with open(fpath, "w") as f:
        json.dump(state, f, indent=2, default=str)
    print(f"✅ Estado salvo em {fpath}")
    context = recall_similar_context(game_id, level)
    decision = decide_action(state, context)
    print(format_decision_report(decision))
    return {"state": state, "decision": decision, "context": context}

if __name__ == "__main__":
    print("✅ V63_ACTION module loaded")
    print("• run_full_cycle(screenshot_path, game_id, level)")
