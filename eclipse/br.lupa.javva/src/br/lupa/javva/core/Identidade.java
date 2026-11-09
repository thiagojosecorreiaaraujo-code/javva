package br.lupa.javva.core;

import java.io.IOException;
import java.net.DatagramSocket;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.util.HexFormat;
import java.util.function.Consumer;

/** Quem e esta maquina para o Javva. Usa o MESMO token do javva.bat
 *  (%LOCALAPPDATA%\javva\token): mesmo codigo, mesmas sessoes. */
public final class Identidade {

    public final Path dir;
    public final String token;
    public final String codigo;
    public final String maquina;

    private Identidade(Path dir, String token) {
        this.dir = dir;
        this.token = token;
        this.codigo = codigoDe(token);
        String m = System.getenv("COMPUTERNAME");
        this.maquina = m == null || m.isBlank() ? "ECLIPSE" : m;
    }

    public static Identidade carregar() throws IOException {
        String d = System.getProperty("javva.dir");
        Path dir;
        if (d != null && !d.isBlank()) {
            dir = Paths.get(d);
        } else {
            String base = System.getenv("LOCALAPPDATA");
            dir = Paths.get(base != null ? base : System.getProperty("user.home"), "javva");
        }
        Files.createDirectories(dir);
        Path arq = dir.resolve("token");
        if (!Files.exists(arq)) {
            byte[] b = new byte[32];
            new SecureRandom().nextBytes(b);
            Files.writeString(arq, HexFormat.of().formatHex(b), StandardCharsets.US_ASCII);
        }
        return new Identidade(dir, Files.readString(arq, StandardCharsets.US_ASCII).trim());
    }

    /** Mesmo codigo que o servidor mostra: 6 primeiros hex do sha256 do token. */
    static String codigoDe(String token) {
        try {
            byte[] h = MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(h).substring(0, 6).toUpperCase();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    /** IP desta maquina na rede do servidor (o servidor so ve o NAT do Docker).
     *  UDP "conectado" nao manda pacote: so escolhe a interface de saida. */
    public static String meuIp(String url) {
        try (DatagramSocket s = new DatagramSocket()) {
            URI u = URI.create(url);
            s.connect(new InetSocketAddress(u.getHost(), u.getPort() > 0 ? u.getPort() : 80));
            return s.getLocalAddress().getHostAddress();
        } catch (Exception e) {
            return "";
        }
    }

    /** Status/registro igual ao javva.bat: 401 registra (o servidor autoaprova),
     *  pendente espera, revogada para. */
    public void garantirAcesso(String url, Consumer<String> aviso) throws IOException, InterruptedException {
        // HTTP/1.1 fixo: o padrao do Java tenta "Upgrade: h2c" e o uvicorn le o
        // corpo do POST vazio ("Pedido invalido" no /registrar).
        HttpClient hc = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(Duration.ofSeconds(10)).build();
        boolean avisou = false;
        for (int tentativa = 0; tentativa < 400; tentativa++) {
            HttpResponse<String> r;
            try {
                r = hc.send(HttpRequest.newBuilder(URI.create(url + "/status"))
                        .header("Authorization", "Bearer " + token)
                        .timeout(Duration.ofSeconds(10)).GET().build(),
                        HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            } catch (IOException e) {
                throw new IOException("Javva fora do ar em " + url + " (" + e.getMessage() + ")", e);
            }
            String txt = r.body() == null ? "" : r.body().trim();
            if (r.statusCode() == 200) {
                return;
            }
            if (r.statusCode() == 401) {
                String corpo = "maquina=" + URLEncoder.encode(maquina, StandardCharsets.UTF_8)
                        + "&token=" + URLEncoder.encode(token, StandardCharsets.UTF_8);
                HttpResponse<String> reg = hc.send(HttpRequest.newBuilder(URI.create(url + "/registrar"))
                        .header("Content-Type", "application/x-www-form-urlencoded")
                        .timeout(Duration.ofSeconds(10))
                        .POST(HttpRequest.BodyPublishers.ofString(corpo)).build(),
                        HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
                if (reg.statusCode() >= 400) {
                    throw new IOException("o Javva recusou o registro desta maquina: " + reg.body().trim());
                }
                continue;                         // registro e silencioso: o servidor ja libera
            }
            if (txt.contains("revogad")) {
                throw new IOException(txt);
            }
            if (!avisou) {
                aviso.accept("Aguardando o servidor liberar esta maquina...");
                avisou = true;
            }
            Thread.sleep(3000);
        }
        throw new IOException("o servidor nao liberou esta maquina");
    }
}
