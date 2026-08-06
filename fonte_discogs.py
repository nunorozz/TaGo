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
"""Procura no Discogs, atraves da API oficial.

O Discogs e a maior base de dados de edicoes fisicas e digitais: e forte em
editoras, numeros de catalogo, pais e ano da edicao original.

Precisa de um token pessoal, gratuito, que se obtem em
https://www.discogs.com/settings/developers ("Generate new token").

Nota sobre o que o Discogs indexa: o catalogo esta organizado por *edicoes*
(releases), nao por faixas. A pesquisa por faixa existe, mas os resultados
vem ao nivel da edicao - por isso o titulo devolvido e muitas vezes o do
album, e o artista o da edicao.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

import dados
import identidade

NOME = "Discogs"

URL_API = "https://api.discogs.com"
AGENTE = identidade.AGENTE
FICHEIRO_CREDENCIAIS = dados.ficheiro("credenciais.json")

# O Discogs limita a 60 pedidos por minuto com token.
PAUSA = 1.1

_ultimo_pedido = 0.0


class ErroDiscogs(Exception):
    pass


# ------------------------------------------------------------- credenciais

def token() -> str:
    try:
        dados = json.loads(FICHEIRO_CREDENCIAIS.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return (dados.get("discogs", {}) or {}).get("token", "").strip()


def disponivel() -> bool:
    return bool(token())


def guardar_token(novo: str) -> None:
    try:
        dados = json.loads(FICHEIRO_CREDENCIAIS.read_text(encoding="utf-8"))
    except Exception:
        dados = {}
    dados["discogs"] = {"token": novo.strip()}
    FICHEIRO_CREDENCIAIS.write_text(json.dumps(dados, indent=1), encoding="utf-8")


def testar_token(candidato: str) -> tuple[bool, str]:
    """Confirma que o token funciona, antes de o guardar."""
    try:
        r = requests.get(
            f"{URL_API}/database/search",
            params={"q": "test", "type": "release", "per_page": 1,
                    "token": candidato.strip()},
            headers={"User-Agent": AGENTE}, timeout=20)
    except requests.RequestException as e:
        return False, f"sem ligacao ao Discogs: {e}"

    if r.status_code == 200:
        return True, "O token funciona."
    if r.status_code in (401, 403):
        return False, "o token do Discogs nao e valido"
    return False, f"o Discogs respondeu com o erro {r.status_code}"


# ------------------------------------------------------------------ procura

def _esperar():
    global _ultimo_pedido
    decorrido = time.time() - _ultimo_pedido
    if decorrido < PAUSA:
        time.sleep(PAUSA - decorrido)
    _ultimo_pedido = time.time()


def procurar(artista: str, titulo: str, limite: int = 10) -> list[dict]:
    if not titulo:
        return []
    chave = token()
    if not chave:
        return []

    parametros = {"track": titulo, "type": "release", "per_page": limite,
                  "token": chave}
    if artista:
        parametros["artist"] = artista

    _esperar()
    try:
        r = requests.get(f"{URL_API}/database/search", params=parametros,
                         headers={"User-Agent": AGENTE}, timeout=25)
    except requests.RequestException as e:
        raise ErroDiscogs(f"sem ligacao ao Discogs: {e}") from e

    if r.status_code in (401, 403):
        raise ErroDiscogs("o token do Discogs foi recusado")
    if r.status_code == 429:
        raise ErroDiscogs("demasiados pedidos ao Discogs; tenta daqui a pouco")
    if r.status_code != 200:
        raise ErroDiscogs(f"o Discogs respondeu com o erro {r.status_code}")

    try:
        resultados = r.json().get("results", []) or []
    except ValueError as e:
        raise ErroDiscogs(f"resposta do Discogs ilegivel: {e}") from e

    return [c for c in (_extrair(x, titulo) for x in resultados) if c]


def _extrair(item: dict, titulo_procurado: str) -> dict | None:
    # O Discogs devolve "Artista - Album" num so campo.
    bruto = (item.get("title") or "").strip()
    if not bruto:
        return None

    if " - " in bruto:
        artista, album = bruto.split(" - ", 1)
    else:
        artista, album = "", bruto
    artista, album = artista.strip(), album.strip()

    editoras = item.get("label") or []
    editora = editoras[0] if editoras else ""
    catalogo = item.get("catno") or ""
    pais = item.get("country") or ""

    generos = item.get("style") or item.get("genre") or []
    genero = generos[0] if generos else ""

    detalhes = " · ".join(x for x in [editora, catalogo, pais] if x)

    return {
        "fonte": NOME,
        # A pesquisa foi por faixa, mas o Discogs so nos devolve a edicao:
        # o titulo da faixa e o que procuramos, nao o do album.
        "titulo": titulo_procurado,
        "artista": artista,
        "artista_album": artista,
        "album": album,
        "ano": str(item.get("year") or "")[:4],
        "genero": genero,
        "bpm": "",                 # o Discogs nao guarda BPM nem tonalidade
        "tom": "",
        "faixa": "",
        "disco": "",
        "duracao_ms": 0,
        "capa_url": item.get("cover_image") or item.get("thumb") or "",
        "ids_lancamento": [],
        "etiqueta": detalhes,
    }


def genero(candidato: dict) -> str:
    return candidato.get("genero", "")


def descarregar_capa(candidato: dict) -> bytes | None:
    url = candidato.get("capa_url", "")
    if not url:
        return None
    try:
        _esperar()
        r = requests.get(url, timeout=25, headers={"User-Agent": AGENTE})
        if r.status_code == 200 and r.content:
            return r.content
    except requests.RequestException:
        return None
    return None
