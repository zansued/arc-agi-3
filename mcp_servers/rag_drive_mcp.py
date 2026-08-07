#!/usr/bin/env python3
#/@BLACKGOV RAG Drive MCP Server
# Porta 8801 - Busca semantica em documentos do Google Drive

import json, sys, os, logging
from http.server import BaseHTTPRequestHandler
from mcp_sse_compat import make_mcp_server

HOST, PORT = "0.0.0.0", 8801
RAG_BASE = "/a0/usr/workdir/rag_drive_advanced"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("rag-mcp")

AVAILABLE_TOOLS = [
    {"name": "search_docs", "description": "Busca semantica nos documentos do Drive. Retorna trechos relevantes.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string", "description": "Texto para busca semantica"}, "k": {"type": "number", "description": "Numero de resultados (default: 5)"}}, "required": ["query"]}},
    {"name": "list_indexed", "description": "Lista os documentos atualmente indexados no RAG.", "inputSchema": {"type": "object", "properties": {"limit": {"type": "number", "description": "Max resultados (default: 20)"}}}},
    {"name": "get_rag_stats", "description": "Estatisticas do sistema RAG: total de documentos, chunks, ultima atualizacao.", "inputSchema": {"type": "object", "properties": {}}}
]

def handle_tool_call(name, args):
    sys.path.insert(0, RAG_BASE)
    if name == "search_docs":
        try:
            from intelligence_search import IntelligenceSearch
            searcher = IntelligenceSearch()
            results = searcher.search(query=args.get("query",""), k=args.get("k",5))
            return {"content": [{"type": "text", "text": json.dumps(results, indent=2, ensure_ascii=False)[:5000]}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Erro ao buscar: {e}"}]}
    elif name == "list_indexed":
        import glob
        files = glob.glob(f"{RAG_BASE}/data/**", recursive=True)
        files = [f for f in files if os.path.isfile(f)][:args.get("limit",20)]
        return {"content": [{"type": "text", "text": json.dumps(files, indent=2, ensure_ascii=False)[:5000]}]}
    elif name == "get_rag_stats":
        import glob
        all_files = glob.glob(f"{RAG_BASE}/**", recursive=True)
        py_files = [f for f in all_files if f.endswith('.py')]
        return {"content": [{"type": "text", "text": json.dumps({"total_arquivos": len(all_files), "scripts_python": len(py_files), "base": RAG_BASE}, indent=2)}]}
    return {"content": [{"type": "text", "text": f"Tool {name} not implemented"}], "isError": True}

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
            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "rag-drive-mcp", "version": "1.0.0"}}})
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
    log.info(f"RAG Drive MCP rodando em http://{HOST}:{PORT}")
    server.serve_forever()
