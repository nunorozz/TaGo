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
"""Leitura e normalizacao das tags de ficheiros de audio.

Cada formato guarda as tags a sua maneira (ID3 usa TPE1, Vorbis usa artist,
MP4 usa (c)ART). Este modulo traduz tudo para um dicionario unico com os
nomes de campo em portugues, usados pelo resto da aplicacao.
"""
from __future__ import annotations

import base64
import re
from datetime import datetime
from pathlib import Path

import mutagen
from mutagen.asf import ASF
from mutagen.easyid3 import EasyID3
from mutagen.easymp4 import EasyMP4Tags
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3
from mutagen.mp4 import MP4

# A tonalidade nao vem registada na interface "easy" do mutagen. Registamo-la
# aqui, uma vez, para poder ser lida e escrita como qualquer outro campo.
# (O BPM ja vem registado nos dois.)
try:
    EasyID3.RegisterTextKey("initialkey", "TKEY")
except Exception:
    pass
try:
    EasyMP4Tags.RegisterFreeformKey("initialkey", "initialkey")
except Exception:
    pass

# Extensoes que a app considera "musica".
EXTENSOES_AUDIO = {
    ".mp3", ".flac", ".m4a", ".mp4", ".ogg", ".oga",
    ".opus", ".wma", ".wav", ".aiff", ".aif",
}

# Campos que o utilizador pode editar e gravar.
CAMPOS_EDITAVEIS = [
    "artista", "titulo", "album",
    "ano", "genero", "bpm", "tom", "comentario",
]

# Campos que a app le (para se ver o que la esta) mas nunca guarda: sao
# sempre removidos do ficheiro quando se grava. Por decisao do utilizador,
# nem a numeracao de faixa e disco nem o artista do album tem lugar nesta
# biblioteca.
CAMPOS_REMOVIDOS = ["faixa", "disco", "artista_album"]

# Tudo o que e lido de um ficheiro.
CAMPOS_LIDOS = CAMPOS_EDITAVEIS + CAMPOS_REMOVIDOS

# Nomes bonitos para a interface. A app fala ingles com quem a usa; os nomes
# dos campos por dentro ficam como estao.
ETIQUETAS = {
    "titulo": "Title",
    "artista": "Artist",
    "artista_album": "Album artist",
    "album": "Album",
    "ano": "Year",
    "genero": "Genre",
    "faixa": "Track no.",
    "disco": "Disc no.",
    "bpm": "BPM",
    "tom": "Key",
    "comentario": "Comment",
}

# Traducao para a interface "easy" do mutagen, que ja normaliza MP3, FLAC,
# MP4, Ogg e WMA entre si.
CHAVES_EASY = {
    "titulo": "title",
    "artista": "artist",
    "artista_album": "albumartist",
    "album": "album",
    "ano": "date",
    "genero": "genre",
    "faixa": "tracknumber",
    "disco": "discnumber",
    "bpm": "bpm",
    "tom": "initialkey",
}

# Fallback para ficheiros com ID3 que o "easy" nao cobre (WAV, AIFF).
FRAMES_ID3 = {
    "titulo": "TIT2",
    "artista": "TPE1",
    "artista_album": "TPE2",
    "album": "TALB",
    "ano": "TDRC",
    "genero": "TCON",
    "faixa": "TRCK",
    "disco": "TPOS",
    "bpm": "TBPM",
    "tom": "TKEY",
}


# Muitos ficheiros trazem a data completa ("2011-05-03", "2011-05-03T00:00:00")
# no campo do ano. Guardamos so o ano.
_ANO = re.compile(r"(\d{4})")


def normalizar_ano(valor) -> str:
    achado = _ANO.search(str(valor or ""))
    return achado.group(1) if achado else ""


def e_audio(caminho) -> bool:
    return Path(caminho).suffix.lower() in EXTENSOES_AUDIO


def ficha_vazia(caminho) -> dict:
    """Dicionario com a estrutura completa de uma faixa, tudo por preencher."""
    p = Path(caminho)
    ficha = {campo: "" for campo in CAMPOS_LIDOS}
    ficha.update(
        caminho=str(p),
        ficheiro=p.name,
        formato=p.suffix.lower().lstrip("."),
        tamanho=0,
        modificado="",
        duracao=0.0,
        bitrate=0,
        sample_rate=0,
        canais=0,
        tem_capa=False,
        erro="",
    )
    return ficha


def ler(caminho) -> dict:
    """Le um ficheiro e devolve a ficha normalizada.

    Nunca levanta excecao: se o ficheiro estiver corrompido ou ilegivel, o
    campo 'erro' fica preenchido e a analise da pasta pode continuar.
    """
    p = Path(caminho)
    ficha = ficha_vazia(p)

    try:
        st = p.stat()
        ficha["tamanho"] = st.st_size
        ficha["modificado"] = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError as e:
        ficha["erro"] = f"nao foi possivel aceder ao ficheiro: {e}"
        return ficha

    try:
        audio = mutagen.File(str(p))
    except Exception as e:
        ficha["erro"] = f"ficheiro ilegivel: {e}"
        return ficha

    if audio is None:
        ficha["erro"] = "formato nao reconhecido"
        return ficha

    info = getattr(audio, "info", None)
    if info is not None:
        ficha["duracao"] = float(getattr(info, "length", 0) or 0)
        ficha["bitrate"] = int(getattr(info, "bitrate", 0) or 0)
        ficha["sample_rate"] = int(getattr(info, "sample_rate", 0) or 0)
        ficha["canais"] = int(getattr(info, "channels", 0) or 0)

    try:
        ficha.update(_ler_texto(str(p)))
        ficha["ano"] = normalizar_ano(ficha.get("ano"))
    except Exception as e:
        ficha["erro"] = f"tags ilegiveis: {e}"

    try:
        ficha["comentario"] = _ler_comentario(audio)
        ficha["tem_capa"] = capa(audio) is not None
    except Exception:
        # Tags secundarias nunca devem invalidar o resto da leitura.
        pass

    return ficha


def _primeiro(valor) -> str:
    """As tags vem quase sempre como lista; queremos texto simples."""
    if valor is None:
        return ""
    if isinstance(valor, (list, tuple)):
        valor = valor[0] if valor else ""
    return str(valor).strip()


def _ler_texto(caminho: str) -> dict:
    out = {}
    try:
        audio = mutagen.File(caminho, easy=True)
    except Exception:
        audio = None

    tags = getattr(audio, "tags", None) if audio is not None else None

    if tags is not None and not isinstance(tags, ID3):
        for campo, chave in CHAVES_EASY.items():
            try:
                out[campo] = _primeiro(tags.get(chave))
            except Exception:
                out[campo] = ""
        return out

    # Ficheiros com ID3 cru (tipicamente WAV e AIFF).
    if isinstance(tags, ID3):
        for campo, frame in FRAMES_ID3.items():
            f = tags.get(frame)
            out[campo] = _primeiro(f.text) if f is not None and getattr(f, "text", None) else ""
    return out


def _ler_comentario(audio) -> str:
    tags = getattr(audio, "tags", None)
    if tags is None:
        return ""

    if isinstance(audio, MP4):
        return _primeiro(tags.get("\xa9cmt"))

    if isinstance(audio, ASF):
        return _primeiro([str(v) for v in tags.get("WM/Comments", [])])

    if isinstance(tags, ID3):
        for frame in tags.getall("COMM"):
            if getattr(frame, "text", None):
                return _primeiro(frame.text)
        return ""

    # Vorbis comments (FLAC, Ogg, Opus) e afins.
    try:
        return _primeiro(tags.get("comment"))
    except Exception:
        return ""


def capa(audio) -> bytes | None:
    """Devolve os bytes da capa embutida, ou None."""
    tags = getattr(audio, "tags", None)

    if isinstance(audio, FLAC):
        return bytes(audio.pictures[0].data) if audio.pictures else None

    if isinstance(audio, MP4):
        covr = (tags or {}).get("covr")
        return bytes(covr[0]) if covr else None

    if isinstance(audio, ASF):
        imgs = (tags or {}).get("WM/Picture")
        return _capa_asf(bytes(imgs[0].value)) if imgs else None

    if isinstance(tags, ID3):
        frames = tags.getall("APIC")
        return bytes(frames[0].data) if frames else None

    # Ogg/Opus guardam a imagem em base64 dentro de um Vorbis comment.
    if tags is not None:
        try:
            b64 = tags.get("metadata_block_picture")
        except Exception:
            b64 = None
        if b64:
            try:
                pic = Picture(base64.b64decode(_primeiro(b64)))
                return bytes(pic.data)
            except Exception:
                return None
    return None


def capa_do_ficheiro(caminho) -> bytes | None:
    try:
        audio = mutagen.File(str(caminho))
    except Exception:
        return None
    if audio is None:
        return None
    try:
        return capa(audio)
    except Exception:
        return None


def _capa_asf(bruto: bytes) -> bytes | None:
    """Desmonta a estrutura WM/Picture do WMA para chegar aos bytes da imagem."""
    try:
        # 1 byte tipo + 4 bytes tamanho, depois mime\0\0 e descricao\0\0 em UTF-16LE.
        pos = 5
        fim_mime = bruto.index(b"\x00\x00", pos)
        pos = fim_mime + 2
        fim_desc = bruto.index(b"\x00\x00", pos)
        return bruto[fim_desc + 2:]
    except Exception:
        return None


def duracao_texto(segundos: float) -> str:
    if not segundos:
        return ""
    segundos = int(round(segundos))
    return f"{segundos // 60}:{segundos % 60:02d}"


def tamanho_texto(bytes_: int) -> str:
    if bytes_ >= 1024 ** 3:
        return f"{bytes_ / 1024 ** 3:.2f} GB"
    if bytes_ >= 1024 ** 2:
        return f"{bytes_ / 1024 ** 2:.1f} MB"
    return f"{bytes_ / 1024:.0f} KB"
