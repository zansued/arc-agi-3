#!/usr/bin/env python3
"""
ARC-ML v1 — Meta-Learner para ARC-AGI-3

Analisa código fonte, testa sequências no arcengine,
registra padrões, aprende com erros e gera novas hipóteses.

Ciclo: ANALISA → TESTA → ERRA → ANOTA → APRENDE → REPETE

Baseado em: 24 jogos locais, arcengine, V58 pattern_memory, recordings
Criado: 2026-07-16 13:30 BRT
"""

import os
import sys
import json
import re
import time
import importlib
from pathlib import Path

WORKDIR = Path('/a0/usr/workdir')
ENV_DIR = WORKDIR / 'environment_files'
PATTERN_FILE = WORKDIR / 'arc_ml_patterns.json'

class GameCodeAnalyzer:
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.game_path = self._find_path()

    def _find_path(self) -> Path | None:
        for folder in ENV_DIR.iterdir():
            if folder.is_dir() and folder.name == self.game_id:
                for sub in folder.iterdir():
                    if sub.is_dir:
                        py_file = sub / f"{self.game_id}.py"
                        if py_file.exists():
                            return sub
        return None

    def extract_level_config(self, level_index: int = 0) -> dict:
        from arcengine import ActionInput, GameAction
        sys.path.insert(0, str(self.game_path))
        mod = importlib.import_module(self.game_id)
        cls_name = self.game_id[0].upper() + self.game_id[1:]
        cls = getattr(mod, cls_name)
        instance = cls()
        instance.set_level(level_index)
        config = {
            'rotation': instance.fahhoimkk,
            'steps': instance.zlhbnhpcq,
            'bars': [], 'pipes': [], 'buckets': [], 'dividers': [],
        }
        for s in instance.current_level.get_sprites():
            tags = s.tags or []
            if 'plzwjbfyfli' in tags:
                config['bars'].append({'x': s.x, 'y': s.y, 'w': s.width, 'name': s.name})
            if 'liolfvkveqg' in tags:
                config['pipes'].append({'x': s.x, 'y': s.y})
            if 'repwkzbkhxl' in tags:
                config['buckets'].append({'x': s.x, 'y': s.y})
            if 'tuvkdkhdokr' in tags:
                config['dividers'].append({'x': s.x, 'y': s.y, 'w': s.width})
        return config

class ArcengineSimulator:
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.game_path = self._find_path()
        self._instance = None
        self._setup_import()

    def _find_path(self) -> Path | None:
        for folder in ENV_DIR.iterdir():
            if folder.is_dir() and folder.name == self.game_id:
                for sub in folder.iterdir():
                    if sub.is_dir:
                        py_file = sub / f"{self.game_id}.py"
                        if py_file.exists():
                            return sub
        return None

    def _setup_import(self):
        if self.game_path:
            sys.path.insert(0, str(self.game_path))

    def load_level(self, level_index: int = 0):
        from arcengine import ActionInput, GameAction
        mod = importlib.import_module(self.game_id)
        cls_name = self.game_id[0].upper() + self.game_id[1:]
        cls = getattr(mod, cls_name)
        self._instance = cls()
        self._instance.set_level(level_index)
        self.GameAction = GameAction
        self.ActionInput = ActionInput
        return self._instance

    def execute_sequence(self, sequence: list[str], level_index: int = 0) -> dict:
        if not self._instance:
            self.load_level(level_index)
        game = self._instance
        for action in sequence:
            action = action.strip()
            if action.startswith('CLICK('):
                coords = action[6:-1].split(',')
                x, y = int(coords[0]), int(coords[1])
                game.perform_action(self.ActionInput(id=self.GameAction.ACTION6, data={'x': x, 'y': y}))
            elif action == 'LEFT':
                game.perform_action(self.ActionInput(id=self.GameAction.ACTION3))
            elif action == 'RIGHT':
                game.perform_action(self.ActionInput(id=self.GameAction.ACTION4))
            elif action == 'UP':
                game.perform_action(self.ActionInput(id=self.GameAction.ACTION1))
            elif action == 'DOWN':
                game.perform_action(self.ActionInput(id=self.GameAction.ACTION2))
            elif action == 'SPILL':
                game.perform_action(self.ActionInput(id=self.GameAction.ACTION5))
        return {
            'success': game.yqejjfwwh if hasattr(game, 'yqejjfwwh') else False,
            'buckets_filled': len(game.cevwbinfgl) if hasattr(game, 'cevwbinfgl') else 0,
            'total_buckets': len(game.current_level.get_sprites_by_tag('repwkzbkhxl')),
            'steps_remaining': game.zlhbnhpcq if hasattr(game, 'zlhbnhpcq') else 0,
        }

class PatternRecorder:
    def __init__(self):
        self.patterns = self._load()

    def _load(self) -> dict:
        if PATTERN_FILE.exists():
            with open(PATTERN_FILE) as f:
                return json.load(f)
        return {'games': {}, 'bugs': [], 'last_updated': None}

    def save(self):
        self.patterns['last_updated'] = time.time()
        with open(PATTERN_FILE, 'w') as f:
            json.dump(self.patterns, f, indent=2)

    def register_result(self, game_id: str, level: int, sequence: list[str], result: dict):
        if game_id not in self.patterns['games']:
            self.patterns['games'][game_id] = {'total_tests': 0, 'wins': 0, 'levels': {}}
        g = self.patterns['games'][game_id]
        g['total_tests'] += 1
        if result.get('success'):
            g['wins'] += 1
        lk = str(level)
        if lk not in g['levels']:
            g['levels'][lk] = {'tests': 0, 'wins': 0, 'sequences': []}
        lv = g['levels'][lk]
        lv['tests'] += 1
        if result.get('success'):
            lv['wins'] += 1
            lv['sequences'].append({'sequence': sequence, 'result': result, 'ts': time.time()})
        self.save()

class MetaController:
    def __init__(self, game_id: str):
        self.game_id = game_id
        self.analyzer = GameCodeAnalyzer(game_id)
        self.simulator = ArcengineSimulator(game_id)
        self.recorder = PatternRecorder()

    def analyze(self, level: int = 0) -> dict:
        config = self.analyzer.extract_level_config(level)
        print(f'Rotation: {config.get("rotation")}')
        print(f'Steps: {config.get("steps")}')
        for k in ['bars', 'pipes', 'buckets', 'dividers']:
            print(f'{k}: {len(config.get(k, []))}')
        return config

    def test(self, sequence: list[str], level: int = 0, source: str = 'generated') -> dict:
        self.simulator.load_level(level)
        result = self.simulator.execute_sequence(sequence, level)
        self.recorder.register_result(self.game_id, level, sequence, result)
        return result

if __name__ == '__main__':
    print('=== ARC-ML v1 ===')
    print('\n--- Analisando SP80 Level 5 ---')
    ml = MetaController('sp80')
    config = ml.analyze(level=4)
    if 'error' in config:
        print(f'ERRO: {config["error"]}')
        sys.exit(1)
    print(f'\nConfig OK: {len(config.get("bars",[]))} bars')
    if config.get('rotation') == 2:
        seq = [
            'CLICK(8,5)', 'LEFT','LEFT','LEFT','LEFT', 'UP','UP',
            'CLICK(11,9)', 'RIGHT','RIGHT','RIGHT','RIGHT', 'UP','UP','UP','UP',
            'CLICK(2,9)', 'LEFT','LEFT',
            'CLICK(7,13)', 'LEFT',
            'SPILL'
        ]
        r = ml.test(seq, level=4, source='human')
        print(f'Result: success={r["success"]}, buckets={r["buckets_filled"]}/{r["total_buckets"]}')
    print(f'\nSaved patterns to {PATTERN_FILE}')