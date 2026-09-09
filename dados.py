# -*- coding: utf-8 -*-
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
"""Onde e que a app guarda o que escreve (definicoes, chaves e caches).

Nao pode ser ao lado do app.py. Instalada em condicoes - por exemplo em
`Program Files` - essa pasta e so de leitura para quem nao e administrador, e
a app arrancava e falhava a gravar tudo: as definicoes, as chaves das fontes e
as caches. Vai tudo para a pasta pessoal de cada utilizador.

Quem ja usava a app com os ficheiros ao lado do codigo nao perde nada: na
primeira vez que se pede cada ficheiro, se ele existir la e ainda nao existir
aqui, e copiado. O original fica onde esta, sem ser tocado - pode apagar-se a
mao mais tarde, ja nao e lido.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

NOME = "TaGo"

# A pasta antiga, ao lado do codigo, de onde se migra o que la estiver.
_ANTIGA = Path(__file__).parent


def _pasta_dados() -> Path:
    """A pasta pessoal onde tudo isto fica.

    A variavel TAGO_DADOS existe para os testes poderem trabalhar numa pasta
    a parte, sem tocar nas definicoes e nas chaves de quem esta a usar a app.
    """
    escolhida = os.environ.get("TAGO_DADOS")
    if escolhida:
        return Path(escolhida)

    # Cada sistema tem o seu sitio para isto, e convem respeita-lo: e onde as
    # copias de seguranca do sistema vao buscar, e onde quem usa o computador
    # espera encontrar as coisas da app.
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / NOME
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / NOME

    return Path.home() / f".{NOME.lower()}"


PASTA = _pasta_dados()


def recurso(nome: str) -> Path:
    """Um ficheiro que veio com a app (o logo, o icone) - so de leitura.

    Nao e a mesma coisa que os de baixo: estes nao se escrevem nem se migram,
    vem dentro da instalacao. Quando a app for empacotada num executavel, o
    PyInstaller desdobra-os numa pasta temporaria que anuncia em `_MEIPASS` -
    daí a primeira hipotese.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        caminho = Path(base) / "recursos" / nome
        if caminho.exists():
            return caminho
    return _ANTIGA / "recursos" / nome


def ficheiro(nome: str) -> Path:
    """O caminho de um dos nossos ficheiros, ja com a pasta criada.

    Nunca levanta excecao por causa da pasta ou da migracao: se algo correr
    mal, devolve na mesma o caminho e quem chama trata do resto - todos estes
    ficheiros sao dispensaveis a arrancar.
    """
    destino = PASTA / nome
    try:
        PASTA.mkdir(parents=True, exist_ok=True)
        antigo = _ANTIGA / nome
        if not destino.exists() and antigo.exists():
            shutil.copy2(antigo, destino)
    except OSError:
        pass
    return destino
