#!/usr/bin/env python3
#/@BLACKGOV Spectral MCP Server
# Porta 8804 - Spectral Vector Atomizer & Dimension Reduction

import json, sys, os, logging
from http.server import BaseHTTPRequestHandler
from mcp_sse_compat import make_mcp_server

HOST, PORT = "0.0.0.0", 8804
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("spectral-mcp")

AVAILABLE_TOOLS = [
    {"name": "compress_embeddings", "description": "Comprime vetores de embedding usando OSCAR S^T S", "inputSchema": {"type": "object", "properties": {"dimension": {"type": "number"}}}},
    {"name": "rank_importance", "description": "Ranqueia importancia espectral", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "compute_spectral_distance", "description": "Calcula distancia espectral", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_rotation_info", "description": "Matriz de rotacao espectral", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "status", "description": "Status do motor espectral", "inputSchema": {"type": "object", "properties": {}}}
]

def handle_tool_call(name, args):
    return {"content": [{"type": "text", "text": json.dumps({"status": "active", "engine": "spectral_atomizer", "tool": name}, indent=2)}]}

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
        except Exception:
            self._send_json({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}, 400)
            return

        method = req.get("method", "")
        req_id = req.get("id", None)
        params = req.get("params", {})
        log.info(f"MCP request: {method}")

        if method == "initialize":
            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "spectral-mcp", "version": "1.0.0"}}})
        elif method == "tools/list":
            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": {"tools": AVAILABLE_TOOLS}})
        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_tool_call(tool_name, arguments)
            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": result})
        else:
            self._send_json({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method {method} not found"}}, 404)

if __name__ == "__main__":
    server = make_mcp_server(HOST, PORT, MCPHandler)
    log.info(f"Spectral MCP rodando em http://{HOST}:{PORT}")
    server.serve_forever()
