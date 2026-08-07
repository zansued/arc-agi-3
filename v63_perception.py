"""
V63_PERCEPTION — Módulo de Percepção Visual para ARC-AGI-3
Parte 1 do sistema: Agente → Percebe → Memoriza → Raciocina → Age

Este módulo captura o estado observável de um jogo ARC-AGI-3
via browser tool + vision_load, extraindo:
- Grid do jogo e seus elementos visuais
- Posição do player, goal, power-ups, obstáculos
- Estado da UI (level, passos restantes, ações tomadas)
"""

import json
import os
from dataclasses import dataclass, asdict, field
from typing import Optional
from datetime import datetime


@dataclass
class SpritesObservation:
    """Sprites visíveis no grid do jogo"""
    player_position: tuple = (0, 0)  # (x, y) no grid
    goal_positions: list = field(default_factory=list)
    powerup_positions: list = field(default_factory=list)  # tiles amarelos
    wall_positions: list = field(default_factory=list)
    collectible_positions: list = field(default_factory=list)


@dataclass
class GameState:
    """Estado completo observável do jogo"""
    game_id: str
    level: int = 1
    total_levels: int = 1
    steps_remaining: Optional[int] = None
    steps_max: Optional[int] = None
    sprites: SpritesObservation = field(default_factory=SpritesObservation)
    available_actions: list = field(default_factory=lambda: [1, 2, 3, 4])
    actions_taken: list = field(default_factory=list)
    screenshot_path: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sprites"] = {
            "player": list(self.sprites.player_position),
            "goals": [list(g) for g in self.sprites.goal_positions],
            "powerups": [list(p) for p in self.sprites.powerup_positions],
            "walls": len(self.sprites.wall_positions),
            "collectibles": [list(c) for c in self.sprites.collectible_positions],
        }
        return d

    def save(self, path: str = "/a0/usr/workdir/arc_runs/"):
        os.makedirs(path, exist_ok=True)
        ts = datetime.now().strftime("%H%M%S")
        fname = f"{path}obs_{self.game_id}_l{self.level}_{ts}.json"
        with open(fname, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return fname


@dataclass
class AgentAction:
    game_id: str
    level: int
    action_id: int
    key: str
    result: str = ""
    new_state_hash: str = ""
    timestamp: str = ""


def arrow_for_action(action_id: int) -> str:
    m = {1: "ArrowUp", 2: "ArrowDown", 3: "ArrowLeft", 4: "ArrowRight",
         5: "Space", 6: "KeyC", 7: "KeyZ"}
    return m.get(action_id, "Space")


def action_for_key(key: str) -> int:
    r = {"ArrowUp": 1, "ArrowDown": 2, "ArrowLeft": 3, "ArrowRight": 4,
         "Space": 5, "KeyC": 6, "KeyZ": 7}
    return r.get(key, 0)


# ─── Observação do padrão visual via browser ───
# NOTA: Este módulo é invocado pelo agente principal que
# já tem acesso ao browser tool e vision_load.
# 
# O fluxo de uso pelo agente:
#
# 1. browser.screenshot() → caminho da imagem
# 2. vision_load(paths=[imagem]) → carrega na visão
# 3. Agente analisa visualmente e extrai:
#    - game_id: da URL atual
#    - level: do texto na UI
#    - steps_remaining: da barra amarela
#    - player_position: posição do sprite do player
#    - goal_positions: posição do(s) goal(s)
#    - powerup_positions: posição dos tiles amarelos
# 4. Preenche GameState
# 5. GameState.save() → JSON
# 6. memory_save() → armazena no Graph RAG


def extract_state_from_vision(
    game_id: str,
    level: int = 1,
    total_levels: int = 1,
    steps_remaining: Optional[int] = None,
    player_pos: tuple = (0, 0),
    goal_positions: list = None,
    powerup_positions: list = None,
    screenshot_path: str = "",
) -> GameState:
    """
    Cria um GameState a partir de observações visuais extraídas.

    Chamado APÓS o agente analisar o screenshot via vision_load.
    """
    sprites = SpritesObservation(
        player_position=player_pos,
        goal_positions=goal_positions or [],
        powerup_positions=powerup_positions or [],
    )

    return GameState(
        game_id=game_id,
        level=level,
        total_levels=total_levels,
        steps_remaining=steps_remaining,
        sprites=sprites,
        screenshot_path=screenshot_path,
        timestamp=datetime.now().isoformat(),
    )


def capture_canvas_state(browser_id: int = 4) -> dict:
    """
    Extrai estado real do canvas ARC-AGI-3 via getImageData.
    Retorna dict com player, power-ups, sprites e barra de passos.
    
    NOTA: Deve ser executado via browser.evaluate().
    O JavaScript de extração está abaixo para referência.
    """
    return {
        "method": "browser.evaluate",
        "script": """(function() {
  const c = document.querySelector('canvas');
  if (!c) return {error:'no canvas'};
  c.focus(); c.click();
  const ctx = c.getContext('2d');
  const w = c.width, h = c.height;
  const d = ctx.getImageData(0, 0, w, h).data;
  const gs = 48;
  const player=[], yellow=[], red=[], blue=[];
  for (let y=0; y<h; y+=2) {
    for (let x=0; x<w; x+=2) {
      const i = (y*w+x)*4;
      const r=d[i], g=d[i+1], b=d[i+2], a=d[i+3];
      if (a<200) continue;
      if (r>20&&r<60 && g>140&&g<200 && b>230) player.push({col:Math.round(x/gs),row:Math.round(y/gs)});
      else if (r>200 && g>200 && b<60) yellow.push({col:Math.round(x/gs),row:Math.round(y/gs)});
      else if (r>200 && g<80 && b<80) red.push({col:Math.round(x/gs),row:Math.round(y/gs)});
      else if (r<80 && g>100 && b>200) blue.push({col:Math.round(x/gs),row:Math.round(y/gs)});
    }
  }
  const cent = (p) => p.length ? {col:Math.round(p.reduce((s,v)=>s+v.col,0)/p.length),row:Math.round(p.reduce((s,v)=>s+v.row,0)/p.length),px:p.length} : null;
  const uniq = (p) => {const s=new Set(),r=[]; for(const v of p){const k=v.col+'_'+v.row;if(!s.has(k)){s.add(k);r.push({col:v.col,row:v.row})}} return r;};
  return {gridSize:gs,player:cent(player),yellowCount:uniq(yellow).length,yellowCells:uniq(yellow).slice(0,15),redCount:uniq(red).length,redCells:uniq(red).slice(0,5),blueCount:uniq(blue).length,focusGiven:true};
})()"""
    }


print("✅ V63_PERCEPTION completo: ")
print("   - GameState, SpritesObservation, AgentAction")
print("   - extract_state_from_vision() — cria estado de observação visual")
print("   - capture_canvas_state() — extrai estado real do canvas (getImageData + cores)")
print("   - arrow_for_action(), action_for_key()")
print("   - GameState.save() — salva como JSON")
