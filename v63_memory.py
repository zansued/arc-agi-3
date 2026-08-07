"""
V63_MEMORY — Módulo de Memória para ARC-AGI-3
Parte 2 do sistema: Agente → Percebe → Memoriza → Raciocina → Age

Conecta observacoes do modulo de percepcao (v63_perception) ao:
- Graph RAG (Knowledge Graph via MCP HTTP em port 8800)
- Memoria vetorial (memory_save/memory_load tools)

Fluxo:
1. Percepcao captura GameState
2. store_experience() salva no KG + vetorial
3. recall_similar() busca experiencias similares
4. Planejamento usa KG + vetorial para decidir acoes
"""

import json
import os
import requests
from datetime import datetime

# Config
KG_SERVER = "http://localhost:8800"
MEMORY_PATH = "/a0/usr/workdir/arc_runs/"
os.makedirs(MEMORY_PATH, exist_ok=True)


# ─── Graph RAG (via MCP HTTP) ───

def query_kg(entity: str, limit: int = 10) -> list:
    """
    Busca entidade no Knowledge Graph.
    Retorna triplas relacionadas.
    """
    try:
        r = requests.post(f"{KG_SERVER}/tools/call", json={
            "method": "tools/call",
            "params": {
                "name": "search_entities",
                "arguments": {"query": entity, "limit": limit}
            }
        }, timeout=5)
        if r.status_code == 200:
            return r.json().get("result", {}).get("content", [])
        return []
    except Exception as e:
        print(f"[KG] Erro ao consultar: {e}")
        return []

def get_entity_relations(entity: str) -> list:
    """
    Retorna todas as relacoes de uma entidade no KG.
    """
    try:
        r = requests.post(f"{KG_SERVER}/tools/call", json={
            "method": "tools/call",
            "params": {
                "name": "get_entity_relations",
                "arguments": {"entity": entity, "type": "both"}
            }
        }, timeout=5)
        if r.status_code == 200:
            return r.json().get("result", {}).get("content", [])
        return []
    except Exception as e:
        print(f"[KG] Erro ao buscar relacoes: {e}")
        return []

def store_triple(subject: str, predicate: str, obj: str, metadata: dict = None):
    """
    Registra uma tripla SPO no Knowledge Graph.
    (RequER que o KG tenha endpoint para escrita)
    Salva em arquivo como fallback.
    """
    triple = {
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat()
    }

    # Fallback: salvar em arquivo para adicionar ao KG depois
    triples_file = f"{MEMORY_PATH}triples_arc.jsonl"
    with open(triples_file, "a") as f:
        f.write(json.dumps(triple) + "\n")

    return triple


# ─── Memoria Vetorial (via memory_save/memory_load) ───
# NOTA: Estas funcoes serao chamadas pelo agente principal
# usando memory_save / memory_load do Agent Zero.
# 
# O agente deve chamar:
#   memory_save(text=..., area="arc_agi")
#   memory_load(query=..., area="arc_agi")
#
# As funcoes abaixo preparam o texto para ser salvo.

def prepare_memory_text(experience: dict) -> str:
    """
    Prepara uma experiencia para salvar como memoria vetorial.
    Formato estruturado para busca semantica.
    """
    game_id = experience.get("game_id", "")
    level = experience.get("level", 1)
    action = experience.get("action", "")
    result = experience.get("result", "")
    sprites = experience.get("sprites", {})

    text = f"""
ARC EXPERIENCE: {game_id} Level {level}
Action: {action}
Result: {result}
Sprites: Player at {sprites.get('player_position')}
Goals at: {sprites.get('goal_positions')}
Power-ups at: {sprites.get('powerup_positions')}
Steps remaining context: {experience.get('steps_remaining')}
""".strip()
    return text


def prepare_observation_text(obs: dict) -> str:
    """
    Prepara uma observacao completa para memoria vetorial.
    """
    game_id = obs.get("game_id", "")
    level = obs.get("level", 1)
    sprites = obs.get("sprites", {})
    steps = obs.get("steps_remaining", "?")

    return f"""
ARC GAME STATE: {game_id} Level {level}
Steps remaining: {steps}
Player position: {sprites.get('player')}
Goals: {sprites.get('goals')}
Power-ups: {sprites.get('powerups')}
Available actions: {obs.get('available_actions')}
""".strip()


# ─── Aprendizado por Experiencia ───

def learn_outcome(game_id: str, level: int, action_key: str, 
                  result: str, new_state_hash: str = ""):
    """
    Registra o resultado de uma acao.

    Args:
        game_id: identificador do jogo
        level: nivel atual
        action_key: tecla pressionada (ArrowDown, etc.)
        result: moved, collected, won, collided, no_effect
        new_state_hash: hash do estado resultante

    Returns:
        Triple stored
    """
    subject = f"game:{game_id}:level:{level}"
    predicate = f"action:{action_key}"
    obj = f"result:{result}"

    triple = store_triple(subject, predicate, obj, {
        "game_id": game_id,
        "level": level,
        "action": action_key,
        "result": result,
        "new_state": new_state_hash,
        "timestamp": datetime.now().isoformat()
    })

    return triple


def get_game_stats(game_id: str) -> dict:
    """
    Recupera estatisticas de um jogo a partir das memorias.
    Retorna: n_actions, n_wins, last_level, actions_sequence
    """
    stats_file = f"{MEMORY_PATH}stats_{game_id}.json"
    if os.path.exists(stats_file):
        with open(stats_file) as f:
            return json.load(f)
    return {"game_id": game_id, "actions": [], "wins": 0, "levels_solved": []}


def update_game_stats(game_id: str, level: int, action_sequence: list, 
                      won: bool = False):
    """
    Atualiza as estatisticas de um jogo.
    """
    stats = get_game_stats(game_id)
    stats.setdefault("actions", []).append({
        "level": level,
        "sequence": action_sequence,
        "won": won,
        "timestamp": datetime.now().isoformat()
    })
    if won:
        stats.setdefault("levels_solved", []).append(level)
        stats["wins"] = stats.get("wins", 0) + 1

    stats_file = f"{MEMORY_PATH}stats_{game_id}.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)
    return stats


# ─── Utilitarios para o agente ───

def recall_similar_context(game_id: str, level: int) -> str:
    """
    Gera texto de contexto para o agente baseado em experiencias passadas.
    O agente usa isso para raciocinar sobre o que fazer.

    Retorna texto formatado para prompt do agente.
    """
    stats = get_game_stats(game_id)
    context_parts = []

    if stats.get("levels_solved"):
        context_parts.append(f"✅ Levels already solved in {game_id}: {stats['levels_solved']}")

    if stats.get("actions"):
        recent = stats["actions"][-3:]  # ultimas 3 experiencias
        for exp in recent:
            won = "🎉" if exp["won"] else "❌"
            context_parts.append(f"{won} Level {exp['level']}: {exp.get('sequence', [])} ({exp['timestamp'][:16]})")

    # Consultar KG para padroes
    kg_results = query_kg(f"game:{game_id}", limit=5)
    if kg_results:
        context_parts.append(f"\nPadroes no KG: {len(kg_results)} relacoes encontradas")

    return "\n".join(context_parts) if context_parts else f"No prior experience with {game_id} yet."


# ─── Acao que o agente principal deve tomar apos percepcao ───
# O agente principal (eu) deve:
#
# 1. [JA FEITO] browser.screenshot() -> caminho_imagem
# 2. [JA FEITO] vision_load(paths=[caminho_imagem]) -> analisa visualmente
# 3. Extrai observacao: game_id, level, player pos, goals, powerups, steps
# 4. Cria GameState via extract_state_from_vision()
# 5. Chama memory_save(text=prepare_observation_text(obs), area="arc_agi")
# 6. Chama store_triple() para cada relacao observada
# 7. Chama recall_similar_context() para obter contexto
# 8. Raciocina com base no contexto
# 9. Decide e executa acoes via browser keyboard
# 10. Chama learn_outcome() apos cada acao
# 11. Loop -> perceber de novo, memorizar, raciocinar, agir


print("✅ V63_MEMORY module loaded")
print(f"   KG server: {KG_SERVER}")
print(f"   Memory path: {MEMORY_PATH}")
print()
print("Funcoes disponiveis:")
print("   • query_kg(entity) — busca no Knowledge Graph")
print("   • get_entity_relations(entity) — relacoes de uma entidade")
print("   • store_triple(subj, pred, obj) — registra experiencia")
print("   • prepare_observation_text(obs) — texto para memory_save")
print("   • prepare_memory_text(exp) — texto para memoria vetorial")
print("   • learn_outcome(game, level, action, result) — aprende resultado")
print("   • recall_similar_context(game, level) — contexto de experiencias")
print("   • get_game_stats(game_id), update_game_stats(...) — estatisticas")
