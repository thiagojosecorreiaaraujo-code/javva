package br.lupa.javva.ui;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Callable;
import java.util.concurrent.atomic.AtomicReference;

import org.eclipse.jface.dialogs.IDialogConstants;
import org.eclipse.swt.widgets.Display;
import org.eclipse.ui.IStartup;
import org.eclipse.ui.IWorkbenchPage;
import org.eclipse.ui.IWorkbenchWindow;
import org.eclipse.ui.PlatformUI;

import br.lupa.javva.core.Json;

/** Prova do plugin DENTRO do eclipse.exe: so roda com -Djavva.autoteste=<cfg.json>.
 *  Abre a aba, escolhe a sessao, manda as mensagens pela propria tela (o
 *  "Permitir?" abre e e respondido sozinho), salva prints e o texto da
 *  conversa, e fecha o Eclipse. Sem a propriedade, nao faz nada. */
public class Autoteste implements IStartup {

    @Override
    public void earlyStartup() {
        String arq = System.getProperty("javva.autoteste");
        if (arq == null || arq.isBlank()) {
            return;
        }
        Thread t = new Thread(() -> rodar(Paths.get(arq)), "javva-autoteste");
        t.setDaemon(true);
        t.start();
    }

    @SuppressWarnings("unchecked")
    static void rodar(Path arqCfg) {
        Map<String, Object> res = new LinkedHashMap<>();
        Map<String, Object> cfg = config(arqCfg);
        Display d = PlatformUI.getWorkbench().getDisplay();
        try {
            AtomicReference<JavvaView> v = new AtomicReference<>();
            esperar(() -> ui(d, () -> {
                IWorkbenchWindow w = PlatformUI.getWorkbench().getActiveWorkbenchWindow();
                if (w == null && PlatformUI.getWorkbench().getWorkbenchWindows().length > 0) {
                    w = PlatformUI.getWorkbench().getWorkbenchWindows()[0];
                }
                if (w == null || w.getActivePage() == null) {
                    return false;
                }
                v.set(trazerParaFrente(w.getActivePage()));
                return true;
            }), 60_000, "a aba do Javva nao abriu");
            JavvaView jv = v.get();
            esperar(() -> ui(d, jv::prontoParaUsar), 60_000, "nao conectou: " + ui(d, jv::textoConversa));
            res.put("sessoes", ui(d, jv::itensCombo));
            int escolha = ((Number) cfg.getOrDefault("escolha", 0L)).intValue();
            ui(d, () -> {
                jv.autotesteEscolher(escolha);
                return null;
            });
            if (cfg.get("print_permitir") != null) {
                PermitirDialog.autotestePng = Paths.get(Json.texto(cfg, "print_permitir"));
            }
            PermitirDialog.autoteste = IDialogConstants.YES_ID;
            // botao de engrenagem: {"config": {"url": ..., "esforco": ...}, "print_config": png}
            if (cfg.get("config") instanceof Map<?, ?> conf) {
                Map<String, String> valores = new LinkedHashMap<>();
                for (Map.Entry<?, ?> e : conf.entrySet()) {
                    valores.put(String.valueOf(e.getKey()), String.valueOf(e.getValue()));
                }
                ConfigDialog.autoteste = valores;
                if (cfg.get("print_config") != null) {
                    ConfigDialog.autotestePng = Paths.get(Json.texto(cfg, "print_config"));
                }
                ui(d, () -> {
                    jv.abrirConfiguracao();      // modal: volta quando o dialogo salva
                    return null;
                });
                Thread.sleep(500);
                esperar(() -> ui(d, jv::prontoParaUsar), 60_000, "nao reconectou depois de configurar");
            }
            // cada mensagem: "texto" ou {"texto": ..., "fotos": [caminhos], "colar": true}
            for (Object m : (List<Object>) cfg.getOrDefault("mensagens", List.of())) {
                String texto = m instanceof Map<?, ?> mm ? String.valueOf(mm.get("texto")) : String.valueOf(m);
                List<String> fotos = new ArrayList<>();
                if (m instanceof Map<?, ?> mm && mm.get("fotos") instanceof List<?> l) {
                    for (Object o : l) {
                        fotos.add(String.valueOf(o));
                    }
                }
                boolean colar = m instanceof Map<?, ?> mm && Boolean.TRUE.equals(mm.get("colar"));
                ui(d, () -> {
                    jv.autotesteEnviar(texto, fotos, colar);
                    return null;
                });
                if (colar) {
                    res.put("colou_imagem", ui(d, () -> jv.colouImagem));
                    res.put("print_colado", String.valueOf(jv.ultimoPrint));
                    res.put("diag_colar", jv.diagColar);
                }
                Thread.sleep(300);
                esperar(() -> ui(d, jv::livre), 180_000, "sem resposta para: " + texto);
            }
            Thread.sleep(500);
            res.put("conversa", ui(d, jv::textoConversa));
            res.put("status", ui(d, jv::textoStatus));
            if (cfg.get("print") != null) {
                ui(d, () -> trazerParaFrente(jv.getSite().getPage()));
                Thread.sleep(800);                // deixa a aba se desenhar
                res.put("janela", ui(d, jv::estadoJanela));
                ui(d, () -> {
                    jv.capturar(Paths.get(Json.texto(cfg, "print")));
                    return null;
                });
            }
            // UX#168: janela estreita (o defeito mora no estreito) - medir, nao olhar
            if (cfg.get("estreito") instanceof List<?> tamanhos) {
                Map<String, Object> medidas = new LinkedHashMap<>();
                for (Object t : tamanhos) {
                    // "LxA" = tamanho da janela; "LxA@lxa" = e o conteudo forcado a lxa
                    String[] partes = String.valueOf(t).split("@");
                    String[] lxa = partes[0].split("x");
                    String[] min = partes.length > 1 ? partes[1].split("x") : null;
                    ui(d, () -> {
                        jv.getSite().getShell().setMaximized(false);
                        jv.getSite().getShell().setSize(Integer.parseInt(lxa[0]), Integer.parseInt(lxa[1]));
                        trazerParaFrente(jv.getSite().getPage());
                        jv.forcarMinimo(min == null ? null
                                : new org.eclipse.swt.graphics.Point(Integer.parseInt(min[0]), Integer.parseInt(min[1])));
                        return null;
                    });
                    Thread.sleep(800);
                    // depois do resize programatico o e4 deixa o conteiner da aba escondido
                    // ate a aba ser ativada de novo (= o usuario clicando na aba)
                    ui(d, () -> trazerParaFrente(jv.getSite().getPage()));
                    try {                     // o Eclipse reorganiza a janela depois do resize
                        esperar(() -> ui(d, jv::visivel), 5000, "");
                    } catch (IllegalStateException e) {
                        // medirRolagem diz "aba invisivel"
                    }
                    medidas.put(String.valueOf(t), ui(d, jv::medirRolagem));
                    medidas.put(t + " esconde", ui(d, jv::quemEsconde));
                    medidas.put(t + " estado", ui(d, () -> jv.getSite().getPage().getPartState(
                            jv.getSite().getPage().findViewReference(JavvaView.ID)) + " " + jv.estadoJanela()));
                    medidas.put(t + " barras", ui(d, jv::barrasVisiveis));
                    if (cfg.get("print_estreito") != null) {
                        ui(d, () -> {
                            jv.capturar(Paths.get(Json.texto(cfg, "print_estreito").replace("{t}", String.valueOf(t))));
                            return null;
                        });
                    }
                }
                res.put("estreito", medidas);
            }
            res.put("ok", true);
        } catch (Throwable e) {
            StringWriter sw = new StringWriter();
            e.printStackTrace(new PrintWriter(sw));
            res.put("ok", false);
            res.put("erro", sw.toString());
        }
        try {
            Files.writeString(Paths.get(Json.texto(cfg, "saida")),
                    Json.escrever(res), StandardCharsets.UTF_8);
        } catch (Exception e) {
            e.printStackTrace();
        }
        if (!Boolean.FALSE.equals(cfg.get("fechar"))) {
            d.asyncExec(() -> PlatformUI.getWorkbench().close());
        }
    }

    /** O Welcome de um workspace novo abre DEPOIS do workbench, por cima de
     *  tudo: a aba fica invisivel e o print sai preto. Fecha e maximiza a aba. */
    private static JavvaView trazerParaFrente(IWorkbenchPage p) throws Exception {
        if (PlatformUI.getWorkbench().getIntroManager().getIntro() != null) {
            PlatformUI.getWorkbench().getIntroManager()
                    .closeIntro(PlatformUI.getWorkbench().getIntroManager().getIntro());
        }
        JavvaView jv = (JavvaView) p.showView(JavvaView.ID);
        // maximizar o que ja esta maximizado ALTERNA (a aba voltava ao layout e sumia)
        if (p.getPartState(p.findViewReference(JavvaView.ID)) != IWorkbenchPage.STATE_MAXIMIZED) {
            p.setPartState(p.findViewReference(JavvaView.ID), IWorkbenchPage.STATE_MAXIMIZED);
        }
        return jv;
    }

    private static Map<String, Object> config(Path arq) {
        try {
            return Json.objeto(Files.readString(arq, StandardCharsets.UTF_8));
        } catch (Exception e) {
            return Map.of("saida", arq + ".saida.json");
        }
    }

    private static <T> T ui(Display d, Callable<T> c) throws Exception {
        AtomicReference<T> r = new AtomicReference<>();
        AtomicReference<Exception> erro = new AtomicReference<>();
        d.syncExec(() -> {
            try {
                r.set(c.call());
            } catch (Exception e) {
                erro.set(e);
            }
        });
        if (erro.get() != null) {
            throw erro.get();
        }
        return r.get();
    }

    interface Condicao {
        boolean ok() throws Exception;
    }

    private static void esperar(Condicao c, long ms, String falha) throws Exception {
        long fim = System.currentTimeMillis() + ms;
        while (System.currentTimeMillis() < fim) {
            if (c.ok()) {
                return;
            }
            Thread.sleep(250);
        }
        throw new IllegalStateException(falha);
    }
}
