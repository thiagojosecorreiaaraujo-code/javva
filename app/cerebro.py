# -*- coding: utf-8 -*-
"""Uma sessao do Javva = um cliente conectado por WebSocket.

O Claude (Agent SDK, sempre o modelo JAVVA_MODELO) roda AQUI, no container.
As ferramentas nativas ficam desligadas: ele so age pelas 4 ferramentas do
servidor MCP "cliente", que nao executam nada aqui - mandam o pedido ao
javva.bat, que pergunta ao usuario, executa NA MAQUINA DELE e devolve.

Protocolo (JSON por mensagem WebSocket):
  cliente -> javva : ola {maquina, usuario, pasta, so}
                      prompt {texto, imagens:[{nome, media_type, base64}]}
                      resultado {id, ok, saida}
                      sair
  javva -> cliente : pronto {modelo}
                      texto {texto}                (pedacos, em streaming)
                      ferramenta {id, nome, args}  (executar no cliente)
                      fim {info}
                      erro {mensagem}
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
import uuid

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions,
                              ClaudeSDKClient, ResultMessage, StreamEvent,
                              TextBlock, ToolUseBlock, create_sdk_mcp_server,
                              tool)

import banco as B

MODELO = os.environ.get("JAVVA_MODELO", "opus")
ULTRACODE = os.environ.get("JAVVA_ULTRACODE", "1") != "0"
ESFORCO = os.environ.get("JAVVA_ESFORCO", "").strip() or None
# Profundidade que o CLIENTE pode pedir no "ola" (plugin: botao de configuracao).
# Fora desta lista vale o padrao do servidor (JAVVA_ESFORCO).
ESFORCOS = ("low", "medium", "high", "xhigh", "max")
# Ultracode precisa das ferramentas nativas Workflow + Agent (medido na sonda
# testes/sonda_ultracode.py: sem elas o modo fica indisponivel). Os agentes
# que elas criam NAO tem ferramenta local: so agem pelas mcp__cliente__*.
ORQUESTRACAO = ["Workflow", "Agent"] if ULTRACODE else []
ESPERA_CLIENTE = 15 * 60
NOMES = ("executar", "ler_arquivo", "escrever_arquivo", "listar_pasta")
LIMITE_CMD = int(os.environ.get("JAVVA_LIMITE_CMD", "180"))

# Todo comando sai daqui BLINDADO: roda num job com limite de tempo; estourou,
# o proprio cliente encerra o job, fecha o Office que o comando abriu e devolve
# ao Claude o texto da caixa de dialogo que travou. Motivo (medido 22/10/2026,
# testes/word_repro): Word via COM abrindo HTML com <img> vinculada mostra o
# "Microsoft Word Security Notice" (Yes/No) - DisplayAlerts=0,
# UpdateLinksAtOpen=$false e ConfirmConversions/NoEncodingDialog NAO suprimem.
# Com o Word escondido ninguem clica e o cliente esperava para sempre.
_BLINDAGEM = r"""$__c = {
__CMD__
}
# --- Javva: limite de __LIMITE__s; Office escondido travado e fechado ---
$__of = 'WINWORD','EXCEL','POWERPNT'
__LIMPA__$__antes = @(Get-Process $__of -EA 0 | ForEach-Object Id)
$__s = New-Object Diagnostics.ProcessStartInfo 'powershell.exe'
$__s.Arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand ' + [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes("[Console]::OutputEncoding=[Text.Encoding]::UTF8; `$ProgressPreference='SilentlyContinue'; " + $__c.ToString() + "`nif (`$LASTEXITCODE) { exit `$LASTEXITCODE }"))
$__s.WorkingDirectory = (Get-Location).Path; $__s.UseShellExecute = $false; $__s.RedirectStandardOutput = $true; $__s.RedirectStandardError = $true; $__s.StandardOutputEncoding = [Text.Encoding]::UTF8; $__s.StandardErrorEncoding = [Text.Encoding]::UTF8
$__p = [Diagnostics.Process]::Start($__s); $__o = $__p.StandardOutput.ReadToEndAsync(); $__e = $__p.StandardError.ReadToEndAsync()
if ($__p.WaitForExit(__LIMITE__ * 1000)) {
  $__p.WaitForExit(); $__o.Result.TrimEnd()
  $__x = $__e.Result.Trim()
  if ($__x.StartsWith('#< CLIXML')) { try { $__x = ((([xml]$__x.Substring(9)).Objs.S | Where-Object { $_.S -eq 'Error' } | ForEach-Object { $_.'#text' }) -join '').Replace('_x000D__x000A_', "`n").Trim() } catch { } }
  if ($__x) { '[erro]'; $__x }
  exit $__p.ExitCode
}
$__d = ''
try { Add-Type -AssemblyName UIAutomationClient; foreach ($__q in @(Get-Process $__of -EA 0 | Where-Object { $__antes -notcontains $_.Id })) { $__k = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty, $__q.Id); foreach ($__w in [Windows.Automation.AutomationElement]::RootElement.FindAll('Children', $__k)) { $__d += ' [' + $__w.Current.Name + ': ' + ((@($__w.FindAll('Descendants', [Windows.Automation.Condition]::TrueCondition)) | ForEach-Object { $_.Current.Name } | Where-Object { $_ } | Select-Object -Unique -First 6) -join ' / ') + ']' } } } catch { }
# Ordem importa: fechar o Office PRIMEIRO solta o comando preso nele; so entao
# encerrar a arvore do processo (parar antes deixava tudo pendurado - medido).
Get-Process $__of -EA 0 | Where-Object { $__antes -notcontains $_.Id } | Stop-Process -Force -EA 0
& taskkill.exe /PID $__p.Id /T /F 2>&1 | Out-Null
"TEMPO ESGOTADO: o comando passou de __LIMITE__s e foi encerrado; o Office aberto por ele foi fechado. Janela que travou:$__d"
exit 124"""
_OFFICE_COM = re.compile(r"ComObject\s+['\"]?(Word|Excel|PowerPoint)\.Application",
                         re.IGNORECASE)
_PROCESSO = {"word": "WINWORD", "excel": "EXCEL", "powerpoint": "POWERPNT"}


def blindar(comando: str) -> str:
    """Embrulha o comando do Claude no limite de tempo + limpeza de Office."""
    apps = sorted({_PROCESSO[m.group(1).lower()]
                   for m in _OFFICE_COM.finditer(comando)})
    limpa = ""
    if apps:
        # Word/Excel SEM janela que sobrou de um travamento anterior segura
        # o arquivo e trava o proximo comando: fecha antes de comecar.
        limpa = ("Get-Process " + ",".join(f"'{a}'" for a in apps)
                 + " -EA 0 | Where-Object { $_.MainWindowHandle -eq 0 }"
                 " | Stop-Process -Force -EA 0\n")
    return (_BLINDAGEM.replace("__LIMPA__", limpa)
            .replace("__LIMITE__", str(LIMITE_CMD))
            .replace("__CMD__", comando))       # por ultimo: o texto do Claude
                                                 # nunca e lido como marcador


def script_blindagem() -> str:
    """O mesmo embrulho, servido em /blindagem.ps1: le o comando de $javva.

    Para o javva.bat original (que mostra o comando INTEIRO na tela e no
    "Permitir?"): o servidor manda so o comando do Claude dentro de uma
    here-string + UMA linha que baixa e roda isto. Tela limpa, protecao igual."""
    limpa = ("if ($javva -match 'ComObject\\s+[''\"]?(Word|Excel|PowerPoint)"
             "\\.Application') { Get-Process 'WINWORD','EXCEL','POWERPNT' -EA 0"
             " | Where-Object { $_.MainWindowHandle -eq 0 }"
             " | Stop-Process -Force -EA 0 }\n")
    return (_BLINDAGEM.replace("$__c = {\n__CMD__\n}",
                               "$__c = [scriptblock]::Create($javva)")
            .replace("__LIMPA__", limpa)
            .replace("__LIMITE__", str(LIMITE_CMD)))


def blindar_curto(comando: str, base: str) -> str:
    """Comando legivel + 1 linha. Sem protecao se o texto quebraria a
    here-string (linha comecando com '@)."""
    if any(l.startswith("'@") for l in comando.split("\n")):
        return comando
    return ("$javva = @'\n" + comando + "\n'@\n"
            f"irm {base}/blindagem.ps1 | iex")


TEXTO_ULTRACODE = """Voce trabalha em modo ultracode: para tarefas que valem, orquestre workflows
e subagentes. Eles tambem so enxergam o computador do usuario pelas
ferramentas mcp__cliente__*; nada roda no servidor. Prefira leitura
(ler_arquivo, listar_pasta) nas investigacoes paralelas e concentre os
comandos e gravacoes no agente principal, para o usuario aprovar menos vezes.

"""


NOME_PUBLICO = "IA LOCAL - JAVVA"
# O cliente NUNCA pode ver o nome do modelo nem do fornecedor (pedido do
# usuario, 23/10/2026). O .bat de primeira versao (legado) imprime um banner
# fixo de 20 colunas terminado em "Claude <modelo>": o servidor manda no lugar
# do modelo um retorno de carro (\r) + este texto, que SOBRESCREVE o banner
# (a 20a coluna do original e espaco).
BANNER = "\r  " + NOME_PUBLICO + " "
# inclui o nome antigo: sessoes retomadas de antes da troca ainda o tem no historico
_PROIBIDO = re.compile(r"(?i)claude(?:\s+code)?|anthropic|opus|sonnet|haiku|jarvis")
_RETEM = 12                     # maior nome proibido ("claude code" + folga)


def limpar_nomes(t: str) -> str:
    return _PROIBIDO.sub("Javva", t or "")


def prompt_sistema(ola: dict) -> str:
    return f"""Voce e o JAVVA, a IA LOCAL deste escritorio, em portugues do Brasil.
Seu nome e sempre "Javva" ou "IA LOCAL - JAVVA". Nunca diga qual modelo,
empresa ou fornecedor esta por tras de voce; se perguntarem, voce e o Javva,
a IA local da casa, e nao entra em detalhes.

Voce roda num servidor, mas TRABALHA no computador do usuario:
- maquina: {ola.get('maquina', '?')} (usuario {ola.get('usuario', '?')})
- sistema: {ola.get('so', 'Windows')}
- pasta atual: {ola.get('pasta', '?')}
{TEXTO_ECLIPSE if ola.get('cliente') == 'eclipse' else ''}
Voce so enxerga e altera esse computador pelas ferramentas:
- executar: roda um comando PowerShell na pasta atual do usuario, em processo
  novo a cada chamada (cd nao persiste: use caminhos absolutos ou ';').
- ler_arquivo, escrever_arquivo, listar_pasta: caminhos do computador dele.
O usuario aprova cada comando e cada gravacao na tela dele; se ele recusar,
respeite e proponha outro caminho. Fotos que ele mandar chegam anexadas.

{TEXTO_ULTRACODE if ULTRACODE else ''}Seja direto e objetivo, como um engenheiro experiente. Antes de algo
destrutivo (apagar, sobrescrever, formatar), diga o que vai fazer."""


TEXTO_ECLIPSE = """- ele fala com voce de DENTRO do Eclipse IDE. Linhas "[Eclipse] ..." no
  comeco do pedido trazem a pasta do projeto selecionado, o arquivo aberto e o
  trecho selecionado no editor: use como contexto, sem repetir de volta.
"""


SESSOES_DIR = os.environ.get("JAVVA_SESSOES_DIR", "/home/javva/sessoes")
MAX_SESSOES = 9
FUSO = dt.timezone(dt.timedelta(hours=-3))       # Brasilia (sem horario de verao)


def quando(d) -> str:
    if not d:
        return "-"
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(FUSO).strftime("%d/%m/%Y - %H:%M")


OFERTA = ("  >> Nova versao do Javva (escolha de sessao com as setas): "
          "digite ATUALIZAR e Enter.")


def rotulo_sessao(s: dict, maq: dict) -> str:
    """HOSTNAME - IP - <numero de resume> - DD/MM/AAAA - HH:MM"""
    return (f"{s.get('maquina') or maq.get('maquina') or '?'} - "
            f"{s.get('ip') or maq.get('ip') or 'sem ip'} - {s['_id']} - "
            f"{quando(s.get('ultimo_comando_em'))}")


def banner_com_menu(lista: list, extra: str = "", maq: dict | None = None) -> str:
    """Menu de sessoes DENTRO do titulo, para o .bat antigo (ele imprime o
    titulo e depois " no servidor <url> - maquina <x>": a ultima linha daqui
    termina em "Conectado" para essa cauda ler bem)."""
    linhas = [BANNER, "",
              "  Sessoes desta maquina (numero de resume - ultimo comando):"]
    for i, s in enumerate(lista, 1):
        linhas.append(f"    {i}) {rotulo_sessao(s, maq or {})}")
    linhas += ["    0) Nova sessao", "",
               "  Digite o numero e Enter para continuar uma sessao, 0 para uma",
               "  nova - ou escreva direto o pedido para abrir uma sessao nova."]
    if extra:
        linhas += ["", extra]
    linhas += ["", "  Conectado"]
    return "\n".join(linhas)


class Sessao:
    async def atualizar_bat(self) -> str:
        """LEGADO (.bat v1/v2, sem auto-atualizacao, com o nome antigo): pelo
        proprio canal de execucao - o usuario ve e aprova no "Permitir?" -
        cria o Javva.bat ao lado, leva a identidade (mesmo token = mesmas
        sessoes) e agenda apagar o .bat antigo quando o cmd dele terminar."""
        if not self.base:
            return "Nao sei o endereco do servidor para baixar a nova versao."
        cmd = ("$antigo = $env:JARVIS_BAT; "
               "$novo = Join-Path (Split-Path -Parent $antigo) 'Javva.bat'; "
               f"Invoke-WebRequest -UseBasicParsing '{self.base}/javva.bat' -OutFile $novo; "
               "$v = Join-Path $env:LOCALAPPDATA 'jarvis'; "
               "$n = Join-Path $env:LOCALAPPDATA 'javva'; "
               "if ((Test-Path $v) -and -not (Test-Path $n)) "
               "{ Move-Item -LiteralPath $v -Destination $n }; "
               "$ps = (Get-CimInstance Win32_Process -Filter \"ProcessId=$PID\").ParentProcessId; "
               "$cmd = (Get-CimInstance Win32_Process -Filter \"ProcessId=$ps\").ParentProcessId; "
               "Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "
               "'-NoProfile','-Command',(\"Wait-Process -Id $cmd -EA 0; Start-Sleep 1; "
               "Remove-Item -LiteralPath '\" + $antigo + \"' -Force\"); "
               "'Javva instalado: ' + $novo")
        r = await self.pedir_cliente("executar", {"comando": cmd})
        if r.get("is_error"):
            return ("Nao foi possivel atualizar: "
                    + r["content"][0]["text"][:200])
        return ("Pronto! Feche esta janela e abra o Javva.bat (na mesma pasta "
                "deste atalho) para escolher a sessao com as setas.")

    def rodape(self, segundos=None) -> str:
        partes = [NOME_PUBLICO]
        if getattr(self, "sid", None):
            partes.append("sessao " + self.sid[:8])
        if segundos is not None:
            partes.append(f"{segundos}s")
        return "[" + " - ".join(partes) + "]"

    def __init__(self, ws, maq: dict, base: str = ""):
        self.ws = ws
        self.maq = maq
        self.sid = None
        self.retomada = None
        self.base = base            # http://host:porta como o CLIENTE o enxerga
        self.ip = ""                # IP que o .bat v4+ informa no "ola"
        self.esforco = ESFORCO      # profundidade desta conversa
        self.pendentes: dict[str, asyncio.Future] = {}
        self.fila: asyncio.Queue = asyncio.Queue()
        self.envio = asyncio.Lock()

    async def enviar(self, obj: dict) -> None:
        async with self.envio:
            await self.ws.send_json(obj)

    # ------------------------------------------------ ferramentas -> cliente
    async def pedir_cliente(self, nome: str, args: dict) -> dict:
        ident = uuid.uuid4().hex
        fut = asyncio.get_running_loop().create_future()
        self.pendentes[ident] = fut
        # Blindagem so para cliente que sabe ESCONDER o embrulho (versao>=2
        # manda "exibir" na tela/permissao). O .bat antigo mostrava o embrulho
        # inteiro a cada comando - reclamacao do usuario em 22/10/2026.
        await self.enviar({"tipo": "ferramenta", "id": ident, "nome": nome,
                           "args": args})
        try:
            r = await asyncio.wait_for(fut, ESPERA_CLIENTE)
        except asyncio.TimeoutError:
            r = {"ok": False, "saida": "o cliente nao respondeu a tempo"}
        finally:
            self.pendentes.pop(ident, None)
        return {"content": [{"type": "text",
                             "text": str(r.get("saida", ""))[:150_000]
                             or "(sem saida)"}],
                "is_error": not r.get("ok", True)}

    def servidor_mcp(self):
        s = self

        @tool("executar", "Executa um comando PowerShell NO COMPUTADOR DO "
              "USUARIO, na pasta atual dele, e devolve a saida.",
              {"comando": str})
        async def executar(args):
            return await s.pedir_cliente("executar", args)

        @tool("ler_arquivo", "Le um arquivo de texto do computador do "
              "usuario.", {"caminho": str})
        async def ler_arquivo(args):
            return await s.pedir_cliente("ler_arquivo", args)

        @tool("escrever_arquivo", "Grava (cria ou sobrescreve) um arquivo de "
              "texto no computador do usuario.",
              {"caminho": str, "conteudo": str})
        async def escrever_arquivo(args):
            return await s.pedir_cliente("escrever_arquivo", args)

        @tool("listar_pasta", "Lista o conteudo de uma pasta do computador "
              "do usuario.", {"caminho": str})
        async def listar_pasta(args):
            return await s.pedir_cliente("listar_pasta", args)

        return create_sdk_mcp_server(
            "cliente", tools=[executar, ler_arquivo, escrever_arquivo,
                              listar_pasta])

    # ------------------------------------------------ leitura do socket
    async def ler(self) -> None:
        while True:
            try:
                msg = await self.ws.receive_json()
            except Exception:                              # noqa: BLE001
                await self.fila.put({"tipo": "sair"})
                return
            if msg.get("tipo") == "resultado":
                fut = self.pendentes.get(msg.get("id"))
                if fut and not fut.done():
                    fut.set_result(msg)
            else:
                await self.fila.put(msg)

    # ------------------------------------------------ o laco da conversa
    async def rodar(self, ola: dict) -> None:
        try:
            self.versao_cliente = int(ola.get("versao") or 1)
        except (TypeError, ValueError):
            self.versao_cliente = 1
        # Pasta FIXA por maquina: o Claude Code guarda a conversa indexada pela
        # pasta de trabalho, e o resume so acha a sessao na MESMA pasta.
        # (Antes era /tmp/javva/<aleatorio> - nenhuma sessao era retomavel.)
        pedido = str(ola.get("esforco") or "").strip().lower()
        if pedido in ESFORCOS:
            self.esforco = pedido
        ip = str(ola.get("ip") or "").strip()
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", ip):
            self.ip = ip
            self.maq["ip"] = ip
            await asyncio.to_thread(B.gravar_ip, self.maq["codigo"], ip)
        pasta = f"{SESSOES_DIR}/{self.maq['codigo']}"
        os.makedirs(pasta, exist_ok=True)
        lista = await asyncio.to_thread(B.sessoes_da_maquina,
                                        self.maq["codigo"], MAX_SESSOES)
        leitor = asyncio.create_task(self.ler())
        retomar, aviso, primeira = None, "", None
        responder, atualizar = False, False
        if self.versao_cliente >= 3:
            # .bat v3: menu por setas no proprio cliente; ele responde
            # {"tipo": "sessao", "id": <resume ou null>} e espera um "fim".
            await self.enviar({"tipo": "pronto", "modelo": "",
                               "nome": NOME_PUBLICO,
                               "sessoes": [{"id": s["_id"],
                                            "quando": quando(s.get("ultimo_comando_em")),
                                            "maquina": s.get("maquina") or self.maq["maquina"],
                                            "ip": s.get("ip") or self.maq.get("ip") or "sem ip",
                                            "rotulo": rotulo_sessao(s, self.maq),
                                            "resumo": s.get("ultimo_texto", "")}
                                           for s in lista]})
            msg = await self.fila.get()
            if msg.get("tipo") == "sair":
                leitor.cancel()
                return
            if msg.get("tipo") == "sessao":
                responder = True
                sid = msg.get("id")
                retomar = next((s for s in lista if s["_id"] == sid), None)
                if sid and not retomar:          # reconexao de sessao antiga
                    retomar = await asyncio.to_thread(
                        B.sessao_por_id, sid, self.maq["codigo"])
                if not retomar and lista:
                    aviso = "Nova sessao aberta."
            else:
                primeira = msg                   # modo "javva pergunta"
        else:
            # .bat antigo (sem menu): o servidor desenha o menu no titulo e a
            # PRIMEIRA linha digitada e a escolha. Numero = retomar; 0 = nova;
            # ATUALIZAR = troca o .bat pela v3; outro texto = nova ja com ele.
            await self.enviar({"tipo": "pronto",
                               "modelo": banner_com_menu(lista, OFERTA, self.maq)
                               if lista else BANNER + "\n\n" + OFERTA
                               + "\n\n  Conectado"})
            msg = await self.fila.get()
            if msg.get("tipo") == "sair":
                leitor.cancel()
                return
            esc = (msg.get("texto") or "").strip()
            if esc.lower() == "atualizar":
                atualizar = True
            elif lista and esc.isdigit() and 1 <= int(esc) <= len(lista):
                retomar = lista[int(esc) - 1]
            elif lista and esc == "0":
                aviso = "Nova sessao aberta. Pode escrever o que precisa."
            else:
                primeira = msg
        if retomar:
            aviso = (f"Sessao {retomar['_id']} retomada (ultimo comando "
                     f"{quando(retomar.get('ultimo_comando_em'))}). "
                     "Pode continuar.")
        if atualizar:
            aviso = await self.atualizar_bat()
        self.retomada = retomar["_id"] if retomar else None
        self.sid = self.retomada
        opcoes = ClaudeAgentOptions(
            resume=self.retomada,
            model=MODELO,
            tools=ORQUESTRACAO,
            mcp_servers={"cliente": self.servidor_mcp()},
            allowed_tools=[f"mcp__cliente__{n}" for n in NOMES]
            + (ORQUESTRACAO + ["Task"] if ULTRACODE else []),
            system_prompt=prompt_sistema(ola),
            include_partial_messages=True,
            setting_sources=[],
            settings=json.dumps({"ultracode": ULTRACODE}),
            env={"CLAUDE_CODE_WORKFLOWS": "1"} if ULTRACODE else {},
            effort=self.esforco,
            cwd=pasta,
        )
        try:
            async with ClaudeSDKClient(options=opcoes) as cli:
                if aviso:
                    await self.enviar({"tipo": "texto", "texto": "  " + aviso})
                if aviso or responder:
                    await self.enviar({"tipo": "fim",
                                       "info": self.rodape() if aviso else "",
                                       "sessao": self.sid})
                if primeira:
                    await self.turno(cli, primeira)
                while True:
                    msg = await self.fila.get()
                    if msg.get("tipo") == "sair":
                        break
                    if msg.get("tipo") != "prompt":
                        continue
                    await self.turno(cli, msg)
        finally:
            leitor.cancel()

    async def turno(self, cli, msg: dict) -> None:
        conteudo = [{"type": "image", "source": {
                        "type": "base64", "media_type": i["media_type"],
                        "data": i["base64"]}}
                    for i in (msg.get("imagens") or [])]
        conteudo.append({"type": "text", "text": msg.get("texto") or "(foto)"})

        async def mensagens():
            yield {"type": "user", "parent_tool_use_id": None,
                   "message": {"role": "user", "content": conteudo}}

        await cli.query(mensagens())
        mandou_texto = False
        retido = ""

        async def texto(t: str, fim: bool = False) -> None:
            # Segura o rabo do texto: um nome proibido pode vir partido entre
            # dois pedacos do streaming ("Cla" + "ude").
            nonlocal retido
            limpo = limpar_nomes(retido + t)
            corte = len(limpo) if fim else max(0, len(limpo) - _RETEM)
            retido = limpo[corte:]
            if limpo[:corte]:
                await self.enviar({"tipo": "texto", "texto": limpo[:corte]})

        async for m in cli.receive_response():
            if getattr(m, "parent_tool_use_id", None):
                continue                     # texto de subagente: so o principal fala
            if isinstance(m, StreamEvent):
                ev = m.event or {}
                d = ev.get("delta") or {}
                if ev.get("type") == "content_block_delta" and \
                        d.get("type") == "text_delta":
                    mandou_texto = True
                    await texto(d["text"])
            elif isinstance(m, AssistantMessage):
                for b in m.content:
                    if isinstance(b, ToolUseBlock) and b.name in (
                            "Workflow", "Agent", "Task"):
                        await texto("\n  [orquestrando agentes...]\n")
                    elif isinstance(b, TextBlock) and b.text and \
                            not mandou_texto:
                        await texto(b.text)
            elif isinstance(m, ResultMessage):
                uso = getattr(m, "usage", None) or {}
                custo = getattr(m, "total_cost_usd", None)
                linha = {"caminho": "sessao", "status": 200, "modelo": MODELO,
                         "ms": getattr(m, "duration_ms", 0), "stream": True,
                         "custo_usd": custo}
                for k in ("input_tokens", "output_tokens",
                          "cache_read_input_tokens",
                          "cache_creation_input_tokens"):
                    if isinstance(uso.get(k), int):
                        linha[k] = uso[k]
                await asyncio.to_thread(B.gravar_uso, self.maq, linha)
                await texto("", fim=True)
                sid = getattr(m, "session_id", None)
                if sid:
                    if self.retomada and sid != self.retomada:
                        # a retomada ganhou id novo: a lista mostra so o atual
                        await asyncio.to_thread(B.apagar_sessao, self.retomada)
                        self.retomada = sid
                    self.sid = sid
                    await asyncio.to_thread(B.gravar_sessao, self.maq, sid,
                                            msg.get("texto") or "(foto)", self.ip)
                info = self.rodape(round((linha["ms"] or 0) / 1000, 1))
                if getattr(m, "is_error", False):
                    await self.enviar({"tipo": "erro", "mensagem": limpar_nomes(
                        str(getattr(m, "result", "") or "falha na IA"))})
                await self.enviar({"tipo": "fim", "info": info,
                                   "sessao": self.sid})
