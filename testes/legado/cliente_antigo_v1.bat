<# : jarvis.bat - cliente do Jarvis (o Claude roda no servidor; os comandos rodam aqui)
@echo off
setlocal
set "JARVIS_BAT=%~f0"
set "JARVIS_ARGS=%*"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression ([IO.File]::ReadAllText($env:JARVIS_BAT))"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" if not defined JARVIS_ARGS pause
exit /b %RC%
#>

# ============================ PowerShell a partir daqui ============================
# Uso:  jarvis            -> conversa (fica esperando comandos, como o claude)
#       jarvis "pergunta" -> responde uma vez e sai
# Fotos: escreva/cole/arraste o caminho de um .png .jpg .gif .webp na mensagem.
# Servidor: variavel JARVIS_URL (padrao http://192.168.68.106:8787).

$ErrorActionPreference = 'Stop'
$URL  = if ($env:JARVIS_URL) { $env:JARVIS_URL.TrimEnd('/') } else { 'http://192.168.68.106:8787' }
$CONT = if ($env:JARVIS_CONTAINER) { $env:JARVIS_CONTAINER } else { 'jarvis' }
$DIR  = Join-Path $env:LOCALAPPDATA 'jarvis'
New-Item -ItemType Directory -Force -Path $DIR | Out-Null
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -AssemblyName System.Web.Extensions
$JSON = New-Object Web.Script.Serialization.JavaScriptSerializer
$JSON.MaxJsonLength = [int]::MaxValue
$script:SempreSim = $false

# ---------------------------------------------------------------- identidade
$arqToken = Join-Path $DIR 'token'
if (-not (Test-Path $arqToken)) {
    $b = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    [IO.File]::WriteAllText($arqToken, (($b | ForEach-Object { $_.ToString('x2') }) -join ''))
}
$TOKEN = ([IO.File]::ReadAllText($arqToken)).Trim()
# Mesmo codigo que o servidor mostra: 6 primeiros hex do sha256 do token.
$sha = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($TOKEN))
$CODIGO = ((($sha | ForEach-Object { $_.ToString('x2') }) -join '').Substring(0, 6)).ToUpper()

function Status {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "$URL/status" -Headers @{ Authorization = "Bearer $TOKEN" } -TimeoutSec 10
        return @{ code = 200; txt = $r.Content.Trim() }
    } catch {
        $resp = $_.Exception.Response
        if ($resp) {
            # PowerShell 5.1: o corpo de uma resposta de ERRO fica em
            # ErrorDetails.Message; o stream da resposta ja vem vazio.
            $txt = ''
            if ($_.ErrorDetails -and $_.ErrorDetails.Message) { $txt = $_.ErrorDetails.Message.Trim() }
            return @{ code = [int]$resp.StatusCode; txt = $txt }
        }
        return @{ code = 0; txt = $_.Exception.Message }
    }
}

function Garantir-Acesso {
    $avisou = $false
    while ($true) {
        $s = Status
        if ($s.code -eq 200) { return }
        if ($s.code -eq 0) { throw "Jarvis fora do ar em $URL ($($s.txt))" }
        if ($s.code -eq 401) {
            $r = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$URL/registrar" -Body @{ maquina = $env:COMPUTERNAME; token = $TOKEN } -TimeoutSec 10
            Write-Host $r.Content.Trim() -ForegroundColor DarkGray
            continue
        }
        if ($s.txt -match 'revogad') { throw $s.txt }
        if (-not $avisou) {
            Write-Host "Esta maquina aguarda aprovacao no servidor (codigo $CODIGO)." -ForegroundColor Yellow
            Write-Host "No servidor: docker exec jarvis python admin.py aprovar $CODIGO" -ForegroundColor Yellow
            $avisou = $true
        }
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            # Rodando NO servidor: quem tem o docker e o administrador.
            try { & docker exec $CONT python admin.py aprovar $CODIGO 2>$null | Out-Null } catch { }
        }
        Start-Sleep -Seconds 3
    }
}

# ---------------------------------------------------------------- websocket
$script:ws = $null

function Enviar($obj) {
    $bytes = [Text.Encoding]::UTF8.GetBytes($JSON.Serialize($obj))
    $seg = New-Object 'System.ArraySegment[byte]' -ArgumentList @(, $bytes)
    [void]$script:ws.SendAsync($seg, [Net.WebSockets.WebSocketMessageType]::Text, $true, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
}

function Receber {
    $buf = New-Object byte[] 65536
    $ms = New-Object IO.MemoryStream
    do {
        $seg = New-Object 'System.ArraySegment[byte]' -ArgumentList @(, $buf)
        $r = $script:ws.ReceiveAsync($seg, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
        if ($r.MessageType -eq [Net.WebSockets.WebSocketMessageType]::Close) { return $null }
        $ms.Write($buf, 0, $r.Count)
    } until ($r.EndOfMessage)
    return $JSON.DeserializeObject([Text.Encoding]::UTF8.GetString($ms.ToArray()))
}

function Conectar {
    $script:ws = New-Object Net.WebSockets.ClientWebSocket
    $script:ws.Options.SetRequestHeader('Authorization', "Bearer $TOKEN")
    $script:ws.Options.KeepAliveInterval = [TimeSpan]::FromSeconds(20)
    $uri = [Uri](($URL -replace '^http', 'ws') + '/sessao')
    [void]$script:ws.ConnectAsync($uri, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
    $so = (Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue).Caption
    Enviar @{ tipo = 'ola'; maquina = $env:COMPUTERNAME; usuario = $env:USERNAME; pasta = (Get-Location).Path; so = "$so" }
    $m = Receber
    if ($null -eq $m) { throw 'o Jarvis fechou a conexao' }
    if ($m.tipo -eq 'erro') { throw $m.mensagem }
    return $m.modelo
}

# ---------------------------------------------------------------- execucao local
function Caminho([string]$c) {
    $c = $c.Trim().Trim('"')
    if ([IO.Path]::IsPathRooted($c)) { return $c }
    return (Join-Path (Get-Location).Path $c)
}

function Permitir([string]$acao, [string]$detalhe) {
    if ($script:SempreSim) { return $true }
    Write-Host ''
    Write-Host "[$acao]" -ForegroundColor Yellow
    Write-Host $detalhe
    Write-Host -NoNewline 'Permitir? (S)im / (N)ao / (T)udo nesta sessao [S]: ' -ForegroundColor Yellow
    $r = [Console]::ReadLine()
    if ($null -eq $r) { return $false }
    if ($r -match '^\s*[tT]') { $script:SempreSim = $true; return $true }
    return ($r -match '^\s*[sS]' -or $r.Trim() -eq '')
}

function Rodar-Comando([string]$cmd) {
    $prefixo = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; `$ProgressPreference='SilentlyContinue'; "
    $enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($prefixo + $cmd))
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = 'powershell.exe'
    $psi.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $enc"
    $psi.WorkingDirectory = (Get-Location).Path
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
    $psi.StandardErrorEncoding = [Text.Encoding]::UTF8
    $p = [Diagnostics.Process]::Start($psi)
    $tarefaErro = $p.StandardError.ReadToEndAsync()
    $saida = $p.StandardOutput.ReadToEnd()
    $p.WaitForExit()
    $erro = $tarefaErro.Result
    $texto = $saida.TrimEnd()
    if ($erro.Trim()) { $texto += "`n[stderr]`n" + $erro.TrimEnd() }
    return @{ ok = ($p.ExitCode -eq 0); saida = "$texto`n[exit $($p.ExitCode)]" }
}

function Executar-Ferramenta($m) {
    $a = $m.args
    try {
        switch ($m.nome) {
            'executar' {
                $mostra = if ($a.exibir) { $a.exibir } else { $a.comando }
                Write-Host "`n  > executar: $mostra" -ForegroundColor DarkYellow
                if (-not (Permitir 'Executar comando' $mostra)) { return @{ ok = $false; saida = 'O usuario recusou este comando.' } }
                $r = Rodar-Comando $a.comando
                Write-Host ('    ' + (($r.saida -split "`n" | Select-Object -First 6) -join "`n    ")) -ForegroundColor DarkGray
                return $r
            }
            'ler_arquivo' {
                $p = Caminho $a.caminho
                Write-Host "`n  > lendo: $p" -ForegroundColor DarkYellow
                if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { return @{ ok = $false; saida = "arquivo nao existe: $p" } }
                if ((Get-Item -LiteralPath $p).Length -gt 2MB) { return @{ ok = $false; saida = "arquivo maior que 2 MB: $p" } }
                return @{ ok = $true; saida = [IO.File]::ReadAllText($p) }
            }
            'escrever_arquivo' {
                $p = Caminho $a.caminho
                $linhas = ($a.conteudo -split "`n").Count
                Write-Host "`n  > gravar: $p ($linhas linhas)" -ForegroundColor DarkYellow
                $previa = (($a.conteudo -split "`n" | Select-Object -First 12) -join "`n")
                if (-not (Permitir "Gravar $p" $previa)) { return @{ ok = $false; saida = 'O usuario recusou a gravacao.' } }
                $pasta = Split-Path -Parent $p
                if ($pasta -and -not (Test-Path -LiteralPath $pasta)) { New-Item -ItemType Directory -Force -Path $pasta | Out-Null }
                [IO.File]::WriteAllText($p, $a.conteudo, (New-Object Text.UTF8Encoding($false)))
                return @{ ok = $true; saida = "gravado: $p" }
            }
            'listar_pasta' {
                $p = Caminho $a.caminho
                Write-Host "`n  > listando: $p" -ForegroundColor DarkYellow
                $itens = Get-ChildItem -LiteralPath $p -Force | ForEach-Object {
                    $tam = if ($_.PSIsContainer) { '<DIR>' } else { $_.Length }
                    "{0}`t{1}`t{2}" -f $tam, $_.LastWriteTime.ToString('yyyy-MM-dd HH:mm'), $_.Name
                }
                return @{ ok = $true; saida = ($itens -join "`n") }
            }
            default { return @{ ok = $false; saida = "ferramenta desconhecida: $($m.nome)" } }
        }
    } catch {
        return @{ ok = $false; saida = "erro no cliente: $($_.Exception.Message)" }
    }
}

# ---------------------------------------------------------------- conversa
function Extrair-Imagens([string]$linha) {
    $imgs = New-Object System.Collections.ArrayList
    $tipos = @{ png = 'image/png'; jpg = 'image/jpeg'; jpeg = 'image/jpeg'; gif = 'image/gif'; webp = 'image/webp' }
    $rx = '"([^"]+\.(?:png|jpe?g|gif|webp))"|(\S+\.(?:png|jpe?g|gif|webp))'
    foreach ($m in [regex]::Matches($linha, $rx, 'IgnoreCase')) {
        $c = if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value }
        $c = Caminho $c
        if (-not (Test-Path -LiteralPath $c -PathType Leaf)) { continue }
        $bytes = [IO.File]::ReadAllBytes($c)
        if ($bytes.Length -gt 5MB) { Write-Host "  (foto acima de 5 MB ignorada: $c)" -ForegroundColor Yellow; continue }
        $ext = [IO.Path]::GetExtension($c).ToLower().TrimStart('.')
        [void]$imgs.Add(@{ nome = [IO.Path]::GetFileName($c); media_type = $tipos[$ext]; base64 = [Convert]::ToBase64String($bytes) })
        Write-Host "  [foto anexada: $([IO.Path]::GetFileName($c))]" -ForegroundColor DarkGray
    }
    return , $imgs.ToArray()
}

function Perguntar([string]$texto) {
    $imgs = Extrair-Imagens $texto
    Enviar @{ tipo = 'prompt'; texto = $texto; imagens = $imgs }
    while ($true) {
        $m = Receber
        if ($null -eq $m) { throw 'conexao com o Jarvis perdida' }
        switch ($m.tipo) {
            'texto'      { Write-Host -NoNewline $m.texto }
            'ferramenta' { $r = Executar-Ferramenta $m; Enviar @{ tipo = 'resultado'; id = $m.id; ok = $r.ok; saida = $r.saida } }
            'erro'       { Write-Host "`n$($m.mensagem)" -ForegroundColor Red }
            'fim'        { Write-Host ''; Write-Host $m.info -ForegroundColor DarkGray; return }
        }
    }
}

try {
    Garantir-Acesso
    $modelo = Conectar
    if ($env:JARVIS_ARGS) {
        # O cmd entrega aspas internas como \" e o texto inteiro entre aspas.
        $q = $env:JARVIS_ARGS -replace '\\"', '"'
        if ($q.Length -ge 2 -and $q.StartsWith('"') -and $q.EndsWith('"')) { $q = $q.Substring(1, $q.Length - 2) }
        Perguntar $q
        Enviar @{ tipo = 'sair' }
        exit 0
    }
    Write-Host ''
    Write-Host "  JARVIS  -  Claude $modelo no servidor $URL  -  maquina $env:COMPUTERNAME" -ForegroundColor Cyan
    Write-Host "  Pasta: $((Get-Location).Path)" -ForegroundColor DarkGray
    Write-Host '  Escreva o que precisa. Fotos: cole ou arraste o arquivo. /sair encerra.' -ForegroundColor DarkGray
    while ($true) {
        Write-Host ''
        Write-Host -NoNewline '> ' -ForegroundColor Cyan
        $linha = [Console]::ReadLine()
        if ($null -eq $linha -or $linha.Trim() -in @('/sair', 'sair', 'exit')) { break }
        if (-not $linha.Trim()) { continue }
        try {
            Perguntar $linha
        } catch {
            Write-Host "`n$($_.Exception.Message) - reconectando (a conversa recomeca)..." -ForegroundColor Yellow
            $modelo = Conectar
        }
    }
    try { Enviar @{ tipo = 'sair' } } catch { }
    exit 0
} catch {
    Write-Host "`nERRO: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
