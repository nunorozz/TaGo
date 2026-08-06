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
"""Escrita de tags no proprio ficheiro de audio, com rede de seguranca.

Regras que este modulo garante:

1. Antes da primeira alteracao a um ficheiro, guarda-se uma copia integral do
   original em _backup_tags\\. Essa copia nunca e substituida, para que
   "Reverter" reponha sempre o estado original.
2. A escrita e atomica: as tags sao aplicadas a uma copia temporaria e so no
   fim essa copia toma o lugar do original (os.replace). Se falhar a meio, o
   ficheiro do utilizador fica intacto.
3. Tudo o que e alterado fica registado em historico.log.

Nota de implementacao: os campos de texto sao escritos pela interface "easy"
do mutagen, que ja normaliza os formatos entre si. Comentario e capa nao sao
cobertos por essa interface, por isso sao escritos num segundo passo, abrindo
o ficheiro no modo normal.
"""
from __future__ import annotations

import base64
import os
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
    return Path(caminho_musica).parent / PASTA_BACKUP


def caminho_backup(caminho_musica) -> Path:
    p = Path(caminho_musica)
    return pasta_backup(p) / p.name


def tem_backup(caminho_musica) -> bool:
    return caminho_backup(caminho_musica).exists()


def criar_backup(caminho_musica) -> Path:
    """Guarda o original. Se ja existir copia, mantem a antiga (a verdadeira)."""
    destino = caminho_backup(caminho_musica)
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(caminho_musica, destino)
    return destino


def ficheiro_bloqueado(caminho) -> bool:
    """Deteta ficheiros abertos por outro programa (ex.: a tocar no leitor)."""
    try:
        with open(caminho, "r+b"):
            return False
    except OSError:
        return True


def reverter(caminho_musica) -> bool:
    """Repoe o ficheiro original a partir da copia de seguranca."""
    origem = caminho_backup(caminho_musica)
    if not origem.exists():
        return False
    if ficheiro_bloqueado(caminho_musica):
        raise ErroEscrita("the file is in use by another program")
    shutil.copy2(origem, caminho_musica)
    _registar(caminho_musica, "REVERTIDO", "", "")
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
    """Muda o nome do ficheiro no disco, levando a copia de seguranca atras."""
    atual = Path(caminho_musica)
    novo_nome = validar_nome(novo_nome, atual)
    destino = atual.with_name(novo_nome)

    if destino == atual:
        return atual
    if destino.exists():
        raise ErroEscrita(f"a file called '{novo_nome}' already exists in this folder")
    if ficheiro_bloqueado(atual):
        raise ErroEscrita("the file is in use by another program")

    # A copia de seguranca e guardada com o nome do ficheiro: se o nome muda,
    # ela tem de mudar tambem, senao o Reverter deixa de a encontrar.
    backup_antigo = caminho_backup(atual)
    try:
        atual.rename(destino)
    except OSError as e:
        raise ErroEscrita(f"could not rename: {e}") from e

    if backup_antigo.exists():
        try:
            backup_antigo.rename(caminho_backup(destino))
        except OSError:
            pass          # o ficheiro ja foi renomeado; nao se desfaz por isto

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

    criar_backup(caminho)

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
