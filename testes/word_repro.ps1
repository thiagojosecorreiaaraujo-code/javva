param([string]$Variante = 'print', [int]$Limite = 60)
# Reproduz o comando do Javva (Word via COM, escondido) exatamente como o
# javva.bat roda: powershell filho, -EncodedCommand, stdout/stderr redirecionados.
$base = Join-Path $PSScriptRoot 'PVO-TESTE'
New-Item -ItemType Directory -Force $base | Out-Null
$png = [Convert]::FromBase64String('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==')
[IO.File]::WriteAllBytes("$base\img.png", $png)
$html = "<html><head><meta charset='utf-8'><title>t</title></head><body><h1>Criterios de aceite</h1><p>Criterio 1 - teste</p><img src='img.png'></body></html>"
[IO.File]::WriteAllText("$base\_fonte.html", $html, (New-Object Text.UTF8Encoding($false)))
Remove-Item "$base\PVO-TESTE.doc" -ErrorAction SilentlyContinue

$abrir = @{
    'print'      = '$d=$w.Documents.Open($src)'
    'sem-dialogo' = '$d=$w.Documents.Open($src, $false, $true, $false, "", "", $false, "", "", 0, 65001, $false, $false, 0, $true)'
    'links-off'   = '$w.Options.UpdateLinksAtOpen=$false; $d=$w.Documents.Open($src)'
    'links-off+sem-dialogo' = '$w.Options.UpdateLinksAtOpen=$false; $d=$w.Documents.Open($src, $false, $true, $false, "", "", $false, "", "", 0, 65001, $false, $false, 0, $true)'
    'montar' = '$d=$w.Documents.Add(); $r=$d.Content; $r.Text="Criterios de aceite"; $r.InsertParagraphAfter(); $r.InsertAfter("Criterio 1 - teste"); $r.InsertParagraphAfter(); [void]$d.InlineShapes.AddPicture((Split-Path $src) + "\img.png", $false, $true, $d.Content.Paragraphs.Last.Range)'
}[$Variante]

$cmd = @"
`$ProgressPreference='SilentlyContinue'; `$w = New-Object -ComObject Word.Application; `$w.Visible=`$false; `$w.DisplayAlerts=0
try { `$src='$base\_fonte.html'; `$dst='$base\PVO-TESTE.doc'; $abrir; `$d.SaveAs2(`$dst,0); `$d.Close(0); if(Test-Path `$dst){ "doc gerado (`$((Get-Item `$dst).Length) bytes)" } else { 'FALHOU' } } finally { `$w.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject(`$w) }
"@

$antes = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object Id)
$enc = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($cmd))
$psi = New-Object Diagnostics.ProcessStartInfo
$psi.FileName = 'powershell.exe'
$psi.Arguments = "-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $enc"
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$t0 = Get-Date
$p = [Diagnostics.Process]::Start($psi)
$out = $p.StandardOutput.ReadToEndAsync()
$err = $p.StandardError.ReadToEndAsync()
if ($p.WaitForExit($Limite * 1000)) {
    "[$Variante] TERMINOU em {0:N1}s, exit {1}" -f ((Get-Date) - $t0).TotalSeconds, $p.ExitCode
    "saida: " + $out.Result.Trim()
    if ($err.Result.Trim()) { "stderr: " + $err.Result.Trim().Substring(0, [Math]::Min(400, $err.Result.Trim().Length)) }
} else {
    "[$Variante] TRAVOU: passou de ${Limite}s"
    Add-Type -AssemblyName UIAutomationClient
    $novos = Get-Process WINWORD -ErrorAction SilentlyContinue | Where-Object { $antes -notcontains $_.Id }
    foreach ($w in $novos) {
        $cond = New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ProcessIdProperty, $w.Id)
        $janelas = [Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children, $cond)
        "WINWORD pid $($w.Id): $($janelas.Count) janela(s) de topo"
        foreach ($j in $janelas) {
            $textos = $j.FindAll([Windows.Automation.TreeScope]::Descendants, [Windows.Automation.Condition]::TrueCondition) |
                ForEach-Object { $_.Current.Name } | Where-Object { $_ } | Select-Object -Unique -First 12
            "  janela: '$($j.Current.Name)'  visivel=$(-not $j.Current.IsOffscreen)  textos: $($textos -join ' | ')"
        }
    }
    try { $p.Kill() } catch { }
    $novos | Stop-Process -Force -ErrorAction SilentlyContinue
    "(processos de teste encerrados)"
}
