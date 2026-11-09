# -*- coding: utf-8 -*-
"""O plugin DENTRO do eclipse.exe de verdade, sem tocar na instalacao do usuario.

Copia so a configuracao do Eclipse (config.ini + bundles.info) para uma pasta
temporaria, acrescenta o jar do plugin no bundles.info e abre o eclipsec.exe
com essa configuracao, um workspace novo e -Djavva.autoteste. O Autoteste do
plugin abre a aba, usa a PROPRIA tela (combo, entrada, Enviar, Permitir?),
salva prints + o texto da conversa e fecha o Eclipse.

Rodada 1: sem sessoes -> sessao nova, comando com Permitir? (Sim), foto.
Rodada 2: mesma maquina -> lista "HOSTNAME - IP - resume - data" e retoma.

Pre: docker compose -f docker-compose.teste.yml up -d --build
     python eclipse/construir.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ECLIPSE = os.environ.get("JAVVA_ECLIPSE", r"C:\Users\MESA_DIREITA\eclipse\java-2026-09\eclipse")
SITE = os.path.join(RAIZ, "eclipse", "build", "site")
SAIDA = os.path.join(RAIZ, "testes", "saida")
URL = "http://192.168.68.106:8788"
PC = os.environ["COMPUTERNAME"]
PROIBIDO = re.compile(r"(?i)claude|anthropic|opus|sonnet|haiku|jarvis")
falhas = []


def ok(n, c, d=""):
    print(("  ok    " if c else "  FALHA ") + n + ("" if c else f"  -> {d}"), flush=True)
    if not c:
        falhas.append(n)


def pedidos():
    return [p for p in json.load(urllib.request.urlopen("http://127.0.0.1:9911/_pedidos"))
            if p["caminho"] == "/v1/messages"]


versao = open(os.path.join(RAIZ, "eclipse", "build", "versao.txt")).read().strip()
jar = os.path.join(SITE, "plugins", f"br.lupa.javva_{versao}.jar")
base = tempfile.mkdtemp(prefix="javva-eclipse-")
cfg = os.path.join(base, "cfg")
os.makedirs(cfg)
shutil.copy(os.path.join(ECLIPSE, "configuration", "config.ini"), cfg)
shutil.copytree(os.path.join(ECLIPSE, "configuration", "org.eclipse.equinox.simpleconfigurator"),
                os.path.join(cfg, "org.eclipse.equinox.simpleconfigurator"))
with open(os.path.join(cfg, "org.eclipse.equinox.simpleconfigurator", "bundles.info"), "a",
          encoding="utf-8") as f:
    f.write(f"br.lupa.javva,{versao},file:/{jar.replace(os.sep, '/')},4,false\n")
identidade = os.path.join(base, "identidade")
ws = os.path.join(base, "workspace")
foto = os.path.join(SAIDA, "menu_setas.png")


def area_de_transferencia(script):
    """PowerShell STA (a area de transferencia do Windows exige STA)."""
    return subprocess.run(["powershell", "-STA", "-NoProfile", "-Command",
                           "Add-Type -AssemblyName System.Windows.Forms, System.Drawing; " + script],
                          capture_output=True, text=True, timeout=60)


def eclipse(rodada, mensagens, escolha, estreito=None, extra=None):
    arq = os.path.join(base, f"rodada{rodada}.json")
    saida = os.path.join(base, f"rodada{rodada}.saida.json")
    cfg_teste = {"mensagens": mensagens, "escolha": escolha, "saida": saida,
                 "print": os.path.join(SAIDA, f"eclipse_javva_{rodada}.png"),
                 "print_permitir": os.path.join(SAIDA, "eclipse_permitir.png")}
    cfg_teste.update(extra or {})
    if estreito:
        cfg_teste["estreito"] = estreito
        cfg_teste["print_estreito"] = os.path.join(SAIDA, "eclipse_estreito_{t}.png")
    json.dump(cfg_teste, open(arq, "w", encoding="utf-8"))
    cmd = [os.path.join(ECLIPSE, "eclipsec.exe"), "-nosplash", "-consoleLog", "-clean",
           "-configuration", cfg, "-data", ws, "-vmargs",
           f"-Djavva.autoteste={arq}", f"-Djavva.dir={identidade}", f"-Djavva.url={URL}",
           "-Doomph.setup.skip=true"]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, timeout=420)
    log = (p.stdout + p.stderr).decode("utf-8", "replace")
    open(os.path.join(base, f"rodada{rodada}.log"), "w", encoding="utf-8").write(log)
    if not os.path.isfile(saida):
        print(log[-3000:])
        return {"ok": False, "erro": "sem arquivo de saida"}, time.time() - t0
    return json.load(open(saida, encoding="utf-8")), time.time() - t0


print("== 1. eclipse.exe com o plugin: sessao nova, comando com Permitir?, foto")
r, seg = eclipse(1, ["rode o teste do cliente",
                     {"texto": "o que tem nesta foto?", "fotos": [foto]}], -1)
print(f"   (eclipse abriu, rodou e fechou em {seg:.0f}s)")
ok("autoteste terminou sem erro", r.get("ok"), r.get("erro", "")[:1500])
conv = r.get("conversa", "")
ok("sem sessoes: a lista so tem + Nova sessao", r.get("sessoes") == ["+ Nova sessão"], r.get("sessoes"))
ok("a mensagem aparece na aba", "Você: rode o teste do cliente" in conv, conv[:300])
ok("comando rodou no processo do Eclipse e voltou",
   f"RESULTADO DO CLIENTE: JAVVA-CLIENTE-OK em {PC}" in conv, conv[-800:])
ok("Permitir? abriu (print salvo)", os.path.getsize(os.path.join(SAIDA, "eclipse_permitir.png")) > 3000
   if os.path.isfile(os.path.join(SAIDA, "eclipse_permitir.png")) else False)
ok("foto anexada chegou ao modelo", "JAVVA OK (foto recebida)" in conv, conv[-500:])
ok("rodape com a sessao", re.search(r"\[IA LOCAL - JAVVA - sessao [0-9a-f]{8} - [\d.]+s\]", conv), conv[-300:])
ok("nada de Claude/Opus nem nome antigo na aba", not PROIBIDO.search(conv), PROIBIDO.findall(conv)[:5])
ok("pronto para usar: avisa que e so escrever", "é só escrever aqui embaixo" in conv, conv[:200])
ok("nada de aprovacao nem codigo na aba nem no status",
   not re.search(r"(?i)aprovad|c[oó]digo", conv + r.get("status", "")), (conv[:200], r.get("status")))
p = [x for x in pedidos() if "rode o teste do cliente" in (x.get("historico") or "")]
ok("modelo soube que e o Eclipse (prompt do sistema)", p and p[-1].get("sistema_eclipse"))
ok("contexto do Eclipse foi junto", p and "[Eclipse] pasta atual: " in p[-1]["historico"],
   p and p[-1]["historico"][:200])
ok("status mostra a pasta do workspace", ws.lower() in r.get("status", "").lower(), r.get("status"))

print("== 2. reabre o Eclipse: lista HOSTNAME - IP - resume - data e retoma")
r2, seg = eclipse(2, ["continua de onde parou"], 0, ["460x620", "460x620@700x900"])
print(f"   (eclipse abriu, rodou e fechou em {seg:.0f}s)")
ok("autoteste 2 sem erro", r2.get("ok"), r2.get("erro", "")[:1500])
s = r2.get("sessoes", [])
ok("lista com o rotulo da sessao", s and re.fullmatch(
    PC + r" - \d+\.\d+\.\d+\.\d+ - [0-9a-f-]{36} - \d\d/\d\d/\d{4} - \d\d:\d\d", s[0]), s)
ok("ultima opcao e + Nova sessao", s and s[-1] == "+ Nova sessão", s)
conv2 = r2.get("conversa", "")
ok("retomou a sessao", "retomada" in conv2, conv2[-600:])
p = [x for x in pedidos() if "continua de onde parou" in (x.get("historico") or "")]
ok("historico da 1a rodada chegou ao modelo", p and "rode o teste do cliente" in p[-1]["historico"],
   p and p[-1]["historico"][:300])
ok("resposta comeca em linha propria (nao cola no [exit 0] nem no aviso)",
   "[exit 0]RESULTADO" not in conv and "parou  Sessao" not in conv2, conv[-400:])

print("== 3. UX#168: janela estreita, medido (o que passa da caixa sem rolagem)")
med = r2.get("estreito", {})
for tam in ("460x620", "460x620@700x900"):
    ok(f"janela {tam}: nada cortado sem rolagem", med.get(tam) == [], med.get(tam))
ok("460x620 cabe: sem barras", med.get("460x620 barras") == "horizontal=false vertical=false",
   med.get("460x620 barras"))
ok("conteudo maior que a aba: as DUAS barras aparecem",
   med.get("460x620@700x900 barras") == "horizontal=true vertical=true", med.get("460x620@700x900 barras"))

print("== 4. botao ⚙ (profundidade maxima) + Ctrl+V de um print da area de transferencia")
# guarda o que o usuario tinha copiado (texto ou imagem) e devolve no fim
guardado_txt = os.path.join(base, "clip_usuario.txt")
guardado_png = os.path.join(base, "clip_usuario.png")
area_de_transferencia(
    f"if ([Windows.Forms.Clipboard]::ContainsText()) {{ [IO.File]::WriteAllText('{guardado_txt}', "
    f"[Windows.Forms.Clipboard]::GetText(), [Text.Encoding]::UTF8) }} "
    f"elseif ([Windows.Forms.Clipboard]::ContainsImage()) {{ [Windows.Forms.Clipboard]::GetImage().Save('{guardado_png}') }}")
# um "Print Screen" 4K gerado pelo teste (bitmap na area de transferencia, como o do Windows)
r = area_de_transferencia(
    "$b = New-Object Drawing.Bitmap 3840, 2160; $g = [Drawing.Graphics]::FromImage($b); "
    "$g.Clear([Drawing.Color]::FromArgb(30, 60, 110)); "
    "$f = New-Object Drawing.Font('Arial', 140, [Drawing.FontStyle]::Bold); "
    "$g.DrawString('PRINT DE TESTE JAVVA 4321', $f, [Drawing.Brushes]::White, 150, 800); "
    "$g.FillRectangle([Drawing.Brushes]::Orange, 150, 1250, 1600, 320); $g.Dispose(); "
    "[Windows.Forms.Clipboard]::SetImage($b); 'ok'")
ok("print colocado na area de transferencia", "ok" in r.stdout, r.stderr[-300:])
try:
    r3, seg = eclipse(3, [{"texto": "o que tem neste print?", "colar": True}], -1, extra={
        "config": {"url": URL, "esforco": "max"},
        "print_config": os.path.join(SAIDA, "eclipse_config.png")})
finally:
    area_de_transferencia(
        f"if (Test-Path '{guardado_txt}') {{ [Windows.Forms.Clipboard]::SetText([IO.File]::ReadAllText('{guardado_txt}', [Text.Encoding]::UTF8)) }} "
        f"elseif (Test-Path '{guardado_png}') {{ [Windows.Forms.Clipboard]::SetImage([Drawing.Image]::FromFile('{guardado_png}')) }} "
        "else { [Windows.Forms.Clipboard]::Clear() }")
    for g in (guardado_txt, guardado_png):
        if os.path.exists(g):
            os.remove(g)
print(f"   (eclipse abriu, rodou e fechou em {seg:.0f}s; area de transferencia do usuario devolvida)")
ok("autoteste 3 sem erro", r3.get("ok"), r3.get("erro", "")[:1500])
conv3 = r3.get("conversa", "")
ok("formulario salvou e reconectou", "Configuração salva" in conv3 and "Reconectando" in conv3, conv3[:400])
ok("status mostra a profundidade escolhida", "profundidade máxima" in r3.get("status", ""), r3.get("status"))
ok("formulario do ⚙ abriu (print salvo)", os.path.isfile(os.path.join(SAIDA, "eclipse_config.png")))
p = [x for x in pedidos() if "o que tem neste print" in (x.get("historico") or "")]
ok("o modelo recebeu a profundidade MAXIMA", p and '"max"' in (p[-1].get("effort") or ""),
   p and p[-1].get("effort"))
print("   colar:", r3.get("diag_colar"))
ok("Ctrl+V (pelo despachante de teclas do Eclipse) virou anexo",
   str(r3.get("diag_colar", "")).startswith("imagem 3840x2160"), r3.get("diag_colar"))
ok("o print chegou ao modelo", "JAVVA OK (foto recebida)" in conv3 and "[1 foto(s)]" in conv3, conv3[-400:])
pc = r3.get("print_colado", "")
try:
    from PIL import Image as PILImage
    im = PILImage.open(pc).convert("RGB")
    cores = len(set(im.resize((96, 54)).getdata()))
    ok("print 4K reduzido para 1920x1080, opaco e com conteudo", im.size == (1920, 1080) and cores > 3,
       (im.size, cores))
    shutil.copy(pc, os.path.join(SAIDA, "eclipse_print_colado.png"))
except Exception as e:                                   # noqa: BLE001
    ok("print colado legivel", False, f"{pc}: {e}")

print("\nPROVA ECLIPSE:", "PASSOU" if not falhas else f"{len(falhas)} FALHA(S): " + "; ".join(falhas))
print("prints:", os.path.join(SAIDA, "eclipse_javva_1.png"), os.path.join(SAIDA, "eclipse_permitir.png"),
      os.path.join(SAIDA, "eclipse_javva_2.png"))
sys.exit(1 if falhas else 0)
