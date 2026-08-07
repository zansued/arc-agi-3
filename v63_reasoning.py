"""
V63_REASONING — Módulo de Raciocínio para ARC-AGI-3
Parte 3 do sistema: Agente que PERCEBE → MEMORIZA → RACIOCINA → AGE

Fluxo:
1. Percepcao: recebe GameState (screenshot + visao)
2. Memoria: busca experiencias similares no KG + vetorial
3. Raciocinio: combina contexto, aplica heuristicas, decide acao
4. Aprendizado: registra resultado da acao apos execucao

Estrategias de raciocinio:
- NAV: coletar power-ups amarelos primeiro, depois ir para o goal
- CLICK: explorar combinacoes de clique em ordem sistematica
- COMPLEX: analisar mudanca de estado apos cada acao
"""

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, '/a0/usr/workdir')
try:
    from v63_perception import GameState, AgentAction
    from v63_memory import (
        query_kg, get_entity_relations, store_triple,
        prepare_observation_text, learn_outcome,
        recall_similar_context, get_game_stats, update_game_stats
    )
    HAS_MODULES = True
except ImportError as e:
    print(f"[REASONING] Aviso: modulos auxiliares nao carregados: {e}")
    HAS_MODULES = False


# ─── Estrategias de Raciocinio ───

# Heuristica: acoes visando coletar power-ups primeiro
NAV_POWERUP_FIRST = True

# Heuristica: priorizar direcao do goal quando visivel
SEEK_GOAL_WHEN_VISIBLE = True

# Numero maximo de exploracoes sem progresso antes de RESET
MAX_STEPS_WITHOUT_PROGRESS = 50


def analyze_game_state(state: dict) -> dict:
    """
    Analisa o estado atual do jogo e retorna contexto estruturado.

    Args:
        state: dicionario com game_id, level, sprites, steps, etc.

    Returns:
        dict com analise: mechanic_type, priority_targets, blocked_dirs, etc.
    """
    analysis = {
        "timestamp": datetime.now().isoformat(),
        "game_id": state.get("game_id", "?"),
        "level": state.get("level", 1),
        "mechanic_type": "unknown",
        "priority_targets": [],
        "blocked_dirs": [],
        "has_powerup_nearby": False,
        "steps_remaining": state.get("steps_remaining", "?"),
        "suggestion": ""
    }

    # Detectar tipo de mecanica baseado nas acoes disponiveis
    actions = state.get("available_actions", [])
    if sorted(actions) == [1, 2, 3, 4]:
        analysis["mechanic_type"] = "NAV"  # navegacao pura
    elif 6 in actions and len(actions) <= 2:
        analysis["mechanic_type"] = "CLICK"
    elif len(actions) >= 5:
        analysis["mechanic_type"] = "COMPLEX"

    # Analisar sprites visiveis
    sprites = state.get("sprites", {})

    # Se temos posicao de power-ups, priorizar o mais proximo
    powerups = sprites.get("powerups", [])
    player_pos = sprites.get("player", None)

    if powerups and player_pos:
        # Encontrar power-up mais proximo do player
        nearest = None
        nearest_dist = float("inf")
        for pu in powerups:
            dx = pu[0] - player_pos[0]
            dy = pu[1] - player_pos[1]
            dist = abs(dx) + abs(dy)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = pu

        if nearest:
            analysis["priority_targets"].append({
                "type": "powerup",
                "position": nearest,
                "distance": nearest_dist,
                "direction": _direction_to(player_pos, nearest)
            })
            analysis["has_powerup_nearby"] = nearest_dist < 20

    # Se temos goals, adicionar como alvo
    goals = sprites.get("goals", [])
    if goals and player_pos:
        nearest_goal = None
        nearest_goal_dist = float("inf")
        for g in goals:
            dx = g[0] - player_pos[0]
            dy = g[1] - player_pos[1]
            dist = abs(dx) + abs(dy)
            if dist < nearest_goal_dist:
                nearest_goal_dist = dist
                nearest_goal = g

        if nearest_goal:
            analysis["priority_targets"].append({
                "type": "goal",
                "position": nearest_goal,
                "distance": nearest_goal_dist,
                "direction": _direction_to(player_pos, nearest_goal)
            })

    # Sugerir estrategia
    if analysis["mechanic_type"] == "NAV":
        if analysis["has_powerup_nearby"]:
            analysis["suggestion"] = f"Coletar power-up mais proximo {nearest}"
        elif goals:
            analysis["suggestion"] = f"Navegar em direcao ao goal {goals[0]}"
        else:
            analysis["suggestion"] = "Explorar para encontrar power-ups ou goal"
    elif analysis["mechanic_type"] == "CLICK":
        analysis["suggestion"] = "Explorar combinacoes de clique nos sprites visiveis"

    return analysis


def _direction_to(origin: tuple, target: tuple) -> str:
    """Determina a direcao principal de origin para target."""
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]

    if abs(dx) > abs(dy):
        return "ArrowRight" if dx > 0 else "ArrowLeft"
    else:
        return "ArrowDown" if dy > 0 else "ArrowUp"


def decide_action(state: dict, context: str = "") -> dict:
    """
    Decisao central: com base no estado e contexto, qual a proxima acao?

    Args:
        state: dict com estado do jogo (game_id, level, sprites, steps, etc.)
        context: string de contexto de experiencias passadas

    Returns:
        dict com decision: action_key, reasoning, confidence
    """
    analysis = analyze_game_state(state)

    decision = {
        "timestamp": datetime.now().isoformat(),
        "game_id": state.get("game_id", "?"),
        "level": state.get("level", 1),
        "steps_remaining": state.get("steps_remaining", "?"),
        "analysis": analysis,
        "action_key": None,
        "reasoning": [],
        "confidence": 0.0
    }

    # Raciocinio baseado em contexto de experiencias passadas
    if context and "solved" in context.lower():
        decision["reasoning"].append(f"Contexto: {len(context.split(chr(10)))} linhas de experiencias")

    # Raciocinio baseado na mecanica
    if analysis["mechanic_type"] == "NAV":
        if analysis["has_powerup_nearby"]:
            targets = [t for t in analysis["priority_targets"] if t["type"] == "powerup"]
            if targets:
                direction = targets[0]["direction"]
                decision["action_key"] = direction
                decision["reasoning"].append(f"NAV: power-up detectado -> {direction}")
                decision["confidence"] = 0.8
        elif analysis["priority_targets"]:
            # Ir em direcao ao alvo mais importante
            targets = [t for t in analysis["priority_targets"] if t["type"] == "goal"]
            if targets:
                direction = targets[0]["direction"]
                decision["action_key"] = direction
                decision["reasoning"].append(f"NAV: indo em direcao ao goal -> {direction}")
                decision["confidence"] = 0.6
        else:
            # Exploracao: tentar uma direcao
            decision["action_key"] = "ArrowRight"
            decision["reasoning"].append("NAV: explorando (sem alvo claro), tentando direita")
            decision["confidence"] = 0.3

    elif analysis["mechanic_type"] == "CLICK":
        decision["action_key"] = " "  # Espaco como acao de clique
        decision["reasoning"].append("CLICK: tentando acao de clique")
        decision["confidence"] = 0.4

    else:  # COMPLEX ou desconhecido
        # Tentar acoes disponiveis em ordem
        actions = state.get("available_actions", [1, 2, 3, 4])
        if actions:
            # Mapear acao 1-4 para setas
            ACTION_TO_KEY = {1: "ArrowDown", 2: "ArrowRight", 3: "ArrowUp", 4: "ArrowLeft"}
            action_id = actions[0]
            decision["action_key"] = ACTION_TO_KEY.get(action_id, "ArrowRight")
            decision["reasoning"].append(f"COMPLEX: tentando acao {action_id}")
            decision["confidence"] = 0.3

    return decision


def plan_sequence(state: dict, max_actions: int = 10) -> list:
    """
    Planeja uma sequencia de acoes baseada no estado atual.
    Retorna lista de action_keys para executar em sequencia.
    """
    sequence = []

    analysis = analyze_game_state(state)

    if analysis["mechanic_type"] == "NAV":
        targets = analysis.get("priority_targets", [])
        if targets:
            # Seguir direcao ate o alvo
            direction = targets[0].get("direction", "ArrowRight")
            distance = targets[0].get("distance", 10)
            # Nao fazer mais que max_actions passos
            steps = min(distance, max_actions)
            sequence = [direction] * steps
        else:
            # Exploracao: tentar padrao em espiral
            sequence = ["ArrowRight"] * 3 + ["ArrowDown"] * 3 + ["ArrowLeft"] * 3 + ["ArrowUp"] * 2

    return sequence[:max_actions]  # Limitar ao maximo


def format_decision_report(decision: dict) -> str:
    """
    Formata a decisao para display amigavel.
    """
    lines = []
    lines.append(f"🎮 {decision.get('game_id','?')} Level {decision.get('level','?')}")
    lines.append(f"   Passos restantes: {decision.get('steps_remaining','?')}")
    lines.append(f"   ⬇️  Acao decidida: {decision.get('action_key','?')}")
    lines.append(f"   🎯 Confianca: {decision.get('confidence',0):.0%}")

    reasoning = decision.get("reasoning", [])
    for r in reasoning[:3]:  # Top 3 razoes
        lines.append(f"   💡 {r}")

    analysis = decision.get("analysis", {})
    if analysis.get("suggestion"):
        lines.append(f"   🧠 Estrategia sugerida: {analysis['suggestion']}")

    return "\n".join(lines)


def full_reasoning_cycle(state: dict) -> dict:
    """
    Ciclo completo de raciocinio:
    1. Analisa estado
    2. Busca contexto no KG
    3. Busca contexto na memoria vetorial (placeHolder)
    4. Decide acao
    5. Retorna decisao

    Args:
        state: dict com game_id, level, sprites, steps, actions

    Returns:
        dict com decision e contexto usado
    """
    print(f"\n{'='*50}")
    print(f"🧠 [REASONING] Ciclo para {state.get('game_id','?')} Level {state.get('level','?')}")
    print(f"{'='*50}")

    # 1. Analisar estado
    analysis = analyze_game_state(state)
    print(f"📊 Analise: {analysis['mechanic_type']} | Power-up proximo: {analysis['has_powerup_nearby']}")

    # 2. Buscar contexto no KG
    game_id = state.get("game_id", "")
    level = state.get("level", 1)

    context = ""
    try:
        context = recall_similar_context(game_id, level)
        if context:
            print(f"📚 Contexto do KG: {len(context)} chars")
    except Exception as e:
        print(f"⚠️  Erro ao buscar contexto KG: {e}")

    # 3. Decidir
    decision = decide_action(state, context)

    # 4. Salvar decisao em arquivo
    decision_file = f"/a0/usr/workdir/arc_runs/decision_{game_id}_l{level}.json"
    with open(decision_file, "w") as f:
        json.dump(decision, f, indent=2, default=str)

    print(f"📝 Decisao salva em {decision_file}")
    print(f"\n{format_decision_report(decision)}")

    return decision


# ─── Execucao Direta ───
if __name__ == "__main__":
    print("\n✅ V63_REASONING module loaded")
    print("Funcoes disponiveis:")
    print("   • analyze_game_state(state) → analise do estado")
    print("   • decide_action(state, context) → decide proxima acao")
    print("   • plan_sequence(state, max_actions) → planeja sequencia")
    print("   • full_reasoning_cycle(state) → ciclo completo")
    print("   • format_decision_report(decision) → formato legivel")

    # Teste com estado simulado
    test_state = {
        "game_id": "ls20",
        "level": 1,
        "steps_remaining": 100,
        "sprites": {
            "player": [1, 5],
            "goals": [[60, 60]],
            "powerups": [[10, 10], [20, 5]],
        },
        "available_actions": [1, 2, 3, 4]
    }

    print("\n🔬 Teste com estado simulado:")
    decision = full_reasoning_cycle(test_state)
