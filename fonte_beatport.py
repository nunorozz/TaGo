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
"""Procura no Beatport - POR VIA NAO OFICIAL.

AVISO IMPORTANTE
----------------
O Beatport nao tem API publica: a api.beatport.com exige aprovacao comercial.
Este modulo obtem os dados como o proprio site do Beatport os obtem - le a
pagina publica de pesquisa, tira de la o token que o site usa, e chama a
mesma API que o site chama.

Consequencias que convem ter presentes:

* Isto pode deixar de funcionar sem aviso, sempre que o Beatport mudar o site.
  Quando isso acontecer, a app continua a funcionar com as outras fontes: esta
  limita-se a nao devolver resultados.
* E uma utilizacao pessoal, de baixo volume. Ha uma pausa entre pedidos e um
  User-Agent identificavel, para nao sobrecarregar o servico.

Em troca, o Beatport da o que as outras fontes nao dao para musica
eletronica: a editora (label), o numero de catalogo, o BPM, a tonalidade e o
genero correto (Melodic House, Minimal / Deep Tech, etc.).
"""
from __future__ import annotations

import base64
import json
import re
import time
import uuid

import requests

import identidade

NOME = "Beatport"

URL_SITE = "https://www.beatport.com"
URL_API = "https://api.beatport.com/v4"
AGENTE = identidade.AGENTE

# Pausa minima entre pedidos, para nao martelar o servico.
PAUSA = 1.0

_sessao: requests.Session | None = None
_token = {"valor": "", "expira": 0.0}
_ultimo_pedido = 0.0


class ErroBeatport(Exception):
    pass


def disponivel() -> bool:
    return True          # nao precisa de chaves


def _obter_sessao() -> requests.Session:
    global _sessao
    if _sessao is None:
        _sessao = requests.Session()
        _sessao.headers.update({
            "User-Agent": AGENTE,
            "Accept-Language": "en-US,en;q=0.9",
        })
    return _sessao


def _esperar():
    global _ultimo_pedido
    decorrido = time.time() - _ultimo_pedido
    if decorrido < PAUSA:
        time.sleep(PAUSA - decorrido)
    _ultimo_pedido = time.time()


# -------------------------------------------------------------------- token

_RE_NEXT_DATA = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def _dados_da_pagina(caminho: str) -> dict:
    """Le o bloco JSON que o site do Beatport embute em cada pagina."""
    _esperar()
    try:
        r = _obter_sessao().get(f"{URL_SITE}{caminho}", timeout=25,
                                headers={"Cache-Control": "no-cache",
                                         "Pragma": "no-cache"})
    except requests.RequestException as e:
        raise ErroBeatport(f"sem ligacao ao Beatport: {e}") from e

    if r.status_code != 200:
        raise ErroBeatport(f"o Beatport respondeu com o erro {r.status_code}")

    achado = _RE_NEXT_DATA.search(r.text)
    if not achado:
        raise ErroBeatport(
            "o site do Beatport mudou de formato; esta fonte deixou de funcionar")
    try:
        return json.loads(achado.group(1))
    except json.JSONDecodeError as e:
        raise ErroBeatport(f"resposta do Beatport ilegivel: {e}") from e


def _procurar_chave(objeto, nomes: tuple[str, ...], profundidade: int = 0):
    """Procura recursivamente uma chave no JSON, seja qual for o sitio onde
    o Beatport a tenha arrumado desta vez."""
    if profundidade > 12:
        return None
    if isinstance(objeto, dict):
        for chave, valor in objeto.items():
            if chave in nomes and isinstance(valor, str) and valor:
                return valor
        for valor in objeto.values():
            achado = _procurar_chave(valor, nomes, profundidade + 1)
            if achado:
                return achado
    elif isinstance(objeto, list):
        for item in objeto:
            achado = _procurar_chave(item, nomes, profundidade + 1)
            if achado:
                return achado
    return None


def _validade(token: str) -> float:
    """Le o 'exp' de dentro do token, sem validar assinatura nenhuma.

    E preciso porque o token que vem na pagina pode ja estar expirado (ver
    _token_valido); o 'expires_in' ao lado dele conta a partir do momento em
    que a pagina foi gerada, nao de agora.
    """
    try:
        corpo = token.split(".")[1]
        corpo += "=" * (-len(corpo) % 4)
        return float(json.loads(base64.urlsafe_b64decode(corpo)).get("exp", 0))
    except Exception:
        return 0.0


def _token_da_pagina() -> tuple[str, float]:
    # Uma pesquisa diferente de cada vez: as paginas comuns estao em cache no
    # CDN do Beatport e trazem um token gerado ha minutos, ja fora de prazo.
    caminho = f"/search?q={uuid.uuid4().hex[:10]}"
    dados = _dados_da_pagina(caminho)
    sessao = (dados.get("props", {}).get("pageProps", {}).get("anonSession") or {})
    valor = sessao.get("access_token", "")
    if not valor:
        # Se mudarem o sitio onde a arrumam, ainda tentamos encontra-la.
        valor = _procurar_chave(dados, ("access_token", "accessToken")) or ""
    return valor, _validade(valor) if valor else 0.0


def _token_valido() -> str:
    if _token["valor"] and time.time() < _token["expira"]:
        return _token["valor"]

    for _ in range(2):
        valor, expira = _token_da_pagina()
        if valor and expira - time.time() > 30:
            _token["valor"] = valor
            _token["expira"] = expira - 30      # margem de seguranca
            return valor

    raise ErroBeatport(
        "nao foi possivel obter um acesso valido ao Beatport "
        "(o site so devolveu sessoes ja expiradas)")


# ------------------------------------------------------------------ procura

def procurar(artista: str, titulo: str, limite: int = 10) -> list[dict]:
    if not titulo:
        return []
    consulta = f"{artista} {titulo}".strip()
    faixas = _procurar_pela_api(consulta, limite)
    return [c for c in (_extrair(f) for f in faixas[:limite]) if c]


def _procurar_pela_api(consulta: str, limite: int) -> list[dict]:
    _esperar()
    try:
        r = _obter_sessao().get(
            f"{URL_API}/catalog/search",
            params={"q": consulta, "type": "tracks", "per_page": limite},
            headers={"Authorization": f"Bearer {_token_valido()}"},
            timeout=25,
        )
    except requests.RequestException as e:
        raise ErroBeatport(f"sem ligacao ao Beatport: {e}") from e

    if r.status_code == 401:
        # O token de sessao anonima expirou: renova-se e tenta-se mais uma vez.
        _token["valor"] = ""
        _esperar()
        r = _obter_sessao().get(
            f"{URL_API}/catalog/search",
            params={"q": consulta, "type": "tracks", "per_page": limite},
            headers={"Authorization": f"Bearer {_token_valido()}"},
            timeout=25)

    if r.status_code != 200:
        raise ErroBeatport(f"o Beatport respondeu com o erro {r.status_code}")

    try:
        return r.json().get("tracks", []) or []
    except ValueError as e:
        raise ErroBeatport(f"resposta do Beatport ilegivel: {e}") from e


def _extrair(faixa: dict) -> dict | None:
    nome = (faixa.get("name") or "").strip()
    if not nome:
        return None

    mistura = (faixa.get("mix_name") or "").strip()
    # "Original Mix" nao acrescenta nada ao titulo; as outras sim.
    titulo = f"{nome} ({mistura})" if mistura and mistura.lower() != "original mix" else nome

    artistas = [a.get("name", "") for a in (faixa.get("artists") or [])
                if isinstance(a, dict)]
    remisturadores = [a.get("name", "") for a in (faixa.get("remixers") or [])
                      if isinstance(a, dict)]

    lancamento = faixa.get("release") or {}
    imagem = (lancamento.get("image") or {}).get("uri", "")
    editora = ((lancamento.get("label") or {}).get("name", "")
               if isinstance(lancamento.get("label"), dict) else "")

    data = (faixa.get("new_release_date") or faixa.get("publish_date")
            or lancamento.get("new_release_date") or "")

    genero = ""
    g = faixa.get("genre")
    if isinstance(g, dict):
        genero = g.get("name", "")
    elif isinstance(faixa.get("genres"), list) and faixa["genres"]:
        primeiro = faixa["genres"][0]
        genero = primeiro.get("name", "") if isinstance(primeiro, dict) else ""

    tonalidade = ""
    k = faixa.get("key")
    if isinstance(k, dict):
        tonalidade = k.get("name", "") or k.get("camelot_number", "")

    bpm = faixa.get("bpm") or ""
    catalogo = lancamento.get("catalog_number", "")

    # Editora e catalogo nao tem campo proprio: vao para o cabecalho da
    # sugestao. O BPM e a tonalidade ja tem campo, ver adiante.
    detalhes = " · ".join(x for x in [editora, catalogo] if x)

    return {
        "fonte": NOME,
        "titulo": titulo,
        "artista": ", ".join(a for a in artistas if a),
        "artista_album": ", ".join(a for a in artistas if a),
        "album": (lancamento.get("name") or "").strip(),
        "ano": str(data)[:4],
        "genero": genero,
        "bpm": str(bpm or ""),
        "tom": tonalidade,
        "faixa": str(faixa.get("number") or ""),
        "disco": "",
        "duracao_ms": int(faixa.get("length_ms") or 0),
        "capa_url": imagem,
        "ids_lancamento": [],
        "etiqueta": detalhes,
        "remisturadores": ", ".join(r for r in remisturadores if r),
    }


def genero(candidato: dict) -> str:
    return candidato.get("genero", "")


def descarregar_capa(candidato: dict) -> bytes | None:
    url = candidato.get("capa_url", "")
    if not url:
        return None
    # As imagens do Beatport vem com marcadores de tamanho no caminho.
    url = url.replace("{w}", "600").replace("{h}", "600")
    try:
        _esperar()
        r = _obter_sessao().get(url, timeout=25)
        if r.status_code == 200 and r.content:
            return r.content
    except requests.RequestException:
        return None
    return None
