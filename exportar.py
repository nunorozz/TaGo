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
"""Exportacao da lista para CSV.

O CSV vai em UTF-8 *com BOM*: sem o BOM, o Excel em portugues abre o ficheiro
em ANSI e os acentos aparecem trocados.
"""
from __future__ import annotations

import csv
from pathlib import Path

from metadata import duracao_texto

COLUNAS = [
    ("ficheiro", "Ficheiro"),
    ("titulo", "Titulo"),
    ("artista", "Artista"),
    ("artista_album", "Artista do album"),
    ("album", "Album"),
    ("ano", "Ano"),
    ("genero", "Genero"),
    ("bpm", "BPM"),
    ("tom", "Key"),
    ("faixa", "N. faixa"),
    ("disco", "N. disco"),
    ("comentario", "Comentario"),
    ("duracao_txt", "Duracao"),
    ("formato", "Formato"),
    ("bitrate_kbps", "Bitrate (kbps)"),
    ("sample_rate", "Sample rate"),
    ("canais", "Canais"),
    ("tamanho", "Tamanho (bytes)"),
    ("tem_capa_txt", "Tem capa"),
    ("modificado", "Modificado"),
    ("caminho", "Caminho completo"),
    ("erro", "Erro"),
]


def para_csv(fichas: list[dict], destino) -> Path:
    destino = Path(destino)
    with open(destino, "w", newline="", encoding="utf-8-sig") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow([titulo for _, titulo in COLUNAS])
        for ficha in fichas:
            linha = dict(ficha)
            linha["duracao_txt"] = duracao_texto(ficha.get("duracao", 0))
            linha["bitrate_kbps"] = round((ficha.get("bitrate") or 0) / 1000)
            linha["tem_capa_txt"] = "sim" if ficha.get("tem_capa") else "nao"
            escritor.writerow([linha.get(chave, "") for chave, _ in COLUNAS])
    return destino
