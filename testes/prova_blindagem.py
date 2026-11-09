# -*- coding: utf-8 -*-
"""Prova da blindagem de comandos (cerebro.blindar) NESTA maquina Windows,
rodando o comando embrulhado exatamente como o javva.bat roda (powershell
filho, -EncodedCommand, stdout/stderr redirecionados).

Uso: python testes/prova_blindagem.py   (precisa de Word instalado p/ casos 3-4)
"""
import base64
import os
import subprocess
import sys
import tempfile
import time
import types

os.environ["JAVVA_LIMITE_CMD"] = "25"
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "app"))
stub = types.ModuleType("claude_agent_sdk")
stub.__getattr__ = lambda nome: (lambda *a, **k: (lambda f: f)) \
    if nome == "tool" else type(nome, (), {})
sys.modules["claude_agent_sdk"] = stub
import cerebro  # noqa: E402

falhas = []
PASTA = tempfile.mkdtemp(prefix="javva-blind-")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQV"
                       "R4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==")


def ok(nome, cond, det=""):
    print(("  ok    " if cond else "  FALHA ") + nome
          + (f"  -> {det}" if det else ""), flush=True)
    if not cond:
        falhas.append(nome)


def rodar_como_cliente(cmd, timeout=120):
    """Igual ao Rodar-Comando do javva.bat."""
    prefixo = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
               "$ProgressPreference='SilentlyContinue'; ")
    enc = base64.b64encode((prefixo + cmd).encode("utf-16-le")).decode()
    t0 = time.monotonic()
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive",
                        "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                       capture_output=True, timeout=timeout, cwd=PASTA)
    out = (r.stdout.decode("utf-8", "replace") + r.stderr.decode(
        "utf-8", "replace"))
    return r.returncode, out, time.monotonic() - t0


def words():
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "Get-Process WINWORD -EA 0 | ForEach-Object { "
                        "'{0}:{1}' -f $_.Id, $_.MainWindowHandle }"],
                       capture_output=True, text=True)
    return [l for l in r.stdout.split() if l]


def resumo(s, n=200):
    return " | ".join(l.strip() for l in s.splitlines() if l.strip())[:n]


print("== 1. comando normal")
rc0, out0, t_puro = rodar_como_cliente("Write-Output 'ola javva'")
rc, out, t = rodar_como_cliente(cerebro.blindar("Write-Output 'ola javva'"))
ok("saida e exit 0", rc == 0 and "ola javva" in out, resumo(out))
ok("sem lixo tecnico (CLIXML) na saida", "CLIXML" not in out, resumo(out, 120))
print(f"     custo da blindagem: {t - t_puro:.1f}s (puro {t_puro:.1f}s, blindado {t:.1f}s)")

print("== 2. comando que estoura o limite (25s)")
rc, out, t = rodar_como_cliente(cerebro.blindar("Start-Sleep -Seconds 60; 'nunca'"))
ok("TEMPO ESGOTADO em ~25s, exit 124",
   rc == 124 and "TEMPO ESGOTADO" in out and t < 60, f"{t:.1f}s {resumo(out, 120)}")

print("== 3. o travamento REAL do Word (HTML com imagem vinculada)")
with open(os.path.join(PASTA, "img.png"), "wb") as fh:
    fh.write(PNG)
with open(os.path.join(PASTA, "_fonte.html"), "w", encoding="utf-8") as fh:
    # Identico ao HTML que trava sempre (word_repro): sem o <head> com meta
    # charset/title o Word abre sem o aviso e o caso nao prova nada.
    fh.write("<html><head><meta charset='utf-8'><title>t</title></head><body>"
             "<h1>Criterios de aceite</h1><p>Criterio 1 - teste</p>"
             "<img src='img.png'></body></html>")
antes = words()
cmd_print = (
    "$w=New-Object -ComObject Word.Application; $w.Visible=$false; "
    "$w.DisplayAlerts=0; try { $d=$w.Documents.Open('" + PASTA
    + "\\_fonte.html'); $d.SaveAs2('" + PASTA + "\\t.doc',0); $d.Close(0); "
    "'gerado' } finally { $w.Quit() }")
rc, out, t = rodar_como_cliente(cerebro.blindar(cmd_print))
time.sleep(2)
ok("nao trava: TEMPO ESGOTADO", rc == 124 and "TEMPO ESGOTADO" in out,
   f"{t:.1f}s")
ok("devolve o texto do aviso que travou", "Security Notice" in out,
   resumo(out, 260))
ok("nenhum Word novo sobrou", words() == antes, words())

print("== 4. Word orfao (sem janela) e fechado antes da proxima automacao")
subprocess.run(["powershell", "-NoProfile", "-Command",
                "$w=New-Object -ComObject Word.Application; $w.Visible=$false"],
               capture_output=True)
time.sleep(2)
orfaos = [w for w in words() if w.endswith(":0") and w not in antes]
ok("orfao criado para o teste", bool(orfaos), orfaos)
cmd_montar = (
    "$w=New-Object -ComObject Word.Application; $w.Visible=$false; "
    "try { $d=$w.Documents.Add(); $d.Content.Text='Criterios de aceite'; "
    "[void]$d.InlineShapes.AddPicture('" + PASTA + "\\img.png', $false, $true, "
    "$d.Content.Paragraphs.Last.Range); $d.SaveAs2('" + PASTA + "\\ok.doc',0); "
    "$d.Close(0); 'doc ok' } finally { $w.Quit() }")
rc, out, t = rodar_como_cliente(cerebro.blindar(cmd_montar))
time.sleep(2)
ok("receita segura gera o .doc", rc == 0 and "doc ok" in out
   and os.path.exists(os.path.join(PASTA, "ok.doc")), f"{t:.1f}s {resumo(out)}")
ok("orfao foi fechado antes", not any(o in words() for o in orfaos), words())

print("== 5. here-string preservada (o Claude usa para JS do Jira)")
here = '$js = @"\nconst x = [1,2];\nreturn x.join(",");\n"@\n$js'
rc, out, _ = rodar_como_cliente(cerebro.blindar(here))
ok("here-string intacta", rc == 0 and 'return x.join(",")' in out, resumo(out))

print("== 6. codigo de saida de programa externo")
rc, out, _ = rodar_como_cliente(cerebro.blindar("cmd /c exit 3"))
ok("codigo de saida repassado", rc == 3, rc)

print("== 7. erro de PowerShell volta legivel")
rc, out, _ = rodar_como_cliente(cerebro.blindar("Get-Item 'Z:/nao-existe-javva'"))
ok("erro em texto, sem XML", "nao-existe-javva" in out and "CLIXML" not in out,
   resumo(out, 160))

print("\nPROVA BLINDAGEM:", "PASSOU" if not falhas else
      f"{len(falhas)} FALHA(S): " + "; ".join(falhas))
sys.exit(1 if falhas else 0)
