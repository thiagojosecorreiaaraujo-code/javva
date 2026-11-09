package br.lupa.javva.core;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

/** As 4 ferramentas que o Javva pede ao cliente, com as MESMAS regras do
 *  javva.bat: executar (PowerShell em processo novo), ler_arquivo,
 *  escrever_arquivo, listar_pasta. Executar e gravar pedem permissao. */
public final class Ferramentas {

    /** Pergunta "Permitir?" na tela. */
    public interface Permissao {
        Resposta pedir(String acao, String detalhe);
    }

    public enum Resposta { SIM, NAO, TUDO }

    /** O que mostrar na conversa enquanto a ferramenta roda. */
    public interface Eco {
        void ferramenta(String linha);

        void saida(String resumo);
    }

    static final long LIMITE_LEITURA = 2L * 1024 * 1024;
    static final long ESPERA_MAX_MS = 15L * 60 * 1000;       // o servidor desiste em 15 min
    private static final DateTimeFormatter DATA = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm")
            .withZone(ZoneId.systemDefault());

    private final Supplier<Path> pasta;
    private final Permissao permissao;
    private volatile boolean sempreSim;
    private volatile Process atual;

    public Ferramentas(Supplier<Path> pasta, Permissao permissao) {
        this.pasta = pasta;
        this.permissao = permissao;
    }

    /** "Tudo nesta sessao" vale ate trocar de sessao. */
    public void novaSessao() {
        sempreSim = false;
    }

    /** Botao Parar: mata o comando que esta rodando (e os filhos dele). */
    public void parar() {
        Process p = atual;
        if (p != null) {
            p.descendants().forEach(ProcessHandle::destroyForcibly);
            p.destroyForcibly();
        }
    }

    public Map<String, Object> executar(Map<String, Object> msg, Eco eco) {
        String nome = Json.texto(msg, "nome");
        @SuppressWarnings("unchecked")
        Map<String, Object> a = msg.get("args") instanceof Map ? (Map<String, Object>) msg.get("args") : Map.of();
        try {
            switch (nome) {
                case "executar": {
                    String cmd = Json.texto(a, "comando");
                    String mostra = a.get("exibir") != null ? Json.texto(a, "exibir") : cmd;
                    eco.ferramenta("> executar: " + mostra);
                    if (!permitir("Executar comando", mostra)) {
                        return resposta(false, "O usuario recusou este comando.");
                    }
                    Map<String, Object> r = rodar(cmd);
                    eco.saida(primeiras(Json.texto(r, "saida"), 6));
                    return r;
                }
                case "ler_arquivo": {
                    Path p = resolver(Json.texto(a, "caminho"));
                    eco.ferramenta("> lendo: " + p);
                    if (!Files.isRegularFile(p)) {
                        return resposta(false, "arquivo nao existe: " + p);
                    }
                    if (Files.size(p) > LIMITE_LEITURA) {
                        return resposta(false, "arquivo maior que 2 MB: " + p);
                    }
                    String t = new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
                    return resposta(true, t.startsWith("﻿") ? t.substring(1) : t);
                }
                case "escrever_arquivo": {
                    Path p = resolver(Json.texto(a, "caminho"));
                    String conteudo = Json.texto(a, "conteudo");
                    eco.ferramenta("> gravar: " + p + " (" + conteudo.split("\n", -1).length + " linhas)");
                    if (!permitir("Gravar " + p, primeiras(conteudo, 12))) {
                        return resposta(false, "O usuario recusou a gravacao.");
                    }
                    if (p.getParent() != null) {
                        Files.createDirectories(p.getParent());
                    }
                    Files.writeString(p, conteudo, StandardCharsets.UTF_8);
                    return resposta(true, "gravado: " + p);
                }
                case "listar_pasta": {
                    Path p = resolver(Json.texto(a, "caminho"));
                    eco.ferramenta("> listando: " + p);
                    List<String> itens = new ArrayList<>();
                    try (DirectoryStream<Path> ds = Files.newDirectoryStream(p)) {
                        for (Path f : ds) {
                            boolean dir = Files.isDirectory(f);
                            itens.add((dir ? "<DIR>" : String.valueOf(Files.size(f))) + "\t"
                                    + DATA.format(Files.getLastModifiedTime(f).toInstant()) + "\t"
                                    + f.getFileName());
                        }
                    }
                    itens.sort(String.CASE_INSENSITIVE_ORDER);
                    return resposta(true, String.join("\n", itens));
                }
                default:
                    return resposta(false, "ferramenta desconhecida: " + nome);
            }
        } catch (Exception e) {
            return resposta(false, "erro no cliente: " + e.getMessage());
        }
    }

    private boolean permitir(String acao, String detalhe) {
        if (sempreSim) {
            return true;
        }
        Resposta r = permissao.pedir(acao, detalhe);
        if (r == Resposta.TUDO) {
            sempreSim = true;
        }
        return r != Resposta.NAO;
    }

    /** Caminho relativo vale a partir da pasta atual (como no .bat). */
    public Path resolver(String c) {
        String s = c.trim();
        if (s.length() >= 2 && s.startsWith("\"") && s.endsWith("\"")) {
            s = s.substring(1, s.length() - 1);
        }
        Path p = Paths.get(s);
        return p.isAbsolute() ? p : pasta.get().resolve(p);
    }

    /** Igual ao Rodar-Comando do .bat: -EncodedCommand com saida em UTF-8,
     *  stderr separado e o codigo de saida no fim. */
    Map<String, Object> rodar(String cmd) throws IOException, InterruptedException {
        String prefixo = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ProgressPreference='SilentlyContinue'; ";
        String enc = Base64.getEncoder().encodeToString((prefixo + cmd).getBytes(StandardCharsets.UTF_16LE));
        ProcessBuilder pb = new ProcessBuilder("powershell.exe", "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc);
        pb.directory(pasta.get().toFile());
        Process p = pb.start();
        atual = p;
        try {
            p.getOutputStream().close();          // sem stdin: nada fica esperando teclado
            ByteArrayOutputStream erro = new ByteArrayOutputStream();
            Thread leitorErro = new Thread(() -> copiar(p.getErrorStream(), erro), "javva-stderr");
            leitorErro.setDaemon(true);
            leitorErro.start();
            ByteArrayOutputStream saida = new ByteArrayOutputStream();
            Thread leitorSaida = new Thread(() -> copiar(p.getInputStream(), saida), "javva-stdout");
            leitorSaida.setDaemon(true);
            leitorSaida.start();
            boolean terminou = p.waitFor(ESPERA_MAX_MS, TimeUnit.MILLISECONDS);
            if (!terminou) {
                parar();
            }
            leitorSaida.join(5000);
            leitorErro.join(5000);
            String texto = saida.toString(StandardCharsets.UTF_8).stripTrailing();
            String e = erro.toString(StandardCharsets.UTF_8).stripTrailing();
            if (!e.isBlank()) {
                texto += "\n[stderr]\n" + e;
            }
            if (!terminou) {
                return resposta(false, texto + "\n[interrompido: passou de 15 min]");
            }
            int rc = p.exitValue();
            return resposta(rc == 0, texto + "\n[exit " + rc + "]");
        } finally {
            atual = null;
        }
    }

    private static void copiar(InputStream in, ByteArrayOutputStream out) {
        byte[] b = new byte[8192];
        try (in) {
            int n;
            while ((n = in.read(b)) > 0) {
                synchronized (out) {
                    out.write(b, 0, n);
                }
            }
        } catch (IOException e) {
            // processo morto: fica o que ja chegou
        }
    }

    static String primeiras(String t, int n) {
        String[] l = t.split("\n", -1);
        if (l.length <= n) {
            return t;
        }
        return String.join("\n", java.util.Arrays.copyOf(l, n)) + "\n...";
    }

    static Map<String, Object> resposta(boolean ok, String saida) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("ok", ok);
        m.put("saida", saida);
        return m;
    }
}
