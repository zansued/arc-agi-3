#!/usr/bin/env python3
"""
Integração Phi-4: Escolhe automaticamente o modelo certo para cada tarefa.
- Tarefas simples: phi4-mini (local, zero custo)
- Tarefas intermediárias: phi4 (local, zero custo) [se instalado]
- Tarefas complexas: DeepSeek (API)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skill_porter', 'imported', 'phi4'))

from phi4_client import generate, chat, get_status, get_info

__all__ = ['generate', 'chat', 'get_status', 'get_info', 'get_task_config']

def get_task_config(task_type: str = "lead_processing") -> dict:
    """Retorna configuração para o tipo de tarefa."""
    from config import TASK_MAP
    return TASK_MAP.get(task_type, {"model": "phi4-mini", "temperature": 0.1})
