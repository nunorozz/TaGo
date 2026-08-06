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
"""Definicoes guardadas entre sessoes (basicamente, a ultima pasta usada).

As tags sao sempre relidas dos ficheiros ao abrir a pasta: e instantaneo para
o punhado de musicas que o utilizador la coloca de cada vez, e garante que o
que se ve na app e mesmo o que esta no disco. O que fica em cache e a parte
lenta e cara - as respostas do MusicBrainz (ver identificador.py).
"""
from __future__ import annotations

import json

import dados

FICHEIRO = dados.ficheiro("definicoes.json")

PADRAO = {
    "ultima_pasta": "",
    "janela": "1240x820",
}


def carregar() -> dict:
    dados = dict(PADRAO)
    try:
        dados.update(json.loads(FICHEIRO.read_text(encoding="utf-8")))
    except Exception:
        pass
    return dados


def guardar(**campos) -> None:
    dados = carregar()
    dados.update(campos)
    try:
        FICHEIRO.write_text(json.dumps(dados, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    except OSError:
        pass
