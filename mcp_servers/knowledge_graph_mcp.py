#!/usr/bin/env python3
"""
@BLACKGOV Knowledge Graph MCP Server

Servidor MCP interno para consulta ao Knowledge Graph do ecossistema.
6541 triplas SPO com dados de OSINT, CPF, CNPJ, subsistemas e conexoes.

Protocolo: MCP 2025-03-26 via HTTP JSON-RPC Streamable
Autor: @zansued
Ciclo: @BLACKGOV
Criado: 2026-05-02
"""

import json
import os
import sys
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from mcp_sse_compat import make_mcp_server
from urllib.parse import urlparse
from pathlib import Path

# Config
KG_FILE = "/a0/usr/workdir/knowledge_graph/data/triples_otimizado.jsonl"
HOST = "0.0.0.0"
PORT = 8800

# Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("kg-mcp")

# Carregar KG
log.info(f"Carregando KG de {KG_FILE}...")
TRIPLES = []
SUBJECTS = {}  # subject -> list of triples
OBJECTS = {}   # object -> list of triples
PREDICATES = set()

if os.path.exists(KG_FILE):
    with open(KG_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    t = json.loads(line)
                    TRIPLES.append(t)
                    s = t.get("subject", "")
                    p = t.get("predicate", "")
                    o = t.get("object", "")
                    if s not in SUBJECTS:
                        SUBJECTS[s] = []
                    SUBJECTS[s].append(t)
                    if o not in OBJECTS:
                        OBJECTS[o] = []
                    OBJECTS[o].append(t)
                    PREDICATES.add(p)
                except json.JSONDecodeError:
                    pass

log.info(f"KG carregado: {len(TRIPLES)} triplas, {len(SUBJECTS)} sujeitos, {len(PREDICATES)} predicados")

# Ferramentas disponiveis
AVAILABLE_TOOLS = [
    {
        "name": "search_entities",
        "description": "Busca entidades no Knowledge Graph por texto (nome, CPF, CNPJ, endereco, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texto para buscar (nome, CPF, CNPJ, etc.)"},
                "limit": {"type": "integer", "description": "Maximo de resultados", "default": 20}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_entity_relations",
        "description": "Retorna todas as relacoes de uma entidade especifica (subject ou object)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Nome da entidade (ex: 'Joao Silva', '123.456.789-00')"},
                "type": {"type": "string", "enum": ["subject", "object", "both"], "description": "Direcao da busca", "default": "both"}
            },
            "required": ["entity"]
        }
    },
    {
        "name": "get_stats",
        "description": "Retorna estatisticas do Knowledge Graph",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_all_predicates",
        "description": "Lista todos os tipos de relacao (predicados) disponiveis no KG",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "search_by_predicate",
        "description": "Busca triplas por tipo de relacao especifico",
        "inputSchema": {
            "type": "object",
            "properties": {
                "predicate": {"type": "string", "description": "Tipo de relacao (ex: tem_nome, tem_cpf, reside_em)"},
                "limit": {"type": "integer", "description": "Maximo de resultados", "default": 20}
            },
            "required": ["predicate"]
        }
    }
]

# Implementacao das ferramentas
def handle_tool_call(tool_name: str, arguments: dict) -> dict:
    """Executa a ferramenta chamada"""
    if tool_name == "search_entities":
        query = arguments.get("query", "").lower()
        limit = arguments.get("limit", 20)
        results = []
        for t in TRIPLES:
            s = str(t.get("subject", "")).lower()
            o = str(t.get("object", "")).lower()
            if query in s or query in o:
                results.append(t)
                if len(results) >= limit:
                    break
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "query": query,
                    "total": len(results),
                    "results": results
                }, indent=2, ensure_ascii=False)
            }]
        }

    elif tool_name == "get_entity_relations":
        entity = arguments.get("entity", "").lower()
        search_type = arguments.get("type", "both")
        results = []
        if search_type in ("subject", "both"):
            for s, triples in SUBJECTS.items():
                if entity in s.lower():
                    results.extend(triples)
        if search_type in ("object", "both"):
            for o, triples in OBJECTS.items():
                if entity in o.lower():
                    results.extend(triples)
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "entity": entity,
                    "total": len(results),
                    "relations": results
                }, indent=2, ensure_ascii=False)
            }]
        }

    elif tool_name == "get_stats":
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "total_triples": len(TRIPLES),
                    "total_subjects": len(SUBJECTS),
                    "total_objects": len(OBJECTS),
                    "total_predicates": len(PREDICATES),
                    "predicates": sorted(list(PREDICATES))
                }, indent=2, ensure_ascii=False)
            }]
        }

    elif tool_name == "get_all_predicates":
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "total": len(PREDICATES),
                    "predicates": sorted(list(PREDICATES))
                }, indent=2, ensure_ascii=False)
            }]
        }

    elif tool_name == "search_by_predicate":
        pred = arguments.get("predicate", "").lower()
        limit = arguments.get("limit", 20)
        results = [t for t in TRIPLES if t.get("predicate", "").lower() == pred][:limit]
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "predicate": pred,
                    "total": len(results),
                    "results": results
                }, indent=2, ensure_ascii=False)
            }]
        }

    return {
        "content": [{"type": "text", "text": f"Tool {tool_name} not found"}],
        "isError": True
    }


# MCP HTTP Handler (Streamable HTTP)
class MCPHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}, 400)
            return

        method = req.get("method", "")
        req_id = req.get("id", None)
        params = req.get("params", {})

        log.info(f"MCP request: {method}")

        if method == "initialize":
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "blackgov-kg-mcp",
                        "version": "1.0.0"
                    }
                }
            })
        elif method == "tools/list":
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": AVAILABLE_TOOLS
                }
            })
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_tool_call(tool_name, arguments)
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            })
        else:
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }, 404)

    def log_message(self, format, *args):
        log.info(f"{args[0]} {args[1]} {args[2]}")


def main():
    server = make_mcp_server(HOST, PORT, MCPHandler)
    log.info(f"KG MCP Server rodando em http://{HOST}:{PORT}")
    log.info(f"Tools disponiveis: {[t["name"] for t in AVAILABLE_TOOLS]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Server encerrado.")
        server.server_close()


if __name__ == "__main__":
    main()
