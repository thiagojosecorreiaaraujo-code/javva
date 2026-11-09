# Container `javva`

Imagem `python:3.12-slim` + FastAPI/uvicorn + agente (`claude-agent-sdk`).
Roda como usuário **não‑root** `javva` (HOME `/home/javva`), porta **8787**.
Fonte: [`Dockerfile`](../Dockerfile).

## Subir

| Cenário | Arquivo | Comando |
|---|---|---|
| Servidor novo, Mongo junto | [`docker-compose.avulso.yml`](../docker-compose.avulso.yml) | `docker compose -f docker-compose.avulso.yml up -d --build` |
| Mongo já existente na rede Docker `lupa_net` | [`docker-compose.yml`](../docker-compose.yml) | `docker compose up -d --build` |
| Prova sem gastar crédito (API falsa, porta 8788) | [`docker-compose.teste.yml`](../docker-compose.teste.yml) | `docker compose -f docker-compose.teste.yml up -d --build` |

Só a imagem, sem compose:

```bash
docker build -t javva:0.2.0 .
docker run -d --name javva -p 8787:8787 --env-file javva.env \
  -v "$PWD/cliente:/dist:ro" -v javva_conta:/home/javva/.claude javva:0.2.0
```

## Variáveis (`javva.env`)

Modelo pronto: [`javva.env.example`](../javva.env.example).

| Variável | Padrão | Para quê |
|---|---|---|
| `JAVVA_MONGO_URI` | — (obrigatória) | Mongo. Replica set anunciado como `localhost`? acrescente `directConnection=true`. |
| `JAVVA_DB` | `digilizacao` | banco das collections `javva_*_claude` |
| `CLAUDE_CODE_OAUTH_TOKEN` / `ANTHROPIC_API_KEY` | — | conta do modelo (uma das duas) |
| `JAVVA_MODELO` | `opus` | apelido do modelo |
| `JAVVA_ESFORCO` | (do modelo) | profundidade padrão: `low` `medium` `high` `xhigh` `max`. O plugin pode pedir outra. |
| `JAVVA_ULTRACODE` | `1` | `1` liga a orquestração com subagentes; `0` desliga |
| `JAVVA_AUTOAPROVAR` | `1` | máquina nova entra sozinha; `0` exige aprovação |
| `JAVVA_LIMITE_CMD` | `180` | segundos máximos de cada comando no cliente |
| `JAVVA_LIMITE_PADRAO` | `0` | teto de tokens/dia por máquina (0 = sem teto) |
| `JAVVA_SESSOES_DIR` | `/home/javva/sessoes` | pasta de trabalho fixa por máquina (necessária para retomar sessão) |
| `JAVVA_DIST` | `/dist` | de onde servir `javva.bat` e o update site do Eclipse |

## Volumes

| Montagem | Para quê |
|---|---|
| `./cliente:/dist:ro` | o que o container serve para download (`javva.bat`, `eclipse/`, zip). Atualizar o plugin = trocar os arquivos de `cliente/eclipse/`, sem rebuild. |
| `javva_conta:/home/javva/.claude` | histórico das conversas. **Sem este volume, recriar o container apaga as sessões.** |

## Rotas

| Rota | O que entrega |
|---|---|
| `GET /saude` | `{"javva", "modelo", "mongo", "conta_claude"}`: diagnóstico |
| `GET /api/hello` | 200 (healthcheck do Docker) |
| `GET /javva.bat`, `/javva.bat/versao` | cliente de console e sua versão (atualização automática) |
| `GET /javva-eclipse.zip` | update site do plugin compactado (instalar com **Archive…**) |
| `GET /eclipse/` | update site p2 aberto + página de instruções |
| `POST /registrar`, `GET /status` | registro da máquina (token gerado no cliente) |
| `WS /sessao` | a conversa (protocolo JSON; o cliente executa as ferramentas) |

## Administração

Não há rota HTTP de admin de propósito: qualquer um na rede alcança a 8787.
Admin é quem tem acesso ao host:

```bash
docker exec javva python admin.py listar
docker exec javva python admin.py aprovar <codigo>
docker exec javva python admin.py revogar <codigo>
docker exec javva python admin.py limite <codigo> <tokens_por_dia>   # 0 = sem teto
docker exec javva python admin.py uso 7
```

## Mongo (collections)

| Collection | Conteúdo |
|---|---|
| `javva_maquinas_claude` | máquinas registradas (`_id` = sha256 do token, nome, código, status, teto) |
| `javva_sessoes_claude` | sessões retomáveis por máquina |
| `javva_uso_claude` | uma linha por chamada (tokens, modelo, ms, status) |
| `javva_uso_diario_claude` | soma diária por máquina |

## Problemas comuns

| Sintoma | Causa | Saída |
|---|---|---|
| `/saude` com `"mongo": false` | URI errada ou replica set anunciado como `localhost` | `directConnection=true` na URI; o host do Mongo tem de ser alcançável **de dentro** do container |
| `"conta_claude": false` | `javva.env` sem conta | preencha e `docker compose up -d` (recria) |
| 401 do modelo logo após configurar | token colado repetido | `gerar_env.py --pedir-token` detecta e corrige |
| Outros PCs não conectam | firewall do servidor | regra `netsh` do README |
| Conversa caiu ao reiniciar o container | WebSocket fecha no restart | no Eclipse clique **↻**; o `javva.bat` reconecta |
