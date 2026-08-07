#!/usr/bin/env python3
#/@BLACKGOV PaperClip MCP Server
# Porta 8802 - Paperclip Zero Task & Employee Management

import json, sys, os, logging, sqlite3
from http.server import BaseHTTPRequestHandler
from mcp_sse_compat import make_mcp_server

HOST, PORT = "0.0.0.0", 8802
WORKDIR = "/a0/usr/workdir"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("paperclip-mcp")

AVAILABLE_TOOLS = [
    {"name": "get_employees", "description": "Lista employees do PaperClip Zero", "inputSchema": {"type": "object", "properties": {"limit": {"type": "number", "description": "Max resultados (default: 20)"}}}},
    {"name": "get_work_items", "description": "Lista work items da fila", "inputSchema": {"type": "object", "properties": {"status": {"type": "string", "description": "Status filter (pending/done/all)"}, "limit": {"type": "number", "description": "Max resultados"}}}},
    {"name": "get_budgets", "description": "Lista budgets configurados", "inputSchema": {"type": "object", "properties": {"limit": {"type": "number"}}}},
    {"name": "get_stats", "description": "Estatisticas do PaperClip Zero", "inputSchema": {"type": "object", "properties": {}}}
]

def handle_tool_call(name, args):
    db_path = f"{WORKDIR}/paperclip_zero/paperclip.db" if os.path.exists(f"{WORKDIR}/paperclip_zero/paperclip.db") else None
    if name == "get_employees":
        if not db_path: return {"content": [{"type": "text", "text": "DB Paperclip nao encontrado"}]}
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, name, role, status FROM employees LIMIT ?", (args.get("limit", 20),))
            rows = cur.fetchall()
            conn.close()
            return {"content": [{"type": "text", "text": json.dumps(rows, indent=2)}]}
        except Exception as e: return {"content": [{"type": "text", "text": f"Erro DB: {e}"}]}
    elif name == "get_work_items":
        if not db_path: return {"content": [{"type": "text", "text": "DB Paperclip nao encontrado"}]}
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, title, status, priority FROM work_items LIMIT ?", (args.get("limit", 20),))
            rows = cur.fetchall()
            conn.close()
            return {"content": [{"type": "text", "text": json.dumps(rows, indent=2)}]}
        except Exception as e: return {"content": [{"type": "text", "text": f"Erro DB: {e}"}]}
    elif name == "get_budgets":
        return {"content": [{"type": "text", "text": json.dumps({"active_budget": "$100.00", "currency": "USD"}, indent=2)}]}
    elif name == "get_stats":
        return {"content": [{"type": "text", "text": json.dumps({"status": "active", "db": db_path}, indent=2)}]}
    return {"content": [{"type": "text", "text": f"Tool {name} not found"}], "isError": True}

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
            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "paperclip-mcp", "version": "1.0.0"}}})
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
    log.info(f"PaperClip MCP rodando em http://{HOST}:{PORT}")
    server.serve_forever()
