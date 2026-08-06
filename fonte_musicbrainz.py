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
"""Procura na MusicBrainz - base de dados publica, gratuita e sem registo.

Limita a 1 pedido por segundo e exige um User-Agent identificado; o
musicbrainzngs trata do espacamento dos pedidos por nos.
"""
from __future__ import annotations

import musicbrainzngs
import requests

import identidade

NOME = "MusicBrainz"

APP_NOME = identidade.NOME
APP_VERSAO = identidade.VERSAO
APP_CONTACTO = identidade.CONTACTO

musicbrainzngs.set_useragent(APP_NOME, APP_VERSAO, APP_CONTACTO)


class ErroMusicBrainz(Exception):
    pass


def disponivel() -> bool:
    return True          # nao precisa de chaves nem de configuracao


def procurar(artista: str, titulo: str, limite: int = 10) -> list[dict]:
    if not titulo:
        return []
    try:
        resposta = musicbrainzngs.search_recordings(
            recording=titulo, artist=artista or None, limit=limite)
    except musicbrainzngs.NetworkError as e:
        raise ErroMusicBrainz(f"sem ligacao a MusicBrainz: {e}") from e
    except musicbrainzngs.MusicBrainzError as e:
        raise ErroMusicBrainz(f"a MusicBrainz recusou o pedido: {e}") from e

    return [c for c in (_extrair(r) for r in resposta.get("recording-list", [])) if c]


def _creditos(lista) -> str:
    return "".join(
        c.get("artist", {}).get("name", "") if isinstance(c, dict) else str(c)
        for c in (lista or [])
    ).strip()


def _extrair(rec: dict) -> dict | None:
    titulo = (rec.get("title") or "").strip()
    if not titulo:
        return None

    album = ano = artista_album = ""
    ids_lancamento: list[str] = []
    faixa = disco = ""

    lancamentos = rec.get("release-list") or []
    if lancamentos:
        ids_lancamento = [l.get("id", "") for l in lancamentos[:4] if l.get("id")]
        # O lancamento mais antigo costuma ser o album original, nao uma
        # coletanea posterior.
        lanc = sorted(lancamentos, key=lambda l: l.get("date") or "9999")[0]
        album = (lanc.get("title") or "").strip()
        ano = (lanc.get("date") or "")[:4]
        artista_album = _creditos(lanc.get("artist-credit"))
        for meio in lanc.get("medium-list", []):
            disco = str(meio.get("position", "") or "")
            for f in meio.get("track-list", []):
                faixa = str(f.get("number", "") or "")
                break
            break

    genero = ""
    etiquetas = rec.get("tag-list") or []
    if etiquetas:
        melhor = max(etiquetas, key=lambda t: int(t.get("count", 0) or 0))
        genero = (melhor.get("name") or "").title()

    return {
        "fonte": NOME,
        "titulo": titulo,
        "artista": _creditos(rec.get("artist-credit")),
        "artista_album": artista_album,
        "album": album,
        "ano": ano,
        "genero": genero,
        "bpm": "",                # a MusicBrainz nao guarda BPM nem tonalidade
        "tom": "",
        "faixa": faixa,
        "disco": disco,
        "duracao_ms": int(rec.get("length") or 0),
        "capa_url": "",
        "ids_lancamento": ids_lancamento,
        "etiqueta": "",
    }


def genero(candidato: dict) -> str:
    return candidato.get("genero", "")


def descarregar_capa(candidato: dict) -> bytes | None:
    """Capa frontal do Cover Art Archive.

    Nem todos os lancamentos tem imagem, por isso tentamos os varios
    lancamentos associados a gravacao ate encontrar um que tenha.
    """
    cabecalhos = {"User-Agent": f"{APP_NOME}/{APP_VERSAO} ({APP_CONTACTO})"}
    for id_lancamento in [i for i in candidato.get("ids_lancamento", []) if i][:4]:
        for tamanho in ("front-500", "front"):
            try:
                r = requests.get(
                    f"https://coverartarchive.org/release/{id_lancamento}/{tamanho}",
                    timeout=20, headers=cabecalhos)
                if r.status_code == 200 and r.content:
                    return r.content
            except requests.RequestException:
                continue
    return None
