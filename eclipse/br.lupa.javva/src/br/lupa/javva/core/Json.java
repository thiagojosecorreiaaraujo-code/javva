package br.lupa.javva.core;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** JSON minimo (Map/List/String/Long/Double/Boolean/null): o plugin nao
 *  carrega biblioteca nenhuma alem do que o Eclipse ja tem. */
public final class Json {

    private Json() {
    }

    public static Object ler(String s) {
        Leitor l = new Leitor(s);
        Object v = l.valor();
        l.espacos();
        if (l.i != s.length()) {
            throw new IllegalArgumentException("JSON com sobra na posicao " + l.i);
        }
        return v;
    }

    @SuppressWarnings("unchecked")
    public static Map<String, Object> objeto(String s) {
        Object o = ler(s);
        if (!(o instanceof Map)) {
            throw new IllegalArgumentException("JSON nao e objeto");
        }
        return (Map<String, Object>) o;
    }

    public static String escrever(Object o) {
        StringBuilder b = new StringBuilder();
        escrever(o, b);
        return b.toString();
    }

    public static String texto(Map<String, Object> m, String chave) {
        Object v = m == null ? null : m.get(chave);
        return v == null ? "" : String.valueOf(v);
    }

    @SuppressWarnings("unchecked")
    private static void escrever(Object o, StringBuilder b) {
        if (o == null) {
            b.append("null");
        } else if (o instanceof String s) {
            aspas(s, b);
        } else if (o instanceof Boolean || o instanceof Integer || o instanceof Long) {
            b.append(o);
        } else if (o instanceof Number n) {
            double d = n.doubleValue();
            b.append(Double.isFinite(d) ? String.valueOf(o) : "null");
        } else if (o instanceof Map<?, ?> m) {
            b.append('{');
            boolean primeiro = true;
            for (Map.Entry<?, ?> e : m.entrySet()) {
                if (!primeiro) {
                    b.append(',');
                }
                primeiro = false;
                aspas(String.valueOf(e.getKey()), b);
                b.append(':');
                escrever(e.getValue(), b);
            }
            b.append('}');
        } else if (o instanceof Iterable<?> it) {
            b.append('[');
            boolean primeiro = true;
            for (Object x : it) {
                if (!primeiro) {
                    b.append(',');
                }
                primeiro = false;
                escrever(x, b);
            }
            b.append(']');
        } else {
            aspas(String.valueOf(o), b);
        }
    }

    private static void aspas(String s, StringBuilder b) {
        b.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> b.append("\\\"");
                case '\\' -> b.append("\\\\");
                case '\n' -> b.append("\\n");
                case '\r' -> b.append("\\r");
                case '\t' -> b.append("\\t");
                case '\b' -> b.append("\\b");
                case '\f' -> b.append("\\f");
                default -> {
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
                }
            }
        }
        b.append('"');
    }

    private static final class Leitor {
        final String s;
        int i;

        Leitor(String s) {
            this.s = s;
        }

        void espacos() {
            while (i < s.length() && Character.isWhitespace(s.charAt(i))) {
                i++;
            }
        }

        Object valor() {
            espacos();
            if (i >= s.length()) {
                throw new IllegalArgumentException("JSON terminou cedo");
            }
            char c = s.charAt(i);
            switch (c) {
                case '{':
                    return objeto();
                case '[':
                    return lista();
                case '"':
                    return string();
                case 't':
                    return palavra("true", Boolean.TRUE);
                case 'f':
                    return palavra("false", Boolean.FALSE);
                case 'n':
                    return palavra("null", null);
                default:
                    return numero();
            }
        }

        Object palavra(String p, Object v) {
            if (!s.startsWith(p, i)) {
                throw new IllegalArgumentException("JSON invalido na posicao " + i);
            }
            i += p.length();
            return v;
        }

        Map<String, Object> objeto() {
            Map<String, Object> m = new LinkedHashMap<>();
            i++;
            espacos();
            if (s.charAt(i) == '}') {
                i++;
                return m;
            }
            while (true) {
                espacos();
                String k = string();
                espacos();
                if (s.charAt(i++) != ':') {
                    throw new IllegalArgumentException("esperava ':' na posicao " + (i - 1));
                }
                m.put(k, valor());
                espacos();
                char c = s.charAt(i++);
                if (c == '}') {
                    return m;
                }
                if (c != ',') {
                    throw new IllegalArgumentException("esperava ',' na posicao " + (i - 1));
                }
            }
        }

        List<Object> lista() {
            List<Object> l = new ArrayList<>();
            i++;
            espacos();
            if (s.charAt(i) == ']') {
                i++;
                return l;
            }
            while (true) {
                l.add(valor());
                espacos();
                char c = s.charAt(i++);
                if (c == ']') {
                    return l;
                }
                if (c != ',') {
                    throw new IllegalArgumentException("esperava ',' na posicao " + (i - 1));
                }
            }
        }

        String string() {
            if (s.charAt(i) != '"') {
                throw new IllegalArgumentException("esperava '\"' na posicao " + i);
            }
            i++;
            StringBuilder b = new StringBuilder();
            while (true) {
                char c = s.charAt(i++);
                if (c == '"') {
                    return b.toString();
                }
                if (c != '\\') {
                    b.append(c);
                    continue;
                }
                char e = s.charAt(i++);
                switch (e) {
                    case 'n' -> b.append('\n');
                    case 'r' -> b.append('\r');
                    case 't' -> b.append('\t');
                    case 'b' -> b.append('\b');
                    case 'f' -> b.append('\f');
                    case 'u' -> {
                        b.append((char) Integer.parseInt(s.substring(i, i + 4), 16));
                        i += 4;
                    }
                    default -> b.append(e);
                }
            }
        }

        Object numero() {
            int ini = i;
            boolean real = false;
            while (i < s.length()) {
                char c = s.charAt(i);
                if (c == '.' || c == 'e' || c == 'E') {
                    real = true;
                } else if (!(c == '-' || c == '+' || Character.isDigit(c))) {
                    break;
                }
                i++;
            }
            String n = s.substring(ini, i);
            if (n.isEmpty()) {
                throw new IllegalArgumentException("JSON invalido na posicao " + ini);
            }
            return real ? (Object) Double.valueOf(n) : (Object) Long.valueOf(n);
        }
    }
}
