import copy
import json
import pickle
from datetime import datetime, timezone

from arc_agi import Arcade


def probe(obj, label):
    out = {"label": label}
    try:
        copy.deepcopy(obj)
        out["deepcopy"] = "ok"
    except Exception as exc:
        out["deepcopy"] = f"{type(exc).__name__}: {exc}"
    try:
        pickle.dumps(obj)
        out["pickle"] = "ok"
    except Exception as exc:
        out["pickle"] = f"{type(exc).__name__}: {exc}"
    return out


game = Arcade().make("sp80")
try:
    game.reset()
except Exception:
    pass
raw = getattr(game, "observation_space", None)
items = [
    probe(game, "game"),
    probe(raw, "observation_space"),
]
for name in sorted(dir(game)):
    if name.startswith("_") and name not in {"_state", "_game", "_env"}:
        continue
    if name in {"state", "game", "env", "_state", "_game", "_env"}:
        try:
            items.append(probe(getattr(game, name), f"game.{name}"))
        except Exception as exc:
            items.append({"label": f"game.{name}", "getattr": f"{type(exc).__name__}: {exc}"})

report = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "game": "sp80",
    "probes": items,
}
print(json.dumps(report, indent=2, ensure_ascii=False))
