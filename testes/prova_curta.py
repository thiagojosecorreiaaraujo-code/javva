# -*- coding: utf-8 -*-
"""Protecao com o javva.bat ORIGINAL (sem versao 2): forma curta + /blindagem.ps1."""
import base64, os, subprocess, sys, tempfile, time, json, urllib.request
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAT = os.path.join(RAIZ, "testes", "legado", "cliente_antigo_v1.bat")
BASE = "http://127.0.0.1:8788"
falhas = []
def ok(n, c, d=""):
    print(("  ok    " if c else "  FALHA ") + n + (f"  -> {d}" if d else ""), flush=True)
    if not c: falhas.append(n)
def curta_servidor(cmd):
    cod = ("import cerebro,json,sys; print(json.dumps(cerebro.blindar_curto(sys.argv[1], %r)))" % BASE)
    r = subprocess.run(["docker", "exec", "javva-teste", "python", "-c", cod, cmd], capture_output=True, text=True)
    return json.loads(r.stdout)
def curta(cmd):
    # monta localmente (argumento via docker exec corrompe barra invertida)
    return "$javva = @'" + chr(10) + cmd + chr(10) + "'@" + chr(10) + "irm " + BASE + "/blindagem.ps1 | iex"
def como_cliente(cmd, timeout=120):
    pre = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ProgressPreference='SilentlyContinue'; "
    enc = base64.b64encode((pre + cmd).encode("utf-16-le")).decode()
    t0 = time.monotonic()
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc], capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace"), time.monotonic() - t0
def words():
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-Process WINWORD -EA 0 | ForEach-Object Id) -join ','"], capture_output=True, text=True)
    return r.stdout.strip()

print("== tela do .bat original")
c = curta_servidor("Write-Output 'ola'")
ok("servidor gera a mesma forma curta", c == curta("Write-Output 'ola'"), repr(c))
ok("comando curto: original legivel + 1 linha", c.count("\n") == 3 and "Write-Output 'ola'" in c and "blindagem.ps1" in c, repr(c))
ok("sem o bloco tecnico", "$__" not in c)
rc, out, t = como_cliente(c)
ok("executa com protecao", rc == 0 and "ola" in out, f"{t:.1f}s {out.strip()[:80]!r}")

print("== travamento REAL do Word pela forma curta")
pasta = tempfile.mkdtemp(prefix="javva-curta-")
open(os.path.join(pasta, "img.png"), "wb").write(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg=="))
open(os.path.join(pasta, "_fonte.html"), "w", encoding="utf-8").write("<html><head><meta charset='utf-8'><title>t</title></head><body><h1>Criterios de aceite</h1><p>Criterio 1 - teste</p><img src='img.png'></body></html>")
antes = words()
cmd = ("$w=New-Object -ComObject Word.Application; $w.Visible=$false; $w.DisplayAlerts=0; try { $d=$w.Documents.Open('" + pasta + "/_fonte.html'); $d.SaveAs2('" + pasta + "/t.doc',0); $d.Close(0); 'gerado' } finally { $w.Quit() }")
rc, out, t = como_cliente(curta(cmd), timeout=180)
time.sleep(2)
ok("nao trava: TEMPO ESGOTADO", rc == 124 and "TEMPO ESGOTADO" in out, f"{t:.1f}s")
ok("devolve a janela que travou", "Security Notice" in out, out.strip()[-160:])
ok("nenhum Word sobrou", words() == antes, words())

print("\nPROVA CURTA:", "PASSOU" if not falhas else f"{len(falhas)} FALHA(S): " + "; ".join(falhas))
sys.exit(1 if falhas else 0)
