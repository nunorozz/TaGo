# TaGo - Music Tag Editor
# Copyright (C) 2026 Nuno Rozz
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.
"""Escrita de tags no proprio ficheiro de audio.

Regras que este modulo garante:

1. A escrita e atomica: as tags sao aplicadas a uma copia temporaria e so no
   fim essa copia toma o lugar do original (os.replace). Se falhar a meio, o
   ficheiro do utilizador fica intacto.
2. Tudo o que e alterado fica registado em historico.log.

O que este modulo ja nao faz: guardar copias dos ficheiros de audio. O que se
escreve nas tags e definitivo. Em _backup_tags\\ fica apenas o historico.log,
a dizer o que foi mudado.

Nota de implementacao: os campos de texto sao escritos pela interface "easy"
do mutagen, que ja normaliza os formatos entre si. Comentario e capa nao sao
cobertos por essa interface, por isso sao escritos num segundo passo, abrindo
o ficheiro no modo normal.
"""
from __future__ import annotations

import base64
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

import mutagen
from mutagen.asf import ASF, ASFByteArrayAttribute
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, COMM, ID3, Frames
from mutagen.mp4 import MP4, MP4Cover

from metadata import (CAMPOS_LIDOS, CAMPOS_REMOVIDOS, CHAVES_EASY,
                      FRAMES_ID3, ler, normalizar_ano)

PASTA_BACKUP = "_backup_tags"
FICHEIRO_HISTORICO = "historico.log"

# ID3v2.3 e lido por praticamente tudo, incluindo o Explorador do Windows e
# leitores antigos. Os acentos ficam corretos (o mutagen usa UTF-16 aqui).
ID3_VERSAO = 3


class ErroEscrita(Exception):
    pass


# --------------------------------------------------------------- seguranca

def pasta_backup(caminho_musica) -> Path:
    """Pasta onde fica o historico.log desta pasta de musicas."""
    return Path(caminho_musica).parent / PASTA_BACKUP


def ficheiro_bloqueado(caminho) -> bool:
    """Deteta ficheiros abertos por outro programa (ex.: a tocar no leitor)."""
    try:
        with open(caminho, "r+b"):
            return False
    except OSError:
        return True



CARACTERES_PROIBIDOS = '\\/:*?"<>|'


def limpar_para_nome(texto: str) -> str:
    """Tira de um valor de tag o que o Windows nao aceita num nome de ficheiro.

    Os caracteres proibidos sao substituidos por um espaco (e nao apagados),
    para "AC/DC" nao ficar "ACDC". Depois junta-se os espacos a mais.
    """
    limpo = "".join(" " if c in CARACTERES_PROIBIDOS else c for c in str(texto or ""))
    # Um ponto ou espaco no fim faz o Windows recusar o nome.
    return " ".join(limpo.split()).rstrip(". ")


def nome_a_partir_das_tags(artista: str, titulo: str, caminho_atual) -> str:
    """Monta o nome "artista - titulo" com a extensao do ficheiro atual."""
    artista = limpar_para_nome(artista)
    titulo = limpar_para_nome(titulo)
    if not artista and not titulo:
        raise ErroEscrita(
            "fill in Artist and Title first - the name is built "
            "from those two fields")
    base = f"{artista} - {titulo}" if artista and titulo else (artista or titulo)
    return validar_nome(base, caminho_atual)


MISTURA_ORIGINAL = "Original Mix"

# As palavras por que se conhece uma mistura no fim de um titulo. Servem para
# distinguir o que e mistura do que nao e: "Afrilounge Remix" e, "feat. Ana"
# nao e - e um titulo acabado em "(feat. Ana)" continua a precisar que se lhe
# diga a mistura.
PALAVRAS_MISTURA = frozenset((
    "mix", "mixes", "remix", "remixes", "edit", "dub", "version", "instrumental",
    "acapella", "capella", "vip", "rework", "reedit", "bootleg", "remaster",
    "remastered", "extended", "radio", "club", "live", "original",
))

# A mistura entre parenteses (ou parenteses rectos) no fim: e assim que o
# Beatport a manda.
_FIM_ENTRE_PARENTESES = re.compile(r"[\(\[]([^()\[\]]+)[\)\]]\s*$")
# A mistura a seguir a um travessao: e assim que o Spotify a manda
# ("Titulo - Radio Edit"). As outras fontes mandam o titulo cru.
_FIM_APOS_TRAVESSAO = re.compile(r"\s[-–—]\s*([^-–—]+)$")


def _e_mistura(texto: str) -> bool:
    """Diz se este pedaco de titulo nomeia uma mistura, e nao outra coisa."""
    palavras = re.findall(r"[a-z]+", (texto or "").lower())
    return any(p in PALAVRAS_MISTURA for p in palavras)


def titulo_com_mistura(titulo: str) -> str:
    """Devolve o titulo a acabar sempre na mistura, entre parenteses.

    Serve para o nome do ficheiro e para a propria tag Title, que no modo
    automatico vao dizer a mesma coisa. E idempotente: um titulo que ja passou
    por aqui volta a sair igual.
    """
    titulo = (titulo or "").strip()
    if not titulo:
        return ""

    # 1. Ja vem no formato certo: fica como esta.
    fim = _FIM_ENTRE_PARENTESES.search(titulo)
    if fim and _e_mistura(fim.group(1)):
        return titulo

    # 2. Vem depois de um travessao: passa-se para parenteses, para os nomes
    #    sairem todos no mesmo formato. Um parentese final que nao seja
    #    mistura ("(feat. Ana)") fica de fora da procura, mas mantem-se.
    cabeca = titulo[:fim.start()].rstrip() if fim else titulo
    cauda = titulo[fim.start():].strip() if fim else ""
    travessao = _FIM_APOS_TRAVESSAO.search(cabeca)
    if travessao and _e_mistura(travessao.group(1)):
        mistura = travessao.group(1).strip()
        cabeca = cabeca[:travessao.start()].rstrip()
        return " ".join(x for x in (cabeca, cauda, f"({mistura})") if x)

    # 3. Nao traz mistura nenhuma: e a versao original.
    return f"{titulo} ({MISTURA_ORIGINAL})"


def nome_com_mistura(artista: str, titulo: str, caminho_atual) -> str:
    """Monta o nome "Artista - Titulo (Mistura)" com a extensao do ficheiro.

    E o formato do modo automatico: o nome leva sempre a mistura no fim. Se o
    titulo ja a traz - entre parenteses como no Beatport, ou depois de um
    travessao como no Spotify - e essa que vai para o nome; se nao traz
    nenhuma, e a versao original e junta-se "(Original Mix)".
    """
    artista = limpar_para_nome(artista)
    titulo = limpar_para_nome(titulo)
    if not artista or not titulo:
        raise ErroEscrita(
            "fill in Artist and Title first - the name is built "
            "from those two fields")
    return validar_nome(f"{artista} - {titulo_com_mistura(titulo)}",
                        caminho_atual)


def validar_nome(novo_nome: str, caminho_atual) -> str:
    """Devolve o nome final a usar, ou levanta ErroEscrita a explicar porque nao."""
    novo_nome = (novo_nome or "").strip()
    if not novo_nome:
        raise ErroEscrita("the file name cannot be empty")

    maus = sorted({c for c in novo_nome if c in CARACTERES_PROIBIDOS})
    if maus:
        raise ErroEscrita(
            f"the name cannot contain {' '.join(maus)} "
            "(Windows does not allow these characters)")

    atual = Path(caminho_atual)
    # A extensao manda-se sozinha: mudar .mp3 para .flac nao converte nada.
    if not novo_nome.lower().endswith(atual.suffix.lower()):
        novo_nome += atual.suffix

    if len(str(atual.with_name(novo_nome))) > 255:
        raise ErroEscrita("the name would be too long")
    return novo_nome


def renomear(caminho_musica, novo_nome: str) -> Path:
    """Muda o nome do ficheiro no disco."""
    atual = Path(caminho_musica)
    novo_nome = validar_nome(novo_nome, atual)
    destino = atual.with_name(novo_nome)

    if destino == atual:
        return atual
    if destino.exists():
        raise ErroEscrita(f"a file called '{novo_nome}' already exists in this folder")
    if ficheiro_bloqueado(atual):
        raise ErroEscrita("the file is in use by another program")

    try:
        atual.rename(destino)
    except OSError as e:
        raise ErroEscrita(f"could not rename: {e}") from e

    _registar(destino, "nome do ficheiro", atual.name, destino.name)
    return destino


def _registar(caminho_musica, campo, antes, depois) -> None:
    log = pasta_backup(caminho_musica) / FICHEIRO_HISTORICO
    log.parent.mkdir(parents=True, exist_ok=True)
    linha = "\t".join([
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        Path(caminho_musica).name,
        campo,
        str(antes).replace("\t", " "),
        str(depois).replace("\t", " "),
    ])
    with open(log, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def ler_historico(pasta) -> list[str]:
    log = Path(pasta) / PASTA_BACKUP / FICHEIRO_HISTORICO
    if not log.exists():
        return []
    return log.read_text(encoding="utf-8", errors="replace").splitlines()


# ----------------------------------------------------------------- escrita

def gravar(caminho_musica, valores: dict, capa_nova: bytes | None = None,
           remover_capa: bool = False) -> list[tuple[str, str, str]]:
    """Grava as tags no ficheiro. Devolve a lista de alteracoes feitas.

    'valores' so precisa de conter os campos a alterar. Um campo com string
    vazia apaga a tag correspondente.
    """
    caminho = Path(caminho_musica)
    if not caminho.exists():
        raise ErroEscrita("the file no longer exists")
    if ficheiro_bloqueado(caminho):
        raise ErroEscrita("the file is in use by another program")

    valores = dict(valores)
    # Os campos dispensados sao sempre limpos, venha o que vier.
    for campo in CAMPOS_REMOVIDOS:
        valores[campo] = ""
    # No ano fica so o ano, mesmo que venha uma data completa.
    if "ano" in valores:
        valores["ano"] = normalizar_ano(valores["ano"])

    antes = ler(caminho)
    alteracoes = [
        (campo, antes.get(campo, ""), str(valores[campo]).strip())
        for campo in CAMPOS_LIDOS
        if campo in valores and str(valores[campo]).strip() != antes.get(campo, "")
    ]
    if not alteracoes and capa_nova is None and not remover_capa:
        return []

    temporario = caminho.with_name(caminho.name + ".tags-tmp")
    try:
        shutil.copy2(caminho, temporario)
        _escrever_texto(temporario, valores)
        if "comentario" in valores:
            _escrever_comentario(temporario, str(valores["comentario"]).strip())
        if capa_nova is not None or remover_capa:
            _escrever_capa(temporario, capa_nova, remover_capa)
        os.replace(temporario, caminho)
    except Exception as e:
        if temporario.exists():
            try:
                temporario.unlink()
            except OSError:
                pass
        # O ficheiro original nao foi tocado: as tags iam para a copia
        # temporaria, e a substituicao nunca chegou a acontecer.
        if isinstance(e, PermissionError):
            raise ErroEscrita(
                "the file is in use by another program (close your music player "
                "and try again). Nothing was changed.") from e
        raise ErroEscrita(f"{e}. Nothing was changed.") from e

    for campo, valor_antes, valor_depois in alteracoes:
        _registar(caminho, campo, valor_antes, valor_depois)
    if capa_nova is not None:
        _registar(caminho, "capa", "", "nova imagem")
    elif remover_capa:
        _registar(caminho, "capa", "existente", "removida")

    return alteracoes


def _abrir_para_escrita(caminho: Path, easy: bool):
    try:
        audio = mutagen.File(str(caminho), easy=easy)
    except Exception as e:
        raise ErroEscrita(f"could not open the file: {e}") from e
    if audio is None:
        raise ErroEscrita("format not supported for writing")
    if audio.tags is None:
        try:
            audio.add_tags()
        except Exception:
            pass
    return audio


def _guardar(audio) -> None:
    """Grava, escolhendo a versao de ID3 mais compativel quando aplicavel."""
    try:
        audio.save(v2_version=ID3_VERSAO)
    except TypeError:
        audio.save()


def _escrever_texto(caminho: Path, valores: dict) -> None:
    audio = _abrir_para_escrita(caminho, easy=True)
    tags = audio.tags
    # WAV e AIFF nao tem interface "easy": ficam com o ID3 cru.
    id3_cru = isinstance(tags, ID3)

    escreveu = False
    for campo, valor in valores.items():
        if campo not in CHAVES_EASY:   # 'comentario' e tratado a parte
            continue
        valor = str(valor).strip()
        escreveu = True

        if id3_cru:
            frame = FRAMES_ID3[campo]
            tags.delall(frame)
            if valor:
                tags.add(Frames[frame](encoding=3, text=[valor]))
        else:
            chave = CHAVES_EASY[campo]
            if valor:
                audio[chave] = [valor]
            elif chave in audio:
                del audio[chave]

    if escreveu:
        _guardar(audio)


def _escrever_comentario(caminho: Path, valor: str) -> None:
    audio = _abrir_para_escrita(caminho, easy=False)
    tags = audio.tags

    if isinstance(audio, MP4):
        if valor:
            tags["\xa9cmt"] = [valor]
        elif "\xa9cmt" in tags:
            del tags["\xa9cmt"]

    elif isinstance(audio, ASF):
        if valor:
            tags["WM/Comments"] = [valor]
        elif "WM/Comments" in tags:
            del tags["WM/Comments"]

    elif isinstance(tags, ID3):
        tags.delall("COMM")
        if valor:
            tags.add(COMM(encoding=3, lang="por", desc="", text=[valor]))

    elif tags is not None:
        # Vorbis comments (FLAC, Ogg, Opus).
        if valor:
            tags["comment"] = [valor]
        elif "comment" in tags:
            del tags["comment"]

    _guardar(audio)


def _mime_da_imagem(dados: bytes) -> str:
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return "image/jpeg"


def _escrever_capa(caminho: Path, dados: bytes | None, remover: bool) -> None:
    audio = _abrir_para_escrita(caminho, easy=False)
    tags = audio.tags
    mime = _mime_da_imagem(dados) if dados else "image/jpeg"

    if isinstance(audio, FLAC):
        audio.clear_pictures()
        if dados:
            pic = Picture()
            pic.type = 3          # capa frontal
            pic.mime = mime
            pic.data = dados
            audio.add_picture(pic)

    elif isinstance(audio, MP4):
        if dados:
            formato = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
            tags["covr"] = [MP4Cover(dados, imageformat=formato)]
        elif "covr" in tags:
            del tags["covr"]

    elif isinstance(audio, ASF):
        if dados:
            bloco = (b"\x03" + len(dados).to_bytes(4, "little")
                     + mime.encode("utf-16-le") + b"\x00\x00"
                     + b"\x00\x00" + dados)
            tags["WM/Picture"] = [ASFByteArrayAttribute(bloco)]
        elif "WM/Picture" in tags:
            del tags["WM/Picture"]

    elif isinstance(tags, ID3):
        tags.delall("APIC")
        if dados:
            tags.add(APIC(encoding=3, mime=mime, type=3, desc="", data=dados))

    elif tags is not None:
        # Ogg / Opus: a imagem vai em base64 dentro de um Vorbis comment.
        if dados:
            pic = Picture()
            pic.type = 3
            pic.mime = mime
            pic.data = dados
            tags["metadata_block_picture"] = [
                base64.b64encode(pic.write()).decode("ascii")
            ]
        elif "metadata_block_picture" in tags:
            del tags["metadata_block_picture"]

    _guardar(audio)
