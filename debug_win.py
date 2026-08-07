import sys
sys.path.insert(0, ".")
from v31_schema_world_model import solve_game
results = solve_game("tn36", max_steps=100)
print("=== DIAGNOSTIC ===")
print("levels_completed:", results.get("levels_completed", 0))
print("level_progress_events:", results.get("level_progress_events", 0))
print("model_plan_successes:", results.get("model_plan_successes", 0))
print("crashes:", results.get("crashes", 0))
print("model_plans:", results.get("model_plans", 0))
print("unique_states:", results.get("unique_states", 0))