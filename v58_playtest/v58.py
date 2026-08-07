"""
v58.py — Entry Point do Solver Híbrido

Orquestra as 3 fases:
Fase 0 → Reconhecimento de Jogo (GameAnalyzer)
Fase 1 → Heurística por Padrão (Paint / Tangram / Navigation)
Fase 2 → BFS Guiado com Priors (fallback)

Baseado nas descobertas de Senhor (@zansued) no playtest manual:
- sp80: Pintura em camadas (6 níveis resolvidos)
- cn04: Tangram expansível (6 níveis resolvidos)
- bp35: Navegação anti-caminho-curto (em progresso)

Arquitetura inovadora:
ANTES (v55): ARC-DSR (quebrado) → BFS cego → 0 níveis
DEPOIS (v58): Reconhecimento → Heurística → BFS guiado → ?? níveis

Extraído de:
https://github.com/niclas349/ARC-AGI-3
"""

import json
import sys
import os
import time
from typing import Dict, List, Optional
from pathlib import Path

# Módulos v58
from v58_game_analyzer import GameAnalyzer
from v58_heuristic_paint import PaintHeuristic
from v58_heuristic_tangram import TangramHeuristic
from v58_heuristic_navigation import NavigationHeuristic
from v58_guided_bfs import GuidedBFS
from v58_memory import PatternMemory


class V58Solver:
    """
    Solver Híbrido v58.
    
    Características principais:
    1. Reconhece o jogo ANTES de buscar solução
    2. Aplica heurística específica baseada no padrão
    3. Fallback para BFS guiado quando heurística falha
    4. Aprendizado por transferência via PatternMemory
    """
    
    def __init__(self, game_id: str, arcade):
        self.game_id = game_id
        self.arcade = arcade
        self.catalog = None
        self.memory = PatternMemory()
        self.results = {
            'game_id': game_id,
            'phases': {},
            'levels_completed': 0,
            'levels_total': 0,
            'total_steps': 0,
            'success': False,
            'error': None,
        }
    
    def run(self) -> Dict:
        """Executa o solver completo (Fase 0 → 1 → 2)."""
        print(f"\n{'='*60}")
        print(f"  V58 Solver — {self.game_id}")
        print(f"{'='*60}")
        
        # FASE 0: Reconhecimento de Jogo
        print(f"\n{'─'*40}")
        print("  FASE 0: RECONHECIMENTO DE JOGO")
        print(f"{'─'*40}")
        
        phase0_start = time.time()
        try:
            analyzer = GameAnalyzer(self.game_id, self.arcade)
            self.catalog = analyzer.analyze()
            self.results['phases']['phase0'] = {
                'status': 'completed',
                'time_s': round(time.time() - phase0_start, 2),
                'catalog': self.catalog,
            }
            print(f"  Catálogo: ACTION5={self.catalog['action5_func']}, "
                  f"ACTION6={self.catalog['action6_func']}")
        except Exception as e:
            self.results['phases']['phase0'] = {'status': 'error', 'error': str(e)}
            print(f"  ERRO Fase 0: {e}")
            self.results['error'] = str(e)
            return self.results
        
        # Verificar heurística recomendada pela memória
        recommended = self.memory.get_recommended_heuristic(
            self.game_id, self.catalog
        )
        print(f"  Memória recomenda: {recommended}")
        
        # FASE 1: Heurística por Padrão
        print(f"\n{'─'*40}")
        print(f"  FASE 1: HEURÍSTICA ({recommended.upper()})")
        print(f"{'─'*40}")
        
        phase1_start = time.time()
        heuristic_success = False
        heuristic_result = None
        
        try:
            if recommended == 'paint' or self._is_paint_game():
                print("  ▶ Tentando heurística de PINTURA...")
                paint = PaintHeuristic(self.game_id, self.arcade, self.catalog)
                if paint.matches_pattern():
                    solution = paint.generate_solution()
                    if solution:
                        heuristic_success = paint.execute_solution()
                        heuristic_result = paint.save_pattern_memory()
            
            elif recommended == 'tangram' or self._is_tangram_game():
                print("  ▶ Tentando heurística de TANGRAM...")
                tangram = TangramHeuristic(self.game_id, self.arcade, self.catalog)
                if tangram.matches_pattern():
                    solution = tangram.generate_solution()
                    if solution:
                        heuristic_success = tangram.execute_solution()
                        heuristic_result = tangram.save_pattern_memory()
            
            elif recommended == 'navigation' or self._is_navigation_game():
                print("  ▶ Tentando heurística de NAVEGAÇÃO...")
                nav = NavigationHeuristic(self.game_id, self.arcade, self.catalog)
                if nav.matches_pattern():
                    solution = nav.generate_solution()
                    if solution:
                        heuristic_success = nav.execute_solution()
                        heuristic_result = nav.save_pattern_memory()
            
            else:
                print(f"  ▶ Nenhuma heurística específica. Tentando genérica...")
                # Tentar cada heurística em ordem
                for heuristic_class, name in [
                    (PaintHeuristic, 'paint'),
                    (TangramHeuristic, 'tangram'),
                    (NavigationHeuristic, 'navigation'),
                ]:
                    h = heuristic_class(self.game_id, self.arcade, self.catalog)
                    if h.matches_pattern():
                        print(f"  ▶ Tentando {name}...")
                        sol = h.generate_solution()
                        if sol and h.execute_solution():
                            heuristic_success = True
                            heuristic_result = h.save_pattern_memory()
                            break
        
        except Exception as e:
            print(f"  ERRO Fase 1: {e}")
        
        self.results['phases']['phase1'] = {
            'status': 'completed' if heuristic_success else 'failed',
            'time_s': round(time.time() - phase1_start, 2),
            'heuristic': recommended,
            'success': heuristic_success,
        }
        
        if heuristic_success:
            # Salvar padrão na memória
            self.memory.save_pattern(
                self.game_id, self.catalog, recommended,
                levels_solved=1
            )
            self.results['success'] = True
            self.results['levels_completed'] = 1
            print(f"\n  ✅ FASE 1: SUCESSO! Jogo {self.game_id} resolvido!")
            return self.results
        
        # FASE 2: BFS Guiado (fallback)
        print(f"\n{'─'*40}")
        print("  FASE 2: BFS GUIADO (FALLBACK)")
        print(f"{'─'*40}")
        
        phase2_start = time.time()
        try:
            bfs = GuidedBFS(self.game_id, self.arcade, self.catalog)
            solution = bfs.search(max_steps=500, max_states=2000)
            
            bfs_stats = bfs.get_statistics()
            self.results['phases']['phase2'] = {
                'status': 'completed',
                'time_s': round(time.time() - phase2_start, 2),
                'solution_found': solution is not None,
                'visited_states': bfs_stats['visited_states'],
                'game_over_states': bfs_stats['game_over_states'],
                'solution_length': len(solution) if solution else 0,
            }
            
            if solution:
                self.results['success'] = True
                self.results['levels_completed'] = 1
                print(f"\n  ✅ FASE 2: SUCESSO! {len(solution)} ações!")
            else:
                print(f"\n  ❌ FASE 2: Nenhuma solução encontrada.")
        
        except Exception as e:
            self.results['phases']['phase2'] = {'status': 'error', 'error': str(e)}
            print(f"  ERRO Fase 2: {e}")
        
        return self.results
    
    def _is_paint_game(self) -> bool:
        """Verifica rapidamente se é jogo de pintura."""
        if not self.catalog:
            return False
        acts = self.catalog.get('actions', {})
        return (acts.get(5, {}).get('has_effect') and
                acts.get(6, {}).get('has_effect'))
    
    def _is_tangram_game(self) -> bool:
        """Verifica rapidamente se é jogo de tangram."""
        if not self.catalog:
            return False
        acts = self.catalog.get('actions', {})
        return (acts.get(6, {}).get('has_effect') and
                self.catalog.get('max_cliques', 1) > 1)
    
    def _is_navigation_game(self) -> bool:
        """Verifica rapidamente se é jogo de navegação."""
        if not self.catalog:
            return False
        acts = self.catalog.get('actions', {})
        return (not acts.get(5, {}).get('has_effect') and
                acts.get(6, {}).get('has_effect'))
    
    def print_report(self):
        """Imprime relatório detalhado da execução."""
        print(f"\n{'='*60}")
        print(f"  RELATÓRIO V58 — {self.game_id}")
        print(f"{'='*60}")
        
        print(f"\n✅ Sucesso: {self.results.get('success', False)}")
        print(f"  Níveis completados: {self.results.get('levels_completed', 0)}")
        print(f"  Erro: {self.results.get('error', 'Nenhum')}")
        
        for phase, data in self.results.get('phases', {}).items():
            status_icon = '✅' if data.get('status') == 'completed' else '❌'
            print(f"\n  {status_icon} {phase}:")
            print(f"     Status: {data.get('status')}")
            print(f"     Tempo: {data.get('time_s', 0)}s")
            if 'visited_states' in data:
                print(f"     Estados visitados: {data.get('visited_states')}")
            if 'game_over_states' in data:
                print(f"     Game overs: {data.get('game_over_states')}")
            if 'heuristic' in data:
                print(f"     Heurística: {data.get('heuristic')}")
            if 'solution_length' in data:
                print(f"     Solução: {data.get('solution_length')} ações")
        
        print(f"\n{'='*60}")


def main():
    """
    Ponto de entrada principal.
    
    Uso:
        python v58.py [game_id]
        python v58.py [game_id] [--all]
        python v58.py --benchmark
    """
    print(f"\n{'='*60}")
    print("  V58 — Solver Híbrido com Playtest Descobertas")
    print(f"{'='*60}")
    print("  Baseado nas descobertas de Senhor (@zansued)")
    print("  sp80: Pintura em camadas (6 níveis)")
    print("  cn04: Tangram expansível (6 níveis)")
    print("  bp35: Navegação anti-caminho-curto")
    print(f"{'='*60}")
    
    # Teste básico de importação
    print("\nMódulos v58 carregados com sucesso:")
    print(f"  - GameAnalyzer (Fase 0: Reconhecimento)")
    print(f"  - PaintHeuristic (sp80-style)")
    print(f"  - TangramHeuristic (cn04-style)")
    print(f"  - NavigationHeuristic (bp35-style)")
    print(f"  - GuidedBFS (Fase 2: Busca com Priors)")
    print(f"  - PatternMemory (Aprendizado por Transferência)")
    
    # Inicializar memória de padrões
    mem = PatternMemory()
    stats = mem.get_statistics()
    print(f"\nMemória de Padrões:")
    print(f"  Padrões salvos: {stats['total_patterns']}")
    for ptype, count in stats.get('pattern_types', {}).items():
        print(f"    - {ptype}: {count} jogos")
    print(f"  Níveis já resolvidos: {stats['total_levels_solved']}")
    
    print(f"\n{'='*60}")
    print("  Para executar contra jogos reais, chame V58Solver(game_id, arcade).run()")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
