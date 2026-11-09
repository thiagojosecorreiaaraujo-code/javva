package br.lupa.javva.ui;

import java.nio.file.Path;

import org.eclipse.jface.dialogs.Dialog;
import org.eclipse.jface.dialogs.IDialogConstants;
import org.eclipse.jface.resource.JFaceResources;
import org.eclipse.swt.SWT;
import org.eclipse.swt.graphics.GC;
import org.eclipse.swt.graphics.Image;
import org.eclipse.swt.graphics.ImageData;
import org.eclipse.swt.graphics.ImageLoader;
import org.eclipse.swt.graphics.Point;
import org.eclipse.swt.layout.GridData;
import org.eclipse.swt.layout.GridLayout;
import org.eclipse.swt.widgets.Composite;
import org.eclipse.swt.widgets.Control;
import org.eclipse.swt.widgets.Label;
import org.eclipse.swt.widgets.Shell;
import org.eclipse.swt.widgets.Text;

import br.lupa.javva.core.Ferramentas;

/** "Permitir?" antes de executar comando ou gravar arquivo: Sim / Nao /
 *  Tudo nesta sessao. O comando aparece inteiro, com rolagem. */
public class PermitirDialog extends Dialog {

    /** Autoteste: botao que o teste "aperta" sozinho e onde salvar o print. */
    static volatile Integer autoteste;
    static volatile Path autotestePng;

    private final String acao;
    private final String detalhe;

    public PermitirDialog(Shell pai, String acao, String detalhe) {
        super(pai);
        this.acao = acao;
        this.detalhe = detalhe;
    }

    public Ferramentas.Resposta perguntar() {
        int r = open();
        if (r == IDialogConstants.YES_TO_ALL_ID) {
            return Ferramentas.Resposta.TUDO;
        }
        return r == IDialogConstants.YES_ID ? Ferramentas.Resposta.SIM : Ferramentas.Resposta.NAO;
    }

    @Override
    protected void configureShell(Shell s) {
        super.configureShell(s);
        s.setText("IA LOCAL - JAVVA - Permitir?");
    }

    @Override
    protected boolean isResizable() {
        return true;
    }

    @Override
    protected Control createDialogArea(Composite pai) {
        Composite c = (Composite) super.createDialogArea(pai);
        c.setLayout(new GridLayout(1, false));
        Label l = new Label(c, SWT.WRAP);
        l.setText("O Javva quer: " + acao);
        l.setFont(JFaceResources.getBannerFont());
        l.setLayoutData(new GridData(SWT.FILL, SWT.CENTER, true, false));
        Text t = new Text(c, SWT.MULTI | SWT.READ_ONLY | SWT.V_SCROLL | SWT.H_SCROLL | SWT.BORDER);
        t.setFont(JFaceResources.getTextFont());
        t.setText(detalhe == null ? "" : detalhe);
        GridData g = new GridData(SWT.FILL, SWT.FILL, true, true);
        g.widthHint = 640;
        g.heightHint = 220;
        t.setLayoutData(g);
        return c;
    }

    @Override
    protected void createButtonsForButtonBar(Composite pai) {
        createButton(pai, IDialogConstants.YES_ID, "&Sim", true);
        createButton(pai, IDialogConstants.NO_ID, "&Não", false);
        createButton(pai, IDialogConstants.YES_TO_ALL_ID, "&Tudo nesta sessão", false);
    }

    @Override
    protected void buttonPressed(int id) {
        setReturnCode(id);
        close();
    }

    @Override
    public void create() {
        super.create();
        Integer auto = autoteste;
        if (auto != null) {
            getShell().getDisplay().timerExec(800, () -> {
                Shell s = getShell();
                if (s == null || s.isDisposed()) {
                    return;
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
                buttonPressed(auto);
            });
        }
    }
}
