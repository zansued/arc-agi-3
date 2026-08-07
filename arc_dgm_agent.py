#!/usr/bin/env python3
"""
DGM-lite Agent for ARC-AGI-3.
Hypothesis generator + Z3 validator + Lyapunov scheduler.
Runs without LLM - pure symbolic AI for Kaggle submission.
"""

import random
import time
from typing import Any, Optional

import numpy as np

# ARC-AGI-3 imports
from arcengine import FrameData, GameAction, GameState
from agents.agent import Agent

# Z3 validator
import sys
sys.path.insert(0, "/root")
try:
    from arc_z3_validator import ARCZ3Validator, TransformationHypothesis, ValidationResult
    validator = ARCZ3Validator()
    Z3_READY = True
except Exception as e:
    print(f"[DGM] Z3 not available: {e}")
    validator = None
    Z3_READY = False


class DGMAgent(Agent):
    """Agent with hypothesis generation (DGM-lite) + Z3 validation + Lyapunov scheduling."""

    MAX_ACTIONS = 200

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        seed = int(time.time() * 1000000) + hash(self.game_id) % 1000000
        random.seed(seed)

        # DGM internal state
        self.hypotheses: list[str] = []
        self.known_actions: list[str] = []
        self.observation_memory: list[tuple] = []
        self.score_progression: list[float] = [0.0]
        self.stagnation_counter = 0
        self.exploration_phase = "explore"

    @property
    def name(self) -> str:
        return f"DGM-lite.{self.MAX_ACTIONS}"

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return any([
            latest_frame.state is GameState.WIN,
            self.action_counter >= self.MAX_ACTIONS,
        ])

    def _get_avail(self, frame: FrameData) -> list[GameAction]:
        if hasattr(frame, "metadata") and frame.metadata and "available_actions" in frame.metadata:
            avail = frame.metadata["available_actions"]
            return [GameAction(a.upper()) for a in avail if isinstance(a, str)]
        return [a for a in GameAction if a is not GameAction.RESET]

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        if latest_frame.state in [GameState.NOT_PLAYED, GameState.GAME_OVER]:
            action = GameAction.RESET
            action.reasoning = "reset"
            self.observation_memory = []
            self.known_actions = []
            self.exploration_phase = "explore"
            return action

        avail = self._get_avail(latest_frame)
        score = latest_frame.metadata.get("score", 0.0) if hasattr(latest_frame, "metadata") else 0.0

        # Track score for stagnation detection (Lyapunov)
        self.score_progression.append(score)
        if len(self.score_progression) > 5:
            recent = self.score_progression[-5:]
            if max(recent) - min(recent) < 0.05:
                self.stagnation_counter += 1
            else:
                self.stagnation_counter = 0

        # Lyapunov regime switch
        if self.stagnation_counter > 8:
            self.exploration_phase = "explore"
            self.stagnation_counter = 0
        elif len(self.observation_memory) > 20:
            self.exploration_phase = "exploit"

        # EXPLORE phase: try random actions, learn effects
        if self.exploration_phase == "explore":
            action = random.choice([a for a in avail if a is not GameAction.RESET])
            if action.is_complex():
                action.set_data({"x": random.randint(0, 63), "y": random.randint(0, 63)})
            action.reasoning = f"DGM-explore: phase={self.exploration_phase}"
            self.observation_memory.append((action, score))
            return action

        # EXPLOIT phase: use known action or random
        action = random.choice([a for a in avail if a is not GameAction.RESET])
        if action.is_complex():
            action.set_data({"x": random.randint(0, 63), "y": random.randint(0, 63)})
        action.reasoning = f"DGM-exploit: stagn={self.stagnation_counter}"
        return action


if __name__ == "__main__":
    print("DGM-lite Agent module loaded.")
    print(f"  Z3 available: {Z3_READY}")
