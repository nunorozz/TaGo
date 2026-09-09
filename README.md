# TaGo — Music Tag Editor

App para ver, corrigir e **gravar** as tags (título, artista, álbum, ano,
género, capa) dos teus ficheiros de música.

---

## Como abrir

Duplo-clique em **`Abrir App.bat`**. É assim que se abre a app a partir do
código, com o Python instalado.

---

## Instalar

### Instalar a app

Duplo-clique em **`Output\TaGo-Setup-2.0.exe`** — o instalador normal do
Windows, com assistente em português. Funciona em computadores **sem Python
instalado**, e é este único ficheiro que se dá a quem quiser a app.

Depois de instalada, o TaGo aparece no menu Iniciar, no ambiente de trabalho
(se escolheres esse atalho) e em **Definições → Aplicações**, de onde se
desinstala como qualquer outro programa.

### Fazer o instalador

Duplo-clique em **`Criar Instalador.bat`**. Demora alguns minutos e só é
preciso quando o código muda. Faz duas coisas:

1. Constrói o programa para `dist\TaGo\` (com o **PyInstaller**).
2. Embrulha-o em `Output\TaGo-Setup-2.0.exe` (com o **Inno Setup**).

Se o Inno Setup não estiver instalado, o ficheiro trata de o instalar. Se
mesmo assim faltar, fica na mesma a pasta `dist\` com um
`Instalar TaGo.bat` ao lado, que faz o mesmo de maneira mais simples.

### No Mac

A app corre em macOS, mas **o instalador do Mac tem de ser feito num Mac**: o
PyInstaller embrulha o Python e o Tk da máquina onde está, e não constrói para
um sistema a partir de outro.

Num Mac, duplo-clique em **`Criar Instalador Mac.command`**. Faz o mesmo que o
`.bat` do Windows, mas à maneira de lá:

1. Constrói o `dist/TaGo.app` (com o **PyInstaller**).
2. Embrulha-o num `Output/TaGo-2.0.dmg`, com o atalho para a pasta Aplicações
   ao lado, usando o **hdiutil** que já vem no macOS.

Para correr a app a partir do código, sem empacotar nada: `python3 app.py`.

Três coisas mudam em relação ao Windows:

- **A app não vai assinada.** Sem uma conta Apple Developer, o Gatekeeper
  recusa-a e diz que "está danificada" — não está, é só o que ele diz a
  software não assinado. Na primeira vez abre-se pelo **botão direito →
  Abrir**, ou tira-se a marca de uma vez:
  `xattr -dr com.apple.quarantine /Applications/TaGo.app`
- **O VLC faz mais falta.** O leitor de reserva do Windows (o MCI) não existe
  no macOS: sem o VLC, carregar em play abre a música no leitor do sistema e a
  app deixa de a controlar. Instala-se com `brew install --cask vlc`.
- **As definições e as chaves** ficam em `~/Library/Application Support/TaGo`,
  que é o sítio que o macOS reserva para isso, e não em `%APPDATA%`.

---

### Quatro coisas que convém saber

- **Não é preciso ser administrador.** Por omissão a app instala-se na pasta
  pessoal, não em `Program Files`. Quem quiser instalar para todos os
  utilizadores do computador escolhe isso na primeira janela do Setup.
- **As definições e as chaves não são tocadas.** Vivem em `%APPDATA%\TaGo` e
  sobrevivem a instalar, desinstalar e actualizar. Também **não** vão dentro
  do instalador: uma cópia da app dada a outra pessoa não leva as tuas chaves
  do Spotify e do Discogs atrás.
- **Actualizar é correr o Setup outra vez.** Ele fecha a app se estiver
  aberta (a perguntar primeiro), substitui os ficheiros e não deixa restos da
  versão anterior. Não é preciso desinstalar antes.
- **O VLC continua a ser preciso** e não vem dentro da app (é um programa à
  parte, com licença própria). Sem ele a app abre na mesma, mas não toca as
  músicas nem desenha as formas de onda. O Setup avisa se não o encontrar.
  Instala-se com `winget install VideoLAN.VLC`.

---

## O aspeto

A app segue o estilo do **Ableton Live**: tudo cinzento escuro e mate, cantos
vivos, painéis separados por linhas finas, e letra estreita.

A regra da cor é simples: **o amarelo é sempre o que interessa**. Os dois
botões amarelos são os dois passos principais (*Analisar Pasta* e *Procurar
Tags*), a música selecionada na lista fica amarela, a capa escolhida fica com
contorno amarelo, e as sugestões da Internet aparecem em amarelo quando a app
está segura. Tudo o resto é cinzento, de propósito.

A exceção é o verde do **Gravar Metadata** — a única ação que mexe mesmo nos
ficheiros.

A letra usada é a *Bahnschrift*, que já vem com o Windows. Se por alguma razão
não estiver instalada, a app usa a normal do sistema e funciona na mesma.

O **logo** aparece em dois sítios: no canto esquerdo da barra de cima, e como
ícone da janela e da barra de tarefas. O original é o `tago-logo-v3.svg`, mas
o tkinter não lê SVG e uma biblioteca só para isso seria mais uma coisa a
instalar em cada computador — por isso o desenho é refeito em código pelo
`criar_logo.py`, que grava o PNG e o ICO em `recursos/`. Só é preciso voltar a
correr esse programa se o logo mudar.

Na barra usa-se uma versão recortada, só com as barras e a palavra: o logo
completo tem quase metade da altura vazia e, ao tamanho da barra, o *TAGO*
ficava ilegível.

No ícone, a marca é centrada no quadrado e ampliada até ocupar cerca de 70%
da largura. No SVG ocupa 28%, o que a 16 píxeis na barra de tarefas dava
quatro píxeis de desenho e não se percebia nada.

---

## Como usar — 3 passos

### 1. Escolher a pasta e analisar

Carrega em **Procurar...** e escolhe a pasta onde puseste as músicas que
queres tratar. A app lê logo os ficheiros.

> **Importante:** a app olha **só** para os ficheiros que estão diretamente
> nessa pasta. Não entra em subpastas. É de propósito: assim controlas
> exatamente que músicas é que ela pode alterar. Vais lá pondo as músicas que
> queres tratar e é só essas que ela toca.

### 2. Identificar na Internet (opcional)

Carrega em **2. Identificar na Internet**. A app procura cada música e sugere
o título, artista, álbum, ano e género corretos.

#### As quatro fontes

Não há nada a escolher: a procura corre **sempre nas quatro fontes**, todas as
que tenham as chaves postas. Se faltarem chaves a alguma, a barra diz quais, e
a procura corre nas restantes.

| Fonte | Precisa de quê | Forte em |
|---|---|---|
| **Beatport\*** | nada | eletrónica em geral: editora, BPM, tonalidade, género exato |
| **Spotify** | duas chaves gratuitas (ver abaixo) | catálogo enorme, capas em alta qualidade |
| **Discogs** | um token gratuito (ver abaixo) | edições físicas: editora, n.º de catálogo, país, ano da edição |
| **MusicBrainz** | nada | música em geral, sobretudo mais antiga e de nicho |

\* via não oficial — ver o aviso mais abaixo.

> O **Traxsource** era a quinta fonte e foi retirado: o site passou a estar
> atrás de um teste da Cloudflare, que responde a qualquer pedido da app com
> um erro. Não há API oficial, e contornar esse teste não é caminho.

As respostas das quatro fontes são pontuadas da mesma maneira, por isso são
comparáveis entre si. Do que vem, fica a hipótese com **mais confiança** — é
essa que aparece na coluna das sugestões, com o nome da fonte por cima
(*SUGERIDO POR ...*).

Quando escolhes uma sugestão do Beatport, o cabeçalho mostra os extras que só
essa fonte tem, por exemplo *"SUGERIDO POR BEATPORT (R&S Records · 124 BPM ·
Gb Minor)"*.

#### Ligar o Spotify e o Discogs

Carrega em **Configurar chaves**. Podes preencher só uma das duas.

**Discogs** — vai a `discogs.com/settings/developers`, carrega em *Generate
new token*, e cola o token.

**Spotify** — são precisas duas chaves gratuitas que só tu podes criar:

1. Vai a **developer.spotify.com/dashboard** e entra com a tua conta Spotify normal.
2. Carrega em **Create app**. Põe qualquer nome e descrição.
3. Em *Redirect URI* escreve `http://localhost` (não é usado, mas o formulário exige).
4. Marca **Web API** e cria.
5. Em *Settings*, copia o **Client ID** e o **Client Secret** para a janela da app.

A app testa as chaves na hora e só as guarda se funcionarem. Ficam apenas
neste computador, em `%APPDATA%\TaGo\credenciais.json`. **Não dão acesso às
tuas contas** — servem só para pesquisar os catálogos públicos.

#### Sobre o Beatport — lê isto

O Beatport **não tem API pública**. A app obtém os dados pela mesma via que o
próprio site usa: lê a página pública e usa a mesma sessão que o site usa.

Duas consequências que deves conhecer:

- **Pode deixar de funcionar sem aviso**, sempre que mudarem o site. Foi o que
  aconteceu ao Traxsource, que era a quinta fonte e teve de sair. Quando isso
  acontece, a app continua a trabalhar com as outras fontes; a que falhou
  limita-se a não devolver resultados. Por isso aparece marcada com um
  asterisco.
- É uma utilização pessoal e de baixo volume: há uma pausa de 1 segundo entre
  pedidos, para não sobrecarregar o serviço.

Se uma fonte falhar três vezes seguidas, a app desliga-a só para essa procura,
avisa-te, e continua com as restantes. Nunca interrompe o trabalho todo por
causa de uma fonte.

Ao clicar numa música, o painel de baixo mostra duas colunas: à esquerda, as
caixas com o que está neste momento no ficheiro — e onde podes escrever
directamente; à direita, por baixo de **SUGERIDO PELA INTERNET**, o que a
Internet sugere.

Cada campo tem os seus botões, por esta ordem:

- Botão **`usar`** — copia essa sugestão para o campo da esquerda.
- Botão **`blank`** — esvazia o campo. Atenção: um campo que fique vazio
  **apaga a tag do ficheiro** quando gravares. Serve para limpar lixo, como
  comentários de sites de download.
- Botão **`undo`** — desfaz a última mudança nesse campo, seja ela feita pelo
  `usar`, pelo `blank`, ou escrita por ti à mão. Só acende quando há mesmo
  algo para desfazer, e é **por música**.

O **artista** e o **título** não têm `blank`. São os dois campos que nunca
interessa deixar vazios — e é deles que sai o nome do ficheiro — por isso não
há como os apagar por engano. Se precisares mesmo, apaga o texto à mão.
Por cima desses botões, e a ocupar a mesma largura que os três, está o par que
trata de todos os campos de uma vez:

- Botão **`usar tudo`** — o mesmo que carregar em todos os `usar`.
- Botão **`undo`** — desfaz tudo o que houver por desfazer nessa música, seja
  do `usar tudo`, dos botões de cada campo, ou do que escreveste à mão. Tal
  como os outros, só acende quando há mesmo algo para desfazer.
- Podes sempre corrigir à mão: escreve diretamente nas caixas da esquerda.
- A caixa **Hipóteses encontradas** tem outras versões (por exemplo, o mesmo
  tema noutro álbum). A percentagem é a confiança; um **`?`** significa que a
  app não está segura — confirma antes de aceitar.

#### As capas

Por baixo das hipóteses aparecem quatro caixas, em duas alturas:

| Onde | O que é |
|---|---|
| em cima, sozinha e **maior** (`atual`) | a capa que o ficheiro já tem — ou "sem capa" |
| logo por baixo, três mais pequenas | as capas das **três melhores hipóteses**, com a fonte por baixo |

A de cima é maior de propósito: é a que está em jogo, e é com ela que se
comparam as outras.

**Clica numa para a escolher.** A escolhida fica com um contorno verde. Uma
caixa que diga *"sem capa"* é uma hipótese sem imagem disponível; *"a
obter..."* é uma que ainda está a ser descarregada.

**Passa o cursor por cima** de qualquer capa para a ver **cinco vezes maior**
do que a caixa onde está, sem clicar. Podes clicar na imagem ampliada para a escolher.

Para voltar atrás, clica na caixa `atual` — a capa do ficheiro fica como
estava. Ou usa **Escolher imagem do PC** para pôr uma imagem tua.

#### Botão "Remover capa"

Ao lado, o **Remover capa** deixa a música **sem capa nenhuma**. A caixa de
cima passa a dizer `a remover`, fica com contorno vermelho, e o painel avisa.

- **Não mexe no ficheiro nesse momento** — como tudo o resto, a capa só
  desaparece mesmo no **Gravar Metadata**.
- Para desistir, clica na caixa de cima (`atual`) e a capa fica como estava.
- A música conta como "por gravar" enquanto estiver marcada.
- Depois de gravares, a capa antiga desaparece de vez: a app não guarda cópia
  do ficheiro original.

Durante a identificação, a app já escolhe automaticamente a capa da melhor
hipótese, mas **só para músicas que ainda não têm capa** — nunca substitui
sozinha uma que já lá esteja.

Nada é gravado nesta fase. É tudo só proposta.

### Mudar o nome do ficheiro

No topo do painel de detalhe, o campo **Ficheiro** é editável: escreve ali o
nome que queres. Tal como as tags, **só muda no disco quando carregares em
Gravar Metadata**.

#### Botão "Alterar nome do ficheiro"

Ao lado do campo há o botão **Alterar nome do ficheiro**. Carrega nele e o
nome passa a ser feito a partir das tags, na ordem **artista - título** — por
exemplo, `Dino Lenny - Did This.flac`.

A ideia é usá-lo **depois de aceitares as sugestões**: primeiro corriges o
Artista e o Título (com o `usar`, ou à mão), depois carregas no botão e o nome
do ficheiro fica a condizer.

- Usa o que está **nas caixas nesse momento**, não o que está no ficheiro.
- A extensão é mantida.
- Caracteres que o Windows não aceita (`\ / : * ? " < > |`) são trocados por
  um espaço, para não colar palavras: `AC/DC` fica `AC DC`.
- Se só houver um dos dois preenchidos, usa só esse. Se estiverem os dois
  vazios, avisa e não mexe.
- Como qualquer outra alteração, **só vai para o disco no Gravar Metadata**.

#### Botão "Undo"

Mesmo ao lado, o **Undo** desfaz o botão anterior: repõe no campo o nome que
lá estava antes de carregares em *Alterar nome do ficheiro*.

Só fica ativo quando há mesmo alguma coisa para desfazer, e é **por música** —
mudas de faixa e ele acompanha essa faixa. Depois de desfazeres, a música
deixa de estar na lista das que vão ser renomeadas.

- A extensão trata-se sozinha: se a apagares, é reposta (mudar `.mp3` para
  `.flac` não converteria nada, só estragaria o ficheiro).
- Nomes com `\ / : * ? " < > |` são recusados — o Windows não os permite.
- Se já existir um ficheiro com esse nome na pasta, a app avisa e não mexe.

### Campos dispensados

O **número de faixa**, o **número de disco** e o **artista do álbum** não
aparecem na app e são **sempre removidos** dos ficheiros quando gravas —
mesmo que não mexas em mais nada.

A limpeza é automática, por isso **não marca a linha** — se marcasse, marcava
a lista quase toda e não te dizia nada. A marca fica reservada ao que *tu*
alteraste e ainda não gravaste. O que está por limpar conta na conta de "por
gravar", no canto inferior direito.

Não há como voltar atrás depois de gravar: a app não guarda cópia do
ficheiro original (ver *Rede de segurança*).

### Ouvir uma música

Na lista, cada música tem à esquerda um **botão amarelo com um triângulo**.
Clica nele para ouvir a música, sem sair da app.

- Enquanto toca, o botão dessa linha passa a **quadrado** — clica outra vez
  para parar.
- À direita do botão há a **forma de onda** da música. Clica em qualquer
  ponto dela para saltares para aí — serve para ires direto ao refrão, ou
  confirmares depressa se a música é mesmo a que pensavas. Se a música ainda
  não estiver a tocar, começa logo nesse ponto.
- A parte já ouvida fica **amarela**, e uma linha clara marca onde vai.
- Toca **uma de cada vez**: clicar noutra música cala a anterior.
- Quando a música chega ao fim, o botão volta sozinho ao triângulo.
- Ao carregares em **Gravar Metadata**, a música é parada automaticamente. Tem de ser: enquanto toca, o ficheiro está aberto e o
  Windows não deixa alterá-lo nem mudar-lhe o nome.

Quem toca a música é o **VLC**, que já está instalado neste computador — dá
conta de todos os formatos (MP3, FLAC, M4A, OGG, WMA, WAV). Se um dia
desinstalares o VLC, a app tenta o leitor do próprio Windows (que só sabe MP3
e WAV) e, em último caso, abre a música no teu leitor habitual. Nunca fica
sem fazer nada.

### 3. Gravar

- Marca na primeira coluna da tabela (☑) as músicas que queres gravar.
- Carrega em **Gravar Metadata**.
- Confirma a pergunta.

A lista é deliberadamente limpa: **a única linha com fundo pintado é a que
está selecionada**. As músicas com alterações por gravar mostram-se apenas
pela **cor das letras** (amarelo), e as que têm erro em vermelho — sem barras
por cima, para a lista se ler bem mesmo com muitas músicas.

Na linha que está selecionada não se põe cor nas letras, porque o fundo da
seleção já é amarelo e letras amarelas por cima dele desapareciam. Basta
clicar noutra música para voltar a ver a marca.

A conta do que falta gravar está sempre no canto inferior direito.

---

## Rede de segurança

Como esta app altera mesmo os teus ficheiros, há duas proteções:

1. **Nada se perde a meio.** As tags são escritas numa cópia temporária e só
   no fim é que essa cópia toma o lugar do original. Se faltar a luz a meio,
   o teu ficheiro fica intacto.
2. **Registo de tudo.** O ficheiro `_backup_tags\historico.log` guarda o que
   foi alterado, quando, e qual era o valor anterior.

O que **não** há é cópia de segurança: a app não guarda cópias dos teus
ficheiros de áudio, e o que gravas nas tags é definitivo. Se quiseres uma
rede, faz tu uma cópia da pasta antes de gravar.

Se um ficheiro estiver a ser usado por outro programa (por exemplo, a tocar
no leitor de música), a app avisa e salta esse ficheiro em vez de falhar.

---

## Outros botões

| Botão | O que faz |
|---|---|
| **Duplicados** | Encontra a mesma música repetida (compara artista + título + duração, não o nome do ficheiro). |

---

## Campos

Artista, título, álbum, ano, género, **BPM**, **Key**, comentário, capa de
álbum, e o nome do ficheiro.

Só de leitura: duração, bitrate, formato, tamanho. A lista mostra-os nas
colunas *Duracao*, *Fmt*, *Bitrate* e *Size* — as duas últimas ordenam pelo
número, não pelo texto, por isso `9 MB` fica mesmo antes de `45 MB`.
Sempre apagados ao gravar: número de faixa, número de disco e **artista do
álbum**.

### Coluna *Quality*

Logo a seguir a *Size* há uma coluna que diz, para cada música:

- **`GOOD TO PLAY`** — 320 kbps ou mais.
- **`BAD TO PLAY`** — abaixo de 320 kbps.

Carregar no cabeçalho *Quality* ordena pelo bitrate, e não pelas palavras:
assim as `BAD TO PLAY` ficam todas juntas, das piores para as melhores.

O mesmo aparece na linha de detalhes da música escolhida, a seguir ao
bitrate, e aí o valor fica **a vermelho** quando está abaixo do mínimo. No
resumo, em baixo, aparece quantas músicas da pasta estão abaixo do mínimo.

Ficheiros cujo bitrate não se consegue ler (fica a 0) ficam com a coluna
**vazia**: não se sabe nada deles, e chamar-lhes maus seria um aviso falso.
O limite está numa só linha no `app.py` (`MINIMO_KBPS = 320`).

### O campo Ano

Mostra **só o ano**, sempre. Muitos ficheiros trazem ali a data completa
(`2011-05-03`, ou até `2011-05-03T00:00:00`); a app extrai o ano tanto ao ler
como ao gravar, por isso o ficheiro também fica só com `2011`.

### Sobre o BPM e a Key

Preenchem-se à mão ou vêm das sugestões. **Só o Beatport os fornece** — o
Spotify, o Discogs e a MusicBrainz não guardam esta informação, por isso
deixam os dois campos vazios.

São gravados nas tags que os leitores e os programas de DJ esperam:

| Formato | BPM | Key |
|---|---|---|
| MP3 | `TBPM` | `TKEY` |
| M4A | `tmpo` | `initialkey` (iTunes) |
| FLAC / OGG | `bpm` | `initialkey` |

O Explorador do Windows mostra-os nas colunas *Beats-per-minute* e
*Initial key*.

## Formatos suportados

MP3, FLAC, M4A/MP4, OGG, Opus, WMA, WAV e AIFF.

Testado a ler **e a gravar** em MP3, M4A e FLAC, incluindo acentos
portugueses, capas de álbum, BPM e Key.

---

## Notas técnicas

- Escrito em Python 3.12. Bibliotecas: `mutagen` (tags), `musicbrainzngs`,
  `requests` (Spotify e Beatport), `customtkinter` + `Pillow` (interface),
  `python-vlc` (ouvir as músicas).
- Nos MP3 as tags são gravadas em **ID3v2.3**, que é a versão que o
  Explorador do Windows e os leitores antigos leem melhor. Os acentos ficam
  corretos.
- **Onde a app guarda o que escreve:** em `%APPDATA%\TaGo` — as definições
  (`definicoes.json`), as chaves (`credenciais.json`) e as caches. Não é ao
  lado do código de propósito: instalada em `Program Files`, essa pasta é só
  de leitura e a app não conseguiria gravar nada. Quem já a usava antes não
  perde nada — os ficheiros antigos são copiados na primeira vez que abre, e
  os originais podem ser apagados depois disso.
- As formas de onda ficam em cache em `cache_ondas.json`. Cada música só é
  descodificada uma vez (menos de um segundo, feito em segundo plano pelo
  VLC). Se o ficheiro for alterado, a onda é recalculada sozinha.
- As respostas das fontes ficam em cache em `cache_procuras.json`, para
  não repetir procuras. MusicBrainz e Beatport limitam a 1 pedido por segundo
  — por isso identificar muitas músicas demora um pouco.
- A confiança **não** usa a pontuação interna de cada serviço (não são
  comparáveis entre si). É calculada aqui, comparando título, artista e
  duração do candidato com o que se sabe do ficheiro.
- **Identificação pelo som (AcoustID)** — está preparada no código mas
  desligada, porque precisa de duas coisas que ainda não estão instaladas: o
  programa `fpcalc.exe` (Chromaprint) e uma chave de API gratuita do AcoustID
  colocada num ficheiro `chave_acoustid.txt` em `%APPDATA%\TaGo`. Sem isso, a
  identificação faz-se por texto (tags e nome do ficheiro), que é o que está
  a ser usado.

---

## Licença

O TaGo é software livre, sob a **GNU General Public License v3 ou posterior**.
Copyright © 2026 Nuno Rozz.

Não foi uma escolha de estilo: o `mutagen`, que é a biblioteca que lê e grava
as tags, é GPL-2.0-**or-later**, e isso obriga qualquer programa distribuído
que o inclua a sair sob uma licença compatível. O *or later* é o que permite
usar a versão 3.

O que isto significa na prática:

- Quem receber a app pode usá-la, estudá-la, alterá-la e voltar a
  distribuí-la.
- **Quem receber o programa tem direito ao código-fonte** daquela versão. Se
  um dia distribuíres um instalador, tens de o entregar — num repositório
  público, ou dentro do próprio instalador.
- A app vem **sem garantia nenhuma**, o que também te protege a ti.
- O texto integral está no ficheiro `LICENSE`, e as licenças das bibliotecas
  em `THIRD-PARTY.md`.

O aviso aparece na app, no botão **About** do rodapé — é o que a GPL pede a
programas com interface.

### Ficheiros

| Ficheiro | Para que serve |
|---|---|
| `LICENSE` | O texto integral da GPL v3 |
| `THIRD-PARTY.md` | As licenças das bibliotecas usadas |
| `app.py` | A interface gráfica |
| `dados.py` | Onde ficam as definições, as chaves e as caches |
| `criar_logo.py` | Desenha o logo e grava o PNG e o ICO (corre-se à mão) |
| `recursos/` | O logo (`logo.png`, `logo_barra.png`, `tago.ico`) e o SVG original |
| `identidade.py` | Como a app se identifica perante os serviços |
| `metadata.py` | Ler tags e traduzir entre formatos |
| `escritor.py` | Gravar tags e renomear ficheiros |
| `scanner.py` | Percorrer a pasta |
| `identificador.py` | Juntar e pontuar os resultados das fontes |
| `fonte_spotify.py` | Pesquisa no Spotify (API oficial) |
| `fonte_discogs.py` | Pesquisa no Discogs (API oficial) |
| `fonte_beatport.py` | Pesquisa no Beatport (via não oficial) |
| `fonte_musicbrainz.py` | Pesquisa na MusicBrainz |
| `relatorios.py` | Tags em falta, duplicados, estatísticas |
| `exportar.py` | Exportação para CSV |
| `armazenamento.py` | Guardar a última pasta usada |
| `tema.py` | As cores e a letra (o aspeto estilo Ableton Live) |
| `leitor.py` | Tocar as músicas dentro da app (botão amarelo da lista) |
| `ondas.py` | Calcular a forma de onda de cada música |
