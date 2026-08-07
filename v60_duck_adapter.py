#!/usr/bin/env python3
"""v60_duck_adapter.py - Duck Harness adapter para ARC-AGI-3."""
import copy, json, sys
from collections import deque

ACTION_NAMES = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 6: "MOUSE", 7: "ACTION7"}
ACTION_IDS = {v: k for k, v in ACTION_NAMES.items()}

class DuckAPI:
    def __init__(self, game):
        self._game = game
        self._last_result = None
        self._history = []
        try:
            self._game.step(1)
        except Exception:
            pass

    @property
    def levels_completed(self):
        if self._last_result and hasattr(self._last_result, "levels_completed"):
            return self._last_result.levels_completed
        return 0

    @property
    def current_frame(self):
        fd = getattr(self._game, "_last_response", None)
        if fd and hasattr(fd, "frame") and fd.frame is not None:
            import numpy as np
            g = np.asarray(fd.frame)
            if g.ndim == 3:
                g = g[0]
            if g.ndim == 2:
                lines = ["".join(str(int(c)) for c in row) for row in g]
                return type("Frame", (), {"ascii": "
".join(lines), "shape": g.shape})()
        return type("Frame", (), {"ascii": "N/A", "shape": (0, 0)})()

    @property
    def valid_actions(self):
        return list(ACTION_NAMES.values())

    def action(self, actions):
        if isinstance(actions, str):
            actions = [actions]
        results = []
        for act in actions:
            if isinstance(act, str):
                action_id = ACTION_IDS.get(act.upper(), 1)
                if action_id == 6:
                    result = self._game.step(6, data={"x": 32, "y": 32})
                else:
                    result = self._game.step(action_id)
            elif isinstance(act, dict):
                name = str(act.get("action", "UP")).upper()
                action_id = ACTION_IDS.get(name, 1)
                if action_id == 6:
                    row = int(act.get("row", 16))
                    col = int(act.get("col", 16))
                    result = self._game.step(6, data={"x": col, "y": row})
                else:
                    result = self._game.step(action_id)
            else:
                result = self._game.step(1)
            self._last_result = result
            self._history.append(str(act))
            lc = 0
            if result and hasattr(result, "levels_completed"):
                lc = result.levels_completed
            results.append({"executed": True, "action": str(act), "levels_completed": lc, "done": lc > 0})
        return results[-1] if results else {}

class HarnessSolver:
    def __init__(self, game, model_fn=None):
        self.game = game
        self.duck = DuckAPI(game)
        self.model_fn = model_fn

    def analyze(self, action_callback=None, step_env=None, **kwargs):
        code = kwargs.get("code", "")
        local_vars = {
            "action": self.duck.action,
            "current_frame": self.duck.current_frame,
            "valid_actions": self.duck.valid_actions,
            "levels_completed": self.duck.levels_completed,
            "step_env": step_env or self.duck.action,
        }
        try:
            if code:
                exec(code, local_vars)
        except Exception as e:
            return {"error": str(e), "executed": False}
        return {"executed": True, "levels": self.duck.levels_completed}
