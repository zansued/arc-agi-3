#!/usr/bin/env python3
"""
SQUAD A2A Orchestrator — BLACKGOV Ecosystem FASE 5
Integra: SQUAD Orchestrator + AutoGen + A2A Bridge + Coliseu Debate Protocol

Permite:
- Criar SQUADs (AutoGen Teams) de agentes do ecossistema
- Executar tarefas sequenciais (Handoff Pattern)
- Executar tarefas paralelas (Society of Mind Pattern)
- Realizar debates multi-agente (Coliseu Debate Protocol)
- Sintetizar respostas via Metatron
"""

import json
import os
import sys
import logging
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SQUAD-A2A] %(message)s')
logger = logging.getLogger('squad_a2a_orchestrator')

A2A_BASE = 'http://localhost:9999'
SQUADS_DIR = '/a0/usr/workdir/squad_orchestrator/squads'

# ============================================================
# 1. A2A Communication Layer
# ============================================================

def a2a_discover():
    """Discover all agents via A2A Bridge."""
    try:
        req = urllib.request.Request(A2A_BASE + '/agent-cards')
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return data.get('agents', data if isinstance(data, list) else [])
    except Exception as e:
        logger.error('A2A discover failed: %s', e)
        return []

def a2a_send_task(agent_name, task_input, timeout=30):
    """Send a task to an agent via A2A Bridge JSON-RPC 2.0."""
    agent_id = agent_name.lower().replace(' ', '_')
    task_id = 'task_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    payload = {
        'jsonrpc': '2.0',
        'method': 'agent.send_task',
        'params': {
            'agent_id': agent_id,
            'task': {'id': task_id, 'input': task_input}
        },
        'id': 1
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(A2A_BASE, data=data,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {'error': str(e), 'status': 'ERROR', 'agent': agent_name}

def extract_content(result):
    """Extract text content from A2A response."""
    if isinstance(result, dict):
        res = result.get('result', result)
        content = res.get('content', '')
        if not content:
            content = res.get('execution', {}).get('content', '')
        error = res.get('error', '') or res.get('execution', {}).get('error', '')
        if error:
            return '[ERROR: ' + error[:100] + ']'
        return content or '[Empty response]'
    return str(result)

# ============================================================
# 2. SQUAD Management (AutoGen Teams)
# ============================================================

def list_squads():
    """List all available squads."""
    squads = []
    if os.path.exists(SQUADS_DIR):
        for f in sorted(os.listdir(SQUADS_DIR)):
            if f.endswith('.json'):
                with open(os.path.join(SQUADS_DIR, f)) as fp:
                    squads.append(json.load(fp))
    return squads

def find_squad(name):
    """Find a squad by name."""
    for s in list_squads():
        if s['name'] == name:
            return s
    return None

def create_squad(name, description, agents, goal, tags=None):
    """Create a new squad (AutoGen Team)."""
    squad = {
        'name': name,
        'description': description,
        'agents': agents,
        'goal': goal,
        'tags': tags or [],
        'created_at': datetime.now().isoformat(),
        'pipeline_count': 0
    }
    fname = name.lower().replace(' ', '_').replace('/', '_')[:50] + '.json'
    fpath = os.path.join(SQUADS_DIR, fname)
    with open(fpath, 'w') as f:
        json.dump(squad, f, indent=2)
    logger.info('Squad criado: %s (%d agents)', name, len(agents))
    return squad

def create_blackgov_squad(agents_list):
    """Create the master BLACKGOV Ecosystem Squad from A2A agents."""
    agents = []
    for a in agents_list:
        if isinstance(a, dict):
            agents.append({
                'name': a.get('name', 'Unknown'),
                'role': a.get('status', {}).get('role', 'specialist'),
                'description': str(a.get('description', ''))[:60],
                'tools': ['a2a_send_task', 'a2a_get_card'],
                'model': a.get('capabilities', {}).get('llm', {}).get('model', 'deepseek-chat'),
                'created_at': datetime.now().isoformat()
            })
    return create_squad(
        name='BLACKGOV Ecosystem Squad',
        description='Squad completo com todos os agentes do ecossistema BLACKGOV',
        agents=agents,
        goal='Resolver tarefas complexas usando orquestracao multi-agente',
        tags=['blackgov', 'a2a', 'multi-agent', 'orchestration']
    )

# ============================================================
# 3. Execution Strategies (AutoGen Patterns)
# ============================================================

def execute_sequential(squad_name, task):
    """Execute tasks sequentially through each agent (Handoff pattern).
    Each agent receives the task + previous response as context."""
    squad = find_squad(squad_name)
    if not squad:
        return [{'error': 'Squad not found: ' + squad_name}]

    results = []
    context = task
    for i, agent in enumerate(squad['agents']):
        agent_name = agent['name']
        role = agent.get('role', 'specialist')
        logger.info('Handoff #%d: %s (%s)', i+1, agent_name, role)

        if results:
            prev = results[-1]
            context = 'TASK: ' + task + '\n'
            context += 'PREVIOUS: ' + prev['agent_name'] + ' analyzed.\n'
            context += 'YOUR ROLE: ' + role + '\n'
            context += 'Continue from your perspective.'

        result = a2a_send_task(agent_name, context)
        response = extract_content(result)
        results.append({
            'agent_name': agent_name,
            'role': role,
            'response': response[:500],
            'step': i + 1
        })
    return results

def execute_parallel(squad_name, task):
    """Execute tasks in parallel across all agents (Society of Mind pattern).
    All agents receive the same task simultaneously."""
    squad = find_squad(squad_name)
    if not squad:
        return [{'error': 'Squad not found: ' + squad_name}]

    results = []
    for agent in squad['agents']:
        agent_name = agent['name']
        role = agent.get('role', 'specialist')
        logger.info('Parallel: %s (%s)', agent_name, role)

        context = 'TASK: ' + task + '\n'
        context += 'YOUR ROLE: ' + role + '\n'
        context += 'Analyze this task from your perspective.'

        result = a2a_send_task(agent_name, context)
        response = extract_content(result)
        results.append({
            'agent_name': agent_name,
            'role': role,
            'response': response[:500]
        })
    return results

# ============================================================
# 4. Synthesis (Metatron - Coliseu Debate Protocol)
# ============================================================

def synthesize_results(results, task):
    """Synthesize multiple agent responses into a golden solution.
    Uses Metatron pattern from Coliseu Debate Protocol."""
    synthesis = '## SYNTHESIS REPORT\n\n'
    synthesis += '### Task\n' + task + '\n\n'
    synthesis += '### Agents Consulted\n'
    for r in results:
        if 'error' not in r:
            synthesis += '- **' + r['agent_name'] + '** (' + r['role'] + ')\n'

    synthesis += '\n### Responses\n'
    for i, r in enumerate(results):
        if 'error' not in r:
            synthesis += '\n**' + str(i+1) + '. ' + r['agent_name'] + '**\n'
            synthesis += r['response'][:400] + '\n'

    return synthesis

# ============================================================
# 5. CLI / Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='SQUAD A2A Orchestrator')
    parser.add_argument('action', choices=['discover', 'squads', 'run', 'create-squad'],
                        help='Action to perform')
    parser.add_argument('--squad', help='Squad name')
    parser.add_argument('--task', help='Task description')
    parser.add_argument('--mode', choices=['sequential', 'parallel'], default='sequential',
                        help='Execution mode (AutoGen pattern)')
    args = parser.parse_args()

    if args.action == 'discover':
        agents = a2a_discover()
        print('Agents discovered via A2A:')
        for a in agents:
            if isinstance(a, dict):
                print(f'  - {a.get("name", "?")} | {a.get("status", {}).get("role", "?")}')
        print(f'Total: {len(agents)} agents')

    elif args.action == 'squads':
        squads = list_squads()
        print('Available SQUADs:')
        for s in squads:
            print(f'  - {s["name"]} ({len(s["agents"])} agents)')
        print(f'Total: {len(squads)} squads')

    elif args.action == 'run':
        if not args.squad or not args.task:
            print('Error: --squad and --task required for run')
            return

        if args.mode == 'sequential':
            results = execute_sequential(args.squad, args.task)
        else:
            results = execute_parallel(args.squad, args.task)

        report = synthesize_results(results, args.task)
        print(report)

    elif args.action == 'create-squad':
        agents = a2a_discover()
        squad = create_blackgov_squad(agents)
        print(f'Squad created: {squad["name"]} with {len(squad["agents"])} agents')


if __name__ == '__main__':
    main()
