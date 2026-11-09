package br.lupa.javva.core;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;

/** O WebSocket /sessao, com o mesmo protocolo do javva.bat (JSON por mensagem). */
public final class Conexao implements WebSocket.Listener {

    private static final Map<String, Object> FECHOU = Map.of("tipo", "_fechou");

    private final BlockingQueue<Map<String, Object>> fila = new LinkedBlockingQueue<>();
    private final StringBuilder parcial = new StringBuilder();
    private volatile WebSocket ws;
    private volatile String motivo = "";

    private Conexao() {
    }

    public static Conexao abrir(String url, String token) throws IOException {
        Conexao c = new Conexao();
        URI u = URI.create(url.replaceFirst("^http", "ws") + "/sessao");
        try {
            c.ws = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                    .connectTimeout(Duration.ofSeconds(15)).build()
                    .newWebSocketBuilder()
                    .header("Authorization", "Bearer " + token)
                    .buildAsync(u, c).get(20, TimeUnit.SECONDS);
        } catch (Exception e) {
            throw new IOException("nao conectou em " + u + ": " + e.getMessage(), e);
        }
        return c;
    }

    @Override
    public void onOpen(WebSocket w) {
        w.request(1);
    }

    @Override
    public CompletionStage<?> onText(WebSocket w, CharSequence dados, boolean ultimo) {
        parcial.append(dados);
        if (ultimo) {
            try {
                fila.add(Json.objeto(parcial.toString()));
            } catch (RuntimeException e) {
                fila.add(Map.of("tipo", "erro", "mensagem", "resposta invalida do servidor: " + e.getMessage()));
            }
            parcial.setLength(0);
        }
        w.request(1);
        return null;
    }

    @Override
    public CompletionStage<?> onClose(WebSocket w, int codigo, String razao) {
        motivo = razao;
        fila.add(FECHOU);
        return null;
    }

    @Override
    public void onError(WebSocket w, Throwable erro) {
        motivo = String.valueOf(erro.getMessage());
        fila.add(FECHOU);
    }

    public synchronized void enviar(Map<String, Object> m) throws IOException {
        try {
            ws.sendText(Json.escrever(m), true).get(30, TimeUnit.SECONDS);
        } catch (Exception e) {
            throw new IOException("falha ao enviar ao Javva: " + e.getMessage(), e);
        }
    }

    /** Proxima mensagem; null quando a conexao fechou. */
    public Map<String, Object> receber() throws InterruptedException {
        Map<String, Object> m = fila.take();
        if (m == FECHOU) {
            fila.add(FECHOU);              // quem perguntar de novo tambem ve o fim
            return null;
        }
        return m;
    }

    public String motivo() {
        return motivo;
    }

    public void fechar() {
        WebSocket w = ws;
        if (w == null) {
            return;
        }
        try {
            enviar(Map.of("tipo", "sair"));
        } catch (IOException e) {
            // ja caiu
        }
        try {
            w.sendClose(WebSocket.NORMAL_CLOSURE, "").get(5, TimeUnit.SECONDS);
        } catch (Exception e) {
            w.abort();
        }
    }
}
