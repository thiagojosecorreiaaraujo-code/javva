# -*- coding: utf-8 -*-
"""Prova ponta a ponta do Javva: o javva.bat REAL contra o javva-teste.

Pre: docker compose -f docker-compose.teste.yml up -d --build
Uso: python testes/prova.py [--manter]

Cada caso roda o cliente como um PC novo (LOCALAPPDATA temporario) e confere:
registro + autoaprovacao no servidor, sessao com o Claude do container,
pedido de execucao repassado ao cliente, permissao, execucao NESTA maquina,
resultado de volta ao Claude, foto anexada, recusa e modo conversa.
"""
import base64
import json
import re
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.environ.get("JAVVA_BAT_TESTE") or os.path.join(RAIZ, "cliente", "javva.bat")
FALSO = "http://127.0.0.1:9911"
CONT = "javva-teste"
PC = os.environ.get("COMPUTERNAME", "")
falhas = []
CLIENTE = tempfile.mkdtemp(prefix="javva-cliente-")


def ok(nome, cond, det=""):
    print(("  ok    " if cond else "  FALHA ") + nome
          + (f"  -> {det}" if det else ""), flush=True)
    if not cond:
        falhas.append(nome)


def javva(args, entrada="", timeout=300):
    env = dict(os.environ, JAVVA_URL="http://127.0.0.1:8788",
               JAVVA_CONTAINER=CONT, LOCALAPPDATA=CLIENTE)
    env.update(JARVIS_URL=env["JAVVA_URL"], JARVIS_CONTAINER=env["JAVVA_CONTAINER"])  # o .bat ANTIGO le estes nomes
    cmd = ["cmd", "/c", BAT] + ([args] if args else [])
    t0 = time.monotonic()
    r = subprocess.run(cmd, input=entrada, capture_output=True, env=env,
                       timeout=timeout, encoding="utf-8", errors="replace",
                       cwd=CLIENTE)
    return r.returncode, r.stdout + r.stderr, time.monotonic() - t0


def pedidos():
    return json.load(urllib.request.urlopen(FALSO + "/_pedidos", timeout=5))


def mongo(expr):
    cod = f"import banco as B, json; print(json.dumps({expr}, default=str))"
    out = subprocess.run(["docker", "exec", CONT, "python", "-c", cod],
                         capture_output=True, text=True)
    return json.loads(out.stdout or "null")


def resumo(txt, n=220):
    return " | ".join(l.strip() for l in txt.splitlines() if l.strip())[-n:]


def main():
    saude = json.load(urllib.request.urlopen("http://127.0.0.1:8788/saude"))
    ok("javva-teste no ar (mongo + conta)", saude.get("mongo")
       and saude.get("conta_claude"), saude)

    print("== 1. cliente novo: registra, se aprova e executa um comando aqui")
    rc, out, dt_ = javva("rode o teste do cliente", "S\n")
    ok("registro + autoaprovacao + resposta", rc == 0, f"{dt_:.1f}s")
    ok("cliente novo liberado SEM codigo de aprovacao",
       "aguardando aprovacao" not in out.lower(), resumo(out, 120))
    ok("nada de aprovacao nem codigo na tela (registro silencioso)",
       not re.search(r"(?i)aprovad|codigo", out), resumo(out, 160))
    ok("o Claude pediu para executar NO CLIENTE", "> executar:" in out,
       resumo(out))
    ok("a permissao foi perguntada", "Permitir?" in out)
    alvo = f"RESULTADO DO CLIENTE: JAVVA-CLIENTE-OK em {PC}"
    ok("o comando rodou NESTA maquina e voltou ao Claude", alvo in out,
       resumo(out))
    ult = [p for p in pedidos() if p["caminho"] == "/v1/messages"][-1]
    ok("o Claude do container usou o modelo configurado",
       "opus" in (ult["modelo"] or ""), ult["modelo"])
    ok("so ferramentas do cliente + orquestracao (nada local)",
       ult["ferramentas"] and all(n.startswith("mcp__cliente__")
                                  or n in ("DeferredToolPlaceholder",
                                           "Workflow", "Agent")
                                  for n in ult["ferramentas"]),
       ult["ferramentas"])
    ultra = os.environ.get("JAVVA_ULTRACODE_ESPERADO", "0") == "1"
    ok("modo conforme a configuracao (ultracode %s)" % ("on" if ultra else "off"),
       ({"Workflow", "Agent"} <= set(ult["ferramentas"] or [])) == ultra
       and bool(ult.get("sistema_ultracode")) == ultra, ult.get("effort"))
    ok("embrulho da blindagem NAO aparece na tela do cliente",
       "Javva: limite de" not in out and "$__" not in out, resumo(out, 120))
    velho = os.path.join(os.environ["USERPROFILE"], "Desktop", "Javva.bat")
    if os.path.exists(velho) and b"versao = 2" not in open(velho, "rb").read():
        env = dict(os.environ, JAVVA_URL="http://127.0.0.1:8788",
                   JAVVA_CONTAINER=CONT, LOCALAPPDATA=CLIENTE)
        env.update(JARVIS_URL=env["JAVVA_URL"], JARVIS_CONTAINER=env["JAVVA_CONTAINER"])  # o .bat ANTIGO le estes nomes
        r = subprocess.run(["cmd", "/c", velho, "rode o teste do cliente"],
                           input="S\n", capture_output=True, env=env,
                           timeout=300, encoding="utf-8", errors="replace",
                           cwd=CLIENTE)
        o2 = r.stdout + r.stderr
        ok(".bat ANTIGO: sem embrulho na tela e comando funciona",
           "$__" not in o2 and alvo in o2, resumo(o2, 120))

    print("== 2. recusa do usuario")
    rc, out, _ = javva("rode o teste do cliente", "N\n")
    ok("recusa chega ao Claude",
       "RESULTADO DO CLIENTE: O usuario recusou" in out, resumo(out))

    print("== 3. foto pelo caminho")
    foto = os.path.join(CLIENTE, "foto teste.png")
    with open(foto, "wb") as fh:
        fh.write(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
            "z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="))
    antes = len(pedidos())
    rc, out, _ = javva(f'o que tem nesta foto "{foto}"')
    ok("cliente anexou a foto", "[foto anexada: foto teste.png]" in out,
       resumo(out))
    ok("a foto chegou ao Claude", any(p["tem_imagem"]
                                      for p in pedidos()[antes:]))
    ok("resposta volta ao cliente", "(foto recebida)" in out, resumo(out))

    print("== 4. modo conversa (fica esperando comandos)")
    rc, out, _ = javva("", "oi javva\nrode o teste do cliente\nS\n/sair\n")
    ok("abre o banner e espera comandos", "JAVVA" in out and "> " in out,
       resumo(out, 160))
    ok("responde a 1a mensagem", "JAVVA OK" in out)
    ok("e a 2a, com execucao no cliente", alvo in out)

    print("== 5. uso por maquina no Mongo")
    time.sleep(1)
    dia = mongo("[d for d in B.db()[B.USO_DIARIO].find({'maquina': '%s'})]"
                % PC)
    ok("uso gravado", dia and dia[0].get("requisicoes", 0) >= 5, dia)

    if "--manter" not in sys.argv:
        mongo("B.db().client.drop_database('javva_teste') and 'ok'")
    print("\nPROVA:", "PASSOU" if not falhas else
          f"{len(falhas)} FALHA(S): " + "; ".join(falhas))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
