# -*- coding: utf-8 -*-
"""Constroi o plugin do Javva para Eclipse e o update site (p2).

    python construir.py              -> build/site e build/javva-eclipse-site.zip
    python construir.py --publicar   -> e copia para ..\\cliente\\eclipse (o servidor
                                        serve em http://<javva>:8787/eclipse/)

Nao precisa de Maven/Tycho nem de JDK instalado: usa o javac do JRE que vem
DENTRO do Eclipse (JustJ), as jars do proprio Eclipse como classpath (lidas do
bundles.info) e o publisher p2 do proprio Eclipse (eclipsec headless).

ATENCAO: ..\\cliente e montado AO VIVO no container. --publicar so DEPOIS de o
servidor estar pronto para o que o pacote novo espera.
"""
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from urllib.parse import unquote, urlparse

RAIZ = os.path.dirname(os.path.abspath(__file__))
JAVVA = os.path.dirname(RAIZ)
ECLIPSE = os.environ.get("JAVVA_ECLIPSE",
                         r"C:\Users\MESA_DIREITA\eclipse\java-2026-09\eclipse")
BUILD = os.path.join(RAIZ, "build")
PLUGIN = os.path.join(RAIZ, "br.lupa.javva")
FEATURE = os.path.join(RAIZ, "br.lupa.javva.feature")
DESTINO = os.path.join(JAVVA, "cliente", "eclipse")


def jdk_bin():
    linhas = open(os.path.join(ECLIPSE, "eclipse.ini"), encoding="utf-8").read().splitlines()
    vm = linhas[linhas.index("-vm") + 1].strip()
    if not os.path.isfile(os.path.join(vm, "javac.exe")):
        sys.exit(f"javac nao achado em {vm} (o -vm do eclipse.ini)")
    return vm


def jars_do_eclipse():
    """Todas as bundles que o Eclipse carrega (bundles.info), como arquivos."""
    info = os.path.join(ECLIPSE, "configuration", "org.eclipse.equinox.simpleconfigurator",
                        "bundles.info")
    jars = []
    for l in open(info, encoding="utf-8"):
        if l.startswith("#"):
            continue
        partes = l.strip().split(",")
        if len(partes) < 3:
            continue
        u = partes[2]
        caminho = unquote(urlparse(u).path).lstrip("/") if u.startswith("file:") else u
        caminho = os.path.normpath(caminho if os.path.isabs(caminho)
                                   else os.path.join(ECLIPSE, caminho))
        if os.path.exists(caminho):
            jars.append(caminho)
    return jars


def url_arquivo(p):
    return "file:/" + p.replace("\\", "/")


def rodar(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", **kw)
    if r.returncode != 0:
        print(r.stdout[-4000:], r.stderr[-4000:], sep="\n")
        sys.exit(f"falhou ({r.returncode}): {cmd[0]}")
    return r


def main():
    versao = "1.0.0.v" + time.strftime("%Y%m%d%H%M")
    shutil.rmtree(BUILD, ignore_errors=True)
    classes = os.path.join(BUILD, "classes")
    staging = os.path.join(BUILD, "staging")
    site = os.path.join(BUILD, "site")
    for d in (classes, os.path.join(staging, "plugins"), os.path.join(staging, "features")):
        os.makedirs(d)

    # 1. compilar (Java 17: roda em Eclipse de 2022 para ca)
    vm = jdk_bin()
    fontes = [os.path.join(r, f) for r, _, fs in os.walk(os.path.join(PLUGIN, "src"))
              for f in fs if f.endswith(".java")]
    argfile = os.path.join(BUILD, "javac.args")
    with open(argfile, "w", encoding="utf-8") as a:
        a.write("-encoding UTF-8\n--release 17\n-nowarn\n")
        a.write("-d \"" + classes.replace("\\", "/") + "\"\n")
        a.write("-cp \"" + ";".join(jars_do_eclipse()).replace("\\", "/") + "\"\n")
        for f in fontes:
            a.write("\"" + f.replace("\\", "/") + "\"\n")
    rodar([os.path.join(vm, "javac.exe"), "@" + argfile])
    print(f"compilou {len(fontes)} fontes")

    # 2. jar do plugin (MANIFEST primeiro) e jar da feature
    manifesto = open(os.path.join(PLUGIN, "META-INF", "MANIFEST.MF"), encoding="utf-8").read()
    manifesto = manifesto.replace("1.0.0.qualifier", versao)
    jar_plugin = os.path.join(staging, "plugins", f"br.lupa.javva_{versao}.jar")
    with zipfile.ZipFile(jar_plugin, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("META-INF/MANIFEST.MF", manifesto)
        z.write(os.path.join(PLUGIN, "plugin.xml"), "plugin.xml")
        for f in os.listdir(os.path.join(PLUGIN, "icons")):
            z.write(os.path.join(PLUGIN, "icons", f), "icons/" + f)
        for r, _, fs in os.walk(classes):
            for f in fs:
                p = os.path.join(r, f)
                z.write(p, os.path.relpath(p, classes).replace("\\", "/"))
    feature = open(os.path.join(FEATURE, "feature.xml"), encoding="utf-8").read()
    with zipfile.ZipFile(os.path.join(staging, "features", f"br.lupa.javva.feature_{versao}.jar"),
                         "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("feature.xml", feature.replace("1.0.0.qualifier", versao))

    # 3. metadados p2 com o publisher do proprio Eclipse, numa configuracao
    #    COPIADA (nao mexe na do usuario)
    cfg = os.path.join(BUILD, "cfg")
    os.makedirs(cfg)
    shutil.copy(os.path.join(ECLIPSE, "configuration", "config.ini"), cfg)
    shutil.copytree(os.path.join(ECLIPSE, "configuration", "org.eclipse.equinox.simpleconfigurator"),
                    os.path.join(cfg, "org.eclipse.equinox.simpleconfigurator"))
    base = [os.path.join(ECLIPSE, "eclipsec.exe"), "-nosplash", "-consoleLog",
            "-configuration", cfg, "-data", os.path.join(BUILD, "ws")]
    rodar(base + ["-application", "org.eclipse.equinox.p2.publisher.FeaturesAndBundlesPublisher",
                  "-metadataRepository", url_arquivo(site), "-artifactRepository", url_arquivo(site),
                  "-metadataRepositoryName", "IA LOCAL - JAVVA",
                  "-artifactRepositoryName", "IA LOCAL - JAVVA",
                  "-source", staging, "-publishArtifacts", "-compress"])
    rodar(base + ["-application", "org.eclipse.equinox.p2.publisher.CategoryPublisher",
                  "-metadataRepository", url_arquivo(site),
                  "-categoryDefinition", url_arquivo(os.path.join(RAIZ, "category.xml")),
                  "-categoryQualifier", "br.lupa.javva", "-compress"])
    for f in ("content.jar", "artifacts.jar", f"plugins/br.lupa.javva_{versao}.jar",
              f"features/br.lupa.javva.feature_{versao}.jar"):
        if not os.path.isfile(os.path.join(site, f)):
            sys.exit("update site incompleto: falta " + f)
    with zipfile.ZipFile(os.path.join(site, "content.jar")) as z:
        conteudo = z.read("content.xml").decode("utf-8")
    if "ia.local" not in conteudo or "br.lupa.javva.feature.feature.group" not in conteudo:
        sys.exit("content.xml sem a categoria ou sem a feature")

    # 4. zip do site (botao "Archive..." do Eclipse)
    zip_site = os.path.join(BUILD, "javva-eclipse-site.zip")
    with zipfile.ZipFile(zip_site, "w", zipfile.ZIP_DEFLATED) as z:
        for r, _, fs in os.walk(site):
            for f in fs:
                p = os.path.join(r, f)
                z.write(p, os.path.relpath(p, site).replace("\\", "/"))
    open(os.path.join(BUILD, "versao.txt"), "w").write(versao)
    print("site pronto:", site, "| versao", versao)

    if "--publicar" in sys.argv:
        shutil.rmtree(DESTINO, ignore_errors=True)
        shutil.copytree(site, DESTINO)
        shutil.copy(zip_site, DESTINO)
        shutil.copy(os.path.join(RAIZ, "index.html"), DESTINO)
        open(os.path.join(DESTINO, "versao.txt"), "w").write(versao)
        print("publicado em", DESTINO)


if __name__ == "__main__":
    main()
