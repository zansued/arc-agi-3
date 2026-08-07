"""
v58_memory.py — Memória de Padrões de Jogo

Registra padrões de jogos descobertos e permite aprendizado
por transferência entre jogos similares.

Baseado no playtest manual de Senhor que revelou:
- sp80: Pintura em camadas (ACTION5=pintar, ACTION6=selecionar)
- cn04: Tangram expansível (ACTION5=girar/crescer, ACTION6=selecionar/crescer, até 5x)
- bp35: Navegação anti-caminho-curto (ACTION5=inativo, ACTION6=portal)

Extraído de:
https://github.com/niclas349/ARC-AGI-3
"""

import json
import os
from typing import Dict, List, Optional
from datetime import datetime


class PatternMemory:
    """
    Memória de padrões de jogo.
    
    Armazena os catálogos e heurísticas que funcionaram,
    permitindo aprendizado por transferência.
    
    Se um novo jogo tiver características similares a sp80,
    a heurística de pintura pode ser tentada primeiro.
    """
    
    def __init__(self, memory_path: str = None):
        if memory_path is None:
            self.memory_path = '/a0/usr/workdir/v58_playtest/pattern_memory.json'
        else:
            self.memory_path = memory_path
        
        self.patterns = {}  # game_id -> pattern_info
        self.transfer_matrix = {}  # pattern_type -> [game_ids]
        
        # Carregar memória existente
        self._load()
        
        # Padrões conhecidos (do playtest)
        if not self.patterns:
            self._init_known_patterns()
    
    def _init_known_patterns(self):
        """Inicializa padrões conhecidos do playtest."""
        known = {
            'sp80': {
                'pattern': 'paint',
                'description': 'Pintura em camadas - ACTION5=pintar, ACTION6=selecionar cor',
                'catalog': {
                    'action5_func': 'paint',
                    'action6_func': 'select',
                    'has_tanque_cores': True,
                },
                'heuristic': 'paint',
                'levels_solved': 6,
                'discovered_by': 'playtest_senhor',
                'date': '2026-06-17',
            },
            'cn04': {
                'pattern': 'tangram',
                'description': 'Tangram expansível - peças crescem com clique (até 5x), ACTION5=girar/crescer',
                'catalog': {
                    'action6_func': 'select_or_grow',
                    'has_pecas_expansiveis': True,
                    'max_cliques': 5,
                },
                'heuristic': 'tangram',
                'levels_solved': 6,
                'discovered_by': 'playtest_senhor',
                'date': '2026-06-17',
            },
        }
        
        self.patterns.update(known)
        self._rebuild_transfer_matrix()
        self._save()
    
    def add_bp35_pattern(self):
        """Adiciona padrão bp35 (quando Senhor completar o playtest)."""
        bp35_pattern = {
            'bp35': {
                'pattern': 'navigation',
                'description': 'Navegação anti-caminho-curto - ACTION5=inativo, ACTION6=portal verde, evitar roxo',
                'catalog': {
                    'action5_func': 'inactive',
                    'action6_func': 'activate_portal',
                    'has_portais': True,
                    'caminho_curto_mata': True,
                },
                'heuristic': 'navigation',
                'levels_solved': 9,
                'discovered_by': 'playtest_senhor',
                'date': '2026-06-17',
            }
        }
        self.patterns.update(bp35_pattern)
        self._rebuild_transfer_matrix()
        self._save()
    
    def save_pattern(self, game_id: str, catalog: Dict, heuristic: str,
                     levels_solved: int, discovered_by: str = 'playtest_senhor'):
        """Salva um padrão de jogo na memória."""
        self.patterns[game_id] = {
            'pattern': catalog.get('action5_func', 'unknown'),
            'description': json.dumps(catalog),
            'catalog': catalog,
            'heuristic': heuristic,
            'levels_solved': levels_solved,
            'discovered_by': discovered_by,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }
        self._rebuild_transfer_matrix()
        self._save()
        print(f"[MEMORY] Padrão salvo: {game_id} -> {heuristic}")
    
    def find_similar_games(self, catalog: Dict) -> List[Dict]:
        """
        Encontra jogos similares na memória baseado no catálogo.
        
        Compara características:
        - action5_func: paint, rotate, expand, inactive
        - action6_func: select, grow, activate_portal
        - has_tanque_cores, has_pecas_expansiveis, has_portais
        - caminho_curto_mata
        """
        matches = []
        
        for game_id, pattern in self.patterns.items():
            if game_id == catalog.get('game_id'):
                continue
            
            pattern_cat = pattern.get('catalog', {})
            similarity = self._calculate_similarity(catalog, pattern_cat)
            
            matches.append({
                'game_id': game_id,
                'pattern': pattern['pattern'],
                'heuristic': pattern['heuristic'],
                'similarity': similarity,
                'levels_solved': pattern.get('levels_solved', 0),
            })
        
        # Ordenar por similaridade (maior primeiro)
        matches.sort(key=lambda m: m['similarity'], reverse=True)
        return matches
    
    def _calculate_similarity(self, cat1: Dict, cat2: Dict) -> float:
        """
        Calcula similaridade entre dois catálogos.
        
        Quanto mais características em comum, maior a similaridade.
        """
        if not cat1 or not cat2:
            return 0.0
        
        score = 0.0
        total = 0.0
        
        # Comparar action5_func
        if cat1.get('action5_func') == cat2.get('action5_func'):
            score += 20
        total += 20
        
        # Comparar action6_func
        if cat1.get('action6_func') == cat2.get('action6_func'):
            score += 20
        total += 20
        
        # Comparar flags booleanas
        bool_flags = ['has_tanque_cores', 'has_pecas_expansiveis',
                      'has_portais', 'caminho_curto_mata']
        for flag in bool_flags:
            if flag in cat1 and flag in cat2:
                if cat1[flag] == cat2[flag]:
                    score += 15
                total += 15
        
        # Comparar max_cliques
        mc1 = cat1.get('max_cliques', 1)
        mc2 = cat2.get('max_cliques', 1)
        if mc1 == mc2:
            score += 10
        total += 10
        
        return score / total if total > 0 else 0.0
    
    def get_recommended_heuristic(self, game_id: str, catalog: Dict) -> str:
        """
        Recomenda uma heurística para um novo jogo.
        
        Se o jogo já tem padrão salvo, usa ele.
        Se não, encontra o jogo mais similar e sugere a heurística.
        """
        # Verificar se o jogo já é conhecido
        if game_id in self.patterns:
            return self.patterns[game_id]['heuristic']
        
        # Encontrar jogos similares
        similar = self.find_similar_games(catalog)
        
        if similar:
            top = similar[0]
            if top['similarity'] >= 0.5:
                print(f"[MEMORY] Transferindo heurística de {top['game_id']} "
                      f"({top['heuristic']}) para {game_id} "
                      f"(similaridade: {top['similarity']:.2f})")
                return top['heuristic']
        
        return 'generic'
    
    def _rebuild_transfer_matrix(self):
        """Reconstrói matriz de transferência por tipo de padrão."""
        self.transfer_matrix = {}
        for game_id, pattern in self.patterns.items():
            ptype = pattern.get('pattern', 'unknown')
            if ptype not in self.transfer_matrix:
                self.transfer_matrix[ptype] = []
            self.transfer_matrix[ptype].append(game_id)
    
    def get_statistics(self) -> Dict:
        """Retorna estatísticas da memória de padrões."""
        return {
            'total_patterns': len(self.patterns),
            'pattern_types': {k: len(v) for k, v in self.transfer_matrix.items()},
            'games': list(self.patterns.keys()),
            'total_levels_solved': sum(
                p.get('levels_solved', 0) for p in self.patterns.values()
            ),
        }
    
    def _load(self):
        """Carrega memória do arquivo JSON."""
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, 'r') as f:
                    data = json.load(f)
                    self.patterns = data.get('patterns', {})
                    self.transfer_matrix = data.get('transfer_matrix', {})
                print(f"[MEMORY] Carregada: {len(self.patterns)} padrões")
            except Exception as e:
                print(f"[MEMORY] Erro ao carregar: {e}")
    
    def _save(self):
        """Salva memória em arquivo JSON."""
        try:
            with open(self.memory_path, 'w') as f:
                json.dump({
                    'patterns': self.patterns,
                    'transfer_matrix': self.transfer_matrix,
                    'last_updated': datetime.now().isoformat(),
                }, f, indent=2)
            print(f"[MEMORY] Salva: {len(self.patterns)} padrões")
        except Exception as e:
            print(f"[MEMORY] Erro ao salvar: {e}")


if __name__ == '__main__':
    print("Módulo v58_memory carregado com sucesso.")
    mem = PatternMemory()
    print(f"Estatísticas: {json.dumps(mem.get_statistics(), indent=2)}")
