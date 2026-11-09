package br.lupa.javva.ui;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicReference;

import org.eclipse.core.resources.IFile;
import org.eclipse.core.resources.IResource;
import org.eclipse.core.resources.ResourcesPlugin;
import org.eclipse.core.runtime.Adapters;
import org.eclipse.core.runtime.IPath;
import org.eclipse.jface.resource.JFaceResources;
import org.eclipse.jface.text.ITextSelection;
import org.eclipse.jface.viewers.ISelection;
import org.eclipse.jface.viewers.IStructuredSelection;
import org.eclipse.swt.SWT;
import org.eclipse.swt.custom.ScrolledComposite;
import org.eclipse.swt.custom.StyleRange;
import org.eclipse.swt.custom.StyledText;
import org.eclipse.swt.dnd.DND;
import org.eclipse.swt.dnd.DropTarget;
import org.eclipse.swt.dnd.DropTargetAdapter;
import org.eclipse.swt.dnd.DropTargetEvent;
import org.eclipse.swt.dnd.Clipboard;
import org.eclipse.swt.dnd.FileTransfer;
import org.eclipse.swt.dnd.ImageTransfer;
import org.eclipse.swt.dnd.TextTransfer;
import org.eclipse.jface.window.Window;
import org.eclipse.jface.action.Action;
import org.eclipse.ui.actions.ActionFactory;
import org.eclipse.swt.graphics.PaletteData;
import org.eclipse.swt.graphics.RGB;
import org.eclipse.swt.widgets.Menu;
import org.eclipse.swt.widgets.MenuItem;
import java.nio.file.Files;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import org.eclipse.swt.dnd.Transfer;
import org.eclipse.swt.graphics.Color;
import org.eclipse.swt.graphics.GC;
import org.eclipse.swt.graphics.Image;
import org.eclipse.swt.graphics.ImageData;
import org.eclipse.swt.graphics.ImageLoader;
import org.eclipse.swt.graphics.Point;
import org.eclipse.swt.graphics.Rectangle;
import org.eclipse.swt.layout.FillLayout;
import org.eclipse.swt.layout.GridData;
import org.eclipse.swt.layout.GridLayout;
import org.eclipse.swt.layout.RowLayout;
import org.eclipse.swt.widgets.Button;
import org.eclipse.swt.widgets.Combo;
import org.eclipse.swt.widgets.Composite;
import org.eclipse.swt.widgets.Display;
import org.eclipse.swt.widgets.FileDialog;
import org.eclipse.swt.widgets.Label;
import org.eclipse.swt.widgets.Text;
import org.eclipse.ui.IEditorInput;
import org.eclipse.ui.IEditorPart;
import org.eclipse.ui.ISelectionListener;
import org.eclipse.ui.IURIEditorInput;
import org.eclipse.ui.IWorkbenchPart;
import org.eclipse.ui.part.ViewPart;

import br.lupa.javva.core.Cliente;
import br.lupa.javva.core.Ferramentas;
import br.lupa.javva.core.Identidade;
import br.lupa.javva.core.Imagens;
import br.lupa.javva.core.Json;

/** A aba "IA LOCAL - JAVVA": escolhe a sessao, conversa, manda fotos e
 *  executa NESTE processo (eclipse.exe) o que o Javva pedir, com "Permitir?". */
public class JavvaView extends ViewPart {

    public static final String ID = "br.lupa.javva.view";
    private static final String NOVA = "+ Nova sessão";
    private static final int LIMITE_SELECAO = 20_000;
    private static final int MIN_LARGURA = 340;
    private static final int MIN_ALTURA = 300;
    private static final int LADO_MAX_PRINT = 1920;

    private ScrolledComposite rolagem;
    private Composite raiz;
    private boolean meioDeTexto;
    private Combo combo;
    private Button botaoAbrir;
    private Label status;
    private StyledText conversa;
    private ScrolledComposite fotosRolagem;
    private Composite fotosBarra;
    private Label fotosTitulo;
    private Text entrada;
    private Button botaoEnviar;
    private Button botaoParar;
    private Button contexto;
    private Color corUsuario;
    private Color corFerramenta;
    private Color corInfo;
    private Color corErro;

    private final List<Path> anexos = new ArrayList<>();
    private final List<Image> miniaturas = new ArrayList<>();
    private List<Map<String, Object>> sessoes = List.of();
    private final ExecutorService rede = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "javva-rede");
        t.setDaemon(true);
        return t;
    });
    private volatile Cliente cliente;
    private volatile Path pastaAtual;
    private volatile boolean ocupado;
    private volatile boolean conectado;
    private volatile boolean sessaoAberta;
    private IResource ultimoRecurso;
    private ISelectionListener ouvinteSelecao;

    @Override
    public void createPartControl(Composite moldura) {
        // UX#168: a aba inteira rola. Mais estreita/baixa que o minimo, aparecem
        // barras - nenhum botao fica cortado fora do alcance.
        moldura.setLayout(new FillLayout());
        rolagem = new ScrolledComposite(moldura, SWT.H_SCROLL | SWT.V_SCROLL);
        Composite parent = new Composite(rolagem, SWT.NONE);
        rolagem.setContent(parent);
        rolagem.setExpandHorizontal(true);
        rolagem.setExpandVertical(true);
        rolagem.setMinSize(MIN_LARGURA, MIN_ALTURA);
        raiz = parent;
        Display d = parent.getDisplay();
        corUsuario = new Color(d, 0x2F, 0x6F, 0xDF);
        corFerramenta = new Color(d, 0xC0, 0x7A, 0x00);
        corInfo = new Color(d, 0x80, 0x80, 0x80);
        corErro = new Color(d, 0xD0, 0x30, 0x30);
        GridLayout gl = new GridLayout(1, false);
        gl.marginWidth = 4;
        gl.marginHeight = 4;
        parent.setLayout(gl);

        Composite topo = new Composite(parent, SWT.NONE);
        GridLayout tl = new GridLayout(5, false);
        tl.marginWidth = 0;
        tl.marginHeight = 0;
        topo.setLayout(tl);
        topo.setLayoutData(new GridData(SWT.FILL, SWT.CENTER, true, false));
        new Label(topo, SWT.NONE).setText("Sessão:");
        combo = new Combo(topo, SWT.READ_ONLY | SWT.DROP_DOWN);
        GridData gc = new GridData(SWT.FILL, SWT.CENTER, true, false);
        gc.widthHint = 120;                       // encolhe com a aba; a lista aberta mostra tudo
        combo.setLayoutData(gc);
        combo.setVisibleItemCount(12);
        combo.addListener(SWT.Selection, e -> combo.setToolTipText(combo.getText()));
        botaoAbrir = new Button(topo, SWT.PUSH);
        botaoAbrir.setText("Abrir");
        botaoAbrir.setToolTipText("Abre a sessão escolhida (ou uma nova)");
        botaoAbrir.addListener(SWT.Selection, e -> abrirEscolhida());
        Button atualizar = new Button(topo, SWT.PUSH);
        atualizar.setText("↻");
        atualizar.setToolTipText("Reconectar e recarregar a lista de sessões");
        atualizar.addListener(SWT.Selection, e -> conectar());
        Button configurar = new Button(topo, SWT.PUSH);
        configurar.setText("⚙");
        configurar.setToolTipText("Configurar o servidor (URL) e a profundidade do modelo");
        configurar.addListener(SWT.Selection, e -> abrirConfiguracao());

        status = new Label(parent, SWT.NONE);
        status.setLayoutData(new GridData(SWT.FILL, SWT.CENTER, true, false));
        status.setForeground(corInfo);

        conversa = new StyledText(parent, SWT.MULTI | SWT.READ_ONLY | SWT.WRAP | SWT.V_SCROLL | SWT.BORDER);
        conversa.setLayoutData(new GridData(SWT.FILL, SWT.FILL, true, true));
        conversa.setFont(JFaceResources.getTextFont());
        conversa.setMargins(6, 4, 6, 4);

        fotosTitulo = new Label(parent, SWT.NONE);
        GridData gft = new GridData(SWT.FILL, SWT.CENTER, true, false);
        gft.exclude = true;
        fotosTitulo.setLayoutData(gft);
        fotosTitulo.setVisible(false);
        fotosRolagem = new ScrolledComposite(parent, SWT.H_SCROLL);
        GridData gfr = new GridData(SWT.FILL, SWT.TOP, true, false);
        gfr.heightHint = 70;
        gfr.exclude = true;
        fotosRolagem.setLayoutData(gfr);
        fotosRolagem.setVisible(false);
        fotosBarra = new Composite(fotosRolagem, SWT.NONE);
        RowLayout rl = new RowLayout(SWT.HORIZONTAL);
        rl.wrap = false;
        rl.spacing = 6;
        fotosBarra.setLayout(rl);
        fotosRolagem.setContent(fotosBarra);
        fotosRolagem.setExpandVertical(true);

        Composite baixo = new Composite(parent, SWT.NONE);
        GridLayout bl = new GridLayout(2, false);
        bl.marginWidth = 0;
        bl.marginHeight = 0;
        baixo.setLayout(bl);
        baixo.setLayoutData(new GridData(SWT.FILL, SWT.FILL, true, false));
        entrada = new Text(baixo, SWT.MULTI | SWT.WRAP | SWT.V_SCROLL | SWT.BORDER);
        GridData ge = new GridData(SWT.FILL, SWT.FILL, true, true);
        ge.widthHint = 100;
        ge.heightHint = entrada.getLineHeight() * 4;
        entrada.setLayoutData(ge);
        entrada.setMessage("Escreva para o Javva (Enter envia, Shift+Enter quebra linha). Arraste fotos para cá.");
        entrada.addListener(SWT.KeyDown, e -> {
            if ((e.keyCode == SWT.CR || e.keyCode == SWT.KEYPAD_CR) && (e.stateMask & SWT.SHIFT) == 0) {
                e.doit = false;
                enviar();
            } else if (((e.stateMask & SWT.MOD1) != 0 && (e.keyCode == 'v' || e.keyCode == 'V'))
                    || ((e.stateMask & SWT.SHIFT) != 0 && e.keyCode == SWT.INSERT)) {
                // Ctrl+V / Shift+Insert: imagem (Print Screen) vira anexo; texto cola normal
                if (colarImagemOuArquivos()) {
                    e.doit = false;
                }
            }
        });
        Menu menu = new Menu(entrada);
        itemMenu(menu, "Colar\tCtrl+V", () -> {
            if (!colarImagemOuArquivos()) {
                entrada.paste();
            }
        });
        itemMenu(menu, "Colar imagem (Print Screen)", () -> {
            if (!colarImagemOuArquivos()) {
                linha("Não há imagem na área de transferência — aperte Print Screen (ou Win+Shift+S) e tente de novo.", corInfo);
            }
        });
        new MenuItem(menu, SWT.SEPARATOR);
        itemMenu(menu, "Recortar\tCtrl+X", entrada::cut);
        itemMenu(menu, "Copiar\tCtrl+C", entrada::copy);
        itemMenu(menu, "Selecionar tudo\tCtrl+A", entrada::selectAll);
        entrada.setMenu(menu);
        Composite botoes = new Composite(baixo, SWT.NONE);
        GridLayout bbl = new GridLayout(1, true);
        bbl.marginWidth = 0;
        bbl.marginHeight = 0;
        botoes.setLayout(bbl);
        botoes.setLayoutData(new GridData(SWT.FILL, SWT.TOP, false, false));
        botaoEnviar = botao(botoes, "Enviar", "Manda a mensagem (Enter)", e -> enviar());
        botao(botoes, "Foto…", "Anexar foto (.png .jpg .gif .webp até 5 MB)", e -> escolherFotos());
        botaoParar = botao(botoes, "Parar", "Interrompe o comando que está rodando aqui", e -> {
            Cliente c = cliente;
            if (c != null) {
                c.ferramentas.parar();
            }
        });

        contexto = new Button(parent, SWT.CHECK);
        contexto.setText("Mandar projeto, arquivo e seleção");
        contexto.setToolTipText("Junto com cada mensagem vão a pasta do projeto selecionado, "
                + "o arquivo aberto no editor e o trecho selecionado nele.");
        contexto.setSelection(true);

        DropTarget alvo = new DropTarget(entrada, DND.DROP_COPY | DND.DROP_MOVE | DND.DROP_DEFAULT);
        alvo.setTransfer(new Transfer[] { FileTransfer.getInstance() });
        alvo.addDropListener(new DropTargetAdapter() {
            @Override
            public void dragEnter(DropTargetEvent e) {
                e.detail = DND.DROP_COPY;
            }

            @Override
            public void drop(DropTargetEvent e) {
                if (e.data instanceof String[] arquivos) {
                    for (String f : arquivos) {
                        if (Imagens.ehImagem(f)) {
                            anexar(Paths.get(f));
                        } else {
                            entrada.insert(f.contains(" ") ? "\"" + f + "\" " : f + " ");
                        }
                    }
                }
            }
        });

        // Ctrl+V no Eclipse e atalho GLOBAL: o despachante de teclas roda o comando
        // "Colar" (que so cola texto) antes do evento chegar ao campo. Por isso o
        // colar de imagem e o tratador do comando Colar desta aba.
        getViewSite().getActionBars().setGlobalActionHandler(ActionFactory.PASTE.getId(), new Action() {
            @Override
            public void run() {
                if (colarImagemOuArquivos()) {
                    return;
                }
                org.eclipse.swt.widgets.Control foco = raiz.getDisplay().getFocusControl();
                if (foco instanceof Text t && (t.getStyle() & SWT.READ_ONLY) == 0) {
                    t.paste();
                } else if (foco instanceof Combo cb && (cb.getStyle() & SWT.READ_ONLY) == 0) {
                    cb.paste();
                }
            }
        });
        getViewSite().getActionBars().updateActionBars();

        ouvinteSelecao = this::selecaoMudou;
        getSite().getWorkbenchWindow().getSelectionService().addPostSelectionListener(ouvinteSelecao);
        habilitar();
        conectar();
    }

    private static Button botao(Composite pai, String texto, String dica,
            org.eclipse.swt.widgets.Listener acao) {
        Button b = new Button(pai, SWT.PUSH);
        b.setText(texto);
        b.setToolTipText(dica);
        b.setLayoutData(new GridData(SWT.FILL, SWT.CENTER, true, false));
        b.addListener(SWT.Selection, acao);
        return b;
    }

    // ------------------------------------------------------------ conexao

    void conectar() {
        if (ocupado) {
            return;
        }
        ocupado = true;
        conectado = false;
        sessaoAberta = false;
        habilitar();
        pastaAtual = pastaDoEclipse();
        String url = Preferencias.url();
        // reconectar (↻ ou nova configuracao) volta para a MESMA conversa
        String anterior = cliente == null ? null : cliente.sessao();
        definirStatus("Conectando em " + url + "…");
        rede.submit(() -> {
            try {
                Identidade id = Identidade.carregar();
                Cliente antigo = cliente;
                if (antigo != null) {
                    antigo.fechar();
                }
                Cliente c = new Cliente(url, id, new Ferramentas(() -> pastaAtual, this::permitir),
                        Preferencias.esforco());
                cliente = c;
                List<Map<String, Object>> lista = c.conectar(pastaAtual.toString(), a -> ui(() -> linha(a, corInfo)));
                ui(() -> {
                    sessoes = lista;
                    combo.removeAll();
                    for (Map<String, Object> s : lista) {
                        combo.add(rotulo(s));
                    }
                    combo.add(NOVA);
                    int escolhida = 0;
                    for (int i = 0; anterior != null && i < lista.size(); i++) {
                        if (anterior.equals(Json.texto(lista.get(i), "id"))) {
                            escolhida = i;
                        }
                    }
                    combo.select(escolhida);
                    combo.setToolTipText(combo.getText());
                    conectado = true;
                    atualizarStatus();
                    // pronto para usar: nada de aprovacao, codigo ou passo extra
                    linha(c.nome() + " pronto — é só escrever aqui embaixo e Enter.", corInfo);
                    if (!lista.isEmpty()) {
                        linha("Continua a conversa escolhida na lista acima; para começar outra, "
                                + "escolha \"" + NOVA + "\".", corInfo);
                    }
                    entrada.setFocus();
                });
            } catch (Exception e) {
                ui(() -> {
                    linha("Não conectou: " + e.getMessage(), corErro);
                    definirStatus("Desconectado — clique ↻ para tentar de novo, ou ⚙ para trocar o servidor ("
                            + url + ")");
                });
            } finally {
                ocupado = false;
                ui(this::habilitar);
            }
        });
    }

    static String rotulo(Map<String, Object> s) {
        String r = Json.texto(s, "rotulo");
        if (!r.isEmpty()) {
            return r;
        }
        return Json.texto(s, "maquina") + " - " + Json.texto(s, "ip") + " - "
                + Json.texto(s, "id") + " - " + Json.texto(s, "quando");
    }

    private String idEscolhido() {
        int i = combo.getSelectionIndex();
        return i >= 0 && i < sessoes.size() ? Json.texto(sessoes.get(i), "id") : null;
    }

    void abrirEscolhida() {
        if (ocupado || !conectado) {
            return;
        }
        String alvo = idEscolhido();
        ocupado = true;
        habilitar();
        pastaAtual = pastaDoEclipse();
        rede.submit(() -> {
            try {
                Cliente c = cliente;
                if (sessaoAberta) {
                    // o servidor recebe a escolha UMA vez por conexao: trocar = reconectar
                    c.conectar(pastaAtual.toString(), a -> ui(() -> linha(a, corInfo)));
                }
                abrirSessao(c, alvo);
            } catch (Exception e) {
                ui(() -> linha("Falha ao abrir a sessão: " + e.getMessage(), corErro));
            } finally {
                ocupado = false;
                ui(() -> {
                    atualizarStatus();
                    habilitar();
                });
            }
        });
    }

    /** Roda na thread de rede. O aviso do servidor ("retomada"/"nova") chega
     *  como texto corrido: comeca numa linha propria, depois do separador. */
    private void abrirSessao(Cliente c, String alvo) throws IOException, InterruptedException {
        ui(() -> linha("──── sessão " + (alvo == null ? "nova" : alvo) + " ────", corInfo));
        c.abrir(alvo, ouvinte());
        sessaoAberta = true;
    }

    // ------------------------------------------------------------ conversa

    void enviar() {
        String texto = entrada.getText().trim();
        if ((texto.isEmpty() && anexos.isEmpty()) || ocupado || !conectado) {
            if (!conectado && !ocupado) {
                linha("Sem conexão com o Javva — clique ↻.", corErro);
            }
            return;
        }
        pastaAtual = pastaDoEclipse();
        String extra = contexto.getSelection() ? contextoDoEclipse() : "";
        List<Path> fotos = new ArrayList<>(anexos);
        String alvo = idEscolhido();
        entrada.setText("");
        limparFotos();
        String eco = "\nVocê: " + (texto.isEmpty() ? "(foto)" : texto)
                + (fotos.isEmpty() ? "" : "  [" + fotos.size() + " foto(s)]");
        ocupado = true;
        habilitar();
        rede.submit(() -> {
            Cliente c = cliente;
            try {
                if (!sessaoAberta) {
                    // abre ANTES de mostrar a mensagem: o aviso "retomada" vem primeiro
                    abrirSessao(c, alvo);
                }
                ui(() -> linha(eco, corUsuario));
                List<String> avisos = new ArrayList<>();
                List<Path> todas = new ArrayList<>(fotos);
                todas.addAll(Imagens.citadas(texto, c.ferramentas::resolver));
                List<Map<String, Object>> imgs = Imagens.montar(todas, avisos);
                for (String a : avisos) {
                    ui(() -> linha(a, corErro));
                }
                c.perguntar(extra + (texto.isEmpty() ? "(veja a foto)" : texto), imgs, ouvinte());
            } catch (IOException e) {
                String sid = c.sessao();
                ui(() -> linha("\n" + e.getMessage() + " — reconectando na mesma sessão…", corErro));
                try {
                    c.conectar(pastaAtual.toString(), a -> { });
                    c.abrir(sid, ouvinte());
                    ui(() -> linha("Reconectado. Reenvie a mensagem.", corInfo));
                } catch (Exception e2) {
                    conectado = false;
                    ui(() -> linha("Não reconectou: " + e2.getMessage() + " — clique ↻.", corErro));
                }
            } catch (Exception e) {
                ui(() -> linha("\nErro: " + e, corErro));
            } finally {
                ocupado = false;
                ui(() -> {
                    lembrarSessaoNova();
                    atualizarStatus();
                    habilitar();
                });
            }
        });
    }

    private Cliente.Ouvinte ouvinte() {
        return new Cliente.Ouvinte() {
            @Override
            public void texto(String t) {
                ui(() -> {
                    // resposta (em pedacos) comeca sempre numa linha propria
                    anexarTexto(meioDeTexto || conversa.getCharCount() == 0 ? t : "\n" + t, null);
                    meioDeTexto = true;
                });
            }

            @Override
            public void info(String t) {
                ui(() -> linha(t, corInfo));
            }

            @Override
            public void erro(String t) {
                ui(() -> linha(t, corErro));
            }

            @Override
            public void ferramenta(String l) {
                ui(() -> linha("\n  " + l, corFerramenta));
            }

            @Override
            public void saida(String resumo) {
                ui(() -> linha("    " + resumo.replace("\n", "\n    "), corInfo));
            }
        };
    }

    /** Sessao nova ganhou numero no servidor: entra no topo da lista. */
    private void lembrarSessaoNova() {
        Cliente c = cliente;
        String sid = c == null ? null : c.sessao();
        if (sid == null || combo.isDisposed()) {
            return;
        }
        for (int i = 0; i < sessoes.size(); i++) {
            if (sid.equals(Json.texto(sessoes.get(i), "id"))) {
                return;
            }
        }
        Map<String, Object> s = new java.util.LinkedHashMap<>();
        s.put("id", sid);
        s.put("maquina", c.id.maquina);
        s.put("ip", Identidade.meuIp(c.url));
        s.put("quando", java.time.format.DateTimeFormatter.ofPattern("dd/MM/yyyy - HH:mm")
                .format(java.time.LocalDateTime.now()));
        List<Map<String, Object>> nova = new ArrayList<>(sessoes);
        nova.add(0, s);
        sessoes = nova;
        combo.add(rotulo(s), 0);
        combo.select(0);
        combo.setToolTipText(combo.getText());
    }

    private Ferramentas.Resposta permitir(String acao, String detalhe) {
        AtomicReference<Ferramentas.Resposta> r = new AtomicReference<>(Ferramentas.Resposta.NAO);
        Display d = raiz.getDisplay();
        if (!d.isDisposed()) {
            d.syncExec(() -> r.set(new PermitirDialog(raiz.getShell(), acao, detalhe).perguntar()));
        }
        return r.get();
    }

    // ------------------------------------------------------------ contexto do Eclipse

    private void selecaoMudou(IWorkbenchPart parte, ISelection sel) {
        if (parte == this || !(sel instanceof IStructuredSelection ss) || ss.isEmpty()) {
            return;
        }
        IResource r = Adapters.adapt(ss.getFirstElement(), IResource.class);
        if (r != null) {
            ultimoRecurso = r;
        }
    }

    private IFile arquivoAberto() {
        IEditorPart ed = getSite().getPage().getActiveEditor();
        return ed == null ? null : ed.getEditorInput().getAdapter(IFile.class);
    }

    /** Pasta onde os comandos rodam: o projeto selecionado (ou o do arquivo
     *  aberto); sem projeto, a raiz do workspace. */
    Path pastaDoEclipse() {
        IResource r = ultimoRecurso;
        if (r == null || !r.exists()) {
            r = arquivoAberto();
        }
        if (r != null && r.getProject() != null && r.getProject().getLocation() != null) {
            return r.getProject().getLocation().toFile().toPath();
        }
        IPath raizWs = ResourcesPlugin.getWorkspace().getRoot().getLocation();
        return raizWs != null ? raizWs.toFile().toPath() : Paths.get(System.getProperty("user.home"));
    }

    private String contextoDoEclipse() {
        StringBuilder b = new StringBuilder("[Eclipse] pasta atual: ").append(pastaAtual);
        IEditorPart ed = getSite().getPage().getActiveEditor();
        if (ed != null) {
            String arq = caminhoDo(ed.getEditorInput());
            if (arq != null) {
                b.append("\n[Eclipse] arquivo aberto: ").append(arq);
            }
            ISelection s = ed.getSite().getSelectionProvider() == null ? null
                    : ed.getSite().getSelectionProvider().getSelection();
            if (s instanceof ITextSelection ts && ts.getLength() > 0 && ts.getText() != null) {
                String t = ts.getText();
                if (t.length() > LIMITE_SELECAO) {
                    t = t.substring(0, LIMITE_SELECAO) + "\n...(cortado)";
                }
                b.append("\n[Eclipse] trecho selecionado (linhas ").append(ts.getStartLine() + 1)
                        .append("-").append(ts.getEndLine() + 1).append("):\n```\n").append(t).append("\n```");
            }
        }
        return b.append("\n\n").toString();
    }

    private static String caminhoDo(IEditorInput in) {
        IFile f = in.getAdapter(IFile.class);
        if (f != null && f.getLocation() != null) {
            return f.getLocation().toOSString();
        }
        if (in instanceof IURIEditorInput u && u.getURI() != null && "file".equals(u.getURI().getScheme())) {
            return Paths.get(u.getURI()).toString();
        }
        return null;
    }

    // ------------------------------------------------------------ configuracao

    void abrirConfiguracao() {
        ConfigDialog d = new ConfigDialog(raiz.getShell());
        if (d.open() != Window.OK) {
            return;
        }
        try {
            Preferencias.salvar(d.url(), d.esforco());
        } catch (Exception e) {
            linha("Não salvei a configuração: " + e.getMessage(), corErro);
            return;
        }
        linha("Configuração salva: servidor " + d.url() + ", profundidade "
                + (d.esforco().isEmpty() ? "padrão do servidor" : Preferencias.rotuloEsforco(d.esforco()))
                + ". Reconectando…", corInfo);
        conectar();
    }

    private static void itemMenu(Menu m, String texto, Runnable acao) {
        MenuItem i = new MenuItem(m, SWT.PUSH);
        i.setText(texto);
        i.addListener(SWT.Selection, e -> acao.run());
    }

    // ------------------------------------------------------------ fotos

    /** Ctrl+V: texto na area de transferencia cola como texto; senao imagem
     *  (Print Screen, Win+Shift+S) ou arquivos de imagem copiados viram anexo.
     *  true = tratou (nao deixar o Text colar). */
    boolean colarImagemOuArquivos() {
        Clipboard cb = new Clipboard(raiz.getDisplay());
        try {
            Object txt = cb.getContents(TextTransfer.getInstance());
            if (txt instanceof String s && !s.isEmpty()) {
                diagColar = "texto";
                return false;
            }
            Object img = cb.getContents(ImageTransfer.getInstance());
            if (img instanceof ImageData dados) {
                diagColar = "imagem " + dados.width + "x" + dados.height + " " + dados.depth + "bits";
                Path p = salvarPrint(dados);
                anexar(p);
                diagColar += " -> " + p;
                return true;
            }
            Object arqs = cb.getContents(FileTransfer.getInstance());
            if (arqs instanceof String[] lista) {
                boolean algum = false;
                for (String f : lista) {
                    if (Imagens.ehImagem(f)) {
                        anexar(Paths.get(f));
                        algum = true;
                    }
                }
                diagColar = "arquivos " + lista.length;
                return algum;
            }
            diagColar = "nada";
            return false;
        } catch (Throwable e) {
            diagColar = "falha " + e;
            linha("Não consegui colar a imagem: " + e, corErro);
            return true;
        } finally {
            cb.dispose();
        }
    }

    /** Print colado vira PNG em %TEMP%\javva-prints: sem transparencia (print de
     *  32 bits pode vir com alfa zerado = imagem "vazia"), lado maior ate 1920 px
     *  e, se ainda passar de 4,5 MB, JPEG. */
    Path salvarPrint(ImageData dados) throws Exception {
        ImageData d = opaco24(dados);
        int maior = Math.max(d.width, d.height);
        if (maior > LADO_MAX_PRINT) {
            int w = Math.max(1, d.width * LADO_MAX_PRINT / maior);
            int h = Math.max(1, d.height * LADO_MAX_PRINT / maior);
            Image origem = new Image(raiz.getDisplay(), d);
            Image destino = new Image(raiz.getDisplay(), w, h);
            GC gc = new GC(destino);
            gc.setInterpolation(SWT.HIGH);
            gc.drawImage(origem, 0, 0, d.width, d.height, 0, 0, w, h);
            gc.dispose();
            d = opaco24(destino.getImageData());
            origem.dispose();
            destino.dispose();
        }
        Path pasta = Paths.get(System.getProperty("java.io.tmpdir"), "javva-prints");
        Files.createDirectories(pasta);
        String nome = "print_" + DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss_SSS").format(LocalDateTime.now());
        ImageLoader il = new ImageLoader();
        il.data = new ImageData[] { d };
        Path png = pasta.resolve(nome + ".png");
        il.save(png.toString(), SWT.IMAGE_PNG);
        if (Files.size(png) <= 4_500_000L) {
            ultimoPrint = png;
            return png;
        }
        Path jpg = pasta.resolve(nome + ".jpg");
        il.compression = 88;
        il.save(jpg.toString(), SWT.IMAGE_JPEG);
        Files.deleteIfExists(png);
        ultimoPrint = jpg;
        return jpg;
    }

    static ImageData opaco24(ImageData d) {
        ImageData out = new ImageData(d.width, d.height, 24, new PaletteData(0xFF0000, 0x00FF00, 0x0000FF));
        int[] linha = new int[d.width];
        for (int y = 0; y < d.height; y++) {
            d.getPixels(0, y, d.width, linha, 0);
            for (int x = 0; x < d.width; x++) {
                RGB c = d.palette.getRGB(linha[x]);
                linha[x] = (c.red << 16) | (c.green << 8) | c.blue;
            }
            out.setPixels(0, y, d.width, linha, 0);
        }
        return out;
    }

    private void escolherFotos() {
        FileDialog fd = new FileDialog(raiz.getShell(), SWT.OPEN | SWT.MULTI);
        fd.setText("Anexar foto");
        fd.setFilterExtensions(new String[] { "*.png;*.jpg;*.jpeg;*.gif;*.webp", "*.*" });
        fd.setFilterNames(new String[] { "Fotos", "Todos os arquivos" });
        if (fd.open() != null) {
            for (String n : fd.getFileNames()) {
                anexar(Paths.get(fd.getFilterPath(), n));
            }
        }
    }

    private void anexar(Path p) {
        if (anexos.contains(p)) {
            return;
        }
        anexos.add(p);
        Label l = new Label(fotosBarra, SWT.BORDER);
        l.setToolTipText(p + "\n(clique para tirar)");
        try {
            Image original = new Image(raiz.getDisplay(), p.toString());
            ImageData dados = original.getImageData();
            int alt = 56;
            int larg = Math.max(1, dados.width * alt / Math.max(1, dados.height));
            Image mini = new Image(raiz.getDisplay(), dados.scaledTo(larg, alt));
            original.dispose();
            miniaturas.add(mini);
            l.setImage(mini);
        } catch (RuntimeException e) {
            l.setText(p.getFileName().toString());   // .webp e afins: sem previa, so o nome
        }
        l.addListener(SWT.MouseUp, e -> {
            anexos.remove(p);
            l.dispose();
            atualizarFotos();
        });
        atualizarFotos();
    }

    private void limparFotos() {
        anexos.clear();
        for (org.eclipse.swt.widgets.Control c : fotosBarra.getChildren()) {
            c.dispose();
        }
        for (Image i : miniaturas) {
            i.dispose();
        }
        miniaturas.clear();
        atualizarFotos();
    }

    private void atualizarFotos() {
        boolean tem = !anexos.isEmpty();
        fotosTitulo.setText("Fotos: " + anexos.size() + " — clique numa foto para tirar");
        for (org.eclipse.swt.widgets.Control c : new org.eclipse.swt.widgets.Control[] { fotosTitulo, fotosRolagem }) {
            ((GridData) c.getLayoutData()).exclude = !tem;
            c.setVisible(tem);
        }
        Point tam = fotosBarra.computeSize(SWT.DEFAULT, SWT.DEFAULT);
        fotosBarra.setSize(tam);
        fotosRolagem.setMinSize(tam);
        raiz.layout(true, true);
    }

    // ------------------------------------------------------------ tela

    private void habilitar() {
        if (raiz.isDisposed()) {
            return;
        }
        boolean livre = !ocupado;
        botaoAbrir.setEnabled(livre && conectado);
        combo.setEnabled(livre && conectado);
        botaoEnviar.setEnabled(livre && conectado);
        botaoParar.setEnabled(ocupado);
    }

    private void atualizarStatus() {
        Cliente c = cliente;
        if (c == null) {
            return;
        }
        String sid = c.sessao();
        definirStatus(c.nome() + "  ·  " + c.url + "  ·  máquina " + c.id.maquina
                + "  ·  profundidade " + (c.esforco.isEmpty() ? "padrão" : Preferencias.rotuloEsforco(c.esforco))
                + "  ·  sessão " + (sid == null ? (sessaoAberta ? "nova" : "não aberta") : sid.substring(0, Math.min(8, sid.length())))
                + "  ·  pasta " + pastaAtual);
    }

    private void definirStatus(String t) {
        status.setText(t);
        status.setToolTipText(t);
    }

    private void linha(String t, Color cor) {
        anexarTexto((conversa.getCharCount() == 0 || t.startsWith("\n") ? "" : "\n") + t, cor);
        meioDeTexto = false;
    }

    private void anexarTexto(String t, Color cor) {
        if (conversa.isDisposed() || t.isEmpty()) {
            return;
        }
        int ini = conversa.getCharCount();
        conversa.append(t);
        if (cor != null) {
            conversa.setStyleRange(new StyleRange(ini, t.length(), cor, null));
        }
        conversa.setTopIndex(conversa.getLineCount() - 1);
    }

    private void ui(Runnable r) {
        Display d = raiz == null ? null : raiz.getDisplay();
        if (d != null && !d.isDisposed()) {
            d.asyncExec(() -> {
                if (!raiz.isDisposed()) {
                    r.run();
                }
            });
        }
    }

    @Override
    public void setFocus() {
        entrada.setFocus();
    }

    @Override
    public void dispose() {
        if (ouvinteSelecao != null) {
            getSite().getWorkbenchWindow().getSelectionService().removePostSelectionListener(ouvinteSelecao);
        }
        Cliente c = cliente;
        if (c != null) {
            c.ferramentas.parar();
            rede.submit(c::fechar);
        }
        rede.shutdown();
        for (Image i : miniaturas) {
            i.dispose();
        }
        for (Color cor : new Color[] { corUsuario, corFerramenta, corInfo, corErro }) {
            if (cor != null) {
                cor.dispose();
            }
        }
        super.dispose();
    }

    // ------------------------------------------------------------ autoteste (so com -Djavva.autoteste)

    boolean prontoParaUsar() {
        return conectado && !ocupado;
    }

    boolean livre() {
        return !ocupado;
    }

    List<String> itensCombo() {
        return List.of(combo.getItems());
    }

    void autotesteEscolher(int indice) {
        combo.select(indice < 0 ? combo.getItemCount() - 1 : indice);
    }

    void autotesteEnviar(String texto, List<String> fotos, boolean colar) {
        for (String f : fotos) {
            anexar(Paths.get(f));
        }
        if (colar) {
            // o MESMO caminho do teclado: KeyDown Ctrl+V no campo de texto
            org.eclipse.swt.widgets.Event ev = new org.eclipse.swt.widgets.Event();
            ev.keyCode = 'v';
            ev.stateMask = SWT.MOD1;
            ev.doit = true;
            entrada.notifyListeners(SWT.KeyDown, ev);
            colouImagem = !ev.doit;
        }
        entrada.setText(texto);
        enviar();
    }

    volatile boolean colouImagem;
    volatile String diagColar = "";
    volatile Path ultimoPrint;

    String textoConversa() {
        return conversa.getText();
    }

    String textoStatus() {
        return status.getText();
    }

    /** UX#168 medido: o que passa da caixa SEM rolagem. Lista vazia = aceite. */
    List<String> medirRolagem() {
        List<String> p = new ArrayList<>();
        if (!rolagem.isVisible()) {
            p.add("aba invisivel nesta janela - medida nao vale");
            return p;
        }
        Rectangle area = rolagem.getClientArea();
        Point tam = raiz.getSize();
        if (tam.x > area.width + 1 && !rolagem.getHorizontalBar().isVisible()) {
            p.add("largura " + tam.x + " > " + area.width + " sem barra horizontal");
        }
        if (tam.y > area.height + 1 && !rolagem.getVerticalBar().isVisible()) {
            p.add("altura " + tam.y + " > " + area.height + " sem barra vertical");
        }
        verificar(raiz, p);
        return p;
    }

    private static void verificar(Composite c, List<String> p) {
        Rectangle ca = c.getClientArea();
        for (org.eclipse.swt.widgets.Control f : c.getChildren()) {
            if (!f.getVisible()) {
                continue;
            }
            Rectangle b = f.getBounds();
            if (b.x + b.width > ca.width + 1 || b.y + b.height > ca.height + 1) {
                p.add(f.getClass().getSimpleName() + " passa de " + c.getClass().getSimpleName()
                        + ": " + b + " vs " + ca);
            }
            if (f instanceof Composite cc && !(f instanceof ScrolledComposite)) {
                verificar(cc, p);
            }
        }
    }

    /** Teste: conteudo MAIOR que a aba (simula aba mais estreita que o minimo,
     *  ja que o Eclipse esconde a aba numa janela minuscula). null volta ao normal. */
    void forcarMinimo(Point min) {
        rolagem.setMinSize(min == null ? new Point(MIN_LARGURA, MIN_ALTURA) : min);
        rolagem.layout(true, true);
    }

    boolean visivel() {
        return rolagem.isVisible();
    }

    /** Diagnostico: quem, na cadeia ate a janela, esta escondido. */
    String quemEsconde() {
        StringBuilder b = new StringBuilder();
        for (org.eclipse.swt.widgets.Control c = rolagem; c != null; c = c.getParent()) {
            if (!c.getVisible()) {
                b.append(c.getClass().getSimpleName()).append(c.getBounds()).append(" ");
            }
        }
        return b.length() == 0 ? "ninguem" : b.toString();
    }

    String barrasVisiveis() {
        return "horizontal=" + rolagem.getHorizontalBar().getVisible()
                + " vertical=" + rolagem.getVerticalBar().getVisible();
    }

    String estadoJanela() {
        return "shell visivel=" + raiz.getShell().isVisible() + " minimizada=" + raiz.getShell().getMinimized()
                + " aba visivel=" + raiz.isVisible() + " tamanho=" + raiz.getSize()
                + " ativa=" + (raiz.getDisplay().getActiveShell() == raiz.getShell());
    }

    void capturar(Path png) {
        Point t = rolagem.getSize();             // o que se ve, com as barras
        Image img = new Image(raiz.getDisplay(), Math.max(1, t.x), Math.max(1, t.y));
        GC gc = new GC(img);
        rolagem.print(gc);
        gc.dispose();
        ImageLoader l = new ImageLoader();
        l.data = new ImageData[] { img.getImageData() };
        l.save(png.toString(), SWT.IMAGE_PNG);
        img.dispose();
    }
}
