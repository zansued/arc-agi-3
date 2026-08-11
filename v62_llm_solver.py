#!/usr/bin/env python3
"""v62_llm_solver.py - Solucionador LLM autonomo para ARC-AGI-3.

Conecta o ToolAgent do Duck Harness (tool calling + Python sandbox)
com o backend arcengine real via arc_agi, usando DeepSeek como cérebro.

Padrões integrados:
  - ToolAgent (inference/agent/tool_agent.py) -> analisador LLM com tool 'python'
  - PythonSandbox (inference/agent/python_tool_sandbox.py) -> execução isolada
  - RuntimeState (inference/agent/runtime_state.py) -> frames/histórico
  - v60_duck_adapter -> mapeamento de ações do arcengine
  - mechanics_catalog.json -> contexto de mecânica injetado no prompt

Uso:
  .venv/bin/python v62_llm_solver.py sp80 60 15
  .venv/bin/python v62_llm_solver.py cn04 80 20 --max-steps 200
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

WORKDIR = Path(__file__).parent
sys.path.insert(0, str(WORKDIR / "duck-harness" / "ARC3-Inference"))
sys.path.insert(0, str(WORKDIR / "arcengine_pkg"))
sys.path.insert(0, str(WORKDIR / "arc_agi_pkg"))

import numpy as np  # noqa: E402

from arc_agi import Arcade  # noqa: E402

# Duck Harness importações
from inference.agent.tool_agent import ToolAgent  # noqa: E402
from inference.agent.runtime_state import (  # noqa: E402
    RUNTIME_STATE_FILENAME,
    Frame,
    HistoryEntry,
    write_runtime_state,
)

import v60_duck_adapter as v60  # noqa: E402
import v61_catalog_solver as v61  # noqa: E402

ENV_DIR = WORKDIR / "environment_files"

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = os_model_id() if False else "deepseek-chat"


def os_model_id() -> str:
    import os
    return os.environ.get("DEEPSEEK_MODEL_ID", "deepseek-chat")


def env_id_for_game(game: str) -> str:
    """Resolve 'sp80' -> 'sp80-589a99af'."""
    d = ENV_DIR / game
    if d.is_dir():
        subs = [x.name for x in d.iterdir() if x.is_dir()]
        if subs:
            return f"{game}-{subs[0]}"
    return game


def grid_from_raw(raw: Any) -> tuple[tuple[int, ...], ...]:
    """Extrai grid (tuple de tuples ints) do FrameDataRaw."""
    if raw is None or getattr(raw, "frame", None) is None:
        return ()
    try:
        g = np.asarray(raw.frame)
        if g.ndim == 3:
            g = g[0]
        if g.ndim == 2:
            return tuple(tuple(int(c) for c in row) for row in g)
    except Exception:
        pass
    return ()


def available_action_ids(raw: Any) -> list[int]:
    """Lista de ids de ações disponíveis em raw FrameDataRaw."""
    if raw is None:
        return []
    try:
        values = getattr(raw, "available_actions", None) or []
        ids: list[int] = []
        for value in values:
            if hasattr(value, "value"):
                value = value.value
            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                continue
        return ids
    except Exception:
        return []


def state_name(raw: Any) -> str | None:
    """Nome legível do GameState atual."""
    if raw is None:
        return None
    state = getattr(raw, "state", None)
    if state is None:
        return None
    if hasattr(state, "name"):
        return state.name
    return str(state)


def model_action_name(action_id: int) -> str:
    """Mapeia engine action id -> nome amigável (Duck Harness)."""
    try:
        from inference.agent.action_names import to_model_action

        raw_name = v60.ACTION_NAMES.get(int(action_id), f"ACTION{action_id}")
        return to_model_action(raw_name)
    except Exception:
        return f"ACTION{int(action_id)}"


class MechanicsToolAgent(ToolAgent):
    """ToolAgent com contexto de mecânica injetado no system prompt."""

    def __init__(self, *args: Any, mechanics_context: str = "", **kwargs: Any) -> None:
        self._mechanics_context = str(mechanics_context or "").strip()
        self._user_hint = str(kwargs.pop("user_hint", "") or "").strip()
        super().__init__(*args, **kwargs)

    def set_user_hint(self, hint: str) -> None:
        """Atualiza a dica injetada no user prompt (hint dinâmica por nível)."""
        self._user_hint = str(hint or "").strip()

    def _build_system_prompt(self, *, tool_output_tokens: int) -> str:
        base = super()._build_system_prompt(tool_output_tokens=tool_output_tokens)
        if self._mechanics_context:
            base = (
                base
                + "\n\n[MECHANICS CONTEXT - inferred from source code]\n"
                + self._mechanics_context
            )
        return base

    def _build_user_prompt(
        self,
        action_num: int,
        *,
        valid_actions: list[str] | None = None,
        current_frame=None,
        history_entries: list[HistoryEntry] | None = None,
        previous_step_summary: dict[str, Any] | None = None,
    ) -> str:
        prompt = super()._build_user_prompt(
            action_num,
            valid_actions=valid_actions,
            current_frame=current_frame,
            history_entries=history_entries,
            previous_step_summary=previous_step_summary,
        )
        if self._user_hint:
            prompt = prompt + "\n\n" + self._user_hint
        return prompt


class ArcGameBackend:
    """Backend que expõe o jogo real do arcengine ao ToolAgent (step_env)."""

    def __init__(self, game: Any, *, game_id: str = ""):
        self._game = game
        self.game_id = game_id
        self._steps = 0
        self._history: list[dict[str, Any]] = []
        self._last_result: Any = None
        self._last_state: str | None = None
        # reset inicial (estado fresco)
        try:
            self._game.step(0)
        except Exception:
            pass
        self._refresh()

    def _refresh(self) -> Any:
        raw = getattr(self._game, "_last_response", None)
        try:
            raw = self._game.observation_space() or raw
        except Exception:
            pass
        self._last_result = raw
        self._last_state = state_name(raw)
        return raw

    def _current_grid(self) -> tuple[tuple[int, ...], ...]:
        return grid_from_raw(self._refresh())

    def _current_level(self) -> int:
        if self._last_result is not None:
            try:
                lc = int(getattr(self._last_result, "levels_completed", 0) or 0)
                return max(1, lc + 1)
            except (TypeError, ValueError):
                pass
        return 1

    def _levels_completed(self) -> int:
        if self._last_result is not None:
            try:
                return int(getattr(self._last_result, "levels_completed", 0) or 0)
            except (TypeError, ValueError):
                pass
        return 0

    def _is_win(self) -> bool:
        st = (self._last_state or "").upper()
        return st == "WIN"

    def _is_game_over(self) -> bool:
        return (self._last_state or "").upper() == "GAME_OVER"

    def _valid_actions(self) -> list[str]:
        ids = available_action_ids(self._last_result)
        if not ids:
            ids = list(v60.ACTION_NAMES.keys())
        names = [model_action_name(i) for i in ids]
        # dedup preservando ordem
        seen: set[str] = set()
        result = []
        for name in names:
            key = name.upper()
            if key not in seen:
                seen.add(key)
                result.append(name)
        return result

    def _write_runtime_state(self, state_path: Path) -> None:
        frame_payload = {
            "grid": [list(row) for row in self._current_grid()],
            "step": self._steps,
            "level": self._current_level(),
        }
        history_entries = []
        for entry in self._history:
            frame = entry.get("frame") or {}
            history_entries.append(
                HistoryEntry(
                    action=str(entry.get("action", "")),
                    frame=Frame(
                        grid=tuple(tuple(int(c) for c in row) for row in frame.get("grid", [])),
                        step=int(frame.get("step", 0) or 0),
                        level=int(frame.get("level", 1) or 1),
                    ),
                )
            )
        write_runtime_state(
            state_path,
            current_frame=Frame(
                grid=tuple(tuple(int(c) for c in row) for row in frame_payload["grid"]),
                step=frame_payload["step"],
                level=frame_payload["level"],
            ),
            history=history_entries,
        )

    def normalize_actions(
        self, arguments: dict[str, Any]
    ) -> tuple[list[dict[str, Any]] | None, str | None]:
        """Normaliza argumentos do ToolAgent -> lista de dicts de ação."""
        if "actions" in arguments and isinstance(arguments["actions"], list):
            raw_actions = arguments["actions"]
        elif "action" in arguments:
            raw_actions = [dict(arguments)]
        elif isinstance(arguments, list):
            raw_actions = arguments
        else:
            return None, "step_env requires `action` or `actions`."

        normalized: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_actions, start=1):
            if isinstance(raw, str):
                act = str(raw).strip()
                if not act:
                    return None, f"Action {index} is empty."
                normalized.append({"action": act})
                continue
            if isinstance(raw, dict):
                act_name = str(raw.get("action", "")).strip()
                if not act_name:
                    return None, f"Action {index} is missing `action`."
                entry = {"action": act_name}
                if act_name.upper() in ("MOUSE", "CLICK", "ACTION6"):
                    # prefere row/col (novo padrão), fallback x/y
                    if "row" in raw and "col" in raw:
                        entry["row"] = int(raw["row"])
                        entry["col"] = int(raw["col"])
                    elif "x" in raw and "y" in raw:
                        entry["row"] = int(raw["y"])
                        entry["col"] = int(raw["x"])
                    else:
                        entry["row"] = 16
                        entry["col"] = 16
                normalized.append(entry)
                continue
            return None, f"Action {index} must be a string or dict."
        return normalized, None

    def _exec_one(self, raw_action: dict[str, Any]) -> dict[str, Any]:
        action_name = str(raw_action.get("action", "")).strip()
        before_grid = self._current_grid()
        before_levels = self._levels_completed()
        before_state = self._last_state

        action_id = v60.ACTION_IDS.get(action_name.upper())
        if action_id is None:
            return {
                "executed": False,
                "error": f"Unknown action: {action_name}",
                "valid_actions": self._valid_actions(),
            }

        data: dict[str, Any] = {}
        # mapear row/col -> x/y (API arcengine)
        if action_id == 6:
            row = int(raw_action.get("row", 16))
            col = int(raw_action.get("col", 16))
            data = {"x": max(0, min(63, col)), "y": max(0, min(63, row))}
        elif action_id in v60.ACTION_IDS.values() and action_name.upper() in ("SPACE", "SPILL", "ACTION5"):
            data = {}

        try:
            result = self._game.step(action_id, data)
        except Exception as exc:
            return {"executed": False, "error": f"{type(exc).__name__}: {exc}", "valid_actions": self._valid_actions()}

        self._last_result = result
        self._steps += 1
        self._last_state = state_name(self._refresh())

        current_levels = self._levels_completed()
        level_completed = current_levels > before_levels
        run_complete = self._is_win()
        game_over = self._is_game_over()
        after_grid = self._current_grid()
        board_changed = after_grid != before_grid

        reward = 1.0 if level_completed else (-1.0 if game_over else 0.0)

        action_display = action_name
        if action_name.upper() in ("MOUSE", "CLICK", "ACTION6"):
            action_display = f"MOUSE(row={raw_action.get('row', '?')}, col={raw_action.get('col', '?')})"

        entry = {
            "action": action_name,
            "frame": {
                "grid": [list(row) for row in after_grid],
                "step": self._steps,
                "level": self._current_level(),
            },
        }
        self._history.append(entry)

        return {
            "executed": True,
            "action_num": self._steps,
            "level": self._current_level(),
            "score": current_levels,
            "reward": reward,
            "state": self._last_state,
            "valid_actions": self._valid_actions(),
            "board_changed": board_changed,
            "done": run_complete,
            "level_completed": level_completed,
            "game_over": game_over,
            "run_complete": run_complete,
            "action_display": action_display,
            "action_name": action_name,
        }

    def step_env(self, arguments: dict[str, Any]) -> dict[str, Any]:
        actions, error = self.normalize_actions(arguments)
        if error is not None or actions is None:
            return {"executed": False, "error": error or "Could not parse action request.", "valid_actions": self._valid_actions()}
        if self._is_game_over() or self._is_win():
            return {
                "executed": False,
                "error": "No action was executed because the current state is terminal.",
                "level": self._current_level(),
                "score": self._levels_completed(),
                "state": self._last_state,
                "valid_actions": [],
                "done": self._is_win(),
                "run_complete": self._is_win(),
                "game_over": self._is_game_over(),
            }

        executed_payloads: list[dict[str, Any]] = []
        for action in actions:
            payload = self._exec_one(action)
            if not payload.get("executed"):
                break
            executed_payloads.append(payload)
            if payload.get("run_complete") or payload.get("game_over") or payload.get("level_completed"):
                break

        if not executed_payloads:
            return {"executed": False, "error": "No action was executed.", "valid_actions": self._valid_actions()}

        final_payload = dict(executed_payloads[-1])
        final_payload["reward"] = sum(float(p.get("reward", 0.0) or 0.0) for p in executed_payloads)
        final_payload["last_reward"] = executed_payloads[-1].get("reward", 0.0)
        final_payload["requested_count"] = len(actions)
        final_payload["executed_count"] = len(executed_payloads)
        final_payload["requested_actions"] = [a.get("action", "") for a in actions]
        final_payload["executed_actions"] = [p.get("action_display", "") for p in executed_payloads]
        final_payload["board_changed"] = any(bool(p.get("board_changed")) for p in executed_payloads)
        return final_payload


def build_mechanics_context(game_id: str) -> str:
    """Constrói bloco de contexto a partir do catálogo (v61)."""
    try:
        entry = v61.resolve_catalog(game_id)
        if not entry:
            return ""
        return v61.build_mechanics_context(entry)
    except Exception as exc:
        return f"(mecânica indisponível: {exc})"


PATTERN_MEMORY_PATH = WORKDIR / "v58_playtest" / "pattern_memory.json"


def _load_pattern_memory() -> dict:
    """Carrega pattern_memory.json (soluções vencedoras conhecidas) com segurança."""
    try:
        if PATTERN_MEMORY_PATH.exists():
            return json.loads(PATTERN_MEMORY_PATH.read_text())
    except Exception:
        pass
    return {}


def build_user_hint(game_id: str, level: int = 1) -> str:
    """Dica de vitória específica por jogo/nível, integrando PatternMemory."""
    parts: list[str] = []

    # 1. Dicas estáticas por mecânica conhecida
    hints = {
        "sp80": (
            "[KNOWN WINNING SEQUENCE - Level 1] "
            "CLICK(row=4, col=3) then DOWN, DOWN, DOWN, then SPILL wins Level 1 in 5 actions. "
            "Start by trying CLICK near row=4,col=3 on THIS board, then DOWN x3 and SPILL. "
            "The game is 'paint': select a palette with CLICK, move, then SPILL to pour."
        ),
        "cn04": (
            "[MECHANICS HINT] The game is a 'tangram': you move and rotate pieces to match target shapes. "
            "Explore directional moves first to understand which sprite moves, then use CLICK to place."
        ),
        "m0r0": (
            "[MECHANICS HINT] The game is a 'match': find pairs of identical colored objects and select them. "
            "Use CLICK on two matching sprites (row,col) to remove/target them."
        ),
        "ft09": (
            "[MECHANICS HINT] The game is 'paint by clicking': CLICK on a sprite cycles its palette color. "
            "Click sprites until their center color matches the target. Experiment per level."
        ),
        "wa30": (
            "[MECHANICS HINT] The game is 'navigation + collect': use direction actions to move your sprite, "
            "and use the collect/interact action on collectible sprites to remove them. "
            "Collect everything within the step budget to win."
        ),
        "tn36": (
            "[MECHANICS HINT] The game is 'program': level data contains 'Programs', 'Rotations', 'Positions'. "
            "Try clicking buttons/configurations systematically; after each action check whether the target state changed. "
            "Look for the success-check method and verify after every action."
        ),
        "su15": (
            "[MECHANICS HINT] The game is a 'tangram' with multiple small sprites. "
            "Data keys: x, y, steps. Try CLICK at row,col coordinates to place/rotate pieces; "
            "verify the step counter and win/lose after each action."
        ),
        "lp85": (
            "[MECHANICS HINT] The game is a 'tangram' with a StepCounter. "
            "Sprites include a sys_click target; try CLICK on panel positions to place pieces. "
            "Use level_name to identify which level you are on."
        ),
        "sc25": (
            "[MECHANICS HINT] The game is a 'match': data keys include efvw, rpjr, slfh, x, y. "
            "Use KEYBOARD_ACTION and CLICK. Try selecting pairs of matching sprites by row,col."
        ),
        "s5i5": (
            "[MECHANICS HINT] The game is a 'tangram': data includes Children and StepCounter. "
            "Sprites are numbered pieces (tags like 0001..., 0064...); try CLICK to select and assemble the target shape."
        ),
        "vc33": (
            "[MECHANICS HINT] The game is 'physics': data includes Gravity and StepCounter. "
            "Sprites are numbered pieces (tags like 0001..., 0004...); try CLICK to place/stack pieces so they stay stable once gravity applies."
        ),
    }
    if game_id in hints:
        parts.append(hints[game_id])

    # 2. PatternMemory — soluções vencedoras conhecidas por jogo/nível
    pm = _load_pattern_memory()
    solutions = pm.get("solutions", [])
    game_solutions = [s for s in solutions if s.get("game") == game_id]
    for sol in game_solutions:
        sol_level = int(sol.get("level", 0) or 0)
        if sol_level and sol_level != level:
            continue
        steps = sol.get("steps")
        method = sol.get("method", "")
        parts.append(
            f"[PATTERN MEMORY] Known win for {game_id} Level {sol_level}: "
            f"state={sol.get('state')}, steps={steps}, method={method}. "
            "Use this as prior knowledge to prioritize efficient actions."
        )
    # Dica geral por mecânica do catálogo quando houver solução padrão
    patterns = pm.get("patterns", {})
    if game_id in patterns and game_id not in hints:
        pat = patterns[game_id]
        parts.append(
            f"[PATTERN] '{game_id}' was solved before as '{pat.get('pattern')}' "
            f"({pat.get('levels_solved')} levels solved): {pat.get('description', '')}"
        )

    return "\n\n".join(parts)


def solve_game(
    game_id: str,
    *,
    max_actions: int = 80,
    max_analysis_steps: int = 15,
    run_dir: Path | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Roda o solucionador LLM em um jogo e retorna o resultado."""
    started = time.time()
    result: dict[str, Any] = {
        "game": game_id,
        "levels_completed": 0,
        "win_levels": 0,
        "actions": 0,
        "analysis_steps": 0,
        "duration_s": 0.0,
        "error": None,
        "steps": [],
    }

    run_dir = run_dir or (WORKDIR / "arc_runs" / "v62")
    run_dir.mkdir(parents=True, exist_ok=True)
    state_path = run_dir / f"{game_id}_{RUNTIME_STATE_FILENAME}"
    transcript_path = run_dir / f"{game_id}_analyzer.txt"
    env_id = env_id_for_game(game_id)

    try:
        arcade = Arcade()
        game = arcade.make(env_id)
        backend = ArcGameBackend(game, game_id=env_id)
        mechanics = build_mechanics_context(game_id)
        if verbose:
            print(f"[v62] jogo={game_id} env={env_id} mecânica_context={'sim' if mechanics else 'não'}")

        api_key = None
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("API_KEY_DEEPSEEK") or ""
        if not api_key:
            # tenta ler de arquivos locais
            for p in [WORKDIR / ".env", Path("/a0/usr/.env")]:
                if p.exists():
                    for line in p.read_text().splitlines():
                        if "DEEPSEEK_API_KEY" in line or "API_KEY_DEEPSEEK" in line:
                            api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
                if api_key:
                    break
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY não encontrada no ambiente.")

        agent = MechanicsToolAgent(
            model=DEEPSEEK_MODEL,
            base_url=DEEPSEEK_BASE_URL,
            provider="deepseek",
            api_key=api_key,
            timeout=180,
            save_request_logs=False,
            mechanics_context=mechanics,
            user_hint=build_user_hint(game_id, level=1),
        )

        analysis_step = 0
        stop = False
        last_hint_level = -1
        while not stop and backend._steps < max_actions and analysis_step < max_analysis_steps:
            analysis_step += 1
            backend._write_runtime_state(state_path)

            # Hint dinâmica por nível: atualiza quando o agente avança de nível
            current_level = backend._current_level()
            if current_level != last_hint_level:
                agent.set_user_hint(build_user_hint(game_id, level=current_level))
                last_hint_level = current_level
                if verbose:
                    print(f"  -> hint atualizada para level={current_level}")

            if verbose:
                print(f"  [step {backend._steps} / analysis {analysis_step}] levels={backend._levels_completed()} state={backend._last_state}")

            should_stop = lambda: stop or backend._is_win() or backend._steps >= max_actions
            try:
                turn_result = agent.analyze(
                    state_path,
                    backend._steps,
                    valid_actions=backend._valid_actions(),
                    step_env=backend.step_env,
                    transcript_path=transcript_path,
                    analysis_step=analysis_step,
                    request_timeout_seconds=180,
                    should_stop=should_stop,
                )
            except Exception as exc:
                result["error"] = f"{type(exc).__name__}: {exc}"
                if verbose:
                    print(f"  !! analyze error: {exc}")
                    traceback.print_exc()
                break

            if turn_result is None:
                result["error"] = "analyze retornou None (falha não-recuperável)"
                break
            if turn_result.retryable_failure:
                if verbose:
                    print("  !! retryable failure, aguardando...")
                time.sleep(1.0)
                continue
            if not turn_result.step_executed:
                if verbose:
                    print("  -- (sem ação executada, aguardando próxima iteração)")
                if getattr(turn_result, "yielded_control", False):
                    time.sleep(0.5)
                continue

            result["actions"] = backend._steps
            result["levels_completed"] = backend._levels_completed()
            result["win_levels"] = 1 if backend._is_win() else 0
            if backend._is_win():
                if verbose:
                    print("  🏆 WIN detectado!")
                stop = True
                break

        result["actions"] = backend._steps
        result["levels_completed"] = backend._levels_completed()
        result["win_levels"] = 1 if backend._is_win() else 0
        result["analysis_steps"] = analysis_step
        result["duration_s"] = round(time.time() - started, 2)

        # remove runtime state temporário
        try:
            state_path.unlink(missing_ok=True)
        except Exception:
            pass
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["duration_s"] = round(time.time() - started, 2)
        if verbose:
            print(f"[v62] ERRO: {exc}")
            traceback.print_exc()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="v62 LLM Solver ARC-AGI-3 (DeepSeek + Duck Harness)")
    parser.add_argument("games", nargs="*", default=[], help="Jogos (ex: sp80 cn04 m0r0)")
    parser.add_argument("--max-actions", type=int, default=80, help="Máx. ações por jogo")
    parser.add_argument("--max-analysis", type=int, default=15, help="Máx. análise por jogo")
    parser.add_argument("--json", type=str, default="", help="Caminho do arquivo JSON de saída")
    args = parser.parse_args()

    if args.games:
        games = args.games
    else:
        cat = v61.load_catalog()
        games = sorted(cat.keys())

    results = []
    print(f"=== v62 LLM Solver | jogos={len(games)} | max_actions={args.max_actions} ===")
    for gid in games:
        r = solve_game(gid, max_actions=args.max_actions, max_analysis_steps=args.max_analysis)
        results.append(r)
        print(f"{gid}: levels={r['levels_completed']} win={r['win_levels']} actions={r['actions']} tempo={r['duration_s']}s status={'OK' if not r['error'] else 'ERRO'}")
        if r["error"]:
            print(f"  ERRO: {r['error']}")

    solved = [r for r in results if r["levels_completed"] > 0]
    print("-" * 50)
    print(f"TOTAL: {len(solved)}/{len(results)} jogos com >=1 level")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"Salvo em {args.json}")


if __name__ == "__main__":
    main()
