# -*- coding: utf-8 -*-
"""Migracao do nome: um PC com o .bat v4 de NOME ANTIGO vira Javva sozinho.

O v4 se auto-atualiza pelo endereco antigo e recebe a PONTE (cabecalho antigo
byte a byte + prologo + corpo do javva.bat): cria o Javva.bat ao lado, leva a
identidade (mesmo token = mesmas sessoes), apaga o .bat antigo quando o cmd
dele sai e ja conversa como Javva na mesma abertura.

    python testes/prova_ponte.py [pasta_do_pc_v4 "mensagem antiga"]

Com a pasta de um PC que CONVERSOU antes da troca de nome (servidor antigo),
prova tambem que a sessao antiga voltou com o historico depois da migracao do
volume e do Mongo. Sem argumentos, monta um PC v4 novo.

Pre: docker compose -f docker-compose.teste.yml up -d --build
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.join(RAIZ, "testes", "legado", "cliente_antigo_v4.bat")
URL = "http://192.168.68.106:8788"
HOST = os.environ["COMPUTERNAME"]
NOME_ANTIGO = re.compile(r"(?i)jarvis")
PROIBIDO = re.compile(r"(?i)claude|anthropic|opus|sonnet|haiku")
falhas = []


def ok(n, c, d=""):
    print(("  ok    " if c else "  FALHA ") + n + ("" if c else f"  -> {d}"), flush=True)
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


def rodar(bat, pc, entrada, antigo):
    env = dict(os.environ, LOCALAPPDATA=pc)
    for k in list(env):
        if k.startswith(("JAVVA_", "JARVIS_")):
            env.pop(k)
    if antigo:                                    # o .bat antigo so conhece estes nomes
        env.update(JARVIS_URL=URL, JARVIS_CONTAINER="javva-teste")
    else:
        env.update(JAVVA_URL=URL, JAVVA_CONTAINER="javva-teste")
    r = subprocess.run(["cmd", "/c", bat], input=entrada.encode(), capture_output=True,
                       env=env, timeout=300, cwd=pc)
    t = tela((r.stdout + r.stderr).decode("utf-8", "replace").replace("\r\n", "\n"))
    # o caminho da pasta do PC e dado do usuario (pode conter qualquer palavra)
    return r.returncode, t.replace(pc, "<PASTA-DO-PC>")


def versao(bat):
    m = re.search(rb"\$VERSAO_BAT = (\d+)", open(bat, "rb").read())
    return int(m.group(1)) if m else 0


def ultimo_pedido_com(trecho):
    ps = json.load(urllib.request.urlopen("http://127.0.0.1:9911/_pedidos"))
    ps = [p for p in ps if p["caminho"] == "/v1/messages" and trecho in (p.get("historico") or "")]
    return ps[-1] if ps else None


VS = int(urllib.request.urlopen(URL + "/javva.bat/versao").read())
ok("endereco antigo publica a MESMA versao", int(urllib.request.urlopen(URL + "/jarvis.bat/versao").read()) == VS)
ponte = urllib.request.urlopen(URL + "/jarvis.bat").read()
cab_antigo = open(V4, "rb").read().split(b"\r\n")[:10]
ok("ponte comeca com o cabecalho antigo BYTE A BYTE", ponte.split(b"\r\n")[:10] == cab_antigo)
ok("ponte so tem CRLF e ASCII", ponte.count(b"\n") == ponte.count(b"\r\n") and max(ponte) < 128)

if len(sys.argv) > 2:
    pc, antiga = sys.argv[1], sys.argv[2]
    print(f"== PC que conversou ANTES da troca de nome: {pc}")
else:
    pc, antiga = tempfile.mkdtemp(prefix="javva-ponte-"), None
    shutil.copyfile(V4, os.path.join(pc, "jarvis.bat"))
    print("== PC v4 novo (sem conversa anterior)")
antigo = os.path.join(pc, "jarvis.bat")
novo = os.path.join(pc, "Javva.bat")
ok("PC comeca com o .bat antigo v4", os.path.isfile(antigo) and versao(antigo) == 4 and not os.path.exists(novo))

print("== 1. abre o .bat antigo: se atualiza, vira Javva e conversa na mesma abertura")
entrada = ("1\nmensagem depois da ponte\n/sair\n" if antiga else "mensagem depois da ponte\n/sair\n")
rc, t = rodar(antigo, pc, entrada, antigo=True)
ok("avisou a atualizacao", "Atualizado para o Javva" in t, t.strip().splitlines()[:6])
ok("banner IA LOCAL - JAVVA", "IA LOCAL - JAVVA  no servidor" in t)
if antiga:
    ok("lista a sessao de ANTES da troca: HOSTNAME - IP - resume - data",
       re.search(r"1\) " + HOST + r" - [\w. ]+ - [0-9a-f-]{36} - \d\d/\d\d/\d{4} - \d\d:\d\d", t),
       [l for l in t.splitlines() if ") " in l][:3])
    ok("retomou", "retomada" in t, t[-500:])
    p = ultimo_pedido_com("mensagem depois da ponte")
    ok("historico de ANTES da troca chegou ao modelo (volume + Mongo migrados)",
       p and antiga in p["historico"], p and p["historico"][:200])
else:
    ok("respondeu", "JAVVA OK" in t, t[-400:])
ok("cmd terminou limpo (cabecalho antigo preservado)",
   rc == 0 and not re.search(r"(?i)reconhecido|recognized|sintaxe|syntax", t), (rc, t.strip().splitlines()[-3:]))
ok("nada de Claude/Opus na tela", not PROIBIDO.search(t), PROIBIDO.findall(t)[:5])
for _ in range(40):
    if not os.path.exists(antigo):
        break
    time.sleep(0.25)
ok("Javva.bat criado ao lado, na versao do servidor", os.path.isfile(novo) and versao(novo) == VS)
ok(".bat de nome antigo apagado depois de sair", not os.path.exists(antigo), os.listdir(pc))
ok("identidade levada para a pasta nova",
   os.path.isfile(os.path.join(pc, "javva", "token")) and not os.path.exists(os.path.join(pc, "jarvis")),
   os.listdir(pc))
ok("Javva.bat sem o nome antigo no arquivo", not NOME_ANTIGO.search(open(novo, encoding="ascii").read()))

print("== 2. abre o Javva.bat: mesma maquina, mesma sessao")
rc, t = rodar(novo, pc, "1\nsegunda depois da ponte\n/sair\n", antigo=False)
ok("lista a sessao (HOSTNAME - IP - resume - data)",
   re.search(r"1\) " + HOST + r" - \d+\.\d+\.\d+\.\d+ - [0-9a-f-]{36} - \d\d/\d\d/\d{4} - \d\d:\d\d", t),
   [l for l in t.splitlines() if ") " in l][:3])
p = ultimo_pedido_com("segunda depois da ponte")
ok("retomou com o historico", p and "mensagem depois da ponte" in p["historico"]
   and (not antiga or antiga in p["historico"]), p and p["historico"][:200])
ok("nada do nome antigo nem de Claude/Opus na tela do Javva",
   not NOME_ANTIGO.search(t) and not PROIBIDO.search(t), (NOME_ANTIGO.findall(t) + PROIBIDO.findall(t))[:5])
ok("sem atualizar de novo (ja e a versao do servidor)", "Atualizado" not in t and "atualizado para" not in t)

print("\nPROVA PONTE:", "PASSOU" if not falhas else f"{len(falhas)} FALHA(S): " + "; ".join(falhas))
sys.exit(1 if falhas else 0)
