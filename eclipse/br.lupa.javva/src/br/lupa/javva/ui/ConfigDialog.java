package br.lupa.javva.ui;

import java.nio.file.Path;
import java.util.Map;

import org.eclipse.jface.dialogs.IDialogConstants;
import org.eclipse.jface.dialogs.TitleAreaDialog;
import org.eclipse.swt.SWT;
import org.eclipse.swt.graphics.GC;
import org.eclipse.swt.graphics.Image;
import org.eclipse.swt.graphics.ImageData;
import org.eclipse.swt.graphics.ImageLoader;
import org.eclipse.swt.graphics.Point;
import org.eclipse.swt.layout.GridData;
import org.eclipse.swt.layout.GridLayout;
import org.eclipse.swt.widgets.Combo;
import org.eclipse.swt.widgets.Composite;
import org.eclipse.swt.widgets.Control;
import org.eclipse.swt.widgets.Label;
import org.eclipse.swt.widgets.Shell;
import org.eclipse.swt.widgets.Text;

/** Botao de engrenagem da aba: servidor (URL) e profundidade do modelo.
 *  Salvar grava nas preferencias e a aba reconecta na mesma conversa. */
public class ConfigDialog extends TitleAreaDialog {

    /** Autoteste: valores a preencher ({url, esforco}) e onde salvar o print. */
    static volatile Map<String, String> autoteste;
    static volatile Path autotestePng;

    private Text url;
    private Combo profundidade;
    private String urlEscolhida;
    private String esforcoEscolhido;

    public ConfigDialog(Shell pai) {
        super(pai);
    }

    public String url() {
        return urlEscolhida;
    }

    public String esforco() {
        return esforcoEscolhido;
    }

    @Override
    protected void configureShell(Shell s) {
        super.configureShell(s);
        s.setText("IA LOCAL - JAVVA - Configurar");
    }

    @Override
    protected boolean isResizable() {
        return true;
    }

    @Override
    protected Control createDialogArea(Composite pai) {
        Composite area = (Composite) super.createDialogArea(pai);
        setTitle("Configurar o Javva");
        setMessage("Servidor na rede e profundidade das respostas. Ao salvar, a aba reconecta "
                + "na mesma conversa.");
        Composite c = new Composite(area, SWT.NONE);
        c.setLayoutData(new GridData(SWT.FILL, SWT.FILL, true, true));
        GridLayout gl = new GridLayout(2, false);
        gl.marginWidth = 12;
        gl.marginHeight = 12;
        gl.verticalSpacing = 10;
        c.setLayout(gl);

        new Label(c, SWT.NONE).setText("Servidor (URL):");
        url = new Text(c, SWT.BORDER);
        GridData gu = new GridData(SWT.FILL, SWT.CENTER, true, false);
        gu.widthHint = 380;
        url.setLayoutData(gu);
        url.setText(Preferencias.url());
        url.addListener(SWT.Modify, e -> validar());

        new Label(c, SWT.NONE).setText("Profundidade:");
        profundidade = new Combo(c, SWT.READ_ONLY | SWT.DROP_DOWN);
        profundidade.setLayoutData(new GridData(SWT.FILL, SWT.CENTER, true, false));
        String atual = Preferencias.esforco();
        int sel = 0;
        for (int i = 0; i < Preferencias.PROFUNDIDADES.length; i++) {
            profundidade.add(Preferencias.PROFUNDIDADES[i][0]);
            if (Preferencias.PROFUNDIDADES[i][1].equals(atual)) {
                sel = i;
            }
        }
        profundidade.select(sel);

        Label dica = new Label(c, SWT.WRAP);
        GridData gd = new GridData(SWT.FILL, SWT.CENTER, true, false, 2, 1);
        gd.widthHint = 460;
        dica.setLayoutData(gd);
        dica.setText("Quanto mais profunda, mais o modelo pensa antes de responder: melhor em "
                + "tarefas difíceis, mais lento e mais caro. Para o dia a dia, Alta ou o padrão "
                + "do servidor bastam.");
        return area;
    }

    private void validar() {
        String u = url.getText().trim();
        boolean ok = u.matches("https?://[^\\s/]+(:\\d+)?/?");
        setErrorMessage(ok ? null : "Use o formato http://endereço:porta (ex.: " + Preferencias.PADRAO + ")");
        if (getButton(IDialogConstants.OK_ID) != null) {
            getButton(IDialogConstants.OK_ID).setEnabled(ok);
        }
    }

    @Override
    protected void createButtonsForButtonBar(Composite pai) {
        createButton(pai, IDialogConstants.OK_ID, "&Salvar e reconectar", true);
        createButton(pai, IDialogConstants.CANCEL_ID, "Cancelar", false);
    }

    @Override
    protected void okPressed() {
        urlEscolhida = url.getText().trim().replaceAll("/+$", "");
        esforcoEscolhido = Preferencias.PROFUNDIDADES[Math.max(0, profundidade.getSelectionIndex())][1];
        super.okPressed();
    }

    @Override
    public void create() {
        super.create();
        validar();
        Map<String, String> auto = autoteste;
        if (auto != null) {
            getShell().getDisplay().timerExec(800, () -> {
                Shell s = getShell();
                if (s == null || s.isDisposed()) {
                    return;
                }
                if (auto.get("url") != null) {
                    url.setText(auto.get("url"));
                }
                for (int i = 0; i < Preferencias.PROFUNDIDADES.length; i++) {
                    if (Preferencias.PROFUNDIDADES[i][1].equals(auto.get("esforco"))) {
                        profundidade.select(i);
                    }
                }
                Path png = autotestePng;
                if (png != null) {
                    Point t = s.getSize();
                    Image img = new Image(s.getDisplay(), t.x, t.y);
                    GC gc = new GC(img);
                    s.print(gc);
                    gc.dispose();
                    ImageLoader il = new ImageLoader();
                    il.data = new ImageData[] { img.getImageData() };
                    il.save(png.toString(), SWT.IMAGE_PNG);
                    img.dispose();
                }
                okPressed();
            });
        }
    }
}
