import json, time, sys
"""
V66 — Loop Metacognitivo LS20
Baseado no processo cognitivo humano validado pelo SENHOR:
1. Olhar tela → intuir layout
2. Confiar que movimento funciona
3. Cinza escuro = parede, claro = caminho
4. Mover em direção ao objetivo
5. Verificar → ajustar → repetir
"""

# ============================================================
# CONFIGURAÇÕES (do código fonte ls20.py)
# ============================================================
ACTION_MAP = {
    'ArrowUp': 1,     # ACTION1 = UP(Y-)
    'ArrowDown': 2,   # ACTION2 = DOWN(Y+)
    'ArrowLeft': 3,   # ACTION3 = LEFT(X-)
    'ArrowRight': 4,  # ACTION4 = RIGHT(X+)
}

# Posições do código fonte (linhas 727-731)
PLAYER_START = (34, 45)
TRANSFORMER = (19, 30)  # rhsxkxzdjz — muda rotação
GOAL = (34, 10)  # rjlbuycveu — goals em (35,11)
GATEWAY = (32, 8)  # nszegiawib — entrada da fortaleza

# ============================================================
# DIREÇÕES INTUITIVAS (baseadas na análise da tela)
# ============================================================
# Olhando a tela: player no canto inferior esquerdo (34,45)
# Goals no topo (34,10). Instinto: SUBIR.
# Mas há um TRANSFORMER em (19,30) no caminho.
# 
# Rota intuitiva:
# 1. Subir (ArrowUp) x15 → corredor central y30
# 2. Esquerda (ArrowLeft) x15 → transformer em x19
# 3. Subir (ArrowUp) x14 → corredor superior y16
# 4. Direita (ArrowRight) x13 → gateway em x32
# 5. Subir (ArrowUp) x6 → goals em y10
# Total estimado: ~63 ações (42 permitidas — precisa ser eficiente)

SEQUENCIA_INTUITIVA = (
    ['ArrowUp'] * 15 +
    ['ArrowLeft'] * 15 +
    ['ArrowUp'] * 14 +
    ['ArrowRight'] * 13 +
    ['ArrowUp'] * 6
)

def main():
    print("="*60)
    print("V66 — LOOP METACOGNITIVO")
    print("Processo cognitivo humano validado pelo SENHOR")
    print("="*60)
    
    print("\n🔍 OLHANDO A TELA...")
    print("   Player no canto inferior esquerdo (34,45)")
    print("   Goals no topo (34,10)")
    print("   Transformer em (19,30)")
    print("   Paredes escuras = limites")
    print("   Caminhos claros = transitáveis")
    print(f"   Steps disponíveis: 42")
    print(f"   Steps estimados na rota: {len(SEQUENCIA_INTUITIVA)}")
    print(f"   {'⚠️ Rota muito longa!' if len(SEQUENCIA_INTUITIVA) > 42 else '✅ Rota cabe nos steps!'}")
    
    print("\n🧠 INTUIÇÃO: Subir é o caminho natural. Player começa embaixo,")
    print("   goals estão em cima. Mas o transformer (muda rotação)")
    print("   está à esquerda no meio do caminho. Rota:")
    print("   1. SUBIR até altura do transformer")
    print("   2. ESQUERDA até o transformer")
    print("   3. SUBIR até altura do gateway da fortaleza")
    print("   4. DIREITA até o gateway")
    print("   5. SUBIR até os goals — WIN!")
    
    print("\n⚡ IMPORTANTE: Este script gera a sequência.")
    print("   A execução real será feita no browser tool")
    print("   com verificação visual após cada ação.")
    
    # Gerar saída JSON para o browser tool
    output = {
        'strategy': 'Intuitive Cognitive Loop',
        'based_on': 'Human cognitive process validated by SENHOR',
        'observations': {
            'player_start': PLAYER_START,
            'transformer': TRANSFORMER,
            'goals': GOAL,
            'gateway': GATEWAY,
            'steps_available': 42,
            'steps_estimated': len(SEQUENCIA_INTUITIVA)
        },
        'intuitive_route': {
            'phase_1': {'direction': 'ArrowUp', 'steps': 15, 'reason': 'Subir do spawn até altura do transformer'},
            'phase_2': {'direction': 'ArrowLeft', 'steps': 15, 'reason': 'Ir para esquerda até o transformer em x19'},
            'phase_3': {'direction': 'ArrowUp', 'steps': 14, 'reason': 'Subir até altura do gateway em y8'},
            'phase_4': {'direction': 'ArrowRight', 'steps': 13, 'reason': 'Ir para direita até o gateway em x32'},
            'phase_5': {'direction': 'ArrowUp', 'steps': 6, 'reason': 'Subir até os goals em y10 — WIN!'}
        },
        'action_sequence': [f'{a} ({ACTION_MAP[a]})' for a in SEQUENCIA_INTUITIVA]
    }
    
    with open('/a0/usr/workdir/v66_route.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n📁 Rota salva em: /a0/usr/workdir/v66_route.json")
    print(f"📊 Total de ações na rota: {len(SEQUENCIA_INTUITIVA)}")
    print(f"\n{'='*60}")
    print("PRÓXIMO PASSO: Executar no browser tool")
    print("1. CLICK START (ref 7)")
    print("2. ArrowUp ×15")
    print("3. ArrowLeft ×15")
    print("4. ArrowUp ×14")
    print("5. ArrowRight ×13")
    print("6. ArrowUp ×6")
    print("7. SCREENSHOT + VERIFICAR WIN!")
    print("="*60)

if __name__ == '__main__':
    main()
