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
"""Relatorios sobre as faixas da pasta: tags em falta, duplicados, estatisticas."""
from __future__ import annotations

import unicodedata
from collections import Counter
from pathlib import Path

from metadata import ETIQUETAS, duracao_texto, tamanho_texto

CAMPOS_ESSENCIAIS = ["titulo", "artista", "album"]


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", (texto or "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return "".join(c for c in texto if c.isalnum())


def tags_em_falta(fichas: list[dict]) -> str:
    linhas = ["FILES WITH MISSING TAGS", "=" * 60, ""]
    total = 0
    for f in fichas:
        faltam = [c for c in CAMPOS_ESSENCIAIS if not (f.get(c) or "").strip()]
        if not faltam:
            continue
        total += 1
        linhas.append(f"{f['ficheiro']}")
        linhas.append(f"    missing: {', '.join(ETIQUETAS.get(c, c) for c in faltam)}")
    if not total:
        linhas.append("None. Every file has title, artist and album.")
    else:
        linhas.insert(2, f"{total} of {len(fichas)} files have empty fields")

    com_erro = [f for f in fichas if f.get("erro")]
    if com_erro:
        linhas += ["", "FILES THAT COULD NOT BE READ", "-" * 60]
        linhas += [f"{f['ficheiro']}: {f['erro']}" for f in com_erro]

    sem_capa = [f for f in fichas if not f.get("tem_capa") and not f.get("erro")]
    if sem_capa:
        linhas += ["", f"NO ALBUM ARTWORK ({len(sem_capa)})", "-" * 60]
        linhas += [f"{f['ficheiro']}" for f in sem_capa]

    return "\n".join(linhas)


def duplicados(fichas: list[dict]) -> str:
    """Agrupa por artista + titulo + duracao aproximada.

    O nome do ficheiro e pouco fiavel para isto: a mesma musica aparece muitas
    vezes com nomes diferentes.
    """
    grupos: dict[tuple, list[dict]] = {}
    for f in fichas:
        if f.get("erro"):
            continue
        chave = (
            _normalizar(f.get("artista", "")),
            _normalizar(f.get("titulo", "")),
            int(round(float(f.get("duracao") or 0) / 5)),   # tolerancia de ~5s
        )
        if not chave[1]:
            continue
        grupos.setdefault(chave, []).append(f)

    repetidos = {k: v for k, v in grupos.items() if len(v) > 1}

    linhas = ["POSSIBLE DUPLICATES", "=" * 60, ""]
    if not repetidos:
        linhas.append("No duplicates found in this folder.")
        return "\n".join(linhas)

    linhas.append(f"{len(repetidos)} groups of repeated tracks:\n")
    for (_, _, _), grupo in sorted(repetidos.items(), key=lambda x: -len(x[1])):
        cabeca = grupo[0]
        linhas.append(f"* {cabeca.get('artista') or '(no artist)'} - "
                      f"{cabeca.get('titulo')} [{duracao_texto(cabeca['duracao'])}]")
        for f in grupo:
            linhas.append(f"      {f['ficheiro']}  ({f['formato']}, "
                          f"{tamanho_texto(f['tamanho'])})")
        linhas.append("")
    return "\n".join(linhas)


def estatisticas(fichas: list[dict]) -> str:
    validas = [f for f in fichas if not f.get("erro")]
    if not validas:
        return "No files scanned."

    duracao_total = sum(float(f.get("duracao") or 0) for f in validas)
    tamanho_total = sum(int(f.get("tamanho") or 0) for f in validas)
    horas = int(duracao_total // 3600)
    minutos = int((duracao_total % 3600) // 60)

    linhas = [
        "FOLDER STATISTICS", "=" * 60, "",
        f"Tracks:        {len(validas)}",
        f"Total length:  {horas}h {minutos}m",
        f"Disk space:    {tamanho_texto(tamanho_total)}",
        f"With artwork:  {sum(1 for f in validas if f.get('tem_capa'))}",
        "",
    ]

    def top(campo, titulo, n=10):
        contagem = Counter(
            (f.get(campo) or "").strip() for f in validas if (f.get(campo) or "").strip()
        )
        if not contagem:
            return []
        out = [titulo, "-" * 60]
        for nome, quantas in contagem.most_common(n):
            out.append(f"  {quantas:4}x  {nome}")
        out.append("")
        return out

    linhas += top("artista", "ARTISTS")
    linhas += top("album", "ALBUMS")
    linhas += top("genero", "GENRES")
    linhas += top("formato", "FORMATS")

    decadas = Counter()
    for f in validas:
        ano = (f.get("ano") or "")[:4]
        if ano.isdigit():
            decadas[f"{int(ano) // 10 * 10}s"] += 1
    if decadas:
        linhas += ["DECADES", "-" * 60]
        linhas += [f"  {q:4}x  {d}" for d, q in sorted(decadas.items())]

    return "\n".join(linhas)
