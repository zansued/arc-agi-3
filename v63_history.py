#!/usr/bin/env python3
"""
V63_HISTORY — Histórico de movimentação para ARC-AGI-3

Estrutura:
  anterior: {col, row} (posição antes da ação)
  posição antes: {col, row} (antes de executar)
  posição atual: {col, row} (depois de executar)
  ação: str
  moveu: bool
  passo: int
"""

import json
import os
from datetime import datetime
from typing import Optional


class MovementStep:
    """Um passo individual no histórico de movimentação."""
    def __init__(self, step: int, action: str,
                 pos_before: Optional[dict] = None,
                 pos_after: Optional[dict] = None):
        self.step = step
        self.action = action
        self.pos_before = pos_before  # {col: int, row: int}
        self.pos_after = pos_after    # {col: int, row: int}
        self.moved = self._check_moved()
        self.timestamp = datetime.now().isoformat()

    def _check_moved(self) -> bool:
        if not self.pos_before or not self.pos_after:
            return False
        return (self.pos_before.get('col') != self.pos_after.get('col') or
                self.pos_before.get('row') != self.pos_after.get('row'))

    def to_dict(self) -> dict:
        return {
            'step': self.step,
            'action': self.action,
            'pos_before': self.pos_before,
            'pos_after': self.pos_after,
            'moved': self.moved,
            'timestamp': self.timestamp
        }


class MovementHistory:
    """
    Histórico completo de movimentação.

    Colunas solicitadas pelo Senhor:
    - anterior: posição antes da última ação
    - posição antes: posição antes da ação atual
    - posição atual: posição depois da ação atual
    - ação executada
    - se moveu ou não
    """

    def __init__(self, game_id: str, level: int = 1,
                 history_path: str = '/a0/usr/workdir/arc_runs/'):
        self.game_id = game_id
        self.level = level
        self.history_path = history_path
        self.steps: list[MovementStep] = []
        os.makedirs(history_path, exist_ok=True)

    @property
    def last_step(self) -> Optional[MovementStep]:
        return self.steps[-1] if self.steps else None

    @property
    def anterior(self) -> Optional[dict]:
        """Posição antes da última ação (penúltima posição antes)."""
        if len(self.steps) >= 2:
            return self.steps[-2].pos_before
        return None

    @property
    def posicao_antes(self) -> Optional[dict]:
        """Posição antes da ação atual."""
        if self.steps:
            return self.steps[-1].pos_before
        return None

    @property
    def posicao_atual(self) -> Optional[dict]:
        """Posição depois da ação atual."""
        if self.steps:
            return self.steps[-1].pos_after
        return None

    @property
    def ultima_acao(self) -> Optional[str]:
        if self.steps:
            return self.steps[-1].action
        return None

    @property
    def moveu(self) -> bool:
        if self.steps:
            return self.steps[-1].moved
        return False

    @property
    def total_tentativas(self) -> int:
        return len(self.steps)

    @property
    def total_movimentos(self) -> int:
        return sum(1 for s in self.steps if s.moved)

    def add_step(self, action: str,
                 pos_before: Optional[dict] = None,
                 pos_after: Optional[dict] = None) -> MovementStep:
        """
        Adiciona um passo ao histórico.

        Args:
            action: tecla pressionada (ex: "ArrowRight")
            pos_before: posição antes de executar
            pos_after: posição depois de executar

        Returns:
            MovementStep criado
        """
        step = MovementStep(
            step=len(self.steps) + 1,
            action=action,
            pos_before=pos_before,
            pos_after=pos_after
        )
        self.steps.append(step)
        self._save_step(step)
        return step

    def is_stuck(self, recent_n: int = 5) -> bool:
        """
        Detecta se o agente está preso (loop).
        Retorna True se as últimas N ações não produziram movimento.
        """
        recent = self.steps[-recent_n:] if len(self.steps) >= recent_n else self.steps
        if len(recent) < recent_n:
            return False
        return all(not s.moved for s in recent)

    def is_same_action_loop(self, recent_n: int = 5) -> bool:
        """
        Detecta se está repetindo a mesma ação sem movimento.
        Ex: 5x ArrowRight sem mover.
        """
        recent = self.steps[-recent_n:] if len(self.steps) >= recent_n else self.steps
        if len(recent) < recent_n:
            return False
        actions = [s.action for s in recent]
        return (len(set(actions)) == 1 and
                all(not s.moved for s in recent))

    def get_last_n(self, n: int = 5) -> list[dict]:
        """Retorna os últimos N passos como dicionários."""
        return [s.to_dict() for s in self.steps[-n:]]

    def get_summary(self) -> dict:
        """Resumo do histórico atual."""
        return {
            'game_id': self.game_id,
            'level': self.level,
            'total_passos': self.total_tentativas,
            'total_movimentos': self.total_movimentos,
            'preso': self.is_stuck(),
            'loop_acao': self.is_same_action_loop(),
            'ultima_acao': self.ultima_acao,
            'moveu': self.moveu,
            'anterior': self.anterior,
            'posicao_antes': self.anterior if len(self.steps) >= 2 else None,
            'posicao_atual': self.posicao_atual
        }

    def _save_step(self, step: MovementStep):
        """Salva o passo em arquivo JSONL."""
        fname = f'{self.history_path}movement_{self.game_id}_l{self.level}.jsonl'
        with open(fname, 'a') as f:
            f.write(json.dumps(step.to_dict()) + '\n')

    def save_full_history(self) -> str:
        """Salva histórico completo como JSON."""
        data = {
            'game_id': self.game_id,
            'level': self.level,
            'summary': self.get_summary(),
            'steps': [s.to_dict() for s in self.steps]
        }
        fname = f'{self.history_path}movement_{self.game_id}_l{self.level}_full_{datetime.now().strftime("%H%M%S")}.json'
        with open(fname, 'w') as f:
            json.dump(data, f, indent=2)
        return fname

    def learn_to_kg(self):
        """
        Aprende com o histórico e registra no Knowledge Graph.
        Tenta importar v63_memory, falha silenciosamente se KG offline.
        """
        if len(self.steps) < 2:
            return

        try:
            from v63_memory import store_triple, learn_outcome

            # Registrar cada ação como triplo no KG
            for step in self.steps[-10:]:  # últimas 10 ações
                if step.pos_before and step.pos_after:
                    learn_outcome(
                        game=self.game_id,
                        level=self.level,
                        action=step.action,
                        result='moved' if step.moved else 'blocked'
                    )

            # Registrar estatísticas
            store_triple(
                f'{self.game_id}_l{self.level}',
                'total_movements',
                str(self.total_movimentos)
            )
            store_triple(
                f'{self.game_id}_l{self.level}',
                'stuck',
                'true' if self.is_stuck() else 'false'
            )
            store_triple(
                f'{self.game_id}_l{self.level}',
                'action_loop',
                'true' if self.is_same_action_loop() else 'false'
            )

        except Exception as e:
            print(f'⚠️  KG offline, pulando aprendizado: {e}')


# Teste rápido
if __name__ == '__main__':
    h = MovementHistory('ls20', 1)

    # Simular movimentos
    h.add_step('ArrowRight', pos_before={'col': 7, 'row': 16}, pos_after={'col': 7, 'row': 16})
    h.add_step('ArrowRight', pos_before={'col': 7, 'row': 16}, pos_after={'col': 7, 'row': 16})
    h.add_step('ArrowDown', pos_before={'col': 7, 'row': 16}, pos_after={'col': 7, 'row': 16})
    h.add_step('ArrowDown', pos_before={'col': 7, 'row': 16}, pos_after={'col': 7, 'row': 17})

    print('\n📊 Histórico de Movimentação:')
    print(json.dumps(h.get_summary(), indent=2))

    print('\n📍 Colunas solicitadas:')
    print(f'  Anterior:        {h.anterior}')
    print(f'  Posição antes:   {h.posicao_antes}')
    print(f'  Posição atual:   {h.posicao_atual}')
    print(f'  Ação:            {h.ultima_acao}')
    print(f'  Moveu:           {h.moveu}')
    print(f'  Preso?           {h.is_stuck()}')
    print(f'  Loop de ação?    {h.is_same_action_loop()}')

    print('\n📁 Salvo em:', h.save_full_history())
