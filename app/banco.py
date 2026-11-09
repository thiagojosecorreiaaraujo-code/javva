# -*- coding: utf-8 -*-
"""Mongo do Javva: maquinas aprovadas e uso por maquina.

Collections (sufixo _claude, padrao da casa):
  javva_maquinas_claude   {_id: sha256(token), maquina, codigo, status,
                            limite_diario_tokens, criado_em, ...}
  javva_uso_claude        uma linha por chamada (tokens, modelo, ms, status)
  javva_uso_diario_claude {_id: "<codigo>:<AAAA-MM-DD>", tokens_in, tokens_out,
                            requisicoes}  - base do teto diario

O token da maquina NUNCA e gravado: so o hash. Vazou o banco, nao vazou acesso.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import os

from pymongo import MongoClient, ReturnDocument

_cliente = None

MAQUINAS = "javva_maquinas_claude"
USO = "javva_uso_claude"
USO_DIARIO = "javva_uso_diario_claude"
SESSOES = "javva_sessoes_claude"   # {_id: session_id (resume), codigo,
                                    #  maquina, criada_em, ultimo_comando_em,
                                    #  ultimo_texto, turnos}


def db():
    global _cliente
    if _cliente is None:
        _cliente = MongoClient(os.environ["JAVVA_MONGO_URI"],
                               serverSelectionTimeoutMS=5000)
    return _cliente[os.environ.get("JAVVA_DB", "digilizacao")]


def agora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def hoje() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def codigo_de(h: str) -> str:
    return h[:6].upper()


def maquina_por_token(token: str) -> dict | None:
    return db()[MAQUINAS].find_one({"_id": hash_token(token)})


def registrar(maquina: str, token: str, ip: str) -> dict:
    h = hash_token(token)
    existente = db()[MAQUINAS].find_one({"_id": h})
    if existente:
        return existente
    # JAVVA_AUTOAPROVAR=1 (padrao, pedido do usuario em 22/10/2026): cliente
    # novo entra liberado, sem codigo. Revogada continua revogada: este ramo
    # so roda para token nunca visto.
    auto = os.environ.get("JAVVA_AUTOAPROVAR", "1") != "0"
    doc = {"_id": h, "maquina": maquina[:64], "codigo": codigo_de(h),
           "status": "aprovada" if auto else "pendente", "ip_registro": ip,
           "aprovada_em": agora() if auto else None,
           "limite_diario_tokens": int(os.environ.get(
               "JAVVA_LIMITE_PADRAO", "0") or 0),
           "criado_em": agora(), "ultimo_uso": None}
    db()[MAQUINAS].insert_one(doc)
    return doc


def por_codigo(codigo: str) -> dict | None:
    return db()[MAQUINAS].find_one({"codigo": codigo.strip().upper()})


def mudar(codigo: str, **campos) -> dict | None:
    return db()[MAQUINAS].find_one_and_update(
        {"codigo": codigo.strip().upper()}, {"$set": campos},
        return_document=ReturnDocument.AFTER)


def uso_de_hoje(codigo: str) -> dict:
    return db()[USO_DIARIO].find_one({"_id": f"{codigo}:{hoje()}"}) or {}


def gravar_uso(maq: dict, linha: dict) -> None:
    linha.update({"maquina": maq["maquina"], "codigo": maq["codigo"],
                  "quando": agora()})
    db()[USO].insert_one(linha)
    db()[USO_DIARIO].update_one(
        {"_id": f"{maq['codigo']}:{hoje()}"},
        {"$inc": {"tokens_in": linha.get("input_tokens", 0)
                  + linha.get("cache_read_input_tokens", 0)
                  + linha.get("cache_creation_input_tokens", 0),
                  "tokens_out": linha.get("output_tokens", 0),
                  "requisicoes": 1},
         "$set": {"maquina": maq["maquina"], "codigo": maq["codigo"],
                  "dia": hoje()}},
        upsert=True)
    db()[MAQUINAS].update_one({"_id": maq["_id"]},
                              {"$set": {"ultimo_uso": agora()}})


# ------------------------------------------------------------------ sessoes
def sessoes_da_maquina(codigo: str, limite: int = 9) -> list:
    """As conversas desta maquina, da mais recente para a mais antiga."""
    return list(db()[SESSOES].find({"codigo": codigo})
                .sort("ultimo_comando_em", -1).limit(limite))


def gravar_sessao(maq: dict, sid: str, texto: str, ip: str = "") -> None:
    db()[SESSOES].update_one(
        {"_id": sid},
        {"$set": {"codigo": maq["codigo"], "maquina": maq["maquina"],
                  "ip": ip or maq.get("ip") or "",
                  "ultimo_comando_em": agora(),
                  "ultimo_texto": (texto or "")[:120]},
         "$setOnInsert": {"criada_em": agora()},
         "$inc": {"turnos": 1}},
        upsert=True)


def apagar_sessao(sid: str) -> None:
    db()[SESSOES].delete_one({"_id": sid})


def gravar_ip(codigo: str, ip: str) -> None:
    """IP da maquina como ELA se ve na rede (o servidor so enxerga o NAT do
    Docker, 172.x)."""
    db()[MAQUINAS].update_one({"codigo": codigo}, {"$set": {"ip": ip}})


def sessao_por_id(sid: str, codigo: str) -> dict | None:
    return db()[SESSOES].find_one({"_id": sid, "codigo": codigo})
