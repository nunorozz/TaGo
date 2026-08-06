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
"""Analise da pasta de trabalho.

Por decisao do utilizador, a app olha *apenas* para os ficheiros que estao
diretamente dentro da pasta escolhida. Nao entra em subpastas: o fluxo e ele
ir colocando ali as musicas que quer tratar.
"""
from __future__ import annotations

from pathlib import Path

from escritor import PASTA_BACKUP
from metadata import e_audio, ler


def listar_ficheiros(pasta) -> list[Path]:
    """Ficheiros de audio na pasta, sem entrar em subpastas."""
    p = Path(pasta)
    if not p.is_dir():
        return []
    ficheiros = [
        f for f in p.iterdir()
        if f.is_file() and e_audio(f) and f.parent.name != PASTA_BACKUP
    ]
    return sorted(ficheiros, key=lambda f: f.name.lower())


def analisar(pasta, progresso=None, cancelado=None) -> list[dict]:
    """Le as tags de todos os ficheiros da pasta.

    progresso: funcao chamada com (feitos, total, nome_do_ficheiro).
    cancelado: funcao sem argumentos que devolve True para interromper.
    """
    ficheiros = listar_ficheiros(pasta)
    total = len(ficheiros)
    fichas = []

    for i, f in enumerate(ficheiros, start=1):
        if cancelado is not None and cancelado():
            break
        fichas.append(ler(f))
        if progresso is not None:
            progresso(i, total, f.name)

    return fichas
