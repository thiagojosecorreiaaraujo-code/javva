# -*- coding: utf-8 -*-
"""Menu de sessoes com SETAS num console Windows de verdade.

Abre o javva.bat v3 num console proprio (minimizado, sem roubar o foco),
se anexa a ele (AttachConsole), injeta teclas com WriteConsoleInputW e le a
tela com ReadConsoleOutputCharacterW/Attribute. Nada de SendKeys: nao depende
de foco e nao interfere no que o usuario esta digitando.

Pre: docker compose -f docker-compose.teste.yml up -d --build
Saida extra: testes/saida/menu_setas.png (a tela capturada, com as cores).
"""
import ctypes
import ctypes.wintypes as W
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V3 = os.path.join(RAIZ, "cliente", "javva.bat")
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
falhas = []


def ok(n, c, d=""):
    print(("  ok    " if c else "  FALHA ") + n + (f"  -> {d}" if d else ""),
          flush=True)
    if not c:
        falhas.append(n)


class COORD(ctypes.Structure):
    _fields_ = [("X", W.SHORT), ("Y", W.SHORT)]


class SMALL_RECT(ctypes.Structure):
    _fields_ = [("Left", W.SHORT), ("Top", W.SHORT),
                ("Right", W.SHORT), ("Bottom", W.SHORT)]


class CSBI(ctypes.Structure):
    _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD),
                ("wAttributes", W.WORD), ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD)]


class KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [("bKeyDown", W.BOOL), ("wRepeatCount", W.WORD),
                ("wVirtualKeyCode", W.WORD), ("wVirtualScanCode", W.WORD),
                ("uChar", W.WCHAR), ("dwControlKeyState", W.DWORD)]


class _EV(ctypes.Union):
    _fields_ = [("KeyEvent", KEY_EVENT_RECORD), ("_pad", ctypes.c_byte * 16)]


class INPUT_RECORD(ctypes.Structure):
    _fields_ = [("EventType", W.WORD), ("Event", _EV)]


k32.CreateFileW.restype = W.HANDLE
VK = {"DOWN": 0x28, "UP": 0x26, "ENTER": 0x0D, "HOME": 0x24, "END": 0x23}


def abrir_console(nome):
    h = k32.CreateFileW(nome, 0xC0000000, 3, None, 3, 0, None)
    if h in (None, W.HANDLE(-1).value):
        raise OSError(f"CreateFileW({nome}) falhou: {ctypes.get_last_error()}")
    return h


def tela(hout):
    info = CSBI()
    k32.GetConsoleScreenBufferInfo(hout, ctypes.byref(info))
    larg = info.dwSize.X
    ate = info.dwCursorPosition.Y + 1
    linhas = []
    for y in range(ate):
        buf = ctypes.create_unicode_buffer(larg)
        attr = (W.WORD * larg)()
        lidos = W.DWORD()
        k32.ReadConsoleOutputCharacterW(hout, buf, larg, COORD(0, y), ctypes.byref(lidos))
        k32.ReadConsoleOutputAttribute(hout, attr, larg, COORD(0, y), ctypes.byref(lidos))
        linhas.append((buf.value[:larg], list(attr)))
    return linhas


def texto(linhas):
    return "\n".join(l.rstrip() for l, _ in linhas)


def tecla(hin, vk=0, ch="\0"):
    recs = (INPUT_RECORD * 2)()
    for i, desce in enumerate((True, False)):
        recs[i].EventType = 1                                 # KEY_EVENT
        ke = recs[i].Event.KeyEvent
        ke.bKeyDown, ke.wRepeatCount = desce, 1
        ke.wVirtualKeyCode = vk
        ke.wVirtualScanCode = u32.MapVirtualKeyW(vk, 0)
        ke.uChar = ch
    n = W.DWORD()
    k32.WriteConsoleInputW(hin, recs, 2, ctypes.byref(n))
    time.sleep(0.05)


def digitar(hin, s):
    for ch in s:
        vk = u32.VkKeyScanW(ord(ch)) & 0xFF
        tecla(hin, vk, ch)
    tecla(hin, VK["ENTER"], "\r")


def esperar(hout, cond, seg=90):
    fim = time.time() + seg
    while time.time() < fim:
        t = texto(tela(hout))
        if cond(t):
            return t
        time.sleep(0.3)
    return texto(tela(hout))


def ultimo_pedido_com(trecho):
    ps = json.load(urllib.request.urlopen("http://127.0.0.1:9911/_pedidos"))
    ps = [p for p in ps if p["caminho"] == "/v1/messages"
          and trecho in (p.get("historico") or "")]
    return ps[-1] if ps else None


def png(linhas, destino):
    """Desenha a tela capturada (texto + cor de cada celula) num PNG."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False
    pal = [(12, 12, 12), (0, 55, 218), (19, 161, 14), (58, 150, 221),
           (197, 15, 31), (136, 23, 152), (193, 156, 0), (204, 204, 204),
           (118, 118, 118), (59, 120, 255), (22, 198, 12), (97, 214, 214),
           (231, 72, 86), (180, 0, 158), (249, 241, 165), (242, 242, 242)]
    fonte = ImageFont.truetype("consola.ttf", 16)
    cw, ch = 9, 19
    larg = max(len(l.rstrip()) for l, _ in linhas) + 2
    img = Image.new("RGB", (larg * cw + 20, len(linhas) * ch + 20), pal[0])
    d = ImageDraw.Draw(img)
    for y, (l, at) in enumerate(linhas):
        for x, c in enumerate(l[:larg]):
            a = at[x] if x < len(at) else 7
            if (a >> 4) & 0xF:
                d.rectangle([10 + x * cw, 10 + y * ch, 10 + (x + 1) * cw, 10 + (y + 1) * ch],
                            fill=pal[(a >> 4) & 0xF])
            if c != " ":
                d.text((10 + x * cw, 10 + y * ch), c, font=fonte, fill=pal[a & 0xF])
    img.save(destino)
    return True


pc = tempfile.mkdtemp(prefix="javva-setas-")
env = dict(os.environ, JAVVA_URL="http://192.168.68.106:8788",
           JAVVA_CONTAINER="javva-teste", LOCALAPPDATA=pc)
env.update(JARVIS_URL=env["JAVVA_URL"], JARVIS_CONTAINER=env["JAVVA_CONTAINER"])  # o .bat ANTIGO le estes nomes
env.pop("JAVVA_ATUALIZADO", None)

print("== 0. duas sessoes nesta maquina (A mais antiga, B mais nova)")
for entrada in ("sessao A alfa\n/sair\n", "0\nsessao B beta\n/sair\n"):
    subprocess.run(["cmd", "/c", V3], input=entrada.encode(), capture_output=True,
                   env=env, timeout=300, cwd=pc)
    time.sleep(1.2)

print("== 1. console real: menu desenhado")
si = subprocess.STARTUPINFO()
si.dwFlags = subprocess.STARTF_USESHOWWINDOW
si.wShowWindow = 7                                           # SW_SHOWMINNOACTIVE
p = subprocess.Popen(["cmd", "/c", V3], env=env, cwd=pc, startupinfo=si,
                     creationflags=subprocess.CREATE_NEW_CONSOLE)
k32.FreeConsole()
for _ in range(50):
    if k32.AttachConsole(p.pid):
        break
    time.sleep(0.2)
hout, hin = abrir_console("CONOUT$"), abrir_console("CONIN$")
t = esperar(hout, lambda t: "+ Nova sessao" in t)
itens = re.findall(r"^\s{2}[ >] " + os.environ["COMPUTERNAME"] + r" - 192\.168\.68\.106 - ([0-9a-f-]{36}) - (\d\d/\d\d/\d{4} - \d\d:\d\d)", t, re.M)
ok("menu lista HOSTNAME - IP - <resume> - <data/hora> das 2 sessoes", len(itens) == 2, itens)
ok("+ Nova sessao no fim", "+ Nova sessao" in t)
ok("1o item vem destacado com '>'", re.search(r"^  > \S+ - [\d.]+ - [0-9a-f-]{36} - ", t, re.M))

print("== 2. seta para baixo move o destaque (e a cor)")
tecla(hin, VK["DOWN"])
time.sleep(0.6)
linhas = tela(hout)
t = texto(linhas)
sel = [(l, a) for l, a in linhas if l.startswith("  > ")]
ok("destaque foi para o 2o item (sessao A)", len(sel) == 1 and itens
   and itens[1][0] in sel[0][0], sel and sel[0][0].rstrip())
ok("linha destacada em ciano", sel and (sel[0][1][4] & 0xF) == 11,
   sel and hex(sel[0][1][4]))
png(linhas, os.path.join(RAIZ, "testes", "saida", "menu_setas.png"))

print("== 3. seta para cima duas vezes da a volta (vai para + Nova sessao)")
tecla(hin, VK["UP"]); tecla(hin, VK["UP"])
time.sleep(0.6)
t = texto(tela(hout))
ok("circular: topo + cima = + Nova sessao", "  > + Nova sessao" in t)
tecla(hin, VK["DOWN"]); tecla(hin, VK["DOWN"])             # volta para a A
time.sleep(0.6)

print("== 4. Enter retoma a sessao escolhida e a conversa segue")
tecla(hin, VK["ENTER"], "\r")
t = esperar(hout, lambda t: "retomada" in t)
ok("avisou que retomou a sessao A", itens and f"Sessao {itens[1][0]} retomada" in t,
   [l for l in t.splitlines() if "retomada" in l])
n0 = t.count("JAVVA OK")
digitar(hin, "pergunta depois da seta")
t = esperar(hout, lambda t: t.count("JAVVA OK") > n0)
pd = ultimo_pedido_com("pergunta depois da seta")
ok("modelo recebeu o historico da A (e nao o da B)",
   pd and "sessao A alfa" in pd["historico"] and "sessao B beta" not in pd["historico"],
   pd and pd["historico"][:160])
digitar(hin, "/sair")
try:
    rc = p.wait(30)
except subprocess.TimeoutExpired:
    p.kill(); rc = None
k32.FreeConsole()
ok("saiu limpo com /sair", rc == 0, rc)
open(os.path.join(RAIZ, "testes", "saida", "menu_setas.txt"), "w",
     encoding="utf-8").write(t)

print("\nPROVA SETAS:", "PASSOU" if not falhas else
      f"{len(falhas)} FALHA(S): " + "; ".join(falhas))
sys.exit(1 if falhas else 0)
