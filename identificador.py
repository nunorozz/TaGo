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
"""Identificacao de faixas: junta os resultados das varias fontes.

Estrategia: procurar por texto, usando as tags que o ficheiro ja tem e, se
estiverem vazias, o proprio nome do ficheiro (que costuma ter "Artista -
Titulo"). Cada candidato leva um grau de confianca calculado da mesma
maneira, venha ele de onde vier - so assim faz sentido comparar resultados
do Spotify com os da MusicBrainz na mesma lista.

Nada e aplicado automaticamente: e sempre o utilizador que aprova.
"""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import fonte_beatport
import fonte_discogs
import fonte_musicbrainz
import fonte_spotify
import fonte_traxsource

import dados

FICHEIRO_CACHE = dados.ficheiro("cache_procuras.json")
LIMITE_CANDIDATOS = 8

# Confianca abaixo da qual a sugestao aparece marcada como duvidosa.
CONFIANCA_DUVIDOSA = 70

# Ordem de preferencia quando as fontes empatam.
FONTES = {
    fonte_spotify.NOME: fonte_spotify,
    fonte_beatport.NOME: fonte_beatport,
    fonte_traxsource.NOME: fonte_traxsource,
    fonte_discogs.NOME: fonte_discogs,
    fonte_musicbrainz.NOME: fonte_musicbrainz,
}

# Fontes que dependem de vias nao oficiais e podem deixar de funcionar.
FONTES_FRAGEIS = {fonte_beatport.NOME, fonte_traxsource.NOME}

_cache: dict | None = None


class SemLigacao(Exception):
    pass


def fontes_disponiveis() -> list[str]:
    return [nome for nome, modulo in FONTES.items() if modulo.disponivel()]


def fontes_por_configurar() -> list[str]:
    return [nome for nome, modulo in FONTES.items() if not modulo.disponivel()]


# -------------------------------------------------------------------- cache

def _carregar_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(FICHEIRO_CACHE.read_text(encoding="utf-8"))
        except Exception:
            _cache = {}
    return _cache


def _guardar_cache() -> None:
    try:
        FICHEIRO_CACHE.write_text(
            json.dumps(_carregar_cache(), ensure_ascii=False, indent=1),
            encoding="utf-8")
    except Exception:
        pass


def limpar_cache() -> None:
    global _cache
    _cache = {}
    try:
        FICHEIRO_CACHE.unlink()
    except OSError:
        pass


# ------------------------------------------- adivinhar a partir do nome

# Lixo comum em nomes de ficheiros descarregados.
_LIXO = re.compile(
    r"(spotidownloader\.com|youtube|ytmp3|320\s*kbps|hq\s*audio|official\s*(video|audio)"
    r"|lyric[s]?\s*video|free\s*download|www\.[\w.-]+)",
    re.IGNORECASE,
)
_NUMERO_INICIAL = re.compile(r"^\s*\d{1,3}\s*[-._)\]]\s*")
_ESPACOS = re.compile(r"\s{2,}")


def adivinhar_do_nome(nome_ficheiro: str) -> tuple[str, str]:
    """Tenta extrair (artista, titulo) do nome do ficheiro."""
    base = Path(nome_ficheiro).stem
    base = _LIXO.sub("", base)
    base = base.replace("_", " ")
    # Numeracoes como "3-4. " ou "01 - " podem vir encadeadas.
    for _ in range(3):
        novo = _NUMERO_INICIAL.sub("", base)
        if novo == base:
            break
        base = novo
    base = _ESPACOS.sub(" ", base).strip(" -–—")

    partes = [p.strip() for p in re.split(r"\s+[-–—]\s+", base) if p.strip()]

    if len(partes) >= 3:
        return partes[-1], partes[-2]
    if len(partes) == 2:
        return partes[0], partes[1]
    return "", base


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", texto)


def _semelhanca(a: str, b: str) -> float:
    a, b = _normalizar(a), _normalizar(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


# ------------------------------------------------------------------ procura

def identificar(ficha: dict, fontes: list[str] | None = None,
                limite: int = LIMITE_CANDIDATOS,
                falhas: list[tuple[str, str]] | None = None) -> list[dict]:
    """Devolve candidatos de todas as fontes, ordenados por confianca.

    Uma fonte que falhe nao estraga as outras: se for passada uma lista em
    'falhas', as avarias sao la registadas como (fonte, mensagem) e a procura
    segue com as restantes. So se nenhuma fonte der resultados e tiver havido
    avarias e que se levanta SemLigacao.
    """
    if fontes is None:
        fontes = fontes_disponiveis()
    fontes = [f for f in fontes if f in FONTES and FONTES[f].disponivel()]
    if not fontes:
        return []

    artista = (ficha.get("artista") or "").strip()
    titulo = (ficha.get("titulo") or "").strip()

    if titulo:
        tentativas = [(artista, titulo)]
        origem = "tags"
    else:
        a, t = adivinhar_do_nome(ficha.get("ficheiro", ""))
        if not t:
            return []
        origem = "nome do ficheiro"
        # O nome do ficheiro e ambiguo: tanto aparece "Artista - Titulo" como
        # "Titulo - Artista". Perguntamos as duas ordens e deixamos a
        # pontuacao decidir qual faz sentido.
        tentativas = [(a, t)]
        if a and _normalizar(a) != _normalizar(t):
            tentativas.append((t, a))

    candidatos = []
    vistos = set()
    avarias: list[tuple[str, str]] = []

    for nome_fonte in fontes:
        for art, tit in tentativas:
            try:
                encontrados = _procurar(nome_fonte, art, tit, limite)
            except SemLigacao as e:
                avarias.append((nome_fonte, str(e)))
                break
            for c in encontrados:
                chave = (c["fonte"], _normalizar(c["titulo"]),
                         _normalizar(c["artista"]), _normalizar(c["album"]))
                if chave in vistos:
                    continue
                vistos.add(chave)
                candidatos.append(c)

    if falhas is not None:
        falhas.extend(avarias)

    if avarias and not candidatos:
        raise SemLigacao("; ".join(f"{f}: {m}" for f, m in avarias))

    return _pontuar(candidatos, ficha, origem, tentativas)[:limite]


def _procurar(nome_fonte: str, artista: str, titulo: str, limite: int) -> list[dict]:
    if not titulo:
        return []

    chave = f"{nome_fonte}|{_normalizar(artista)}|{_normalizar(titulo)}"
    cache = _carregar_cache()
    if chave in cache:
        return cache[chave]

    modulo = FONTES[nome_fonte]
    try:
        resultados = modulo.procurar(artista, titulo, limite)
    except Exception as e:
        raise SemLigacao(str(e)) from e

    cache[chave] = resultados
    _guardar_cache()
    return resultados


def _pontuar(candidatos: list[dict], ficha: dict, origem: str,
             tentativas: list[tuple[str, str]]) -> list[dict]:
    """Confianca 0-100, calculada da mesma maneira para todas as fontes.

    Compara-se cada candidato com o que sabemos do ficheiro: titulo, artista
    e duracao. Nao se usam as pontuacoes internas de cada servico, que nao
    sao comparaveis entre si.

    Quando partimos do nome do ficheiro nao sabemos se ele esta em
    "Artista - Titulo" ou "Titulo - Artista", por isso experimentamos as duas
    leituras e fica a que melhor explica o candidato.
    """
    duracao_ficheiro = float(ficha.get("duracao") or 0)

    resultado = []
    for c in candidatos:
        c = dict(c)

        if duracao_ficheiro and c.get("duracao_ms"):
            diferenca = abs(c["duracao_ms"] / 1000 - duracao_ficheiro)
            if diferenca <= 2:
                sim_duracao = 1.0
            elif diferenca <= 5:
                sim_duracao = 0.75
            elif diferenca <= 15:
                sim_duracao = 0.35
            else:
                sim_duracao = 0.0
        else:
            sim_duracao = 0.4      # sem duracao conhecida, nem premeia nem penaliza

        melhor = 0.0
        for ref_artista, ref_titulo in tentativas:
            sim_titulo = _semelhanca(c.get("titulo", ""), ref_titulo)
            if ref_artista:
                sim_artista = _semelhanca(c.get("artista", ""), ref_artista)
                pontos = 100 * (0.45 * sim_titulo + 0.30 * sim_artista
                                + 0.25 * sim_duracao)
            else:
                pontos = 100 * (0.60 * sim_titulo + 0.40 * sim_duracao)
            melhor = max(melhor, pontos)

        pontos = melhor
        if not c.get("album"):
            pontos -= 5
        if c.get("capa_url") or c.get("ids_lancamento"):
            pontos += 3
        if origem != "tags":
            # Partimos do nome do ficheiro, que e menos fiavel do que as tags.
            pontos -= 6

        c["confianca"] = max(0, min(100, int(round(pontos))))
        c["origem"] = origem
        c["duvidoso"] = c["confianca"] < CONFIANCA_DUVIDOSA
        resultado.append(c)

    return sorted(resultado, key=lambda c: (c["confianca"], c["fonte"] == fonte_spotify.NOME),
                  reverse=True)


# ------------------------------------------------------------------- extras

def preencher_genero(candidato: dict) -> str:
    """O genero exige um pedido extra em algumas fontes; so o pedimos quando
    o candidato e mesmo usado."""
    if candidato.get("genero"):
        return candidato["genero"]
    modulo = FONTES.get(candidato.get("fonte", ""))
    if modulo is None:
        return ""
    try:
        candidato["genero"] = modulo.genero(candidato)
    except Exception:
        candidato["genero"] = ""
    return candidato["genero"]


def descarregar_capa(candidato: dict) -> bytes | None:
    if not candidato:
        return None
    modulo = FONTES.get(candidato.get("fonte", ""))
    if modulo is None:
        return None
    try:
        return modulo.descarregar_capa(candidato)
    except Exception:
        return None


# ------------------------------------------- impressao digital (AcoustID)

def acoustid_disponivel() -> bool:
    """A identificacao por som exige pyacoustid, o fpcalc.exe e uma chave."""
    try:
        import acoustid  # noqa: F401
    except ImportError:
        return False
    return bool(_chave_acoustid())


def _chave_acoustid() -> str:
    ficheiro = dados.ficheiro("chave_acoustid.txt")
    try:
        return ficheiro.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def identificar_por_som(caminho, limite: int = LIMITE_CANDIDATOS) -> list[dict]:
    """Identifica pela impressao digital do audio. Requer configuracao extra."""
    if not acoustid_disponivel():
        return []
    import acoustid

    try:
        resultados = acoustid.match(_chave_acoustid(), str(caminho),
                                    meta="recordings releases")
    except Exception:
        return []

    candidatos = []
    for pontuacao, _id, titulo, artista in resultados:
        candidatos.append({
            "fonte": "AcoustID",
            "titulo": titulo or "",
            "artista": artista or "",
            "artista_album": artista or "",
            "album": "", "ano": "", "genero": "", "faixa": "", "disco": "",
            "duracao_ms": 0, "capa_url": "", "ids_lancamento": [], "etiqueta": "",
            "confianca": int(round(float(pontuacao) * 100)),
            "origem": "som",
            "duvidoso": float(pontuacao) < 0.7,
        })
    return sorted(candidatos, key=lambda c: c["confianca"], reverse=True)[:limite]
