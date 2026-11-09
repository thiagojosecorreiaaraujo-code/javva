# -*- coding: utf-8 -*-
"""Javva - o Claude (sua conta, sempre Opus) no servidor; as maos no cliente.

  GET  /saude           -> estado do servico
  POST /registrar       -> maquina gera o proprio token e pede acesso
  GET  /status          -> aprovada / pendente / revogada (Bearer token)
  GET  /javva.bat      -> o cliente, para baixar em qualquer PC da rede
  GET  /eclipse/        -> update site (p2) do plugin do Eclipse
  GET  /javva-eclipse.zip -> o mesmo site em zip (botao Archive... do Eclipse)
  WS   /sessao          -> conversa: prompts e fotos chegam, pedidos de
                           execucao saem para o cliente (ver cerebro.py)
"""
from __future__ import annotations

import asyncio
import os
import re
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

import banco as B
import cerebro

VERSAO = "0.2.0"
DIST = os.environ.get("JAVVA_DIST", "/dist")

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
# Update site do plugin: Help > Install New Software > Add > http://<javva>/eclipse/
app.mount("/eclipse", StaticFiles(directory=os.path.join(DIST, "eclipse"), html=True,
                                  check_dir=False), name="eclipse")


def token_de(cabecalhos) -> str:
    aut = cabecalhos.get("authorization", "")
    return aut[7:].strip() if aut.lower().startswith("bearer ") else ""


def situacao(maq: dict | None) -> tuple[int, str]:
    if not maq:
        return 401, "Javva: maquina desconhecida. Rode o javva.bat."
    if maq["status"] == "pendente":
        return 403, (f"Javva: maquina {maq['maquina']} aguardando aprovacao "
                     f"(codigo {maq['codigo']}).")
    if maq["status"] != "aprovada":
        return 403, f"Javva: acesso da maquina {maq['maquina']} {maq['status']}."
    # cliente antigo imprime este texto ao se registrar: sem codigo, sem "aprovada"
    return 200, "Javva pronto nesta maquina."


@app.get("/saude")
async def saude():
    try:
        await asyncio.to_thread(lambda: B.db().command("ping"))
        mongo = True
    except Exception:                                      # noqa: BLE001
        mongo = False
    return {"javva": VERSAO, "modelo": cerebro.MODELO, "mongo": mongo,
            "conta_claude": bool(os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
                                 or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                                 or os.environ.get("ANTHROPIC_API_KEY"))}


@app.api_route("/api/hello", methods=["GET", "HEAD"])
async def hello():
    return Response(status_code=200)


@app.post("/registrar")
async def registrar(req: Request):
    campos = parse_qs((await req.body()).decode("utf-8", "replace"))
    maquina = (campos.get("maquina") or [""])[0].strip()
    token = (campos.get("token") or [""])[0].strip()
    if not maquina or not re.fullmatch(r"[0-9a-fA-F]{32,128}", token):
        return PlainTextResponse("Pedido invalido.\n", status_code=400)
    ip = req.client.host if req.client else "?"
    maq = await asyncio.to_thread(B.registrar, maquina, token, ip)
    st, txt = situacao(maq)
    return PlainTextResponse(txt + "\n", status_code=200 if st == 200 else 202)


@app.get("/status")
async def status(req: Request):
    token = token_de(req.headers)
    maq = await asyncio.to_thread(B.maquina_por_token, token) if token else None
    st, txt = situacao(maq)
    return PlainTextResponse(txt + "\n", status_code=st)


@app.get("/blindagem.ps1")
async def blindagem():
    return PlainTextResponse(cerebro.script_blindagem(),
                             media_type="text/plain; charset=utf-8")


def versao_do_cliente() -> str:
    try:
        m = re.search(r"\$VERSAO_BAT = (\d+)",
                      open(os.path.join(DIST, "javva.bat"), encoding="ascii",
                           errors="replace").read())
    except OSError:
        m = None
    return m.group(1) if m else "0"


@app.get("/javva.bat/versao")
async def versao_bat():
    """Versao do .bat distribuido (o cliente v3+ se auto-atualiza por ela)."""
    return PlainTextResponse(versao_do_cliente() + "\n")


@app.api_route("/javva-eclipse.zip", methods=["GET", "HEAD"])
async def zip_eclipse():
    """Link curto do plugin do Eclipse (Install New Software > Add > Archive...)."""
    caminho = os.path.join(DIST, "eclipse", "javva-eclipse-site.zip")
    if not os.path.isfile(caminho):
        return PlainTextResponse("nao encontrado\n", status_code=404)
    return FileResponse(caminho, filename="javva-eclipse-site.zip", media_type="application/zip")


@app.get("/javva.bat")
async def javva_bat():
    caminho = os.path.join(DIST, "javva.bat")
    if not os.path.isfile(caminho):
        return PlainTextResponse("nao encontrado\n", status_code=404)
    return FileResponse(caminho, filename="Javva.bat")


# ---- LEGADO: PCs que ainda tem o .bat com o nome antigo. O v3/v4 se
# auto-atualiza por estes enderecos e recebe a PONTE: o cabecalho antigo byte a
# byte (trocar o arquivo com o cmd rodando so e seguro assim) + prologo que cria
# o Javva.bat e apaga o antigo + o corpo do javva.bat. Sai quando todos migrarem.
@app.get("/jarvis.bat/versao")
async def versao_bat_legado():
    return PlainTextResponse(versao_do_cliente() + "\n")


@app.get("/jarvis.bat")
async def ponte_legado():
    try:
        cab = open(os.path.join(DIST, "legado", "cabecalho_antigo.bat"), "rb").read()
        prologo = open(os.path.join(DIST, "legado", "prologo.ps1"), "rb").read()
        novo = open(os.path.join(DIST, "javva.bat"), "rb").read()
    except OSError:
        return PlainTextResponse("nao encontrado\n", status_code=404)
    corpo = b"\r\n".join(novo.split(b"\r\n")[10:])      # tudo depois do cabecalho
    return Response(cab + prologo + corpo, media_type="application/octet-stream")


@app.websocket("/sessao")
async def sessao(ws: WebSocket):
    await ws.accept()
    token = token_de(ws.headers)
    maq = await asyncio.to_thread(B.maquina_por_token, token) if token else None
    st, txt = situacao(maq)
    if st != 200:
        await ws.send_json({"tipo": "erro", "mensagem": txt})
        await ws.close(code=4403)
        return
    if not (os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_API_KEY")):
        await ws.send_json({"tipo": "erro", "mensagem":
                            "Javva: a IA LOCAL ainda nao foi configurada. "
                            "No servidor, rode C:\\mongo\\javva\\configurar.bat."})
        await ws.close(code=4503)
        return
    try:
        ola = await asyncio.wait_for(ws.receive_json(), 30)
        base = "http://" + (ws.headers.get("host") or "192.168.68.106:8787")
        await cerebro.Sessao(ws, maq, base).rodar(ola)
    except Exception as e:                                 # noqa: BLE001
        print("sessao encerrada:", type(e).__name__, str(e)[:300], flush=True)
        try:
            await ws.send_json({"tipo": "erro", "mensagem": cerebro.limpar_nomes(
                                f"Javva: falha no servidor ({type(e).__name__}"
                                f": {str(e)[:200]})")})
            await ws.close()
        except Exception:                                  # noqa: BLE001
            pass
