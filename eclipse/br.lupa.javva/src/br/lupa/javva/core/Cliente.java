package br.lupa.javva.core;

import java.io.IOException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Uma conversa com o Javva: conectar, escolher a sessao, perguntar.
 *  Nada de SWT aqui: a tela (JavvaView) e o teste usam a mesma classe. */
public final class Cliente {

    /** Protocolo v4 do javva.bat: o servidor manda a lista de sessoes com o
     *  rotulo pronto (HOSTNAME - IP - resume - data/hora) e espera "sessao". */
    public static final int VERSAO = 4;

    /** O que chega do servidor durante uma resposta. */
    public interface Ouvinte extends Ferramentas.Eco {
        void texto(String t);

        void info(String t);

        void erro(String t);
    }

    public final String url;
    public final Identidade id;
    public final Ferramentas ferramentas;
    private Conexao con;
    private Map<String, Object> pronto = Map.of();
    private volatile String sessao;

    /** Profundidade pedida ao servidor (low..max); vazio = padrao do servidor. */
    public final String esforco;

    public Cliente(String url, Identidade id, Ferramentas ferramentas) {
        this(url, id, ferramentas, "");
    }

    public Cliente(String url, Identidade id, Ferramentas ferramentas, String esforco) {
        this.url = url.replaceAll("/+$", "");
        this.id = id;
        this.ferramentas = ferramentas;
        this.esforco = esforco == null ? "" : esforco.trim();
    }

    public String sessao() {
        return sessao;
    }

    public String nome() {
        String n = Json.texto(pronto, "nome");
        return n.isEmpty() ? "IA LOCAL - JAVVA" : n;
    }

    /** Conecta e devolve as sessoes desta maquina (mais recente primeiro). */
    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> conectar(String pasta, java.util.function.Consumer<String> aviso)
            throws IOException, InterruptedException {
        fechar();
        id.garantirAcesso(url, aviso);
        con = Conexao.abrir(url, id.token);
        Map<String, Object> ola = new LinkedHashMap<>();
        ola.put("tipo", "ola");
        ola.put("maquina", id.maquina);
        ola.put("usuario", String.valueOf(System.getenv("USERNAME")));
        ola.put("pasta", pasta);
        ola.put("so", System.getProperty("os.name") + " " + System.getProperty("os.version"));
        ola.put("ip", Identidade.meuIp(url));
        ola.put("versao", VERSAO);
        ola.put("cliente", "eclipse");
        if (!esforco.isEmpty()) {
            ola.put("esforco", esforco);
        }
        con.enviar(ola);
        Map<String, Object> m = con.receber();
        if (m == null) {
            throw new IOException("o Javva fechou a conexao " + con.motivo());
        }
        if ("erro".equals(m.get("tipo"))) {
            throw new IOException(Json.texto(m, "mensagem"));
        }
        pronto = m;
        List<Map<String, Object>> l = new ArrayList<>();
        if (m.get("sessoes") instanceof List<?> s) {
            for (Object o : s) {
                if (o instanceof Map) {
                    l.add((Map<String, Object>) o);
                }
            }
        }
        return l;
    }

    /** null = sessao nova. */
    public void abrir(String idSessao, Ouvinte o) throws IOException, InterruptedException {
        ferramentas.novaSessao();
        sessao = idSessao;
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("tipo", "sessao");
        m.put("id", idSessao);
        con.enviar(m);
        lerResposta(o);
    }

    public void perguntar(String texto, List<Map<String, Object>> imagens, Ouvinte o)
            throws IOException, InterruptedException {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("tipo", "prompt");
        m.put("texto", texto);
        m.put("imagens", imagens);
        con.enviar(m);
        lerResposta(o);
    }

    private void lerResposta(Ouvinte o) throws IOException, InterruptedException {
        while (true) {
            Map<String, Object> m = con.receber();
            if (m == null) {
                throw new IOException("conexao com o Javva perdida " + con.motivo());
            }
            switch (Json.texto(m, "tipo")) {
                case "texto" -> o.texto(Json.texto(m, "texto"));
                case "ferramenta" -> {
                    Map<String, Object> r = ferramentas.executar(m, o);
                    Map<String, Object> res = new LinkedHashMap<>();
                    res.put("tipo", "resultado");
                    res.put("id", m.get("id"));
                    res.putAll(r);
                    con.enviar(res);
                }
                case "erro" -> o.erro(Json.texto(m, "mensagem"));
                case "fim" -> {
                    if (m.get("sessao") != null) {
                        sessao = Json.texto(m, "sessao");
                    }
                    String info = Json.texto(m, "info");
                    if (!info.isEmpty()) {
                        o.info(info);
                    }
                    return;
                }
                default -> {
                    // tipo novo de um servidor mais novo: ignora
                }
            }
        }
    }

    public void fechar() {
        Conexao c = con;
        con = null;
        if (c != null) {
            c.fechar();
        }
    }
}
