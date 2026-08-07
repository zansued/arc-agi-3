#!/usr/bin/env python3
"""
Compatibilidade universal SSE com MCP SDK 1.27 para todos os MCPs locais.
Intercepta do_POST e redireciona qualquer wfile.write de resposta JSON-RPC
para a fila de eventos SSE da sessão.

Autor: @zansued
Ciclo: @BLACKGOV
Criado: 2026-08-05
"""

import json
import time
import uuid
import queue
import logging
import urllib.parse
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("mcp_sse_compat")

SESSIONS = {}

class DummyWFile:
    def __init__(self):
        self.buffer = io.BytesIO()
    def write(self, data):
        self.buffer.write(data)
    def flush(self):
        pass
    def getvalue(self):
        return self.buffer.getvalue()

def install_sse(handler_cls):
    orig_do_post = getattr(handler_cls, "do_POST")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip("/") not in ("/mcp", ""):
            self.send_error(404, "Not Found")
            return

        session_id = uuid.uuid4().hex
        msg_queue = queue.Queue()
        SESSIONS[session_id] = msg_queue

        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            endpoint_evt = f"event: endpoint\ndata: /mcp?session_id={session_id}\n\n"
            self.wfile.write(endpoint_evt.encode("utf-8"))
            self.wfile.flush()

            while True:
                try:
                    msg = msg_queue.get(timeout=15.0)
                    msg_str = json.dumps(msg)
                    sse_evt = f"event: message\ndata: {msg_str}\n\n"
                    self.wfile.write(sse_evt.encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            SESSIONS.pop(session_id, None)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed.query)
        session_id = query_params.get("session_id", [None])[0]

        real_wfile = self.wfile
        dummy_wfile = DummyWFile()
        self.wfile = dummy_wfile

        orig_send_response = self.send_response
        orig_send_header = self.send_header
        orig_end_headers = self.end_headers

        self.send_response = lambda code, message=None: None
        self.send_header = lambda keyword, value: None
        self.end_headers = lambda: None

        try:
            orig_do_post(self)
        finally:
            self.wfile = real_wfile
            self.send_response = orig_send_response
            self.send_header = orig_send_header
            self.end_headers = orig_end_headers

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")

        raw_written = dummy_wfile.getvalue()
        if raw_written:
            self.send_header("Content-Length", str(len(raw_written)))
            self.end_headers()
            self.wfile.write(raw_written)
            self.wfile.flush()
        else:
            # Notification (no id): no body required.
            self.send_header("Content-Length", "0")
            self.end_headers()

        if raw_written:
            try:
                res_obj = json.loads(raw_written.decode("utf-8"))
                if session_id and session_id in SESSIONS:
                    SESSIONS[session_id].put(res_obj)
                else:
                    for q in list(SESSIONS.values()):
                        q.put(res_obj)
                        break
            except Exception as e:
                log.error(f"Error parsing POST response body: {e}")

    handler_cls.do_GET = do_GET
    handler_cls.do_POST = do_POST
    handler_cls._mcp_sse_installed = True

def make_mcp_server(host, port, handler_cls):
    install_sse(handler_cls)
    return ThreadingHTTPServer((host, port), handler_cls)

__all__ = ["install_sse", "make_mcp_server", "ThreadingHTTPServer"]
