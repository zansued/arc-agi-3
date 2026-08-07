#!/bin/bash
# Hermes Watchdog - verifica mission-supervisor.jsonl a cada execução
# Instalado como cron job para manter fluxo de conversa contínuo

WORKDIR="/a0/usr/workdir"
MISSION_FILE="$WORKDIR/mcp_state/mission-supervisor.jsonl"
FLAG_FILE="$WORKDIR/hermes_watchdog.last_entry"

cd "$WORKDIR" || exit 1

# Pega o último timestamp de Hermes no arquivo
LAST_HERMES=$(tail -1 "$MISSION_FILE" 2>/dev/null | python3 -c "
import sys,json
try:
    d = json.loads(sys.stdin.read().strip())
    if d.get('author') == 'hermes-gateway':
        print(d.get('timestamp', d.get('source_report_timestamp', 'unknown')))
    else:
        print('NONE')
except:
    print('ERROR')
" 2>/dev/null || echo "NONE")

# Só processa se for mensagem nova
if [ "$LAST_HERMES" = "NONE" ] || [ "$LAST_HERMES" = "ERROR" ]; then
    exit 0
fi

# Verificar se já processamos esta mensagem
if [ -f "$FLAG_FILE" ] && [ "$(cat "$FLAG_FILE")" = "$LAST_HERMES" ]; then
    exit 0
fi

# Registrar que processamos
echo "$LAST_HERMES" > "$FLAG_FILE"

# Log
echo "[$(date)] Nova mensagem Hermes: $LAST_HERMES" >> "$WORKDIR/hermes_watchdog.log"

# Extrair instruções e preparar resposta
python3 -c "
import json

with open('$MISSION_FILE') as f:
    lines = f.readlines()

# Pega última mensagem Hermes
for line in reversed(lines):
    line = line.strip()
    if not line: continue
    try:
        d = json.loads(line)
        if d.get('author') == 'hermes-gateway':
            msg = d.get('message', '')
            print(f'Processed Hermes guidance. Length: {len(msg)}')
            
            # Escreve instruções para o Agent Zero processar
            instructions = {
                'timestamp': '$(date -u +%Y-%m-%dT%H:%M:%SZ)',
                'kind': 'internal_dispatch',
                'author': 'hermes-watchdog',
                'source_timestamp': d.get('timestamp', 'unknown'),
                'message': 'Novas instruções Hermes disponíveis em mission-supervisor.jsonl'
            }
            with open('$WORKDIR/hermes_next_instructions.json', 'w') as f:
                json.dump(instructions, f)
            print('Instructions saved to hermes_next_instructions.json')
            break
    except:
        continue
" 2>&1 >> "$WORKDIR/hermes_watchdog.log"
