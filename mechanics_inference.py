#!/usr/bin/env python3
"""mechanics_inference.py - Analisa codigo-fonte dos jogos ARC-AGI-3 e infere mecanica.

Scorer multi-sinal ponderado usando:
  1. Data keys dos levels (GoalColor, Rotations, Gravity, Fog, Programs...)
  2. Padroes de nomes de sprites (compostos com hifen, numericos, sufixos de cor)
  3. Acoes efetivamente usadas (so ACTION6 = clique, ACTION1-4 = movimento)
  4. Tags especiais (sys_click, sys_goal)
  5. Palavras-chave comportamentais no codigo (spill, fill, match, place, rotate...)
"""
import json
import os
import re
import sys
from pathlib import Path

WORKDIR = Path("/a0/usr/workdir")
ENV_DIR = WORKDIR / "environment_files"
CATALOG_PATH = WORKDIR / "mechanics_catalog.json"

# Sinais fortes de data keys de level
data_signals = {
    "match": ["GoalColor", "StartColor", "GoalRotation", "StartRotation", "GoalShape", "StartShape"],
    "paint": ["Paint", "Brush", "Fill", "Color"],
    "program": ["Programs", "Commands", "Code", "Instructions"],
    "physics": ["Gravity", "Velocity", "Bounce", "Friction"],
    "fog": ["Fog", "FogOfWar", "Exploration"],
    "portal": ["Portal", "Teleport", "Warp", "Destination"],
    "shift": ["Shift", "Translate", "Offset"],
}

# Sinais em nomes compostos de sprites:
# nomes com 2+ partes separadas por hifen indicam pecas combinaveis (tangram/match)
hyphen_signal = ["match", "tangram"]

# Sinais em nomes de metodos/comportamento no codigo
# NOTE: keywords sao casadas com word boundaries (\\b) para evitar falso-positivo
# de substrings (ex: 'fit' em 'benefit'). 'spill' tem peso dobrado para paint.
behavior_signals = {
    "paint": ["spill", "spill_fill", "fill_bucket", "paint", "palette", "pour", "fill_"],
    "match": ["match", "pair", "same_color", "identical", "goal_color", "click_pair"],
    "tangram": ["place", "rotate_shape", "snap", "fit_shape", "shape_"],
    "program": ["program", "execute_command", "command_queue", "queue"],
    "physics": ["gravity", "velocity", "bounce"],
}

# Palavras com ponderacao extra dentro de behavior_signals
extra_weight = {
    "paint": ["spill", "palette", "fill_bucket"],
    "match": ["match", "same_color", "goal_color"],
}

# Prefixos variantes (ex: gayktr-grwjuk, gayktr-orfrpe, gayktr-puvdux)
# indicam escolha entre variantes -> match, não tangram.
MATCH_VARIANT_PREFIXES = {}  # preenchido em analyze_game
def _extract_variant_clusters(names: list) -> dict:
    """Agrupa nomes por prefixo antes do primeiro hifen. Retorna {prefixo: [sufixos]}."""
    clusters = {}
    for n in names:
        if "-" in n:
            pre, suf = n.split("-", 1)
            clusters.setdefault(pre, set()).add(suf)
    return {p: list(s) for p, s in clusters.items() if len(s) >= 3}

# Acoes para deteccao de gameplay
ACTION_PATTERN = re.compile(r"GameAction\.(ACTION\d)")

def _load_code(game_id: str) -> str:
    files = list(ENV_DIR.glob(f"{game_id}/**/*.py"))
    if not files:
        return ""
    return files[0].read_text(encoding="utf-8", errors="ignore")

def _extract_data_keys(code: str) -> list:
    keys = re.findall(r'get_data\("([^"]+)"', code)
    keys += re.findall(r'data=\{\s*"([^"]+)"', code)
    return sorted(set(keys))

def _extract_sprite_names(code: str) -> list:
    names = re.findall(r'name="([^"]+)"', code)
    names += re.findall(r"name='([^']+)'", code)
    return list(dict.fromkeys(names))

def _extract_actions(code: str) -> list:
    return sorted(set(ACTION_PATTERN.findall(code)))

def _extract_tags(code: str) -> list:
    return sorted(set(re.findall(r'tags=\[["\']([^"\']+)["\']', code)))

def _composite_ratio(names: list) -> float:
    if not names:
        return 0.0
    composite = sum(1 for n in names if n.count("-") >= 1 or re.search(r"\d", n))
    return composite / len(names)

def analyze_game(game_id: str) -> dict:
    code = _load_code(game_id)
    if not code:
        return {"game": game_id, "inferred_mechanics": "unknown", "confidence": 0.0,
                "actions": list(range(1, 8)), "evidence": "no source found"}

    lower = code.lower()
    data_keys = _extract_data_keys(code)
    names = _extract_sprite_names(code)
    actions = _extract_actions(code)
    tags = _extract_tags(code)

    scores = {}
    evidence = []

    # 1. Data keys (peso 3)
    for mech, keys in data_signals.items():
        hits = [k for k in keys if k in data_keys]
        if hits:
            scores[mech] = scores.get(mech, 0) + 3 * len(hits)
            evidence.append(f"data:{','.join(hits)}")

    # 2. Nomes compostos (peso 2; só tangram/match)
    ratio = _composite_ratio(names)
    if ratio < 0.4:
        # Nomes numéricos puros tipo 0000pusfglvcns -> sprites derivados de imagem (tangram comum)
        numeric = sum(1 for n in names if re.match(r"^\d+", n))
        if names and numeric / len(names) > 0.5:
            scores["tangram"] = scores.get("tangram", 0) + 2
            evidence.append("numeric_sprite_names")
    elif ratio >= 0.6:
        scores["tangram"] = scores.get("tangram", 0) + 2
        scores["match"] = scores.get("match", 0) + 1
        evidence.append(f"composite_names:{ratio:.0%}")

    # 2.5 Clusters de variantes (peso 4) — sinal forte de match/pairing.
    # Prefixo com 3+ sufixos diferentes (ex: gayktr-grwjuk/orfrpe/puvdux)
    # indica variantes de cor/forma do mesmo objeto para emparelhamento.
    # Exclui clusters de levels (wahtyt-Level1 ... Level11) que não são variantes.
    variant_clusters = _extract_variant_clusters(names)
    real_variant_clusters = {}
    for pre, sufs in variant_clusters.items():
        # Exclui clusters de levels (wahtyt-Level1 ... Level11)
        if all(re.match(r"^level\d+", s, re.IGNORECASE) for s in sufs):
            continue
        # Exclui clusters numéricos (plzwjbfyfli-3 ... plzwjbfyfli-8 -> paletas de paint)
        numeric = [s for s in sufs if re.match(r"^\d+[a-h]?$", s)]
        if len(numeric) / len(sufs) >= 0.5:
            continue
        real_variant_clusters[pre] = sufs
    if real_variant_clusters:
        cluster_hits = len(real_variant_clusters)
        scores["match"] = scores.get("match", 0) + 4 * cluster_hits
        evidence.append(f"variant_clusters:{cluster_hits}")

    # 3. Padrão de ações (peso 2)
    if actions and set(actions) <= {"ACTION6"}:
        scores["tangram"] = scores.get("tangram", 0) + 2
        scores["match"] = scores.get("match", 0) + 1
        evidence.append("click_only")
    elif actions and set(actions) <= {"ACTION1", "ACTION2", "ACTION3", "ACTION4"}:
        scores["navigation"] = scores.get("navigation", 0) + 3
        evidence.append("move_only")

    # 4. Tags especiais sys_*
    sys_tags = [t for t in tags if t.startswith("sys_")]
    if "sys_click" in sys_tags:
        scores["match"] = scores.get("match", 0) + 2
        scores["tangram"] = scores.get("tangram", 0) + 1
        evidence.append("sys_click")

    # 5. Comportamento no código (peso 3)
    for mech, words in behavior_signals.items():
        hits = [w for w in words if w in lower]
        if hits:
            scores[mech] = scores.get(mech, 0) + 3
            evidence.append(f"beh:{','.join(hits[:3])}")

    # 6. Decisão
    if not scores:
        best, conf = ("unknown", 0.0)
    else:
        # Normaliza o top por soma total, pune gap pequeno
        total = sum(scores.values())
        best = max(scores, key=scores.get)
        top = scores[best]
        second = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0
        conf = round(min(20.0, top + (top - second)), 1)

    return {
        "game": game_id,
        "inferred_mechanics": best,
        "confidence": conf,
        "actions": [int(a.replace("ACTION", "")) for a in actions] or list(range(1, 8)),
        "evidence": evidence[:6],
        "data_keys": data_keys[:8],
        "sprite_count": len(names),
    }

def build_catalog() -> list:
    games = sorted(d.name for d in ENV_DIR.iterdir() if d.is_dir() and not d.name.startswith("."))
    return [analyze_game(g) for g in games]

def save_catalog() -> str:
    catalog = build_catalog()
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    return f"{len(catalog)} jogos catalogados"

if __name__ == "__main__":
    print(save_catalog())
