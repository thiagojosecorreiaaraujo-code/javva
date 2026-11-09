package br.lupa.javva.ui;

import org.eclipse.core.commands.AbstractHandler;
import org.eclipse.core.commands.ExecutionEvent;
import org.eclipse.core.commands.ExecutionException;
import org.eclipse.ui.PartInitException;
import org.eclipse.ui.handlers.HandlerUtil;

/** Menu IA LOCAL > Abrir o Javva (e o botao da barra). */
public class AbrirJavva extends AbstractHandler {

    @Override
    public Object execute(ExecutionEvent e) throws ExecutionException {
        try {
            HandlerUtil.getActiveWorkbenchWindowChecked(e).getActivePage().showView(JavvaView.ID);
        } catch (PartInitException ex) {
            throw new ExecutionException("nao abriu a aba do Javva", ex);
        }
        return null;
    }
}
