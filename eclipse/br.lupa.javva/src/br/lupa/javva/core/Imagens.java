package br.lupa.javva.core;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Fotos: as anexadas pelo botao/arrastar e os caminhos escritos na mensagem
 *  (mesma regra do javva.bat: .png .jpg .jpeg .gif .webp, ate 5 MB). */
public final class Imagens {

    public static final long LIMITE = 5L * 1024 * 1024;
    private static final Pattern RX = Pattern.compile(
            "\"([^\"]+\\.(?:png|jpe?g|gif|webp))\"|(\\S+\\.(?:png|jpe?g|gif|webp))",
            Pattern.CASE_INSENSITIVE);

    private Imagens() {
    }

    public static boolean ehImagem(String nome) {
        return tipo(nome) != null;
    }

    static String tipo(String nome) {
        String n = nome.toLowerCase(Locale.ROOT);
        if (n.endsWith(".png")) {
            return "image/png";
        }
        if (n.endsWith(".jpg") || n.endsWith(".jpeg")) {
            return "image/jpeg";
        }
        if (n.endsWith(".gif")) {
            return "image/gif";
        }
        if (n.endsWith(".webp")) {
            return "image/webp";
        }
        return null;
    }

    /** Caminhos de imagem citados no texto, resolvidos pela pasta atual. */
    public static List<Path> citadas(String texto, Function<String, Path> resolver) {
        List<Path> l = new ArrayList<>();
        Matcher m = RX.matcher(texto);
        while (m.find()) {
            String c = m.group(1) != null ? m.group(1) : m.group(2);
            try {
                Path p = resolver.apply(c);
                if (Files.isRegularFile(p)) {
                    l.add(p);
                }
            } catch (RuntimeException e) {
                // caminho invalido: e so texto
            }
        }
        return l;
    }

    /** Monta a lista que vai no "prompt" ({nome, media_type, base64}).
     *  avisos recebe o que foi ignorado. */
    public static List<Map<String, Object>> montar(List<Path> arquivos, List<String> avisos) {
        List<Map<String, Object>> l = new ArrayList<>();
        Set<Path> vistos = new LinkedHashSet<>();
        for (Path p : arquivos) {
            if (!vistos.add(p.toAbsolutePath().normalize())) {
                continue;
            }
            try {
                if (Files.size(p) > LIMITE) {
                    avisos.add("foto acima de 5 MB ignorada: " + p);
                    continue;
                }
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("nome", p.getFileName().toString());
                m.put("media_type", tipo(p.getFileName().toString()));
                m.put("base64", Base64.getEncoder().encodeToString(Files.readAllBytes(p)));
                l.add(m);
            } catch (IOException e) {
                avisos.add("nao li a foto " + p + ": " + e.getMessage());
            }
        }
        return l;
    }
}
