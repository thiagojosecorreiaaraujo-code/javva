# Notas técnicas (gotchas medidos)

## Cliente de console (`javva.bat`, PowerShell 5.1)

- Corpo de resposta de ERRO fica em `$_.ErrorDetails.Message` (o stream vem
  vazio). O código da máquina é calculado no cliente (sha256 do token) para
  não depender desse texto.
- `.GetAwaiter().GetResult()` de `SendAsync`/`ConnectAsync` imprime
  `System.Threading.Tasks.VoidTaskResult`: use `[void]`.
- `cmd`: `"%VAR%"==""` quebra se a variável tiver aspas; use `if defined`.
  Argumentos chegam com `\"`: normalize no PowerShell.

## Servidor

- O SDK anexa uma mensagem `role: system` DEPOIS da do usuário no
  `messages`: quem inspeciona o pedido deve buscar a última `role: user`.
- `tools=[]` no Agent SDK desliga as ferramentas nativas; ainda aparece
  `DeferredToolPlaceholder` na lista enviada ao modelo.
- Retomar sessão exige `cwd` FIXO por máquina (`JAVVA_SESSOES_DIR/<codigo>`)
  e `~/.claude` num volume nomeado criado na imagem com `chown` (senão o
  volume nasce root).
- Replica set do Mongo anunciado como `localhost` → `directConnection=true`
  dentro do container.
- WebSocket: ping do servidor espaçado (`--ws-ping-interval 3600`); o
  PowerShell só responde ping enquanto lê o socket.
- Todo comando roda "blindado": job com limite (`JAVVA_LIMITE_CMD`); se
  estourar, o cliente encerra o job, fecha o Office escondido que o comando
  abriu e devolve o texto da caixa de diálogo que travou.

## Plugin Eclipse

- `java.net.http.HttpClient` tenta `Upgrade: h2c` em http puro e o uvicorn
  lê o corpo do POST vazio: fixe `HttpClient.Version.HTTP_1_1`.
- `Ctrl+V` numa view é atalho global do Eclipse: para colar imagem, use
  `setGlobalActionHandler(ActionFactory.PASTE.getId(), …)`, não `KeyDown`.
- Imagem da área de transferência vem em 32 bits (alfa pode vir zerado):
  converter para 24 bits opaco e reduzir com `GC.setInterpolation(SWT.HIGH)`.
- p2 (2024+) reescreve `http://` → `https://`: instale por **Archive…** ou
  use `-Dp2.httpRule=allow`.
