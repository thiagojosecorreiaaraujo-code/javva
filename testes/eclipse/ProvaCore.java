import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import br.lupa.javva.core.Cliente;
import br.lupa.javva.core.Ferramentas;
import br.lupa.javva.core.Identidade;
import br.lupa.javva.core.Imagens;
import br.lupa.javva.core.Json;

/** O nucleo do plugin (o MESMO codigo que a aba do Eclipse usa) contra o
 *  javva-teste + API falsa. Roda com o java do Eclipse, sem OSGi:
 *    java -Djavva.dir=<tmp> -cp br.lupa.javva_X.jar ProvaCore.java <url> <foto.png>
 *  Saida: uma linha "ok"/"FALHA" por verificacao e um JSON final. */
public class ProvaCore {

    static int falhas;

    static void ok(String nome, boolean c, Object det) {
        System.out.println((c ? "  ok    " : "  FALHA ") + nome + (c ? "" : "  -> " + det));
        if (!c) {
            falhas++;
        }
    }

    static final class Gravador implements Cliente.Ouvinte {
        final StringBuilder t = new StringBuilder();

        public void texto(String s) { t.append(s); }
        public void info(String s) { t.append("\n[info] ").append(s); }
        public void erro(String s) { t.append("\n[erro] ").append(s); }
        public void ferramenta(String s) { t.append("\n[ferramenta] ").append(s); }
        public void saida(String s) { t.append("\n[saida] ").append(s); }
    }

    public static void main(String[] a) throws Exception {
        String url = a[0];
        Path foto = Path.of(a[1]);
        Path pasta = Files.createTempDirectory("javva-eclipse-pasta");
        List<String> pedidos = new ArrayList<>();
        Ferramentas.Resposta[] resposta = { Ferramentas.Resposta.SIM };
        Identidade id = Identidade.carregar();
        Cliente c = new Cliente(url, id, new Ferramentas(() -> pasta, (acao, det) -> {
            pedidos.add(acao + " | " + det);
            return resposta[0];
        }));

        System.out.println("== 1. conecta, registra sozinho, sem sessoes");
        List<Map<String, Object>> s = c.conectar(pasta.toString(), aviso -> System.out.println("  aviso: " + aviso));
        ok("conectou e a lista veio vazia", s.isEmpty(), s);
        ok("nome publico", c.nome().equals("IA LOCAL - JAVVA"), c.nome());
        Gravador g = new Gravador();
        c.abrir(null, g);

        System.out.println("== 2. comando no cliente com Permitir? = Sim");
        g = new Gravador();
        c.perguntar("[Eclipse] pasta atual: " + pasta + "\n\nrode o teste do cliente", List.of(), g);
        ok("pediu permissao com o comando visivel", pedidos.size() == 1 && pedidos.get(0).contains("JAVVA-CLIENTE-"), pedidos);
        ok("comando rodou AQUI e voltou ao modelo",
                g.t.toString().contains("RESULTADO DO CLIENTE: JAVVA-CLIENTE-OK em " + id.maquina), g.t);
        ok("rodape com a sessao", g.t.toString().matches("(?s).*\\[IA LOCAL - JAVVA - sessao [0-9a-f]{8} - [\\d.]+s\\].*"), g.t);
        String sid = c.sessao();
        ok("sessao ganhou numero", sid != null && sid.length() == 36, sid);

        System.out.println("== 3. recusa (Nao)");
        resposta[0] = Ferramentas.Resposta.NAO;
        g = new Gravador();
        c.perguntar("rode o teste de novo", List.of(), g);
        ok("recusa chegou ao modelo", g.t.toString().contains("O usuario recusou este comando."), g.t);
        resposta[0] = Ferramentas.Resposta.SIM;

        System.out.println("== 4. foto anexada");
        List<String> avisos = new ArrayList<>();
        List<Map<String, Object>> imgs = Imagens.montar(List.of(foto), avisos);
        g = new Gravador();
        c.perguntar("olha esta foto", imgs, g);
        ok("modelo recebeu a foto", g.t.toString().contains("JAVVA OK (foto recebida)"), g.t);
        List<Path> citadas = Imagens.citadas("veja \"" + foto + "\" por favor", c.ferramentas::resolver);
        ok("caminho de foto escrito na mensagem e reconhecido", citadas.size() == 1, citadas);
        c.fechar();

        System.out.println("== 5. reabre: lista HOSTNAME - IP - sessao - data e retoma");
        Cliente c2 = new Cliente(url, id, new Ferramentas(() -> pasta, (x, y) -> Ferramentas.Resposta.SIM));
        List<Map<String, Object>> s2 = c2.conectar(pasta.toString(), x -> { });
        String rot = s2.isEmpty() ? "" : Json.texto(s2.get(0), "rotulo");
        ok("rotulo da sessao", rot.matches(id.maquina + " - \\d+\\.\\d+\\.\\d+\\.\\d+ - " + sid
                + " - \\d\\d/\\d\\d/\\d{4} - \\d\\d:\\d\\d"), rot);
        g = new Gravador();
        c2.abrir(sid, g);
        ok("avisou que retomou", g.t.toString().contains("Sessao " + sid + " retomada"), g.t);
        g = new Gravador();
        c2.perguntar("mensagem depois de reabrir", List.of(), g);
        ok("resposta na sessao retomada", g.t.toString().contains("JAVVA OK"), g.t);
        c2.fechar();

        System.out.println("== 6. ferramentas locais");
        Ferramentas f = new Ferramentas(() -> pasta, (x, y) -> Ferramentas.Resposta.SIM);
        Cliente.Ouvinte mudo = new Gravador();
        Map<String, Object> r = f.executar(Map.of("nome", "escrever_arquivo",
                "args", Map.of("caminho", "sub/ola.txt", "conteudo", "linha 1\nação ✓")), mudo);
        ok("grava relativo a pasta atual", Boolean.TRUE.equals(r.get("ok"))
                && Files.readString(pasta.resolve("sub/ola.txt")).equals("linha 1\nação ✓"), r);
        r = f.executar(Map.of("nome", "ler_arquivo", "args", Map.of("caminho", "sub/ola.txt")), mudo);
        ok("le em UTF-8", "linha 1\nação ✓".equals(r.get("saida")), r);
        r = f.executar(Map.of("nome", "listar_pasta", "args", Map.of("caminho", "sub")), mudo);
        ok("lista a pasta", String.valueOf(r.get("saida")).endsWith("\tola.txt"), r);
        r = f.executar(Map.of("nome", "executar", "args", Map.of("comando", "Write-Output 'acentuação'; exit 3")), mudo);
        ok("saida UTF-8 e codigo de saida", String.valueOf(r.get("saida")).startsWith("acentuação")
                && String.valueOf(r.get("saida")).endsWith("[exit 3]") && Boolean.FALSE.equals(r.get("ok")), r);
        r = f.executar(Map.of("nome", "executar", "args", Map.of("comando", "(Get-Location).Path")), mudo);
        ok("comando roda na pasta atual", String.valueOf(r.get("saida")).startsWith(pasta.toString()), r);

        System.out.println("\nPROVA CORE: " + (falhas == 0 ? "PASSOU" : falhas + " FALHA(S)"));
        System.exit(falhas == 0 ? 0 : 1);
    }
}
