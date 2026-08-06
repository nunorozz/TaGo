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
"""Procura no Traxsource - POR VIA NAO OFICIAL.

AVISO IMPORTANTE
----------------
Tal como o Beatport, o Traxsource nao tem API publica. Este modulo le a
pagina publica de pesquisa e retira dela os resultados.

* Pode deixar de funcionar sem aviso, sempre que mudarem o site. Quando isso
  acontecer, a app continua com as outras fontes; esta limita-se a nao
  devolver resultados.
* E uma utilizacao pessoal, de baixo volume: ha uma pausa entre pedidos.

O Traxsource e forte em house, deep house, soulful e afro house - generos
onde o Beatport as vezes falha - e da editora, BPM, tonalidade e genero.
"""
from __future__ import annotations

import html
import re
import time

import requests

NOME = "Traxsource"

URL_SITE = "https://www.traxsource.com"
# O site so responde a um User-Agent de navegador.
AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
PAUSA = 1.0

_sessao: requests.Session | None = None
_ultimo_pedido = 0.0


class ErroTraxsource(Exception):
    pass


def disponivel() -> bool:
    return True          # nao precisa de chaves


def _obter_sessao() -> requests.Session:
    """A pesquisa so responde a quem ja tenha visitado o site.

    Sem a cookie de sessao (PHPSESSID), o /search/tracks devolve 403. Basta
    abrir a pagina inicial uma vez para a obter.
    """
    global _sessao
    if _sessao is None:
        _sessao = requests.Session()
        _sessao.headers.update({"User-Agent": AGENTE,
                                "Accept-Language": "en-US,en;q=0.9"})
    if "PHPSESSID" not in _sessao.cookies:
        _esperar()
        try:
            _sessao.get(URL_SITE, timeout=25)
        except requests.RequestException as e:
            raise ErroTraxsource(f"sem ligacao ao Traxsource: {e}") from e
    return _sessao


def _largar_sessao():
    global _sessao
    _sessao = None


def _esperar():
    global _ultimo_pedido
    decorrido = time.time() - _ultimo_pedido
    if decorrido < PAUSA:
        time.sleep(PAUSA - decorrido)
    _ultimo_pedido = time.time()


# --------------------------------------------------- leitura da pagina

# Cada resultado e um <div data-trid="..." class="trk-row ...">.
_LINHA = re.compile(r'<div data-trid="(\d+)"[^>]*class="[^"]*trk-row[^"]*"(.*?)'
                    r'(?=<div data-trid="|\Z)', re.DOTALL)

_TITULO = re.compile(r'class="trk-cell title".*?<a href="/track/[^"]*">([^<]+)</a>',
                     re.DOTALL)
_VERSAO = re.compile(r'<span class="version">\s*(.*?)\s*(?:<span class="duration">'
                     r'\(([\d:]+)\)</span>)?\s*</span>', re.DOTALL)
_ARTISTAS = re.compile(r'class="com-artists"[^>]*>([^<]+)</a>')
_EDITORA = re.compile(r'class="trk-cell label".*?<a href="/label/[^"]*">([^<]+)</a>',
                      re.DOTALL)
_GENERO = re.compile(r'class="trk-cell genre".*?<a href="/genre/[^"]*">([^<]+)</a>',
                     re.DOTALL)
_TOM_BPM = re.compile(r'class="trk-cell key-bpm">\s*([^<]*?)\s*<br\s*/?>\s*(\d+)',
                      re.DOTALL)
_DATA = re.compile(r'class="trk-cell r-date">\s*([\d-]{4,10})')
_IMAGEM = re.compile(r'class="trk-cell thumb".*?<img src="([^"]+)"', re.DOTALL)


def _texto(valor: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", valor or "")).strip()


def procurar(artista: str, titulo: str, limite: int = 10) -> list[dict]:
    if not titulo:
        return []
    from urllib.parse import quote_plus

    consulta = f"{artista} {titulo}".strip()
    endereco = f"{URL_SITE}/search/tracks?term={quote_plus(consulta)}"

    def pedir():
        _esperar()
        try:
            return _obter_sessao().get(endereco, timeout=25)
        except requests.RequestException as e:
            raise ErroTraxsource(f"sem ligacao ao Traxsource: {e}") from e

    r = pedir()
    if r.status_code == 403:
        # A sessao caducou: comeca-se uma nova e tenta-se mais uma vez.
        _largar_sessao()
        r = pedir()

    if r.status_code != 200:
        raise ErroTraxsource(f"o Traxsource respondeu com o erro {r.status_code}")

    linhas = _LINHA.findall(r.text)
    if not linhas and "trk-row" in r.text:
        raise ErroTraxsource(
            "o site do Traxsource mudou de formato; esta fonte deixou de funcionar")

    vistos, resultados = set(), []
    for id_faixa, bloco in linhas:
        if id_faixa in vistos:          # o site repete a mesma faixa em blocos
            continue
        vistos.add(id_faixa)
        candidato = _extrair(bloco)
        if candidato:
            resultados.append(candidato)
        if len(resultados) >= limite:
            break
    return resultados


def _extrair(bloco: str) -> dict | None:
    achado = _TITULO.search(bloco)
    if not achado:
        return None
    nome = _texto(achado.group(1))
    if not nome:
        return None

    mistura = duracao_txt = ""
    versao = _VERSAO.search(bloco)
    if versao:
        mistura = _texto(versao.group(1))
        duracao_txt = versao.group(2) or ""

    # "Original Mix" nao acrescenta nada ao titulo; as outras versoes sim.
    titulo = (f"{nome} ({mistura})"
              if mistura and mistura.lower() != "original mix" else nome)

    artistas = [_texto(a) for a in _ARTISTAS.findall(bloco)]
    artistas = [a for a in artistas if a]

    editora = _texto(_EDITORA.search(bloco).group(1)) if _EDITORA.search(bloco) else ""
    genero = _texto(_GENERO.search(bloco).group(1)) if _GENERO.search(bloco) else ""

    tom = bpm = ""
    tom_bpm = _TOM_BPM.search(bloco)
    if tom_bpm:
        tom, bpm = _texto(tom_bpm.group(1)), tom_bpm.group(2)

    data = _DATA.search(bloco)
    ano = data.group(1)[:4] if data else ""

    imagem = _IMAGEM.search(bloco)
    capa = imagem.group(1) if imagem else ""
    # As miniaturas vem a 52x52; o mesmo caminho serve tamanhos maiores.
    capa = re.sub(r"/image\.php/\d+x\d+/", "/image.php/500x500/", capa)

    duracao_ms = 0
    if ":" in duracao_txt:
        try:
            minutos, segundos = duracao_txt.split(":")
            duracao_ms = (int(minutos) * 60 + int(segundos)) * 1000
        except ValueError:
            duracao_ms = 0

    # O BPM e a tonalidade tem campo proprio; a editora nao, vai no cabecalho.
    detalhes = editora

    return {
        "fonte": NOME,
        "titulo": titulo,
        "artista": ", ".join(artistas),
        "artista_album": ", ".join(artistas),
        "album": "",              # a pesquisa por faixa nao devolve o lancamento
        "ano": ano,
        "genero": genero,
        "bpm": bpm,
        "tom": tom,
        "faixa": "",
        "disco": "",
        "duracao_ms": duracao_ms,
        "capa_url": capa,
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
        r = _obter_sessao().get(url, timeout=25)
        if r.status_code == 200 and r.content:
            return r.content
    except requests.RequestException:
        return None
    return None
