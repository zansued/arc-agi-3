#!/usr/bin/env python3
"""v60_duck_adapter.py - Duck Harness adapter para ARC-AGI-3.

Usa a API real do LocalEnvironmentWrapper do arc_agi:
    result = game.step(action_id, data=data)
(nao usar perform_action(ActionInput): isso e API interna do arcengine BaseGame).

Mapeamento sp80 validado: ACTION1=LEFT, ACTION2=RIGHT, ACTION3=UP,
ACTION4=DOWN, ACTION5=SPILL, ACTION6=CLICK (com data x/y).
Sequencia vencedora sp80 L1: CLICK(3,4) + DOWN*3 + SPILL => levels_completed=1.
"""
import json
from typing import Union

from arcengine import GameAction

# Mapeamento real do sp80 (validado empiricamente).
ACTION_NAMES = {
    1: "LEFT",
    2: "RIGHT",
    3: "UP",
    4: "DOWN",
    5: "SPILL",
    6: "CLICK",
    7: "ACTION7",
}
ACTION_IDS = {
    "LEFT": 1,
    "RIGHT": 2,
    "UP": 3,
    "DOWN": 4,
    "SPILL": 5,
    "SPACE": 5,
    "ACTION5": 5,
    "CLICK": 6,
    "MOUSE": 6,
    "ACTION6": 6,
    "ACTION7": 7,
}


def _resolve_action(act: Union[str, dict]) -> tuple:
    """Converte acao (str ou dict) em (action_id:int, data:dict)."""
    if isinstance(act, str):
        key = act.strip().upper()
        action_id = ACTION_IDS.get(key, 1)
        if action_id == 6:
            return action_id, {"x": 32, "y": 32}
        return action_id, {}
    if isinstance(act, dict):
        key = str(act.get("action", "LEFT")).strip().upper()
        action_id = ACTION_IDS.get(key, 1)
        if action_id == 6:
            if "x" in act and "y" in act:
                return action_id, {"x": int(act["x"]), "y": int(act["y"])}
            return action_id, {"x": int(act.get("col", 16)), "y": int(act.get("row", 16))}
        return action_id, {}
    return 1, {}


class DuckAPI:
    def __init__(self, game):
        self._game = game
        self._last_result = None
        self._history = []
        # Reset para estado inicial (seguro em ambiente novo).
        try:
            self._game.step(0)
        except Exception:
            pass

    @property
    def levels_completed(self):
        if self._last_result is not None:
            lc = getattr(self._last_result, "levels_completed", 0) or 0
            return lc
        return 0

    @property
    def win_levels(self):
        if self._last_result is not None:
            return getattr(self._last_result, "win_levels", 0) or 0
        return 0

    @property
    def current_frame(self):
        """Retorna frame atual como ASCII + shape, quando disponivel."""
        try:
            fd = getattr(self._game, "_last_response", None)
            if fd is not None and getattr(fd, "frame", None) is not None:
                import numpy as np
                g = np.asarray(fd.frame)
                if g.ndim == 3:
                    g = g[0]
                if g.ndim == 2:
                    lines = ["".join(str(int(c)) for c in row) for row in g]
                    return type("Frame", (), {"ascii": "\n".join(lines), "shape": g.shape})()
        except Exception:
            pass
        return type("Frame", (), {"ascii": "N/A", "shape": (0, 0)})()

    @property
    def valid_actions(self):
        return list(ACTION_NAMES.values())

    def action(self, actions):
        """Executa uma ou mais acoes reais via game.step(action_id, data)."""
        if isinstance(actions, (str, dict)):
            actions = [actions]
        results = []
        for act in actions:
            action_id, data = _resolve_action(act)
            try:
                result = self._game.step(action_id, data)
            except Exception as e:
                results.append({"executed": False, "action": str(act), "error": str(e)})
                continue
            self._last_result = result
            self._history.append(str(act))
            lc = getattr(result, "levels_completed", 0) or 0
            ws = getattr(result, "win_levels", 0) or 0
            st = getattr(result, "state", None)
            results.append({
                "executed": True,
                "action": str(act),
                "action_id": action_id,
                "data": data,
                "levels_completed": lc,
                "win_levels": ws,
                "state": st.name if st is not None else None,
                "done": lc > 0 or ws > 0,
            })
        return results[-1] if results else {}


class HarnessSolver:
    def __init__(self, game, model_fn=None):
        self.game = game
        self.duck = DuckAPI(game)
        self.model_fn = model_fn
        self.context = ""

    def analyze(self, code=None, **kwargs):
        """Executa codigo Python com DuckAPI exposta para acoes e observacao."""
        local_vars = {
            "action": self.duck.action,
            "current_frame": self.duck.current_frame,
            "valid_actions": self.duck.valid_actions,
            "levels_completed": self.duck.levels_completed,
            "win_levels": self.duck.win_levels,
        }
        if not code:
            return {"executed": True, "levels": self.duck.levels_completed}
        try:
            exec(code, local_vars)
        except Exception as e:
            return {"error": str(e), "executed": False}
        return {"executed": True, "levels": self.duck.levels_completed, "win_levels": self.duck.win_levels}

    def set_context(self, context: str):
        self.context = context
