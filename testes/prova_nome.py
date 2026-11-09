# -*- coding: utf-8 -*-
"""O cliente (javva.bat ORIGINAL) nunca pode MOSTRAR Claude/Opus/Anthropic.

Renderiza a saida como o console faz (\r volta ao inicio da linha e o texto
seguinte sobrescreve) e procura os nomes proibidos no que fica NA TELA.
Pre: docker compose -f docker-compose.teste.yml up -d --build
"""
import os
import re
import subprocess
import sys
import tempfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.environ.get("JAVVA_BAT_TESTE") or os.path.join(
    RAIZ, "testes", "legado", "cliente_antigo_v1.bat")
PROIBIDO = re.compile(r"(?i)claude|opus|anthropic")
falhas = []


def ok(n, c, d=""):
    print(("  ok    " if c else "  FALHA ") + n + (f"  -> {d}" if d else ""),
          flush=True)
    if not c:
        falhas.append(n)


def tela(saida: str) -> str:
    linhas = []
    for linha in saida.split("\n"):
        buf = []
        for parte in linha.split("\r"):
            for i, ch in enumerate(parte):
                if i < len(buf):
                    buf[i] = ch
                else:
                    buf.append(ch)
        linhas.append("".join(buf))
    return "\n".join(linhas)


def javva(entrada):
    env = dict(os.environ, JAVVA_URL="http://127.0.0.1:8788",
               JAVVA_CONTAINER="javva-teste",
               LOCALAPPDATA=tempfile.mkdtemp(prefix="javva-nome-"))
    env.update(JARVIS_URL=env["JAVVA_URL"], JARVIS_CONTAINER=env["JAVVA_CONTAINER"])  # o .bat ANTIGO le estes nomes
    # bytes crus: o modo texto do Python converte \r em \n e esconde o efeito
    r = subprocess.run(["cmd", "/c", BAT], input=entrada.encode(),
                       capture_output=True, env=env, timeout=300)
    return (r.stdout + r.stderr).decode("utf-8", "replace").replace("\r\n", "\n")


out = javva("quem e voce\n/sair\n")
visto = tela(out)
banner = next((l for l in visto.split("\n") if "JAVVA" in l), "")
ok("banner mostra IA LOCAL - JAVVA", "IA LOCAL - JAVVA" in banner, banner.strip())
ok("resposta com o nome trocado", "Sou o Javva Javva, criado pela Javva" in visto
   or ("Sou o Javva" in visto and "criado pela Javva" in visto),
   [l.strip() for l in visto.split("\n") if "Sou o" in l])
ok("rodape sem modelo", "[IA LOCAL - JAVVA -" in visto)
achados = sorted(set(m.group(0) for m in PROIBIDO.finditer(visto)))
ok("NADA de Claude/Opus/Anthropic na tela", not achados, achados)
print("\nPROVA NOME:", "PASSOU" if not falhas else f"{len(falhas)} FALHA(S)")
sys.exit(1 if falhas else 0)
