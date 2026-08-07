#!/a0/usr/workdir/.venv/bin/python3
"""Servidor Flask visual para sp80 Level 2 - play com mouse + teclado"""

import sys, os, io, base64, json
sys.path.insert(0, '/a0/usr/workdir')
os.chdir('/a0/usr/workdir/environment_files/sp80/589a99af')

from flask import Flask, render_template_string, jsonify, request
import numpy as np
from PIL import Image
import importlib.util

spec = importlib.util.spec_from_file_location('sp80_module', 'sp80.py')
sp80_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp80_module)

from arcengine import ActionInput, GameAction, GameState

app = Flask(__name__)

GAME = None

def render_frame_to_b64(frame_ndarray):
    """Converte frame 64x64 numpy array para base64 PNG colorido."""
    # Mapa de cores ARC-AGI
    COLORS = {
        0: (0, 0, 0),       # preto
        1: (0, 116, 217),    # azul
        2: (255, 65, 54),    # vermelho
        3: (46, 204, 64),    # verde
        4: (255, 220, 0),    # amarelo
        5: (170, 170, 170),  # cinza
        6: (240, 18, 190),   # rosa
        7: (255, 133, 27),   # laranja
        8: (127, 219, 255),  # azul claro
        9: (135, 12, 37),    # marrom
        10: (160, 80, 200),  # roxo
        11: (0, 200, 200),   # ciano
        12: (200, 0, 150),   # magenta
        13: (0, 150, 200),   # azul medio
        14: (200, 200, 0),   # amarelo escuro
        15: (255, 255, 255), # branco
    }
    default_color = (40, 40, 40)
    
    # Upscale 4x para visibilidade (64*4=256)
    scale = 4
    h, w = frame_ndarray.shape
    rgb = np.zeros((h * scale, w * scale, 3), dtype=np.uint8)
    
    for y in range(h):
        for x in range(w):
            val = int(frame_ndarray[y, x])
            color = COLORS.get(val, default_color)
            rgb[y*scale:(y+1)*scale, x*scale:(x+1)*scale] = color
    
    img = Image.fromarray(rgb, 'RGB')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    return b64

def reset_game():
    global GAME
    GAME = sp80_module.Sp80()
    GAME.set_level(1)
    return GAME

def get_frame():
    frame = GAME.camera.render(GAME.current_level.get_sprites())
    return frame

def game_state():
    frame = get_frame()
    b64 = render_frame_to_b64(frame)
    
    # Coletar informacoes do estado
    sink = [(s.x, s.y) for s in GAME.current_level.get_sprites_by_tag('sowlljgtjvn')]
    gotas = [(s.x, s.y) for s in GAME.current_level.get_sprites() if hasattr(s, 'tags') and 'liolfvkveqg' in s.tags]
    baldes = [(s.x, s.y) for s in GAME.mxdlffpzkc()]
    barra = (GAME.vsoxmtrhqt.x, GAME.vsoxmtrhqt.y, GAME.vsoxmtrhqt.width) if GAME.vsoxmtrhqt else None
    barra_nome = GAME.vsoxmtrhqt.name if GAME.vsoxmtrhqt else None
    
    return {
        'frame_b64': b64,
        'k': GAME.fahhoimkk,
        'dkv': GAME.dkvpswzsjg,
        'sel': barra_nome,
        'sel_pos': barra,
        'avangppqui': GAME.avangppqui,
        'yqejjfwwh': GAME.yqejjfwwh,
        'lyremoheq': GAME.lyremoheq,
        'sink': sink,
        'gotas': gotas,
        'baldes': baldes,
        'levels': GAME._score,
        'lvl_index': GAME._current_level_index,
        'state': GAME._state.name,
        'next_level': GAME._next_level,
        'steps': GAME.zlhbnhpcq,
    }

HTML = '''<!DOCTYPE html>
<html>
<head>
    <title>sp80 Level 2 - ARC-AGI 3</title>
    <style>
        body { font-family: monospace; background: #1a1a2e; color: #eee; text-align: center; padding: 20px; }
        h1 { color: #0ff; text-shadow: 0 0 10px #0ff; }
        #gamecanvas { border: 2px solid #0ff; cursor: crosshair; }
        .info { margin: 10px; font-size: 14px; }
        .info span { color: #0ff; }
        .controls { margin: 15px; }
        .controls kbd { background: #333; border: 1px solid #0ff; padding: 4px 8px; border-radius: 4px; color: #0ff; }
        button { background: #0ff; color: #000; border: none; padding: 8px 16px; margin: 5px; font-weight: bold; cursor: pointer; border-radius: 4px; }
        button:hover { background: #5ff; }
        #log { margin-top: 15px; padding: 10px; background: #111; border: 1px solid #333; border-radius: 5px; max-height: 200px; overflow-y: auto; text-align: left; font-size: 12px; }
        #log div { margin: 2px 0; }
        .victory { color: #0f0; font-weight: bold; text-shadow: 0 0 10px #0f0; font-size: 20px; }
    </style>
</head>
<body>
    <h1>🎮 sp80 Level 2 (k=2)</h1>
    <div id="stats" class="info">Carregando...</div>
    <canvas id="gamecanvas" width="256" height="256"></canvas>
    <div class="controls">
        <p><kbd>↑</kbd> <kbd>↓</kbd> <kbd>←</kbd> <kbd>→</kbd> Mover sprite | <kbd>Space</kbd> SPILL</p>
        <p><kbd>Click</kbd> no canvas = ACTION6 (selecionar palette)</p>
        <button onclick="reset()">🔄 RESET</button>
        <button onclick="step5()">💧 SPILL</button>
    </div>
    <div id="log">Bem vindo ao sp80 Level 2! Clique no canvas ou use teclas.</div>
    <script>
        const canvas = document.getElementById('gamecanvas');
        const ctx = canvas.getContext('2d');
        
        function updateState(data) {
            const stats = document.getElementById('stats');
            stats.innerHTML = `
                Estado: <span>${data.state}</span> | 
                Nivel: <span>${data.levels}/6</span> | 
                k=${data.k} | 
                Selecionado: <span>${data.sel||'None'}</span> (${data.sel_pos ? data.sel_pos.join(',') : ''}) |
                Baldes: <span>${data.baldes.length}</span> |
                Gotas: <span>${data.gotas.length}</span> |
                Steps: <span>${data.steps}</span>
            `;
            
            const img = new Image();
            img.onload = function() {
                ctx.drawImage(img, 0, 0);
            };
            img.src = 'data:image/png;base64,' + data.frame_b64;
            
            if (data.state === 'WIN' || data.next_level) {
                document.getElementById('log').innerHTML += '<div class="victory">🏆 VITORIA!</div>';
            }
        }
        
        function fetchState() {
            fetch('/state').then(r => r.json()).then(data => {
                updateState(data);
            });
        }
        
        function doAction(action_id, data) {
            const payload = { action_id: action_id };
            if (data) payload.data = data;
            fetch('/action', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(r => r.json()).then(res => {
                updateState(res);
                if (res.log) {
                    const log = document.getElementById('log');
                    log.innerHTML += '<div>' + res.log + '</div>';
                    log.scrollTop = log.scrollHeight;
                }
            });
        }
        
        function reset() {
            fetch('/reset').then(r => r.json()).then(data => {
                document.getElementById('log').innerHTML = '<div>🔁 Game resetado</div>';
                updateState(data);
            });
        }
        
        function step5() {
            doAction('ACTION5');
        }
        
        canvas.addEventListener('click', function(e) {
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            let x = Math.floor((e.clientX - rect.left) * scaleX / 4);  // scale=4
            let y = Math.floor((e.clientY - rect.top) * scaleY / 4);
            if (x < 0) x = 0; if (x > 63) x = 63;
            if (y < 0) y = 0; if (y > 63) y = 63;
            document.getElementById('log').innerHTML += `<div>Clique em (${x},${y})</div>`;
            doAction('ACTION6', {x: x, y: y});
        });
        
        document.addEventListener('keydown', function(e) {
            const keyMap = {
                'ArrowUp': 'ACTION1',
                'ArrowDown': 'ACTION2',
                'ArrowLeft': 'ACTION3',
                'ArrowRight': 'ACTION4',
                ' ': 'ACTION5',
            };
            const action = keyMap[e.key];
            if (action) {
                e.preventDefault();
                doAction(action);
            }
        });
        
        fetchState();
    </script>
</body>
</html>'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/state')
def state():
    return jsonify(game_state())

@app.route('/action', methods=['POST'])
def action():
    global GAME
    data = request.json
    action_id_str = data.get('action_id', 'RESET')
    action_data = data.get('data', {})
    
    action_id = getattr(GameAction, action_id_str, GameAction.RESET)
    
    ai = ActionInput(id=action_id, data=action_data)
    try:
        r = GAME.perform_action(ai)
        log = f"{action_id_str}: state={r.state.name} levels={r.levels_completed}"
    except Exception as e:
        log = f"ERRO: {e}"
    
    result = game_state()
    result['log'] = log
    return jsonify(result)

@app.route('/reset')
def reset():
    reset_game()
    return jsonify(game_state())

@app.route('/set_level/<int:level_index>')
def set_level(level_index):
    global GAME
    GAME = sp80_module.Sp80()
    GAME.set_level(min(level_index + 1, 5))
    return jsonify(game_state())

if __name__ == '__main__':
    reset_game()
    print('Servidor sp80 rodando em http://127.0.0.1:5000')
    app.run(host='0.0.0.0', port=5000, debug=False)
