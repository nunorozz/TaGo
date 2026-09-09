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
"""Como a app se identifica perante os servicos que consulta.

Num so sitio, porque tem de ser igual em todo o lado. A MusicBrainz **exige**
um User-Agent com nome, versao e um contacto verdadeiro - com um contacto
inventado, o mais provavel e serem os pedidos bloqueados. O Discogs pede o
mesmo, e o Beatport agradece.
"""

NOME = "TaGo"
DESCRICAO = "Music Tag Editor"
VERSAO = "2.0"

# Quem detem os direitos de autor e sob que licenca a app e distribuida. A
# GPL-3 pede que um programa interativo mostre isto a quem o usa - e o que a
# janela "About" faz (ver app.py).
AUTOR = "Nuno Rozz"
ANO = "2026"
LICENCA = "GNU General Public License v3 or later"
LICENCA_URL = "https://www.gnu.org/licenses/gpl-3.0.html"

# O contacto de quem fez a app, que vai em cada pedido as fontes de pesquisa.
# Tem de existir mesmo: a MusicBrainz exige-o e pode bloquear os pedidos se
# for falso. E por aqui que os servicos falam com quem fez a app - por
# exemplo, se ela estiver a pedir de mais.
CONTACTO = "nraiprojects@gmail.com"

AGENTE = f"{NOME}/{VERSAO} ( {CONTACTO} )"
