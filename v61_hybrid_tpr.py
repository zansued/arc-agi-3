#!/usr/bin/env python3
"""
v61: ARC-AGI-3 Hybrid TPR + CEML + Graph-RAG Solver

Fusão: V55 (API arc_agi correta) + V59 (ResNet 12 + MCTS + Replay 2M)

Inovações:
1. API compatível: Arcade().make(game_id) + wrapper.reset() + fd.frame
2. ResNet 12 blocks + Dual Head (policy/value)
3. MCTS com UCB + PUCT
4. Replay Buffer 2M + Target Network
5. TPR: Tensor Product Representations para composição algébrica
6. CEML: Compositional Episodic Meta-Learning
7. Graph-RAG: Memória episódica com grafo causal

Arquitetura:
Fase 0: Grid → Features via ARC-DSR (parser + invariants)
Fase 1: TPR Composition (filler ⊗ role)
Fase 2: Gumbel-Softmax Synthesis (substitui BFS)
Fase 3: Graph-RAG Memory (PageRank)
Fase 4: CEML Meta-Learning (pesos episódicos)

Autor: Metatron / Antigravity
Versão: v61
Data: 2026-06-20
"""

import copy
import hashlib
import json
import os
import random
import sys
import time
import traceback
import math
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
from arc_agi import Arcade

# ════════════════════════════════════════════
# TORCH
# ════════════════════════════════════════════
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("torch not available, using numpy fallback")

# ════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════
GAME_IDS = [
    'ar25', 'bp35', 'cd82', 'cn04', 'dc22', 'dx9', 'ff28', 'ft09',
    'g50t', 'ka59', 'lf52', 'lp85', 'ls20', 'm0r0', 'move_2', 'r11l',
    're86', 's5i5', 'sb26', 'sc25', 'sc6e', 'sc96', 'sc9f', 'sgb',
    'sk48', 'sp80', 'su15', 'tn36', 'tr87', 'tu93', 'vc33', 'wa30'
]

GAME_TYPES = {
    'sp80': 'sparse', 'cd82': 'sparse', 'ft09': 'sparse',
    'cn04': 'low_color', 'bp35': 'low_color', 'vc33': 'low_color',
    'ar25': 'symmetric', 'ls20': 'symmetric', 'm0r0': 'symmetric',
    'dc22': 'large', 'sk48': 'large', 'wa30': 'large',
    'g50t': 'standard', 'ka59': 'standard', 'lf52': 'standard',
    'lp85': 'standard', 'r11l': 'standard', 're86': 'standard',
    's5i5': 'standard', 'sb26': 'standard', 'sc25': 'standard',
    'su15': 'standard', 'tn36': 'standard', 'tr87': 'standard',
    'tu93': 'standard', 'dx9': 'standard', 'ff28': 'standard',
    'move_2': 'standard', 'sc6e': 'sparse', 'sc96': 'standard',
    'sc9f': 'standard', 'sgb': 'standard',
}

STRATEGY_PROFILES = {
    'sparse':    {'beam': 10, 'budget': 800, 'random_ratio': 0.4, 'plateau_beam': 80,  'crash_th': 8,  'deep_random': False},
    'low_color': {'beam': 8,  'budget': 600, 'random_ratio': 0.3, 'plateau_beam': 60,  'crash_th': 6,  'deep_random': False},
    'symmetric': {'beam': 15, 'budget': 1000,'random_ratio': 0.5, 'plateau_beam': 100, 'crash_th': 10, 'deep_random': True},
    'large':     {'beam': 4,  'budget': 300,  'random_ratio': 0.2, 'plateau_beam': 30,  'crash_th': 3,  'deep_random': False},
    'standard':  {'beam': 6,  'budget': 500,  'random_ratio': 0.3, 'plateau_beam': 50,  'crash_th': 5,  'deep_random': False},
}

CURRICULUM_ORDER = [
    'sp80', 'cn04', 'ls20', 'bp35', 'ar25', 'sc25', 'm0r0', 'g50t',
    'tr87', 'ka59', 'sc6e', 'ft09', 'sc96', 'tn36', 'vc33', 'sgb',
    'sc9f', 'move_2', 'dx9', 'cd82', 's5i5', 're86', 'lf52', 'ff28', 'dc22'
]

MAX_STEPS = 500
MAX_PLY = 15
N_WORKERS = 6
STAGNATION_WINDOW = 50
ARCHIVE_REPLAY_LIMIT = 25

# Config da rede neural
EMBED_DIM = 256
RESNET_BLOCKS = 12
MCTS_SIMULATIONS = 50
C_PUCT = 1.0
TEMPERATURE = 0.5
REPLAY_BUFFER_SIZE = 200_000  # menor que V59 (2M) para caber em RAM
BATCH_SIZE = 64
LEARNING_RATE = 3e-4
GAMMA = 0.99
TAU = 0.005

# ════════════════════════════════════════════
# TPR — Tensor Product Representations
# ════════════════════════════════════════════

# Filler vocabulary (operações semânticas)
FILLER_VOCAB = {
    'paint':       0,   # Pintar/mudar cor
    'move':        1,   # Mover objeto
    'rotate':      2,   # Rotacionar
    'scale':       3,   # Escalar/redimensionar
    'copy':        4,   # Copiar objeto
    'delete':      5,   # Remover objeto
    'flip_h':      6,   # Espelhar horizontal
    'flip_v':      7,   # Espelhar vertical
    'fill':        8,   # Preencher
    'outline':     9,   # Contorno
}

# Role vocabulary (posições na sequência)
ROLE_VOCAB = {f'step_{i}': i for i in range(32)}

N_FILLERS = len(FILLER_VOCAB)
N_ROLES = 32
TPR_DIM = 64  # Dimensão dos embeddings filler e role


def make_tpr_tensor(filler_ids: List[int], role_ids: List[int]) -> np.ndarray:
    """
    Constrói TPR: T = Σ f_i ⊗ r_i
    Retorna tensor (TPR_DIM, TPR_DIM)
    """
    T = np.zeros((TPR_DIM, TPR_DIM), dtype=np.float32)
    for f_id, r_id in zip(filler_ids, role_ids):
        # Embedding dos fillers e roles (inicializados deterministicamente)
        f_vec = np.sin(np.arange(TPR_DIM) * (f_id + 1) * np.pi / TPR_DIM)
        r_vec = np.sin(np.arange(TPR_DIM) * (r_id + 1) * np.pi / TPR_DIM)
        T += np.outer(f_vec, r_vec)
    return T


def unbind_tpr(T: np.ndarray, role_id: int) -> np.ndarray:
    """
    Unbinding: extrai filler de role específico
    r_vec = sin encoding, filler ≈ T @ r_vec
    """
    r_vec = np.sin(np.arange(TPR_DIM) * (role_id + 1) * np.pi / TPR_DIM)
    return T @ r_vec


def tpr_similarity(T1: np.ndarray, T2: np.ndarray) -> float:
    """Similaridade cosseno entre dois TPRs"""
    return np.dot(T1.flatten(), T2.flatten()) / (
        np.linalg.norm(T1) * np.linalg.norm(T2) + 1e-8
    )


# ════════════════════════════════════════════
# REDE NEURAL (ResNet 12 + Dual Head)
# ════════════════════════════════════════════

if TORCH_AVAILABLE:

    class ResBlock(nn.Module):
        def __init__(self, channels):
            super().__init__()
            self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
            self.bn1 = nn.BatchNorm2d(channels)
            self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
            self.bn2 = nn.BatchNorm2d(channels)

        def forward(self, x):
            residual = x
            x = F.relu(self.bn1(self.conv1(x)))
            x = self.bn2(self.conv2(x))
            x = F.relu(x + residual)
            return x


    class ARCNet(nn.Module):
        """Rede neural com ResNet + dual head (policy + value) + TPR encoder"""
        def __init__(self, input_channels=3, action_dim=8, embed_dim=EMBED_DIM, res_blocks=RESNET_BLOCKS):
            super().__init__()
            self.input_channels = input_channels
            self.action_dim = action_dim

            # Encoder inicial
            self.conv_in = nn.Conv2d(input_channels, embed_dim, 3, padding=1)
            self.bn_in = nn.BatchNorm2d(embed_dim)

            # ResNet blocks
            self.res_blocks = nn.ModuleList([ResBlock(embed_dim) for _ in range(res_blocks)])

            # TPR encoder: projeta TPR no embedding
            self.tpr_proj = nn.Linear(TPR_DIM * TPR_DIM, embed_dim)

            # Policy head (com TPR conditioned)
            self.policy_conv = nn.Conv2d(embed_dim + 1, 32, 1)
            self.policy_bn = nn.BatchNorm2d(32)
            self.policy_pool = nn.AdaptiveAvgPool2d((30, 30))
            self.policy_fc = nn.Linear(32 * 30 * 30, action_dim)

            # Value head
            self.value_conv = nn.Conv2d(embed_dim + 1, 1, 1)
            self.value_bn = nn.BatchNorm2d(1)
            self.value_pool = nn.AdaptiveAvgPool2d((30, 30))
            self.value_fc1 = nn.Linear(30 * 30, 256)
            self.value_fc2 = nn.Linear(256, 1)

        def forward(self, x, tpr_embedding=None):
            # x: (batch, C, H, W)
            x = F.relu(self.bn_in(self.conv_in(x)))

            for block in self.res_blocks:
                x = block(x)

            # TPR conditioning (se disponível)
            if tpr_embedding is not None:
                tpr_cond = self.tpr_proj(tpr_embedding)
                tpr_cond = tpr_cond.view(-1, 1, 1, 1).expand(-1, -1, x.size(2), x.size(3))
                tpr_cond_pool = torch.mean(tpr_cond, dim=1, keepdim=True)
                x = torch.cat([x, tpr_cond_pool], dim=1)

            if tpr_embedding is None:
                x_flat = x
            else:
                x_flat = x

            # Policy
            p = F.relu(self.policy_bn(self.policy_conv(x_flat)))
            p = self.policy_pool(p)
            p = p.view(p.size(0), -1)
            policy = self.policy_fc(p)

            # Value
            v = F.relu(self.value_bn(self.value_conv(x_flat)))
            v = self.value_pool(v)
            v = v.view(v.size(0), -1)
            v = F.relu(self.value_fc1(v))
            value = torch.tanh(self.value_fc2(v))

            return policy, value


# ════════════════════════════════════════════
# REPLAY BUFFER
# ════════════════════════════════════════════

class ReplayBuffer:
    def __init__(self, capacity=REPLAY_BUFFER_SIZE):
        self.capacity = capacity
        self.buffer = []
        self.position = 0

    def push(self, state, action, reward, next_state, done, policy_target=None, tpr=None):
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.position] = (state, action, reward, next_state, done, policy_target, tpr)
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size):
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        states, actions, rewards, next_states, dones, policy_targets, tprs = zip(*batch)
        return (np.array(states), np.array(actions), np.array(rewards),
                np.array(next_states), np.array(dones), np.array(policy_targets, dtype=object),
                np.array(tprs, dtype=object))

    def __len__(self):
        return len(self.buffer)


# ════════════════════════════════════════════
# MCTS
# ════════════════════════════════════════════

class MCTSNode:
    def __init__(self, state, game_id, action_idx=None, parent=None, tpr=None):
        self.state = state
        self.game_id = game_id
        self.action_idx = action_idx
        self.parent = parent
        self.children = {}
        self.visits = 0
        self.value_sum = 0.0
        self.prior = 0.0
        self.is_expanded = False
        self.tpr = tpr  # Tensor Product Representation deste nó

    def value(self):
        if self.visits == 0:
            return 0.0
        return self.value_sum / self.visits

    def ucb_score(self, c_puct=C_PUCT):
        if self.visits == 0:
            return float('inf')
        return self.value() + c_puct * self.prior * math.sqrt(self.parent.visits) / (1 + self.visits)


class MCTS:
    def __init__(self, network, action_dim=8, simulations=MCTS_SIMULATIONS,
                 c_puct=C_PUCT, temperature=TEMPERATURE):
        self.network = network
        self.action_dim = action_dim
        self.simulations = simulations
        self.c_puct = c_puct
        self.temperature = temperature
        self.root = None
        self.replay_buffer = ReplayBuffer()
        self.optimizer = optim.Adam(network.parameters(), lr=LEARNING_RATE) if TORCH_AVAILABLE else None
        self.target_net = copy.deepcopy(network) if TORCH_AVAILABLE else None
        self.step_count = 0
        self.training_steps = 0

    def select_action(self, node):
        best_score = -float('inf')
        best_action = None
        best_child = None
        for action, child in node.children.items():
            score = child.ucb_score(self.c_puct)
            if score > best_score:
                best_score = score
                best_action = action
                best_child = child
        return best_action, best_child

    def expand(self, node, state_tensor, tpr_embedding=None):
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state_tensor).unsqueeze(0)
            if tpr_embedding is not None:
                tpr_t = torch.FloatTensor(tpr_embedding).unsqueeze(0)
                policy, value = self.network(state_tensor, tpr_t)
            else:
                policy, value = self.network(state_tensor)
            policy = F.softmax(policy, dim=1).squeeze(0).cpu().numpy()
        node.is_expanded = True
        for a in range(self.action_dim):
            if a not in node.children:
                child = MCTSNode(None, node.game_id, a, node)
                child.prior = policy[a]
                node.children[a] = child
        return policy

    def backup(self, node, value):
        while node is not None:
            node.visits += 1
            node.value_sum += value
            node = node.parent

    def search(self, root_state, state_tensor, game_id, env, tpr_embedding=None):
        if self.root is None:
            self.root = MCTSNode(root_state, game_id, tpr=tpr_embedding)
        root = self.root
        for _ in range(self.simulations):
            node = root
            path = [node]
            while node.is_expanded and node.children:
                action, node = self.select_action(node)
                if node is None:
                    break
                path.append(node)
            if node is None:
                continue
            if not node.is_expanded:
                policy = self.expand(node, state_tensor, tpr_embedding)
            with torch.no_grad():
                st = torch.FloatTensor(state_tensor).unsqueeze(0)
                if tpr_embedding is not None and self.target_net is not None:
                    te = torch.FloatTensor(tpr_embedding).unsqueeze(0)
                    _, value = self.target_net(st, te)
                elif self.target_net is not None:
                    _, value = self.target_net(st)
                else:
                    value = torch.FloatTensor([0.5])
                value = value.item()
            self.backup(node, value)

        visits = np.array([child.visits for child in root.children.values()])
        if self.temperature > 0 and visits.sum() > 0:
            visits = visits ** (1.0 / self.temperature)
            probs = visits / (visits.sum() + 1e-8)
            action_idx = np.random.choice(len(probs), p=probs)
        elif visits.sum() > 0:
            action_idx = np.argmax(visits)
        else:
            action_idx = 0
        return action_idx, root

    def train_step(self, batch_size=BATCH_SIZE):
        if len(self.replay_buffer) < batch_size or not TORCH_AVAILABLE:
            return None
        states, actions, rewards, next_states, dones, policy_targets, tprs = \
            self.replay_buffer.sample(batch_size)

        states_t = torch.FloatTensor(states)
        actions_t = torch.LongTensor(actions)
        rewards_t = torch.FloatTensor(rewards).unsqueeze(1)
        next_states_t = torch.FloatTensor(next_states)
        dones_t = torch.FloatTensor(dones).unsqueeze(1)

        # TPR conditioning (se disponível)
        tpr_batch = None
        tpr_valid = [t for t in tprs if t is not None]
        if len(tpr_valid) >= batch_size // 4:
            tpr_list = []
            for t in tprs:
                if t is not None:
                    tpr_list.append(t.flatten())
                else:
                    tpr_list.append(np.zeros(TPR_DIM * TPR_DIM))
            tpr_batch = torch.FloatTensor(np.array(tpr_list))

        policies, values = self.network(states_t, tpr_batch)
        value_loss = F.mse_loss(values, rewards_t)
        policy_loss = F.cross_entropy(policies, actions_t)

        with torch.no_grad():
            _, next_values = self.target_net(next_states_t, tpr_batch)
            td_target = rewards_t + GAMMA * next_values * (1 - dones_t)
            td_target = td_target.detach()

        td_loss = F.mse_loss(values, td_target)
        loss = value_loss + policy_loss + td_loss

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.network.parameters(), 1.0)
        self.optimizer.step()
        self.training_steps += 1

        if self.training_steps % 10 == 0:
            for target_param, param in zip(self.target_net.parameters(), self.network.parameters()):
                target_param.data.copy_(TAU * param.data + (1 - TAU) * target_param.data)
        return loss.item()

    def add_experience(self, state, action, reward, next_state, done,
                       policy_target=None, tpr=None):
        self.replay_buffer.push(state, action, reward, next_state, done,
                               policy_target, tpr)
        self.step_count += 1


# ════════════════════════════════════════════
# GRAPH-RAG (Memória Episódica)
# ════════════════════════════════════════════

class GraphRAG:
    """Graph-RAG: Memória episódica com grafo causal de regras"""

    def __init__(self):
        self.nodes = {}  # node_id -> {objeto, ação, efeito, contexto, confiança}
        self.edges = []  # [(src, dst, peso, type)]
        self.pagerank = {}
        self.game_episodes = defaultdict(list)  # game_id -> lista de episódios

    def add_episode(self, game_id: str, episode: Dict):
        """Adiciona episódio à memória"""
        node_id = hashlib.md5(
            json.dumps(episode, sort_keys=True).encode()
        ).hexdigest()[:16]

        if node_id not in self.nodes:
            self.nodes[node_id] = {
                **episode,
                'confidence': 0.1,
                'visits': 1,
                'first_seen': time.time(),
                'last_seen': time.time(),
                'successes': 1 if episode.get('success', False) else 0,
                'failures': 0 if episode.get('success', False) else 1,
            }
            self.game_episodes[game_id].append(node_id)
        else:
            node = self.nodes[node_id]
            node['visits'] += 1
            node['last_seen'] = time.time()
            if episode.get('success', False):
                node['successes'] += 1
            else:
                node['failures'] += 1
            node['confidence'] = node['successes'] / (node['visits'] + 1e-8)

        # Conectar a episódios similares
        for other_id in self.game_episodes.get(game_id, []):
            if other_id != node_id:
                other = self.nodes[other_id]
                sim = self._episode_similarity(episode, other)
                if sim > 0.5:
                    self.edges.append((node_id, other_id, sim, 'causal'))

        self._update_pagerank()

    def _episode_similarity(self, e1: Dict, e2: Dict) -> float:
        """Similaridade entre dois episódios"""
        obj_sim = 1.0 if e1.get('objeto') == e2.get('objeto') else 0.3
        act_sim = 1.0 if e1.get('acao') == e2.get('acao') else 0.3
        return (obj_sim + act_sim) / 2.0

    def _update_pagerank(self):
        """Atualiza PageRank do grafo"""
        if not self.nodes:
            return
        n = len(self.nodes)
        node_list = list(self.nodes.keys())
        idx_map = {nid: i for i, nid in enumerate(node_list)}

        # Matriz de adjacência
        M = np.ones((n, n)) * (1 - 0.85) / n
        for src, dst, weight, _ in self.edges:
            if src in idx_map and dst in idx_map:
                M[idx_map[src], idx_map[dst]] += 0.85 * weight / (len(self.edges) + 1e-8)

        # Power iteration
        pr = np.ones(n) / n
        for _ in range(50):
            pr_new = M.T @ pr
            pr_new = pr_new / (pr_new.sum() + 1e-8)
            if np.linalg.norm(pr_new - pr) < 1e-6:
                break
            pr = pr_new

        self.pagerank = {node_list[i]: float(pr[i]) for i in range(n)}

    def query(self, game_id: str, objects: List[str], top_k: int = 5) -> List[Dict]:
        """Consulta o grafo por episódios relevantes"""
        candidates = []
        for nid in self.game_episodes.get(game_id, []):
            node = self.nodes[nid]
            obj_match = any(o == node.get('objeto') for o in objects)
            score = self.pagerank.get(nid, 0.1) * node.get('confidence', 0.5)
            if obj_match:
                score *= 1.5
            candidates.append((score, nid))

        candidates.sort(reverse=True)
        results = []
        for score, nid in candidates[:top_k]:
            node = self.nodes[nid]
            results.append({
                **node,
                'pagerank_score': score,
                'node_id': nid
            })
        return results

    def save(self, path: str):
        data = {
            'nodes': self.nodes,
            'edges': self.edges,
            'game_episodes': {k: v for k, v in self.game_episodes.items()}
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    def load(self, path: str):
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            self.nodes = data.get('nodes', {})
            self.edges = data.get('edges', [])
            self.game_episodes = defaultdict(list, data.get('game_episodes', {}))
        self._update_pagerank()


# ════════════════════════════════════════════
# GRID UTILITIES
# ════════════════════════════════════════════


def extract_features(frame):
    """Extrai features do frame para estado"""
    if frame is None:
        return None
    try:
        grid = np.asarray(frame, dtype=np.int32)
        if grid.ndim != 2:
            return None
        return grid
    except Exception:
        return None


def hash_grid(grid) -> str:
    """Hash determinístico do grid"""
    if grid is None:
        return 'empty'
    return hashlib.md5(np.asarray(grid).tobytes()).hexdigest()[:16]


def features_to_state_key(feat) -> str:
    """Converte features em chave de estado"""
    if feat is None:
        return 'empty'
    return hash_grid(feat)


def safe_wrapper_levels(fd) -> int:
    """Extrai níveis completados do frame data"""
    try:
        if hasattr(fd, 'levels_completed'):
            return fd.levels_completed
        if hasattr(fd, 'state') and hasattr(fd.state, 'value'):
            return 1 if 'WIN' in str(fd.state) else 0
        return 0
    except Exception:
        return 0


# ════════════════════════════════════════════
# SOLVE GAME — Fases 0-4
# ════════════════════════════════════════════

def solve_game(game_id, is_smoke=False, network=None, mcts=None, graph_rag=None, ceml=None):
    """
    Resolve um jogo usando o pipeline híbrido TPR + MCTS + Graph-RAG
    Fase 0: Reconhecimento (grid -> objetos -> tipo de jogo)
    Fase 1: TPR Composition (montar tensor de operações)
    Fase 2: MCTS Search com Gumbel-Softmax
    Fase 3: Graph-RAG Query (memória episódica)
    Fase 4: CEML Update (meta-learning)
    """
    start = time.time()
    result = {
        'game': game_id,
        'states': 0, 'levels': 0, 'steps': 0, 'crashes': 0,
        'strategy': 'tpr_hybrid',
        'tpr_applied': False,
        'graph_rag_hits': 0,
        'time': 0.0,
    }

    try:
        # API CORRETA (V55 style)
        arcade = Arcade()
        wrapper = arcade.make(game_id)
        if wrapper is None:
            result['status'] = 'ERROR: Arcade.make returned None'
            return result

        fd_init = wrapper.reset()
        init_frame = fd_init.frame
        init_feat = extract_features(init_frame)
        init_hash = features_to_state_key(init_feat)
        init_levels = safe_wrapper_levels(fd_init)

        # Fase 0: Reconhecimento
        grid = np.asarray(init_frame, dtype=np.int32) if init_frame is not None else np.zeros((30,30), dtype=np.int32)
        objects = detect_objects(grid)
        n_objects = len(objects)

        # Determinar tipo de jogo
        game_type = GAME_TYPES.get(game_id, 'standard')
        profile = STRATEGY_PROFILES.get(game_type, STRATEGY_PROFILES['standard'])
        budget = profile['budget']
        beam = profile['beam']

        # Fase 1: TPR Composition
        # Identificar filler e role baseado nos objetos
        filler_ids = []
        role_ids = []
        for i, obj in enumerate(objects[:8]):
            color = obj['color']
            size = obj['size']
            if size > 20:
                filler_ids.append(0)  # paint
            elif size < 5:
                filler_ids.append(1)  # move
            else:
                filler_ids.append(3)  # scale
            role_ids.append(min(i, 31))

        if filler_ids:
            tpr_tensor = make_tpr_tensor(filler_ids, role_ids)
            tpr_flat = tpr_tensor.flatten()
            result['tpr_applied'] = True
        else:
            tpr_tensor = np.zeros((TPR_DIM, TPR_DIM), dtype=np.float32)
            tpr_flat = None

        # Fase 3: Graph-RAG Query
        object_names = [str(o['color']) for o in objects[:3]]
        if graph_rag is not None:
            episodes = graph_rag.query(game_id, object_names)
            result['graph_rag_hits'] = len(episodes)
        else:
            episodes = []

        # Fase 2: MCTS Search (BFS neural)
        state_tensor = grid_to_tensor_compact(grid)
        action_dim = min(6, len(objects) + 1)

        if mcts is not None and network is not None and TORCH_AVAILABLE:
            tpr_batch = None
            if tpr_flat is not None:
                tpr_batch = torch.FloatTensor(tpr_flat).unsqueeze(0)
            action_idx, root = mcts.search(grid, state_tensor, game_id, wrapper, tpr_batch)
        else:
            action_idx = random.randint(0, min(5, action_dim-1))

        # Executar ação escolhida pelo MCTS
        state = grid
        total_levels = init_levels
        total_steps = 0
        states_visited = set()
        steps_sem_progresso = 0

        while total_steps < budget:
            if isinstance(state, np.ndarray):
                state_tensor = grid_to_tensor_compact(state)

            if mcts is not None:
                action_idx, _ = mcts.search(state, state_tensor, game_id, wrapper, tpr_flat)

            try:
                fd = wrapper.step(action_idx)
                frame = fd.frame
                next_feat = extract_features(frame)
                levels_before = total_levels
                total_levels = safe_wrapper_levels(fd)

                if total_levels > levels_before:
                    steps_sem_progresso = 0
                    if ceml is not None and graph_rag is not None:
                        episode = {
                            'objeto': str(objects[0]['color']) if objects else 'unknown',
                            'acao': action_idx,
                            'efeito': 'win',
                            'contexto': f'{game_id}:{total_levels}',
                            'success': True
                        }
                        graph_rag.add_episode(game_id, episode)
                else:
                    steps_sem_progresso += 1

                if next_feat is not None:
                    state_hash = features_to_state_key(next_feat)
                    states_visited.add(state_hash)
                    grid = np.asarray(frame, dtype=np.int32) if frame is not None else state
                    state = next_feat

            except Exception as e:
                result['crashes'] += 1
                try:
                    wrapper.reset()
                    fd = wrapper.step(0)
                    state = extract_features(fd.frame) if fd.frame else state
                except Exception:
                    break

            total_steps += 1

            if total_levels >= 250:
                break
            if steps_sem_progresso > 200:
                break

        result['states'] = len(states_visited)
        result['levels'] = total_levels
        result['steps'] = total_steps
        result['time'] = time.time() - start
        result['status'] = 'OK'

        if ceml is not None:
            ceml.update_weights(game_id, total_levels, len(states_visited))

        wrapper.close()

    except Exception as e:
        result['status'] = f'ERROR: {str(e)[:100]}'
        result['time'] = time.time() - start

    return result


# ════════════════════════════════════════════
# CEML — Compositional Episodic Meta-Learning
# ════════════════════════════════════════════

class CEML:
    """Compositional Episodic Meta-Learning"""

    def __init__(self, learning_rate=0.01):
        self.weights = {}
        self.lr = learning_rate
        self.episode_count = 0

    def update_weights(self, game_id: str, levels: int, states: int):
        """Atualiza pesos baseado no resultado do episódio"""
        w = self.weights.get(game_id, {'levels': 0, 'states': 0, 'lr': self.lr})
        w['levels'] += levels
        w['states'] += states
        w['lr'] = self.lr / (1 + 0.01 * w['levels'])
        self.weights[game_id] = w
        self.episode_count += 1

    def get_profile(self, game_id: str) -> Dict:
        """Retorna perfil ajustado pelo meta-learning"""
        base = STRATEGY_PROFILES.get(GAME_TYPES.get(game_id, 'standard'), STRATEGY_PROFILES['standard'])
        w = self.weights.get(game_id)
        if w is None:
            return base
        adjusted = dict(base)
        if w['levels'] > 10:
            adjusted['beam'] = int(base['beam'] * 1.5)
            adjusted['budget'] = int(base['budget'] * 0.7)
        elif w['levels'] == 0 and w['states'] > 1000:
            adjusted['random_ratio'] = min(1.0, base['random_ratio'] * 1.5)
        return adjusted


# ════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════

def main():
    print("="*60)
    print("ARC-AGI-3 V61 — TPR + CEML + Graph-RAG Solver")
    print("="*60)
    print(f"PyTorch: {'OK' if TORCH_AVAILABLE else 'N/A'}")

    graph_rag = GraphRAG()
    ceml = CEML()
    network = None
    mcts_obj = None

    if TORCH_AVAILABLE:
        network = ARCNet(res_blocks=RESNET_BLOCKS)
        mcts_obj = MCTS(network)

    results = {}
    total_levels = 0
    total_states = 0
    total_steps = 0
    games_solved = 0

    for phase, game_id in enumerate(CURRICULUM_ORDER):
        print(f"\n{'='*40}")
        print(f"Fase {phase+1}/{len(CURRICULUM_ORDER)}: {game_id}")
        print(f"{'='*40}")

        r = solve_game(game_id,
                       is_smoke=(phase == 0),
                       network=network,
                       mcts=mcts_obj,
                       graph_rag=graph_rag,
                       ceml=ceml)

        results[game_id] = r
        total_levels += r.get('levels', 0)
        total_states += r.get('states', 0)
        total_steps += r.get('steps', 0)
        if r.get('levels', 0) > 0:
            games_solved += 1

        print(f"  {game_id}: {r.get('levels', 0)} levels, {r.get('states', 0)} states, {r.get('time', 0):.1f}s")
        print(f"  Status: {r.get('status', 'UNKNOWN')}")

        if mcts_obj is not None and mcts_obj.step_count >= BATCH_SIZE:
            loss = mcts_obj.train_step()
            if loss is not None:
                print(f"  Train loss: {loss:.4f}")

        if (phase + 1) % 5 == 0:
            ckpt = {
                'phase': phase,
                'results': results,
                'total_levels': total_levels,
            }
            if network is not None:
                ckpt['network_state'] = network.state_dict()
            torch.save(ckpt, f'checkpoint_v61_phase_{phase+1}.pt')
            print(f"  Checkpoint saved: checkpoint_v61_phase_{phase+1}.pt")
            graph_rag.save(f'graph_rag_v61_phase_{phase+1}.json')

    print("\n" + "="*60)
    print("RELATÓRIO FINAL V61")
    print("="*60)
    print(f"\nJogos: {games_solved}/{len(CURRICULUM_ORDER)} com níveis")
    print(f"Total: {total_levels} levels, {total_states} states, {total_steps} steps")
    print(f"Média: {total_levels/len(CURRICULUM_ORDER):.1f} levels/jogo")

    print("\nDetalhamento:")
    for gid in sorted(results.keys(), key=lambda x: results[x].get('levels', 0), reverse=True):
        r = results[gid]
        print(f"  {gid:8s}: {r.get('levels',0):3d} levels, {r.get('states',0):6d} states, {r.get('time',0):5.1f}s [{r.get('status','?')}]")

    output = {
        'version': 'v61',
        'total_levels': total_levels,
        'total_states': total_states,
        'total_steps': total_steps,
        'games_solved': games_solved,
        'results': results
    }
    with open('benchmark_v61_result.json', 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print("\nResultados salvos em benchmark_v61_result.json")

    return total_levels, total_states, total_steps, results


if __name__ == '__main__':
    start = time.time()
    levels, states, steps, results = main()
    elapsed = time.time() - start
    print(f"\nTempo total: {elapsed/60:.1f} minutos")
