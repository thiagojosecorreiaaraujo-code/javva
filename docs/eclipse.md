# Plugin Eclipse: IA LOCAL - JAVVA

## Requisitos

- Eclipse rodando com **Java 17+** (Eclipse 2022 em diante; testado no 2026‑09).
- Acesso de rede ao servidor Javva (porta 8787).

## Instalar pelo zip (recomendado)

1. Baixe `javva-eclipse.zip` da [Release](../../../releases/latest) ou de
   `http://<servidor>:8787/javva-eclipse.zip`. **Não descompacte.**
2. **Help → Install New Software…**
3. **Add…** → **Archive…** → escolha o zip → Name `IA LOCAL - JAVVA` → **Add**.
4. Marque **IA LOCAL** → **Next** → **Next** → aceite a licença → **Finish**.
5. **Trust** (conteúdo sem assinatura) → marque → **Trust Selected**.
6. **Restart Now**.
7. Menu **IA LOCAL → Abrir o Javva** (ou o botão "J" na barra).

> Não aparece nada na lista? Desmarque *Group items by category* ou confira
> se escolheu o zip certo (contém `content.jar`, `artifacts.jar`,
> `features/`, `plugins/`).

## Instalar pelo endereço (recebe atualizações)

O Eclipse novo troca `http://` por `https://` sozinho e a instalação por
endereço falha com *Unsupported or unrecognized SSL message*. Para usar o
endereço direto:

1. Feche o Eclipse e acrescente no fim do `eclipse.ini`, **depois** de
   `-vmargs`:
   ```
   -Dp2.httpRule=allow
   ```
2. Abra o Eclipse → **Install New Software → Add…** → Location
   `http://<servidor>:8787/eclipse/`.
3. Depois disso, versões novas chegam por **Help → Check for Updates**.

## Atualizar

- Instalado pelo zip: baixe o zip novo e repita a instalação (o Eclipse
  troca a versão).
- Instalado pelo endereço: **Help → Check for Updates**.

Depois de reiniciar, se a aba já estava aberta, clique **↻**.

## Configurar

Botão **⚙** da aba (ou **Window → Preferences → IA LOCAL - JAVVA**):

| Campo | Padrão | Observação |
|---|---|---|
| Servidor (URL) | `http://192.168.68.106:8787` | formato `http://endereço:porta` |
| Profundidade | padrão do servidor | Rápida · Normal · Alta · Muito alta · Máxima. Mais profunda = melhor em tarefas difíceis, mais lenta e mais cara. |

Salvar reconecta **na mesma conversa**.

## Recursos da aba

| Ação | Como |
|---|---|
| Mandar mensagem | Enter (`Shift+Enter` = nova linha) |
| Colar Print Screen / imagem copiada | `Ctrl+V` na caixa de texto, ou botão direito → *Colar imagem (Print Screen)*. Imagens grandes são reduzidas para 1920 px. |
| Anexar arquivo de imagem | **Foto…** (png, jpg, gif, webp até 5 MB); clique na miniatura para tirar |
| Retomar conversa | escolha na lista **Sessão** → **Abrir** |
| Interromper comando | **Parar** |
| Contexto do Eclipse | caixa *Mandar projeto, arquivo e seleção* |

Toda ação no computador (comando, gravar/ler arquivo, listar pasta) passa
pelo **Permitir?**: *Sim*, *Não* ou *Tudo nesta sessão*.

## Gerar o plugin a partir da fonte

Sem Maven/Tycho: usa o `javac` do JustJ e o publisher p2 do Eclipse instalado.

```bash
python eclipse/construir.py
```

Saída: `cliente/eclipse/` (update site) e `cliente/eclipse/javva-eclipse-site.zip`
(o mesmo publicado como `javva-eclipse.zip` na Release e na rota do servidor).

Prova dentro do `eclipse.exe` real, sem mexer na instalação do usuário
(abre a aba, conecta, responde o Permitir?, cola imagem, mede rolagem):

```bash
python testes/eclipse/prova_eclipse.py
```
