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

O Traxsource e a excecao: so responde a um User-Agent de navegador, por isso
esse fica como esta (ver fonte_traxsource.py).
"""

NOME = "TaGo"
DESCRICAO = "Music Tag Editor"
VERSAO = "1.0"

# Quem detem os direitos de autor e sob que licenca a app e distribuida. A
# GPL-3 pede que um programa interativo mostre isto a quem o usa - e o que a
# janela "About" faz (ver app.py).
AUTOR = "Nuno Rozz"
ANO = "2026"
LICENCA = "GNU General Public License v3 or later"
LICENCA_URL = "https://www.gnu.org/licenses/gpl-3.0.html"

# ATENCAO - POR MUDAR ANTES DE DISTRIBUIR.
# Isto e um endereco de exemplo, que nao existe. Enquanto a app for so para
# uso proprio, passa despercebido; a partir do momento em que ande por outras
# maos, a MusicBrainz pode bloquear os pedidos por o contacto ser falso.
# Substituir por um email ou pelo endereco de uma pagina do projeto que exista
# mesmo - e o que os servicos usam para falar com quem fez a app.
CONTACTO = "https://github.com/local/tago"

AGENTE = f"{NOME}/{VERSAO} ( {CONTACTO} )"
