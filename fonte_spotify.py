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
"""Procura no Spotify, atraves da API oficial (Web API).

Usa o fluxo "Client Credentials": a app identifica-se com duas chaves e pode
pesquisar o catalogo publico. Nao ha login de utilizador nem acesso a conta
nenhuma - so pesquisa.

As chaves obtem-se de graca em https://developer.spotify.com/dashboard
(criar uma app; ficam disponiveis o Client ID e o Client Secret).
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import requests

import dados

FICHEIRO_CREDENCIAIS = dados.ficheiro("credenciais.json")
URL_TOKEN = "https://accounts.spotify.com/api/token"
URL_API = "https://api.spotify.com/v1"

NOME = "Spotify"

_token = {"valor": "", "expira": 0.0}
_generos_artista: dict[str, str] = {}


class ErroSpotify(Exception):
    pass


# ------------------------------------------------------------- credenciais

def credenciais() -> tuple[str, str]:
    try:
        dados = json.loads(FICHEIRO_CREDENCIAIS.read_text(encoding="utf-8"))
    except Exception:
        return "", ""
    spotify = dados.get("spotify", {})
    return spotify.get("client_id", "").strip(), spotify.get("client_secret", "").strip()


def disponivel() -> bool:
    return all(credenciais())


def guardar_credenciais(client_id: str, client_secret: str) -> None:
    try:
        dados = json.loads(FICHEIRO_CREDENCIAIS.read_text(encoding="utf-8"))
    except Exception:
        dados = {}
    dados["spotify"] = {"client_id": client_id.strip(),
                        "client_secret": client_secret.strip()}
    FICHEIRO_CREDENCIAIS.write_text(json.dumps(dados, indent=1), encoding="utf-8")
    _token["valor"] = ""
    _token["expira"] = 0.0


def testar_credenciais(client_id: str, client_secret: str) -> tuple[bool, str]:
    """Confirma que as chaves funcionam, antes de as guardar."""
    try:
        _pedir_token(client_id, client_secret)
        return True, "As chaves funcionam."
    except ErroSpotify as e:
        return False, str(e)


# ------------------------------------------------------------------- token

def _pedir_token(client_id: str, client_secret: str) -> str:
    autorizacao = base64.b64encode(
        f"{client_id}:{client_secret}".encode()).decode()
    try:
        r = requests.post(
            URL_TOKEN,
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {autorizacao}",
                     "Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        )
    except requests.RequestException as e:
        raise ErroSpotify(f"sem ligacao ao Spotify: {e}") from e

    if r.status_code == 400:
        raise ErroSpotify("as chaves do Spotify nao sao validas "
                          "(Client ID ou Client Secret errados)")
    if r.status_code != 200:
        raise ErroSpotify(f"o Spotify respondeu com o erro {r.status_code}")

    dados = r.json()
    _token["valor"] = dados["access_token"]
    _token["expira"] = time.time() + int(dados.get("expires_in", 3600)) - 60
    return _token["valor"]


def _token_valido() -> str:
    if _token["valor"] and time.time() < _token["expira"]:
        return _token["valor"]
    client_id, client_secret = credenciais()
    if not client_id or not client_secret:
        raise ErroSpotify("faltam as chaves do Spotify")
    return _pedir_token(client_id, client_secret)


def _pedir(caminho: str, parametros: dict) -> dict:
    for tentativa in range(3):
        r = requests.get(
            f"{URL_API}/{caminho}", params=parametros,
            headers={"Authorization": f"Bearer {_token_valido()}"}, timeout=25)

        if r.status_code == 429:                      # limite de pedidos
            espera = int(r.headers.get("Retry-After", 2))
            time.sleep(min(espera, 10))
            continue
        if r.status_code == 401:                      # token expirou
            _token["valor"] = ""
            continue
        if r.status_code != 200:
            raise ErroSpotify(f"o Spotify respondeu com o erro {r.status_code}")
        return r.json()
    raise ErroSpotify("o Spotify recusou varios pedidos seguidos")


# ------------------------------------------------------------------ procura

def procurar(artista: str, titulo: str, limite: int = 10) -> list[dict]:
    if not titulo:
        return []

    consulta = f'track:"{titulo}"'
    if artista:
        consulta += f' artist:"{artista}"'

    try:
        dados = _pedir("search", {"q": consulta, "type": "track", "limit": limite})
        faixas = dados.get("tracks", {}).get("items", [])
        # A pesquisa com campos e restritiva; se nao der nada, tenta texto livre.
        if not faixas:
            texto = f"{artista} {titulo}".strip()
            dados = _pedir("search", {"q": texto, "type": "track", "limit": limite})
            faixas = dados.get("tracks", {}).get("items", [])
    except requests.RequestException as e:
        raise ErroSpotify(f"sem ligacao ao Spotify: {e}") from e

    return [c for c in (_extrair(f) for f in faixas) if c]


def _extrair(faixa: dict) -> dict | None:
    titulo = (faixa.get("name") or "").strip()
    if not titulo:
        return None

    artistas = [a.get("name", "") for a in faixa.get("artists", [])]
    album = faixa.get("album", {}) or {}
    artistas_album = [a.get("name", "") for a in album.get("artists", [])]
    imagens = album.get("images") or []

    return {
        "fonte": NOME,
        "titulo": titulo,
        "artista": ", ".join(a for a in artistas if a),
        "artista_album": ", ".join(a for a in artistas_album if a),
        "album": (album.get("name") or "").strip(),
        "ano": (album.get("release_date") or "")[:4],
        "genero": "",                       # preenchido a pedido, ver abaixo
        "bpm": "",                          # o Spotify nao expoe BPM nem tom
        "tom": "",
        "faixa": str(faixa.get("track_number") or ""),
        "disco": str(faixa.get("disc_number") or ""),
        "duracao_ms": int(faixa.get("duration_ms") or 0),
        "capa_url": imagens[0]["url"] if imagens else "",
        "ids_lancamento": [],
        "id_artista": (faixa.get("artists") or [{}])[0].get("id", ""),
        "etiqueta": album.get("label", ""),
    }


def genero(candidato: dict) -> str:
    """O Spotify guarda os generos no artista, nao na faixa."""
    id_artista = candidato.get("id_artista", "")
    if not id_artista:
        return ""
    if id_artista in _generos_artista:
        return _generos_artista[id_artista]
    try:
        dados = _pedir(f"artists/{id_artista}", {})
        generos = dados.get("genres") or []
        resultado = generos[0].title() if generos else ""
    except Exception:
        resultado = ""
    _generos_artista[id_artista] = resultado
    return resultado


def descarregar_capa(candidato: dict) -> bytes | None:
    url = candidato.get("capa_url", "")
    if not url:
        return None
    try:
        r = requests.get(url, timeout=25)
        if r.status_code == 200 and r.content:
            return r.content
    except requests.RequestException:
        return None
    return None
