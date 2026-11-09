# -*- coding: utf-8 -*-
"""javva.bat v3: o .bat ANTIGO vira v3 com ATUALIZAR (uma aprovacao), a v3
lista as sessoes "<resume> - <data/hora>", retoma/abre nova, e uma v3 mais
velha se auto-atualiza sozinha. Nada de Claude/Opus na tela.

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
ORIGINAL = os.path.join(RAIZ, "testes", "legado", "cliente_antigo_v1.bat")
V3 = os.path.join(RAIZ, "cliente", "javva.bat")
URL = "http://192.168.68.106:8788"          # IP de LAN: o .bat informa o IP real
HOST = os.environ["COMPUTERNAME"]
PROIBIDO = re.compile(r"(?i)claude|anthropic|opus|sonnet|haiku")
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


def abrir(bat, appdata, entrada):
    env = dict(os.environ, JAVVA_URL=URL,
               JAVVA_CONTAINER="javva-teste", LOCALAPPDATA=appdata)
    env.update(JARVIS_URL=env["JAVVA_URL"], JARVIS_CONTAINER=env["JAVVA_CONTAINER"])  # o .bat ANTIGO le estes nomes
    env.pop("JAVVA_ATUALIZADO", None)
    r = subprocess.run(["cmd", "/c", bat], input=entrada.encode(),
                       capture_output=True, env=env, timeout=300,
                       cwd=os.path.dirname(bat))
    return r.returncode, tela((r.stdout + r.stderr).decode("utf-8", "replace")
                              .replace("\r\n", "\n"))


def versao(bat):
    m = re.search(rb"\$VERSAO_BAT = (\d+)", open(bat, "rb").read())
    return int(m.group(1)) if m else 0


def ultimo_pedido_com(trecho):
    ps = json.load(urllib.request.urlopen("http://127.0.0.1:9911/_pedidos"))
    ps = [p for p in ps if p["caminho"] == "/v1/messages"
          and trecho in (p.get("historico") or "")]
    return ps[-1] if ps else None


def sem_lixo_do_cmd(t):
    """Se o cmd retomasse a leitura no offset errado depois da troca do
    arquivo, apareceria 'nao e reconhecido como um comando' e afins."""
    return not re.search(r"(?i)reconhecido|recognized|sintaxe|syntax", t)


v_srv = urllib.request.urlopen("http://127.0.0.1:8788/javva.bat/versao").read()
VS = int(v_srv)
ok("servidor publica a versao do .bat", VS >= 4, v_srv)

print("== 1. .bat ANTIGO (CRLF, como nos PCs) + ATUALIZAR")
pc = tempfile.mkdtemp(prefix="javva-v3-antigo-")
antigo = os.path.join(pc, "jarvis.bat")          # o nome que esta nos PCs antigos
shutil.copyfile(ORIGINAL, antigo)
rc, t = abrir(antigo, pc, "uma pergunta antiga\n/sair\n")    # cria uma sessao
rc, t = abrir(antigo, pc, "atualizar\nS\n/sair\n")
ok("menu antigo oferece ATUALIZAR", "digite ATUALIZAR" in t)
ok("menu antigo mostra HOST - sem ip - <resume> - <data/hora>",
   re.search(r"1\) " + HOST + r" - sem ip - [0-9a-f-]{36} - \d\d/\d\d/\d{4} - \d\d:\d\d", t))
ok("pede Permitir com o comando visivel", "Permitir?" in t and "Javva.bat" in t)
ok("manda abrir o Javva.bat", "abra o Javva.bat" in t,
   [l for l in t.splitlines() if "javva" in l.lower()][-2:])
bat = os.path.join(pc, "Javva.bat")
for _ in range(40):                               # o antigo some quando o cmd dele sai
    if not os.path.exists(antigo):
        break
    time.sleep(0.25)
ok("Javva.bat criado ao lado, na versao do servidor", os.path.isfile(bat) and versao(bat) == VS)
ok(".bat de nome antigo apagado depois de sair", not os.path.exists(antigo), os.listdir(pc))
ok("identidade levada para a pasta nova (mesmo token)",
   os.path.isfile(os.path.join(pc, "javva", "token")) and not os.path.exists(os.path.join(pc, "jarvis")),
   os.listdir(pc))
ok("cmd terminou limpo", rc == 0 and sem_lixo_do_cmd(t), (rc, t.strip().splitlines()[-3:]))
ok("nada de Claude/Opus na tela (antigo)", not PROIBIDO.search(t),
   PROIBIDO.findall(t)[:5])

print("== 2. mesmo PC, agora v3: lista, retoma pela escolha")
rc, t = abrir(bat, pc, "1\nmensagem na v3\n/sair\n")
ok("cabecalho IA LOCAL - JAVVA", "IA LOCAL - JAVVA  no servidor" in t)
ok("lista HOSTNAME - IP - <resume> - <data/hora> + Nova sessao",
   re.search(r"1\) " + HOST + r" - 192\.168\.68\.106 - [0-9a-f-]{36} - \d\d/\d\d/\d{4} - \d\d:\d\d", t)
   and "+ Nova sessao" in t, [l for l in t.splitlines() if ") " in l][:4])
ok("avisa que retomou", "retomada" in t)
p = ultimo_pedido_com("mensagem na v3")
ok("historico da sessao escolhida chegou ao modelo",
   p and "uma pergunta antiga" in p["historico"], p and p["historico"][:160])
ok("rodape com a sessao", re.search(r"\[IA LOCAL - JAVVA - sessao [0-9a-f]{8} - [\d.]+s\]", t))
ok("nada de Claude/Opus na tela (v3)", not PROIBIDO.search(t), PROIBIDO.findall(t)[:5])
ok("nada do nome antigo na tela do Javva", not re.search(r"(?i)jarvis", t))

print("== 3. v3: 0 = nova sessao, sem historico")
rc, t = abrir(bat, pc, "0\nmensagem nova na v3\n/sair\n")
p = ultimo_pedido_com("mensagem nova na v3")
ok("nova sessao nao carrega historico", p and "uma pergunta antiga" not in p["historico"])
ok("v3 sem a oferta de ATUALIZAR", "digite ATUALIZAR" not in t)

print("== 4. v3 mais velha (VERSAO 2) se auto-atualiza")
pc2 = tempfile.mkdtemp(prefix="javva-v3-auto-")
bat2 = os.path.join(pc2, "javva.bat")
b = re.sub(rb"\$VERSAO_BAT = \d+", b"$VERSAO_BAT = 2", open(V3, "rb").read())
open(bat2, "wb").write(b)
rc, t = abrir(bat2, pc2, "primeira na auto\n/sair\n")
ok("avisou a auto-atualizacao", f"atualizado para a versao {VS}" in t)
ok("arquivo ficou na versao do servidor", versao(bat2) == VS)
ok("seguiu e respondeu na mesma abertura", "JAVVA OK" in t)
ok("cmd terminou limpo", rc == 0 and sem_lixo_do_cmd(t), (rc, t.strip().splitlines()[-3:]))

print("== 5. pergunta direta (javva \"...\") na v3")
env = dict(os.environ, JAVVA_URL=URL,
           JAVVA_CONTAINER="javva-teste", LOCALAPPDATA=pc2)
env.update(JARVIS_URL=env["JAVVA_URL"], JARVIS_CONTAINER=env["JAVVA_CONTAINER"])  # o .bat ANTIGO le estes nomes
r = subprocess.run(["cmd", "/c", bat2, "pergunta direta"], capture_output=True,
                   env=env, timeout=300, cwd=pc2)
t = tela((r.stdout + r.stderr).decode("utf-8", "replace").replace("\r\n", "\n"))
ok("responde e sai", r.returncode == 0 and "JAVVA OK" in t, t.strip().splitlines()[-3:])

print("\nPROVA V3:", "PASSOU" if not falhas else
      f"{len(falhas)} FALHA(S): " + "; ".join(falhas))
sys.exit(1 if falhas else 0)
