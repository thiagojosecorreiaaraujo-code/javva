# -*- coding: utf-8 -*-
"""Sessoes com o javva.bat ORIGINAL: menu no titulo, retomar pelo numero,
nova com 0, pedido direto abre nova, e tudo sobrevive a recriar o container.

Pre: docker compose -f docker-compose.teste.yml up -d --build
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.environ.get("JAVVA_BAT_TESTE") or os.path.join(
    RAIZ, "testes", "legado", "cliente_antigo_v1.bat")
CLIENTE = tempfile.mkdtemp(prefix="javva-sess-")       # um PC so, varias aberturas
falhas = []


def ok(n, c, d=""):
    print(("  ok    " if c else "  FALHA ") + n + (f"  -> {d}" if d else ""),
          flush=True)
    if not c:
        falhas.append(n)


def tela(s):
    out = []
    for l in s.split("\n"):
        buf = []
        for p in l.split("\r"):
            for i, ch in enumerate(p):
                if i < len(buf):
                    buf[i] = ch
                else:
                    buf.append(ch)
        out.append("".join(buf))
    return "\n".join(out)


def abrir(entrada):
    env = dict(os.environ, JAVVA_URL="http://127.0.0.1:8788",
               JAVVA_CONTAINER="javva-teste", LOCALAPPDATA=CLIENTE)
    env.update(JARVIS_URL=env["JAVVA_URL"], JARVIS_CONTAINER=env["JAVVA_CONTAINER"])  # o .bat ANTIGO le estes nomes
    r = subprocess.run(["cmd", "/c", BAT], input=entrada.encode(),
                       capture_output=True, env=env, timeout=300, cwd=CLIENTE)
    return tela((r.stdout + r.stderr).decode("utf-8", "replace")
                .replace("\r\n", "\n"))


def pedidos():
    return json.load(urllib.request.urlopen("http://127.0.0.1:9911/_pedidos"))


def ultimo_pedido_com(trecho):
    ps = [p for p in pedidos() if p["caminho"] == "/v1/messages"
          and trecho in (p.get("historico") or "")]
    return ps[-1] if ps else None


def sessoes_no_menu(t):
    return re.findall(r"^\s+(\d)\) (?:.+? - )?([0-9a-f-]{36}) - (\d\d/\d\d/\d{4} - \d\d:\d\d)",
                      t, re.M)


print("== 1. primeira abertura: sem sessoes, sem menu")
t = abrir("primeira mensagem do teste\n/sair\n")
ok("sem menu quando nao ha sessao", "Sessoes desta maquina" not in t)
ok("responde normal", "JAVVA OK" in t)
sid1 = re.search(r"sessao ([0-9a-f]{8})", t)
ok("rodape mostra o numero da sessao", bool(sid1), t.strip().splitlines()[-2:])

print("== 2. segunda abertura: menu, escolhe 1, retoma")
time.sleep(1)
t = abrir("1\nsegunda mensagem\n/sair\n")
menu = sessoes_no_menu(t)
ok("menu lista a sessao com numero + data/hora", menu and sid1
   and menu[0][1].startswith(sid1.group(1)), menu)
ok("ultima linha do menu le bem com a cauda do .bat",
   "Conectado no servidor" in t)
ok("avisa que retomou", "retomada" in t, [l for l in t.splitlines() if "retomada" in l])
p = ultimo_pedido_com("segunda mensagem")
ok("Claude recebeu o HISTORICO da sessao (resume de verdade)",
   p and "primeira mensagem do teste" in p["historico"],
   p and p["historico"][:160])

print("== 3. 0 = nova sessao (sem historico)")
t = abrir("0\nterceira mensagem\n/sair\n")
ok("avisa nova sessao", "Nova sessao aberta" in t)
p = ultimo_pedido_com("terceira mensagem")
ok("nova sessao NAO carrega historico anterior",
   p and "primeira mensagem" not in p["historico"], p and p["historico"][:160])

print("== 4. pedido direto no menu abre nova sessao ja respondendo")
t = abrir("quarta mensagem direta\n/sair\n")
p = ultimo_pedido_com("quarta mensagem direta")
ok("pedido processado sem passo extra", "JAVVA OK" in t and p
   and "terceira" not in p["historico"])

print("== 5. recriar o container: sessoes continuam la e retomaveis")
subprocess.run(["docker", "compose", "-f", os.path.join(RAIZ, "docker-compose.teste.yml"),
                "up", "-d", "--force-recreate", "javva-teste"],
               capture_output=True, cwd=RAIZ)
for _ in range(30):
    try:
        urllib.request.urlopen("http://127.0.0.1:8788/saude", timeout=3)
        break
    except OSError:
        time.sleep(1)
time.sleep(2)
t = abrir("/sair\n")
menu = sessoes_no_menu(t)
ok("menu apos recriar mostra as sessoes (mais recente primeiro)",
   len(menu) >= 3, menu)
alvo = next((m for m in menu if m[1].startswith(sid1.group(1))), None) if sid1 else None
t = abrir(f"{alvo[0] if alvo else 9}\nquinta mensagem\n/sair\n")
p = ultimo_pedido_com("quinta mensagem")
ok("retoma a 1a sessao DEPOIS de recriar o container",
   p and "primeira mensagem do teste" in p["historico"]
   and "segunda mensagem" in p["historico"], p and p["historico"][:200])

print("\nPROVA SESSOES:", "PASSOU" if not falhas else
      f"{len(falhas)} FALHA(S): " + "; ".join(falhas))
sys.exit(1 if falhas else 0)
