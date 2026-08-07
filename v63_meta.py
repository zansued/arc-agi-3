"""
V63_META — Modulo de METACOGNICAO para ARC-AGI-3
Parte 5: Agente que pensa SOBRE como esta pensando.

Diferencial dos 12+ solvers anteriores:
- Eles NUNCA questionavam a propria estrategia
- Eles NUNCA diziam "essa abordagem nao funciona, trocando"
- Eles continuavam tentando o mesmo com parametros diferentes

A metacognicao resolve isto.
"""

import json
import os
import sys
from datetime import datetime
from collections import deque

sys.path.insert(0, '/a0/usr/workdir')

try:
    from v63_memory import store_triple, prepare_observation_text, learn_outcome
    HAS_MODULES = True
except ImportError:
    HAS_MODULES = False


# ─── Estrategias Disponiveis ───

STRATEGIES = {
    "NAV_POWERUP_FIRST": {
        "name": "Coletar power-ups primeiro",
        "desc": "Navegar ate tiles amarelos antes de ir para o goal",
        "type": "nav",
        "max_steps": 30
    },
    "NAV_SEEK_GOAL": {
        "name": "Buscar goal diretamente",
        "desc": "Ir direto para o goal ignorando power-ups",
        "type": "nav",
        "max_steps": 50
    },
    "EXPLORE_SYSTEMATIC": {
        "name": "Exploracao sistematica",
        "desc": "Varrer o grid em padrao espiral",
        "type": "explore",
        "max_steps": 100
    },
    "EXPLORE_GREEDY": {
        "name": "Exploracao greedy",
        "desc": "Seguir direcao com mais espaco livre",
        "type": "explore",
        "max_steps": 60
    },
    "CLICK_SYSTEMATIC": {
        "name": "Clique sistematico",
        "desc": "Testar combinacoes de clique nos sprites",
        "type": "click",
        "max_steps": 50
    },
    "RESET_AND_RETRY": {
        "name": "Reset e tentativa diferente",
        "desc": "Reiniciar o nivel com nova estrategia",
        "type": "reset",
        "max_steps": 1
    },
    "BACKTRACK": {
        "name": "Backtrack",
        "desc": "Voltar para estado anterior conhecido",
        "type": "backtrack",
        "max_steps": 20
    },
    "OBSERVE_ONLY": {
        "name": "Observar sem agir",
        "desc": "Capturar screenshot e analisar sem pressionar teclas",
        "type": "observe",
        "max_steps": 3
    }
}


# ─── Rastreador de Progresso ───

class ProgressTracker:
    """
    Rastreia se o agente esta progredindo ou preso.
    """

    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.action_history = []  # [(timestamp, action, result_state_hash)]
        self.state_hashes = deque(maxlen=window_size)
        self.steps_without_change = 0
        self.steps_without_win = 0
        self.loops_detected = []
        self.last_significant_event = None

    def record_action(self, state_hash: str, action: str, result: str):
        """Registra uma acao e seu resultado."""
        now = datetime.now()
        self.action_history.append((now, action, state_hash, result))

        # Verificar se o estado mudou significativamente
        if state_hash in self.state_hashes:
            self.steps_without_change += 1
        else:
            self.state_hashes.append(state_hash)
            if self.steps_without_change > 0:
                self.steps_without_change = 0  # Reset porque algo mudou

        self.steps_without_win += 1

        # Detectar loops
        # Se o mesmo hash apareceu 3+ vezes, e loop
        from collections import Counter
        hash_counts = Counter(self.state_hashes)
        for h, count in hash_counts.items():
            if count >= 3:
                self.loops_detected.append({
                    "hash": h,
                    "count": count,
                    "action": action,
                    "timestamp": now.isoformat()
                })

    def record_win(self):
        """Registra que o nivel foi vencido."""
        self.steps_without_win = 0
        self.steps_without_change = 0
        self.last_significant_event = "won"

    def get_status(self) -> dict:
        """
        Retorna diagnostico do progresso.
        """
        return {
            "total_actions": len(self.action_history),
            "steps_without_change": self.steps_without_change,
            "steps_without_win": self.steps_without_win,
            "unique_states": len(set(self.state_hashes)),
            "loops_detected": len(self.loops_detected),
            "is_stuck": self.steps_without_change >= 5,
            "is_lost": self.steps_without_win >= 50,
            "loops": self.loops_detected[-3:] if self.loops_detected else []
        }


# ─── Avaliador de Estrategia ───

class StrategyEvaluator:
    """
    Avalia se a estrategia atual esta funcionando.
    """

    def __init__(self):
        self.strategy_history = []  # [(timestamp, strategy_name, reason)]
        self.current_strategy = None
        self.current_strategy_steps = 0
        self.strategy_results = {}  # strategy_name -> {attempts, successes, failures}

    def start_strategy(self, name: str, reason: str = ""):
        """Inicia uma nova estrategia."""
        now = datetime.now()
        self.strategy_history.append({
            "timestamp": now.isoformat(),
            "strategy": name,
            "reason": reason
        })
        self.current_strategy = name
        self.current_strategy_steps = 0

        if name not in self.strategy_results:
            self.strategy_results[name] = {"attempts": 0, "successes": 0, "failures": 0}
        self.strategy_results[name]["attempts"] += 1

        # Registrar no KG
        store_triple("agent:strategy", "switched_to", name, {
            "reason": reason,
            "timestamp": now.isoformat()
        })

        return {"strategy": name, "reason": reason}

    def step(self):
        """Incrementa contador de passos na estrategia atual."""
        self.current_strategy_steps += 1

    def evaluate(self, progress: dict) -> dict:
        """
        Avalia se deve trocar de estrategia.
        Retorna: should_switch (bool), new_strategy (str), reason (str)
        """
        result = {
            "should_switch": False,
            "new_strategy": self.current_strategy,
            "reason": ""
        }

        if not self.current_strategy:
            result["should_switch"] = True
            result["new_strategy"] = "NAV_POWERUP_FIRST"
            result["reason"] = "Nenhuma estrategia ativa. Iniciando com power-up first."
            return result

        strategy_info = STRATEGIES.get(self.current_strategy, {})
        max_steps = strategy_info.get("max_steps", 50)

        # Criterio 1: Muitos passos sem progresso
        if self.current_strategy_steps >= max_steps:
            result["should_switch"] = True
            # Escolher proxima estrategia baseada no tipo
            strat_type = strategy_info.get("type", "nav")
            next_strat = self._get_next_strategy(strat_type)
            result["new_strategy"] = next_strat
            result["reason"] = f"{self.current_strategy} atingiu {max_steps} passos sem sucesso. Trocando para {next_strat}."
            self.strategy_results[self.current_strategy]["failures"] += 1
            return result

        # Criterio 2: Detectou loop
        if progress.get("is_stuck"):
            result["should_switch"] = True
            result["new_strategy"] = "BACKTRACK"
            result["reason"] = "Loop detectado: agente esta repetindo estados. Trocando para BACKTRACK."
            self.strategy_results[self.current_strategy]["failures"] += 1
            return result

        # Criterio 3: Muitas acoes sem vencer
        if progress.get("is_lost"):
            result["should_switch"] = True
            result["new_strategy"] = "RESET_AND_RETRY"
            result["reason"] = "50+ acoes sem vencer. Algo fundamentalmente errado. Resetando com nova abordagem."
            self.strategy_results[self.current_strategy]["failures"] += 1
            return result

        return result

    def _get_next_strategy(self, current_type: str) -> str:
        """Escolhe a proxima estrategia baseada no tipo atual."""
        # Ciclo de estrategias: NAV -> EXPLORE -> CLICK -> RESET -> NAV
        strategy_order = [
            "NAV_POWERUP_FIRST",
            "NAV_SEEK_GOAL",
            "EXPLORE_SYSTEMATIC",
            "EXPLORE_GREEDY",
            "CLICK_SYSTEMATIC",
            "RESET_AND_RETRY",
            "NAV_POWERUP_FIRST"  # Ciclo completo
        ]

        if self.current_strategy in strategy_order:
            idx = strategy_order.index(self.current_strategy)
            return strategy_order[(idx + 1) % len(strategy_order)]

        return "NAV_POWERUP_FIRST"

    def record_success(self):
        """Registra que a estrategia atual foi bem-sucedida."""
        if self.current_strategy:
            self.strategy_results[self.current_strategy]["successes"] += 1

    def get_report(self) -> str:
        """Gera relatorio do metacognicao."""
        lines = []
        lines.append("🧠 RELATORIO DE METACOGNICAO")
        lines.append("="*40)

        if self.strategy_history:
            last = self.strategy_history[-1]
            lines.append(f"\nEstrategia atual: {last['strategy']}")
            lines.append(f"Motivo: {last['reason']}")
            lines.append(f"Passos nesta estrategia: {self.current_strategy_steps}")

        lines.append(f"\nTrocas de estrategia: {len(self.strategy_history)}")

        lines.append("\nHistorico:")
        for h in self.strategy_history[-5:]:
            lines.append(f"  [{h['timestamp'][:16]}] {h['strategy']}: {h['reason'][:80]}")

        return "\n".join(lines)


# ─── Log de Reflexao ───

class ReflectionLog:
    """
    Registra reflexoes do agente sobre seu proprio processo.
    """

    def __init__(self):
        self.entries = []
        self.file_path = "/a0/usr/workdir/arc_runs/reflection_log.jsonl"

    def reflect(self, game_id: str, level: int, observation: str):
        """
        Registra uma reflexao.

        Args:
            game_id: jogo atual
            level: nivel atual
            observation: texto da reflexao (ex: "Estou preso ha 20 passos. Percebo que ArrowRight sempre retorna ao mesmo estado. Isso sugere que a mecanica NAO e de navegacao pura.")
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "game_id": game_id,
            "level": level,
            "observation": observation
        }
        self.entries.append(entry)

        with open(self.file_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def get_recent(self, n: int = 5) -> list:
        """Retorna as N reflexoes mais recentes."""
        return self.entries[-n:]

    def summarize(self) -> str:
        """Sumariza as ultimas reflexoes."""
        if not self.entries:
            return "Nenhuma reflexao registrada ainda."

        recent = self.entries[-3:]
        lines = ["🧠 Reflexoes recentes:"]
        for r in recent:
            lines.append(f"  [{r['timestamp'][:16]}] {r['observation'][:120]}")
        return "\n".join(lines)


# ─── Ciclo Completo de Metacognicao ───

class MetacognitiveAgent:
    """
    O agente completo com metacognicao.
    Integra Partes 1-4 + Parte 5 (metacognicao).
    """

    def __init__(self, game_id: str = "ls20"):
        self.game_id = game_id
        self.level = 1
        self.progress = ProgressTracker(window_size=15)
        self.evaluator = StrategyEvaluator()
        self.reflection = ReflectionLog()
        self.cycle_count = 0
        self.reset_count = 0

    def run_cycle(self, state_hash: str, action: str, result: str) -> dict:
        """
        Executa um ciclo do agente com metacognicao.

        Args:
            state_hash: hash do estado atual do jogo
            action: acao executada
            result: resultado da acao (moved, collected, won, etc.)

        Returns:
            dict com proxima acao e contexto metacognitivo
        """
        self.cycle_count += 1

        # 1. Registrar acao e progresso
        self.progress.record_action(state_hash, action, result)
        self.evaluator.step()

        # 2. Se venceu, registrar sucesso
        if result == "won":
            self.progress.record_win()
            self.evaluator.record_success()
            return {
                "action": None,
                "metacognition": {
                    "status": "won",
                    "message": f"Nivel {self.level} vencido apos {self.cycle_count} ciclos!"
                }
            }

        # 3. Avaliar estrategia atual
        status = self.progress.get_status()
        eval_result = self.evaluator.evaluate(status)

        # 4. Se precisa trocar de estrategia
        if eval_result["should_switch"]:
            self.evaluator.start_strategy(
                eval_result["new_strategy"],
                eval_result["reason"]
            )

            # Registrar reflexao
            self.reflection.reflect(
                self.game_id, self.level,
                f"Estrategia trocada: {eval_result['reason']} "
                f"(ciclo {self.cycle_count}, {status['total_actions']} acoes totais)"
            )

            # Se for RESET, incrementar contador
            if eval_result["new_strategy"] == "RESET_AND_RETRY":
                self.reset_count += 1

        # 5. Retornar decisao metacognitiva
        return {
            "action": eval_result.get("action"),
            "metacognition": {
                "status": "active",
                "current_strategy": self.evaluator.current_strategy,
                "strategy_steps": self.evaluator.current_strategy_steps,
                "total_cycles": self.cycle_count,
                "progress": status,
                "loops_detected": status["loops_detected"],
                "is_stuck": status["is_stuck"],
                "should_switch": eval_result["should_switch"],
                "switch_reason": eval_result["reason"],
                "reflections": self.reflection.get_recent(2)
            }
        }

    def get_full_report(self) -> str:
        """Gera relatorio completo do estado metacognitivo."""
        lines = []
        lines.append("="*60)
        lines.append("🧠 META-RELATORIO: AGENTE ARCV63")
        lines.append("="*60)
        lines.append(f"\nJogo: {self.game_id} Level {self.level}")
        lines.append(f"Ciclos executados: {self.cycle_count}")
        lines.append(f"Resets: {self.reset_count}")
        lines.append(f"")
        lines.append(self.evaluator.get_report())
        lines.append(f"")
        lines.append(self.reflection.summarize())
        lines.append(f"")

        status = self.progress.get_status()
        emoji = "🟢" if not status["is_stuck"] else "🟡" if not status["is_lost"] else "🔴"
        lines.append(f"{emoji} Status: {status['total_actions']} acoes | {status['unique_states']} estados unicos")
        if status["loops_detected"]:
            lines.append(f"⚠️  {len(status['loops_detected'])} loops detectados")

        return "\n".join(lines)


# ─── Execucao Direta ───
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧠 PARTE 5: METACOGNICAO — INSTALADA")
    print("="*60)
    print("""
    Classes:
    • ProgressTracker — detecta loops, falta de progresso
    • StrategyEvaluator — avalia e troca estrategias
    • ReflectionLog — registra reflexoes do agente
    • MetacognitiveAgent — agente completo integrado

    Estrategias: 8 disponiveis
    • NAV_POWERUP_FIRST: Coletar power-ups primeiro
    • NAV_SEEK_GOAL: Buscar goal diretamente
    • EXPLORE_SYSTEMATIC: Exploracao espiral
    • EXPLORE_GREEDY: Seguir espaco livre
    • CLICK_SYSTEMATIC: Combinacoes de clique
    • RESET_AND_RETRY: Reset com nova abordagem
    • BACKTRACK: Voltar a estado conhecido
    • OBSERVE_ONLY: Observar sem agir
    """)

    # Teste com simulacao
    print("\n🔬 Testando ciclo metacognitivo simulado...")
    agent = MetacognitiveAgent("ls20")
    agent.evaluator.start_strategy("NAV_POWERUP_FIRST", "Iniciando partida")

    # Simular 20 acoes sem progresso
    for i in range(20):
        result = agent.run_cycle(f"state_hash_same_{i%3}", "ArrowRight", "no_effect")

    print(agent.get_full_report())
