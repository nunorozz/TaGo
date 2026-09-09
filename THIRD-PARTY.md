# Bibliotecas de terceiros

O TaGo é distribuído sob a **GPL-3.0-or-later** (ver `LICENSE`). Usa as
bibliotecas abaixo, cada uma com a sua licença. As versões são as que estavam
instaladas quando esta lista foi feita — as licenças foram lidas dos próprios
pacotes, não copiadas de memória.

| Biblioteca | Versão | Licença | Para que serve aqui |
|---|---|---|---|
| [mutagen](https://mutagen.readthedocs.io) | 1.48.1 | **GPL-2.0-or-later** | Ler e gravar as tags |
| [musicbrainzngs](https://python-musicbrainzngs.readthedocs.io/) | 0.7.1 | BSD 2-Clause | Pesquisa na MusicBrainz |
| [requests](https://requests.readthedocs.io) | 2.34.2 | Apache-2.0 | Pedidos ao Spotify, Discogs e Beatport |
| [customtkinter](https://customtkinter.tomschimansky.com) | 6.0.0 | MIT | A interface |
| [Pillow](https://pillow.readthedocs.io) | 12.3.0 | MIT-CMU | Capas, formas de onda e o logo |
| [darkdetect](http://github.com/albertosottile/darkdetect) | 0.8.0 | BSD 3-Clause | Usada pelo customtkinter |
| [python-vlc](https://wiki.videolan.org/PythonBinding) | 3.0.21203 | LGPL-2.1-or-later | Tocar as músicas e calcular as ondas |

## Onde está o código-fonte

O código do próprio TaGo vai **dentro do instalador**, na pasta
`codigo-fonte\`, ao lado do programa. É o que a GPL exige de quem distribui:
quem recebeu o programa tem direito ao código daquela versão.

O código das bibliotecas acima não é redistribuído aqui — obtém-se de cada
projeto, nas versões indicadas na tabela. O `mutagen`, por ser GPL, é o que
mais importa: <https://github.com/quodlibet/mutagen>.

## O mutagen é a razão de isto ser GPL

O `mutagen` é **GPL-2.0-or-later**. Um programa que o inclua e seja
distribuído tem de sair sob uma licença compatível com a GPL — daí o TaGo ser
GPL-3.0-or-later (o *or later* do mutagen é o que permite subir para a 3).

Não há alternativa realista: é a biblioteca que lê e escreve tags em MP3,
FLAC, M4A, OGG e WMA de forma consistente.

## O VLC

O `python-vlc` são apenas as ligações Python (LGPL-2.1+); quem faz o trabalho
é o **VLC**, que tem de estar instalado no computador. O TaGo **não** o
distribui — procura o que já lá estiver.

Se um dia o VLC for embebido no instalador, passam a aplicar-se as obrigações
da LGPL do próprio VLC, que são outras e mais exigentes do que estas.

## Windows

A letra *Bahnschrift* e o leitor MCI (usado quando não há VLC) vêm com o
Windows e não são distribuídos com a app.
