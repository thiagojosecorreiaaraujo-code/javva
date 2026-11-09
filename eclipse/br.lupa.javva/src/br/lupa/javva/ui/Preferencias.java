package br.lupa.javva.ui;

import org.eclipse.core.runtime.preferences.IEclipsePreferences;
import org.eclipse.core.runtime.preferences.InstanceScope;
import org.eclipse.jface.preference.ComboFieldEditor;
import org.eclipse.jface.preference.FieldEditorPreferencePage;
import org.eclipse.jface.preference.StringFieldEditor;
import org.eclipse.ui.IWorkbench;
import org.eclipse.ui.IWorkbenchPreferencePage;
import org.eclipse.ui.preferences.ScopedPreferenceStore;

import br.lupa.javva.core.Identidade;

/** Window > Preferences > IA LOCAL - JAVVA: servidor e profundidade. O botao
 *  de engrenagem da aba abre o mesmo par de campos (ConfigDialog). */
public class Preferencias extends FieldEditorPreferencePage implements IWorkbenchPreferencePage {

    public static final String NO = "br.lupa.javva";
    public static final String URL = "url";
    public static final String ESFORCO = "esforco";
    public static final String PADRAO = "http://192.168.68.106:8787";

    /** {rotulo, valor}: valor vazio = o servidor decide. */
    public static final String[][] PROFUNDIDADES = {
        { "Padrão do servidor", "" },
        { "Rápida — respostas curtas e diretas", "low" },
        { "Normal", "medium" },
        { "Alta", "high" },
        { "Muito alta", "xhigh" },
        { "Máxima — pensa mais, demora mais", "max" },
    };

    public Preferencias() {
        super(GRID);
        setPreferenceStore(new ScopedPreferenceStore(InstanceScope.INSTANCE, NO));
    }

    /** -Djavva.url manda (teste); senao a preferencia; senao o servidor da casa. */
    public static String url() {
        String p = System.getProperty("javva.url");
        if (p != null && !p.isBlank()) {
            return p.trim();
        }
        return InstanceScope.INSTANCE.getNode(NO).get(URL, PADRAO).trim();
    }

    public static String esforco() {
        String p = System.getProperty("javva.esforco");
        if (p != null && !p.isBlank()) {
            return p.trim();
        }
        return InstanceScope.INSTANCE.getNode(NO).get(ESFORCO, "").trim();
    }

    public static String rotuloEsforco(String valor) {
        for (String[] p : PROFUNDIDADES) {
            if (p[1].equals(valor)) {
                return p[0].split(" — ")[0].toLowerCase();
            }
        }
        return valor;
    }

    public static void salvar(String url, String esforco) throws Exception {
        IEclipsePreferences no = InstanceScope.INSTANCE.getNode(NO);
        no.put(URL, url.trim());
        no.put(ESFORCO, esforco == null ? "" : esforco.trim());
        no.flush();
    }

    @Override
    public void init(IWorkbench w) {
        getPreferenceStore().setDefault(URL, PADRAO);
        getPreferenceStore().setDefault(ESFORCO, "");
        String maq;
        try {
            Identidade id = Identidade.carregar();
            maq = "Esta máquina: " + id.maquina + ". Identidade em " + id.dir
                    + " — a mesma do javva.bat, então as sessões são as mesmas.";
        } catch (Exception e) {
            maq = "";
        }
        setDescription("Servidor do Javva na rede e profundidade das respostas. Depois de mudar, "
                + "clique ↻ na aba do Javva.\n" + maq);
    }

    @Override
    protected void createFieldEditors() {
        addField(new StringFieldEditor(URL, "Servidor:", getFieldEditorParent()));
        String[][] opcoes = new String[PROFUNDIDADES.length][];
        for (int i = 0; i < PROFUNDIDADES.length; i++) {
            opcoes[i] = new String[] { PROFUNDIDADES[i][0], PROFUNDIDADES[i][1] };
        }
        addField(new ComboFieldEditor(ESFORCO, "Profundidade:", opcoes, getFieldEditorParent()));
    }
}
