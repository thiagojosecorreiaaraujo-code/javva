# -*- coding: utf-8 -*-
"""Imita a API da Anthropic para provar o Javva sem gastar credito.

- POST /v1/messages        -> SSE (stream=true) com pausas entre eventos,
                              para provar que o Javva NAO bufferiza; ou JSON.
- POST /v1/messages/count_tokens -> {"input_tokens": 42}
- GET  /_pedidos           -> o que chegou aqui (caminho, query, cabecalhos
                              relevantes, modelo) para as assercoes.
Exige x-api-key == "chave-falsa-de-teste" (a credencial que o Javva injeta).
"""
import json
import uuid
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CHAVE = "chave-falsa-de-teste"
TEXTO = ["JAVVA", " OK"]
PEDIDOS = []


def _textos(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return [c]
    return [b.get("text", "") for b in c or [] if b.get("type") == "text"]


def tem_imagem(d):
    for m in d.get("messages") or []:
        c = m.get("content")
        if isinstance(c, list) and any(b.get("type") == "image" for b in c):
            return True
    return False


def decidir(d):
    """('ferramenta', nome, args) ou ('texto', resposta)."""
    msgs = d.get("messages") or []
    # O Claude Code anexa uma mensagem role=system DEPOIS da do usuario:
    # a "ultima" nao e a do usuario.
    doUsuario = [m for m in msgs if m.get("role") == "user"]
    ultimo = doUsuario[-1] if doUsuario else {}
    c = ultimo.get("content")
    if isinstance(c, list):
        for b in c:
            if b.get("type") == "tool_result":
                saida = b.get("content")
                if isinstance(saida, list):
                    saida = " ".join(x.get("text", "") for x in saida)
                return ("texto", "RESULTADO DO CLIENTE: " + str(saida))
    pedido = " ".join(_textos(ultimo)).lower()
    nomes = [t.get("name", "") for t in d.get("tools") or []]
    exe = next((n for n in nomes if n.endswith("__executar")), None)
    if "quem e voce" in pedido:
        return ("texto", "Sou o Claude Opus, criado pela Anthropic.")
    if "rode o teste" in pedido and exe:
        return ("ferramenta", exe,
                {"comando": "Write-Output ('JAVVA-CLIENTE-' + 'OK em ' + $env:COMPUTERNAME)"})
    return ("texto", "JAVVA OK" + (" (foto recebida)" if tem_imagem(d) else ""))


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, status, obj, extra=None):
        corpo = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(corpo)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _sse_ferramenta(self, modelo, nome, args):
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("connection", "close")
        self.end_headers()
        evs = [
            {"type": "message_start", "message": {
                "id": "msg_falso_t", "type": "message", "role": "assistant",
                "model": modelo, "content": [], "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 20, "output_tokens": 1}}},
            {"type": "content_block_start", "index": 0, "content_block": {
                "type": "tool_use", "id": "toolu_falso_" + uuid.uuid4().hex[:12], "name": nome,
                "input": {}}},
            {"type": "content_block_delta", "index": 0, "delta": {
                "type": "input_json_delta", "partial_json": json.dumps(args)}},
            {"type": "content_block_stop", "index": 0},
            {"type": "message_delta", "delta": {"stop_reason": "tool_use",
                                                "stop_sequence": None},
             "usage": {"output_tokens": 9}},
            {"type": "message_stop"},
        ]
        for ev in evs:
            self.wfile.write(
                ("event: %s\ndata: %s\n\n" % (ev["type"], json.dumps(ev)))
                .encode())
            self.wfile.flush()
        self.close_connection = True

    def do_GET(self):
        if self.path == "/_pedidos":
            return self._json(200, PEDIDOS)
        self._json(404, {"type": "error", "error": {"type": "not_found_error",
                                                    "message": "falso"}})

    def do_POST(self):
        n = int(self.headers.get("content-length") or 0)
        corpo = self.rfile.read(n) if n else b""
        try:
            d = json.loads(corpo or b"{}")
        except ValueError:
            d = {}
        caminho, _, query = self.path.partition("?")
        PEDIDOS.append({
            "caminho": caminho, "query": query,
            "x_api_key": self.headers.get("x-api-key"),
            "authorization": self.headers.get("authorization"),
            "anthropic_version": self.headers.get("anthropic-version"),
            "anthropic_beta": self.headers.get("anthropic-beta"),
            "modelo": d.get("model"), "stream": d.get("stream"),
            "ultima_crua": json.dumps((d.get("messages") or [{}])[-1])[:1500],
            "sistema_ultracode": "ultracode" in json.dumps(d.get("system") or "").lower()
            or "ultracode" in json.dumps(d.get("messages") or "").lower(),
            "sistema_eclipse": "DENTRO do Eclipse IDE" in json.dumps(d.get("system") or "", ensure_ascii=False),
            "effort": json.dumps({k: d[k] for k in ("thinking", "output_config")
                                  if k in d})[:300],
            "historico": " | ".join(
                " ".join(_textos(m)) for m in d.get("messages") or []
                if m.get("role") == "user")[-3000:],
            "tem_imagem": tem_imagem(d), "ferramentas": [
                t.get("name") for t in d.get("tools") or []][:20],
        })
        aut = self.headers.get("authorization") or ""
        if self.headers.get("x-api-key") != CHAVE and aut != "Bearer " + CHAVE:
            return self._json(401, {"type": "error", "error": {
                "type": "authentication_error",
                "message": "invalid x-api-key"}})
        if caminho == "/v1/messages/count_tokens":
            return self._json(200, {"input_tokens": 42})
        if caminho != "/v1/messages":
            return self._json(404, {"type": "error", "error": {
                "type": "not_found_error", "message": caminho}})
        modelo = d.get("model", "claude-falso")
        plano = decidir(d)
        if plano[0] == "ferramenta":
            return self._sse_ferramenta(modelo, plano[1], plano[2])
        texto = plano[1]
        if not d.get("stream"):
            return self._json(200, {
                "id": "msg_falso", "type": "message", "role": "assistant",
                "model": modelo, "stop_reason": "end_turn",
                "content": [{"type": "text", "text": texto}],
                "usage": {"input_tokens": 11, "output_tokens": 3}},
                {"anthropic-ratelimit-unified-status": "allowed"})
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.send_header("anthropic-ratelimit-unified-status", "allowed")
        self.send_header("connection", "close")
        self.end_headers()
        eventos = [
            ("message_start", {"type": "message_start", "message": {
                "id": "msg_falso", "type": "message", "role": "assistant",
                "model": modelo, "content": [], "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 11, "output_tokens": 1,
                          "cache_read_input_tokens": 5}}}),
            ("content_block_start", {"type": "content_block_start",
                                     "index": 0, "content_block": {
                                         "type": "text", "text": ""}}),
            ("ping", {"type": "ping"}),
        ]
        eventos += [("content_block_delta", {
            "type": "content_block_delta", "index": 0,
            "delta": {"type": "text_delta", "text": t}}) for t in
            [texto[:len(texto) // 2], texto[len(texto) // 2:]]]
        eventos += [
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta",
                               "delta": {"stop_reason": "end_turn",
                                         "stop_sequence": None},
                               "usage": {"output_tokens": 7}}),
            ("message_stop", {"type": "message_stop"}),
        ]
        for nome, dado in eventos:
            self.wfile.write(f"event: {nome}\ndata: {json.dumps(dado)}\n\n"
                             .encode())
            self.wfile.flush()
            time.sleep(0.4)
        self.close_connection = True


if __name__ == "__main__":
    print("upstream falso em :9911", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 9911), H).serve_forever()
