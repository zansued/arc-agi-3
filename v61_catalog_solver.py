#!/usr/bin/env python3
"""v61_catalog_solver.py - Injeta contexto de mecanica no solver."""
import json, sys
from pathlib import Path

WORKDIR = Path("/a0/usr/workdir")
CATALOG_PATH = WORKDIR / "mechanics_catalog.json"


def load_catalog() -> dict:
    """Carrega catálogo de mecânicas."""
    if not CATALOG_PATH.exists():
        return {}
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {item["game"]: item for item in data}


def build_mechanics_context(game_id: str) -> str:
    """Retorna contexto textual da mecânica do jogo."""
    catalog = load_catalog()
    info = catalog.get(game_id, {})
    mech = info.get("inferred_mechanics", "unknown")
    conf = info.get("confidence", 0)
    return f"Game {game_id}: inferred mechanics = {mech} (confidence {conf:.1f}). Actions: {list(range(1, 8))}"


def run_with_catalog(solver, game_id: str):
    """Executa solver injetando contexto de mecânica."""
    context = build_mechanics_context(game_id)
    if hasattr(solver, "set_context"):
        solver.set_context(context)
    return context


def resolve_catalog(game_id: str) -> dict:
    """Resolve info do catálogo para um jogo."""
    catalog = load_catalog()
    return catalog.get(game_id, {})


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(build_mechanics_context(sys.argv[1]))
    else:
        print("Usage: python3 v61_catalog_solver.py <game_id>")
