
# ===================== PONTE DO NOME ANTIGO =====================
# Servida SO no endereco antigo do .bat. Este arquivo ainda tem o nome antigo:
# cria o Javva.bat ao lado, leva a identidade (mesmo token = mesmas sessoes)
# e apaga este arquivo quando o cmd terminar. Depois segue como o Javva.
if (-not $env:JAVVA_BAT) {
    $antigo = $env:JARVIS_BAT
    if (-not $env:JAVVA_URL -and $env:JARVIS_URL) { $env:JAVVA_URL = $env:JARVIS_URL }
    if (-not $env:JAVVA_CONTAINER -and $env:JARVIS_CONTAINER) { $env:JAVVA_CONTAINER = $env:JARVIS_CONTAINER }
    if ($env:JARVIS_ARGS) { $env:JAVVA_ARGS = $env:JARVIS_ARGS }
    $base = if ($env:JAVVA_URL) { $env:JAVVA_URL.TrimEnd('/') } else { 'http://192.168.68.106:8787' }
    $env:JAVVA_ATUALIZADO = '1'
    $env:JAVVA_BAT = $antigo
    try {
        $dirVelho = Join-Path $env:LOCALAPPDATA 'jarvis'
        $dirNovo = Join-Path $env:LOCALAPPDATA 'javva'
        if ((Test-Path -LiteralPath $dirVelho) -and -not (Test-Path -LiteralPath $dirNovo)) {
            Move-Item -LiteralPath $dirVelho -Destination $dirNovo
        }
        $pastaBat = Split-Path -Parent $antigo
        $novoBat = Join-Path $pastaBat 'Javva.bat'
        Invoke-WebRequest -UseBasicParsing -Uri "$base/javva.bat" -OutFile $novoBat -TimeoutSec 30
        $cmdPid = (Get-CimInstance Win32_Process -Filter "ProcessId=$PID").ParentProcessId
        $apagar = "Wait-Process -Id $cmdPid -ErrorAction SilentlyContinue; Start-Sleep -Seconds 1; " +
                  "Remove-Item -LiteralPath '" + ($antigo -replace "'", "''") + "' -Force"
        Start-Process powershell.exe -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', $apagar
        $env:JAVVA_BAT = $novoBat
        Write-Host "  Atualizado para o Javva. Daqui para a frente use o Javva.bat em $pastaBat" -ForegroundColor DarkGray
    } catch {
        Write-Host "  (nao consegui criar o Javva.bat: $($_.Exception.Message))" -ForegroundColor Yellow
    }
}
# =================================================================
