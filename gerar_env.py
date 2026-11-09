# -*- coding: utf-8 -*-
"""Gera javva.env a partir do cofre local (E:\\CHAVES\\chaves.json).

- JAVVA_MONGO_URI: a URI `mongoLocal` do cofre, com o host trocado para o
  container MONGO_FATAL (o javva entra na rede docker lupa_net) e
  directConnection=true (o replica set se anuncia como localhost).
- CLAUDE_CODE_OAUTH_TOKEN: token da SUA conta, gerado por `claude setup-token`
  (chave `claudeCodeOauthToken` no cofre). Com --pedir-token ele e pedido sem
  eco na tela e gravado no cofre (backup .bak antes).
- JAVVA_MODELO: opus.

Nada sensivel e impresso. javva.env esta no .gitignore.
Uso: python gerar_env.py [--pedir-token] [--cofre CAMINHO]
"""
import argparse
import getpass
import json
import os
import re
import shutil

p = argparse.ArgumentParser()
p.add_argument("--cofre", default=os.environ.get("LUPAXP_CHAVES",
                                                 r"E:\CHAVES\chaves.json"))
p.add_argument("--mongo-host", default="MONGO_FATAL:27017")
p.add_argument("--pedir-token", action="store_true")
p.add_argument("--saida", default=os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "javva.env"))
a = p.parse_args()

with open(a.cofre, encoding="utf-8") as fh:
    cofre = json.load(fh)

if a.pedir_token:
    tok = "".join(getpass.getpass(
        "Cole o token (sk-ant-oat...) e tecle Enter: ").split())
    # Medido 21/10/2026: o botao direito do Prompt de Comando colou o token
    # 3x grudado (324 chars = 3 x 108) e a Anthropic devolveu 401. Se o
    # prefixo se repete com partes identicas, fica uma copia so.
    pos = [i for i in range(len(tok)) if tok.startswith("sk-ant-", i)]
    if len(pos) > 1:
        partes = {tok[a:b] for a, b in zip(pos, pos[1:] + [len(tok)])}
        if len(partes) != 1:
            raise SystemExit("Colou textos diferentes juntos. Rode de novo e "
                             "cole o token UMA vez.")
        tok = partes.pop()
        print(f"(o token veio colado {len(pos)}x; usei uma copia)")
    if not tok.startswith("sk-ant-"):
        raise SystemExit("Isso nao parece um token do Claude (sk-ant-...). "
                         "Nada foi alterado.")
    shutil.copy2(a.cofre, a.cofre + ".bak")
    cofre["claudeCodeOauthToken"] = tok
    with open(a.cofre, "w", encoding="utf-8") as fh:
        json.dump(cofre, fh, ensure_ascii=False, indent=2)
    print("token gravado no cofre (backup em .bak)")

uri = cofre.get("mongoLocal") or cofre.get("mongo")
if not uri:
    raise SystemExit("cofre sem mongoLocal/mongo")
uri = re.sub(r"(@)[^/?]+", r"\g<1>" + a.mongo_host, uri, count=1)
# MONGO_FATAL e replica set anunciado como localhost:27017: sem
# directConnection o driver "descobre" localhost e, dentro do container,
# localhost e o proprio container (ServerSelectionTimeoutError, ReplicaSetNoPrimary).
if "directConnection=" not in uri:
    uri += ("&" if "?" in uri else "?") + "directConnection=true"
token = (cofre.get("claudeCodeOauthToken") or "").strip()

linhas = [
    "# gerado por gerar_env.py - NAO versionar",
    f"JAVVA_MONGO_URI={uri}",
    "JAVVA_DB=digilizacao",
    f"CLAUDE_CODE_OAUTH_TOKEN={token}",
    "JAVVA_MODELO=opus",
    "JAVVA_ULTRACODE=0",
    "JAVVA_ESFORCO=high",
    "JAVVA_LIMITE_PADRAO=0",
]
with open(a.saida, "w", encoding="utf-8", newline="\n") as fh:
    fh.write("\n".join(linhas) + "\n")
print("javva.env gerado:", a.saida)
print("  conta do Claude:", "configurada" if token else
      "AUSENTE - rode configurar.bat")
