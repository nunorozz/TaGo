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
"""Aspeto da aplicacao - inspirado no Ableton Live.

O que define o visual do Live, e o que se copia aqui:

- Tudo cinzento escuro, mate, sem brilhos nem gradientes.
- Cantos vivos: nada e arredondado.
- Cada painel e separado do seguinte por uma linha fina escura, em vez de
  sombras ou espacos grandes.
- Uma unica cor forte - o amarelo - reservada ao que esta selecionado ou
  ativo. Tudo o resto e cinzento, para o amarelo se ver de longe.
- Letra estreita e compacta, com os titulos em maiusculas pequenas.

Este modulo mexe no tema global do customtkinter, por isso tem de ser
aplicado ANTES de se criar a janela. Assim os botoes, caixas e molduras
nascem ja com este aspeto, sem ser preciso repetir cores widget a widget.
"""
from __future__ import annotations

import customtkinter as ctk

# --------------------------------------------------------------- as cores

FUNDO = "#232323"          # fundo da janela
PAINEL = "#2e2e2e"         # barras de cima e de baixo, molduras
PAINEL_ALTO = "#383838"    # painel dentro de painel
CONTROLO = "#4a4a4a"       # botoes e caixas de texto
CONTROLO_ALTO = "#5c5c5c"  # o mesmo, com o rato por cima
CAIXA = "#1e1e1e"          # fundo das caixas de escrita e da lista
LINHA = "#161616"          # as linhas finas que separam tudo

TEXTO = "#d8d8d8"
TEXTO_FRACO = "#8c8c8c"
TEXTO_ESCURO = "#1a1a1a"   # para escrever por cima do amarelo
TEXTO_CLARO = "#ffffff"    # para escrever por cima do verde

DESTAQUE = "#f2d024"       # o amarelo do Live: so para selecionado/ativo
DESTAQUE_ALTO = "#ffe15c"

SUGESTAO = "#f2d024"       # o texto vindo da Internet, ao lado de cada campo
TAXA_BAIXA = "#ff5c5c"     # musicas abaixo da qualidade minima

VERDE = "#5aa84f"          # accao principal (gravar)
VERDE_ALTO = "#6cbe60"
VERMELHO = "#c25151"       # accao destrutiva (blank, remover capa)
VERMELHO_ALTO = "#d46262"
AVISO = "#e0a02a"

# Realce das linhas da lista.
ALTERADO_FUNDO = "#4a3f12"
ALTERADO_TEXTO = "#f2d024"
ERRO_FUNDO = "#4a2020"
ERRO_TEXTO = "#ff9a9a"

# --------------------------------------------------------------- a letra

# O Live usa uma letra estreita e tecnica. O Bahnschrift (que vem com o
# Windows 10 e 11) e o que mais se aproxima; se nao existir, cai para as do
# costume, e a app fica na mesma - so menos parecida.
FAMILIAS = ["Bahnschrift SemiCondensed", "Bahnschrift", "Segoe UI Semilight",
            "Segoe UI", "Tahoma", "Arial"]
_familia = None


def familia() -> str:
    """A primeira letra da lista que exista neste computador.

    A lista de letras instaladas so pode ser pedida ao tkinter quando ja
    existe uma janela. Como o tema e aplicado antes de a janela principal ser
    criada, abre-se aqui uma janela temporaria e escondida so para perguntar.
    Sem isto a resposta vinha vazia e caia-se sempre na letra de reserva.
    """
    global _familia
    if _familia is not None:
        return _familia

    import tkinter as tk
    from tkinter import font as tkfont

    temporaria = None
    try:
        if tk._default_root is None:
            temporaria = tk.Tk()
            temporaria.withdraw()
        disponiveis = set(tkfont.families())
    except Exception:
        disponiveis = set()
    finally:
        if temporaria is not None:
            try:
                temporaria.destroy()
            except Exception:
                pass

    if not disponiveis:
        return "Segoe UI"          # nao se guarda: para tentar outra vez
    _familia = next((f for f in FAMILIAS if f in disponiveis), "Segoe UI")
    return _familia


def fonte(tamanho=12, negrito=False) -> ctk.CTkFont:
    return ctk.CTkFont(family=familia(), size=tamanho,
                       weight="bold" if negrito else "normal")


def titulo(tamanho=11) -> ctk.CTkFont:
    """Para os cabecalhos de seccao, que vao em maiusculas."""
    return ctk.CTkFont(family=familia(), size=tamanho, weight="bold")


# ------------------------------------------------------------- aplicacao

def _par(cor):
    """O customtkinter quer sempre [claro, escuro]; aqui e sempre o mesmo."""
    return [cor, cor]


def aplicar():
    """Poe o tema de pe. Chamar antes de criar a janela principal."""
    ctk.set_appearance_mode("dark")     # o Live nao tem modo claro
    ctk.set_default_color_theme("blue")  # base, logo a seguir substituida

    t = ctk.ThemeManager.theme

    t["CTk"]["fg_color"] = _par(FUNDO)
    t["CTkToplevel"]["fg_color"] = _par(FUNDO)

    t["CTkFrame"].update({
        "corner_radius": 0,
        "border_width": 1,
        "fg_color": _par(PAINEL),
        "top_fg_color": _par(PAINEL_ALTO),
        "border_color": _par(LINHA),
    })

    t["CTkButton"].update({
        "corner_radius": 0,
        "border_width": 1,
        "fg_color": _par(CONTROLO),
        "hover_color": _par(CONTROLO_ALTO),
        "border_color": _par(LINHA),
        "text_color": _par(TEXTO),
        "text_color_disabled": _par("#666666"),
    })

    t["CTkLabel"].update({
        "corner_radius": 0,
        "fg_color": "transparent",
        "text_color": _par(TEXTO),
    })

    t["CTkEntry"].update({
        "corner_radius": 0,
        "border_width": 1,
        "fg_color": _par(CAIXA),
        "border_color": _par(LINHA),
        "text_color": _par(TEXTO),
        "placeholder_text_color": _par("#6e6e6e"),
    })

    t["CTkCheckBox"].update({
        "corner_radius": 0,
        "border_width": 2,
        "fg_color": _par(DESTAQUE),          # marcada = amarelo
        "border_color": _par("#6a6a6a"),
        "hover_color": _par(DESTAQUE_ALTO),
        "checkmark_color": _par(TEXTO_ESCURO),
        "text_color": _par(TEXTO),
        "text_color_disabled": _par("#666666"),
    })

    t["CTkOptionMenu"].update({
        "corner_radius": 0,
        "fg_color": _par(CONTROLO),
        "button_color": _par(PAINEL_ALTO),
        "button_hover_color": _par(CONTROLO_ALTO),
        "text_color": _par(TEXTO),
        "text_color_disabled": _par("#666666"),
    })

    t["CTkProgressBar"].update({
        "corner_radius": 0,
        "border_width": 1,
        "fg_color": _par(CAIXA),
        "progress_color": _par(DESTAQUE),
        "border_color": _par(LINHA),
    })

    t["CTkScrollbar"].update({
        "corner_radius": 0,
        "fg_color": _par(CAIXA),
        "button_color": _par("#484848"),
        "button_hover_color": _par(CONTROLO_ALTO),
    })

    t["CTkTextbox"].update({
        "corner_radius": 0,
        "border_width": 1,
        "fg_color": _par(CAIXA),
        "border_color": _par(LINHA),
        "text_color": _par(TEXTO),
        "scrollbar_button_color": _par("#484848"),
        "scrollbar_button_hover_color": _par(CONTROLO_ALTO),
    })

    t["CTkScrollableFrame"]["label_fg_color"] = _par(PAINEL_ALTO)

    # As listas que se abrem a partir do menu de hipoteses.
    t["DropdownMenu"].update({
        "fg_color": _par(PAINEL_ALTO),
        "hover_color": _par(CONTROLO),
        "text_color": _par(TEXTO),
    })

    # A letra por omissao de todos os widgets. Nesta versao do customtkinter
    # o CTkFont e um dicionario simples (family/size/weight), nao um por
    # sistema operativo - por isso mexe-se so na familia.
    if isinstance(t.get("CTkFont"), dict) and "family" in t["CTkFont"]:
        t["CTkFont"]["family"] = familia()
        t["CTkFont"]["size"] = 12


def estilizar_tabela(estilo, nome="Musica.Treeview"):
    """A lista de musicas e um widget do tkinter antigo: pinta-se a parte.

    Sem isto ficava um retangulo branco no meio de uma janela escura.
    """
    try:
        estilo.theme_use("clam")     # o unico tema do ttk que aceita cores
    except Exception:
        pass

    estilo.configure(nome,
                     background=CAIXA, fieldbackground=CAIXA, foreground=TEXTO,
                     rowheight=28, borderwidth=0, font=(familia(), 10))
    estilo.configure(f"{nome}.Heading",
                     background=PAINEL_ALTO, foreground=TEXTO_FRACO,
                     relief="flat", borderwidth=1,
                     font=(familia(), 9, "bold"))

    # O fundo e a letra tem de ser sempre definidos em conjunto: mudar so um
    # deixa texto claro sobre fundo claro, e a linha fica ilegivel.
    estilo.map(f"{nome}.Heading",
               background=[("active", CONTROLO), ("pressed", CONTROLO)],
               foreground=[("active", TEXTO), ("pressed", TEXTO)])
    # Selecionado = amarelo com letra escura, como as faixas escolhidas no Live.
    estilo.map(nome,
               background=[("selected", DESTAQUE)],
               foreground=[("selected", TEXTO_ESCURO)])

    estilo.configure("Vertical.TScrollbar",
                     background=CONTROLO, troughcolor=CAIXA,
                     bordercolor=LINHA, arrowcolor=TEXTO_FRACO,
                     relief="flat")
    estilo.map("Vertical.TScrollbar",
               background=[("active", CONTROLO_ALTO)])
