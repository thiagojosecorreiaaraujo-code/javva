# -*- coding: utf-8 -*-
"""Administracao do Javva (rode DENTRO do container):

  docker exec javva python admin.py listar
  docker exec javva python admin.py aprovar <codigo>
  docker exec javva python admin.py revogar <codigo>
  docker exec javva python admin.py limite <codigo> <tokens_por_dia>   (0 = sem teto)
  docker exec javva python admin.py uso [dias]

Admin = quem tem acesso ao host do container. Nao ha rota HTTP de admin de
proposito: qualquer um na rede alcanca a porta 8787.
"""
import datetime as dt
import sys

import banco as B


def _fmt(d):
    return d.astimezone().strftime("%d/%m %H:%M") if d else "-"


def listar():
    print(f"{'CODIGO':8} {'MAQUINA':20} {'STATUS':10} {'TETO/DIA':>10} "
          f"{'HOJE':>10} {'ULTIMO USO':12} REGISTRO")
    for m in B.db()[B.MAQUINAS].find().sort("criado_em", 1):
        hoje = B.uso_de_hoje(m["codigo"])
        usado = hoje.get("tokens_in", 0) + hoje.get("tokens_out", 0)
        print(f"{m['codigo']:8} {m['maquina'][:20]:20} {m['status']:10} "
              f"{m.get('limite_diario_tokens') or 0:>10} {usado:>10} "
              f"{_fmt(m.get('ultimo_uso')):12} {_fmt(m['criado_em'])} "
              f"{m.get('ip_registro', '')}")


def mudar_status(codigo, status):
    campos = {"status": status, f"{status}_em": B.agora()}
    m = B.mudar(codigo, **campos)
    print(f"{m['maquina']} ({m['codigo']}) -> {status}" if m
          else f"codigo {codigo} nao existe")


def limite(codigo, n):
    m = B.mudar(codigo, limite_diario_tokens=int(n))
    print(f"{m['maquina']} ({m['codigo']}) teto diario = {int(n)} tokens"
          if m else f"codigo {codigo} nao existe")


def uso(dias="7"):
    desde = (dt.datetime.now() - dt.timedelta(days=int(dias))).strftime(
        "%Y-%m-%d")
    print(f"{'DIA':10} {'CODIGO':8} {'MAQUINA':20} {'REQ':>6} "
          f"{'TOKENS IN':>11} {'TOKENS OUT':>11}")
    for u in B.db()[B.USO_DIARIO].find({"dia": {"$gte": desde}}).sort(
            [("dia", 1), ("codigo", 1)]):
        print(f"{u['dia']:10} {u['codigo']:8} {u['maquina'][:20]:20} "
              f"{u.get('requisicoes', 0):>6} {u.get('tokens_in', 0):>11} "
              f"{u.get('tokens_out', 0):>11}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["listar"]:
        listar()
    elif a[:1] == ["aprovar"] and len(a) == 2:
        mudar_status(a[1], "aprovada")
    elif a[:1] == ["revogar"] and len(a) == 2:
        mudar_status(a[1], "revogada")
    elif a[:1] == ["limite"] and len(a) == 3:
        limite(a[1], a[2])
    elif a[:1] == ["uso"]:
        uso(*a[1:2])
    else:
        print(__doc__)
        sys.exit(2)
