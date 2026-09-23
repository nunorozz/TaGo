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
"""Interface grafica da app de metadata de musicas.

Fluxo pensado para o utilizador: escolhe uma pasta, carrega em Analisar, ve as
tags atuais, pede sugestoes a Internet, corrige o que quiser, e so depois
carrega em Gravar. Nada e escrito nos ficheiros sem esse ultimo passo.
"""
from __future__ import annotations

import queue
import sys
import threading
import traceback
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import armazenamento
import dados
import identidade
import escritor
import fonte_discogs
import fonte_spotify
import identificador
import leitor
import ondas
import relatorios
import scanner
import tema
from metadata import (CAMPOS_EDITAVEIS, CAMPOS_REMOVIDOS, ETIQUETAS, capa_do_ficheiro,
                      duracao_texto, tamanho_texto)

# O aspeto (ao estilo do Ableton Live) tem de ser posto de pe antes de se
# criar qualquer widget - e o que faz os botoes e caixas nascerem ja certos.
tema.aplicar()

COLUNAS_TABELA = [
    ("marca", "", 34),
    ("ficheiro", "File", 240),
    ("artista", "Artist", 175),
    ("titulo", "Title", 190),
    ("album", "Album", 170),
    ("ano", "Year", 50),
    ("duracao", "Length", 70),
    ("formato", "Fmt", 50),
    ("bitrate", "Bitrate", 80),
    ("tamanho", "Size", 80),
    ("qualidade", "Quality", 110),
]

MARCADO = "☑"      # caixa com visto
DESMARCADO = "☐"   # caixa vazia

# Campos sem botao "blank": nunca interessa deixa-los vazios, e e deles que
# sai o nome do ficheiro.
SEM_BLANK = {"artista", "titulo"}

# Qualidade minima aceitavel. Abaixo disto o valor aparece a vermelho, na
# lista e na linha de detalhes da musica escolhida.
MINIMO_KBPS = 320
BOA = "GOOD TO PLAY"
MA = "BAD TO PLAY"


def _taxa_baixa(ficha) -> bool:
    """A musica esta abaixo da qualidade minima?

    Um ficheiro sem bitrate conhecido (0) nao conta como fraco: nao se sabe
    nada dele, e marca-lo a vermelho seria um aviso falso.
    """
    taxa = ficha.get("bitrate") or 0
    return 0 < round(taxa / 1000) < MINIMO_KBPS


class App(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.definicoes = armazenamento.carregar()

        self.title(f"{identidade.NOME} {identidade.VERSAO} - {identidade.DESCRICAO}")
        self._por_icone()
        self.geometry(self._geometria_inicial())
        self.minsize(980, 600)

        self.fichas: list[dict] = []
        self.por_id: dict[str, dict] = {}
        self.ficha_atual: dict | None = None
        self.fila: queue.Queue = queue.Queue()
        # Ja nao ha botao de Cancel: este sinal so serve para os fios de
        # trabalho pararem quando se fecha a janela.
        self.cancelar = threading.Event()
        self.a_trabalhar = False
        # Modo automatico: o botao I'M FEELING LAZY poe isto a True e o
        # fluxo (scan -> procura -> aplicar -> gravar) vai avancando sozinho
        # a cada passo que termina, em _processar_fila. Um erro poe-o a False.
        self.automatico = False
        self.entradas: dict[str, ctk.CTkEntry] = {}
        self.sugestoes_txt: dict[str, ctk.CTkLabel] = {}
        self.botoes_undo: dict[str, ctk.CTkButton] = {}
        # Uma imagem por caixa de capa, e uma para a ampliacao. Sao precisas
        # porque o tkinter nao segura sozinho as imagens que mostra: sem uma
        # referencia nossa, a imagem era recolhida e a caixa ficava vazia.
        # Guardadas por caixa (e nao numa lista que so cresce) para a imagem
        # antiga poder ser libertada quando a caixa muda de conteudo.
        self.imagens_capa_ref: dict = {}
        self._imagem_ampliada = None
        self._a_tocar = ""          # caminho da musica que esta a tocar
        self._vigia = None          # o "after" que vigia o fim da musica

        self._construir()
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.after(100, self._processar_fila)

        ultima = self.definicoes.get("ultima_pasta", "")
        if ultima and Path(ultima).is_dir():
            self.var_pasta.set(ultima)

    def _por_icone(self):
        """O logo na barra de titulo e na barra de tarefas.

        No Windows quem serve e o .ico, que leva varios tamanhos dentro. Fora
        dele o `iconbitmap` nao le esse formato, e o caminho e o PNG pelo
        `iconphoto` - no macOS o icone do Dock vem do bundle e nao daqui, mas
        isto ainda serve para quando a app corre a partir do codigo.

        Nunca deve impedir a app de abrir: se o ficheiro faltar ou o sistema
        recusar o icone, fica o icone normal do tkinter e segue-se.
        """
        if sys.platform == "win32":
            icone = dados.recurso("tago.ico")
            if icone.exists():
                try:
                    self.iconbitmap(default=str(icone))
                    return
                except Exception:
                    pass

        logo = dados.recurso("logo.png")
        if not logo.exists():
            return
        try:
            # A referencia tem de ficar guardada: se o PhotoImage for recolhido
            # pelo Python, o tkinter fica com um icone vazio.
            self._icone_janela = tk.PhotoImage(file=str(logo))
            self.iconphoto(True, self._icone_janela)
        except Exception:
            pass

    ALTURA_LOGO = 30

    def _por_logo(self, pai):
        """O logo no canto da barra de cima. Sem ele, a app abre na mesma.

        Usa-se a versao recortada (`logo_barra`), sem o fundo escuro: o do
        icone tem quase metade da altura vazia, e a esta escala a palavra
        TAGO ficava ilegivel.
        """
        caminho = dados.recurso("logo_barra.png")
        if not caminho.exists():
            return
        try:
            from PIL import Image
            imagem = Image.open(caminho)
            largura = round(imagem.width * self.ALTURA_LOGO / imagem.height)
            self._logo = ctk.CTkImage(light_image=imagem, dark_image=imagem,
                                      size=(largura, self.ALTURA_LOGO))
        except Exception:
            return
        ctk.CTkLabel(pai, image=self._logo, text="").pack(side="left")

    def _geometria_inicial(self) -> str:
        """Nunca abrir maior do que o ecra: com escalas do Windows a 125% ou
        150%, a area util e bem menor do que a resolucao nominal."""
        guardada = self.definicoes.get("janela", "")
        largura, altura = 1240, 820
        if "x" in guardada:
            try:
                l, a = guardada.split("+")[0].split("x")
                largura, altura = int(l), int(a)
            except ValueError:
                pass
        max_l = self.winfo_screenwidth() - 60
        max_a = self.winfo_screenheight() - 120     # margem para a barra de tarefas
        largura, altura = min(largura, max_l), min(altura, max_a)
        # Posicao fixa perto do topo: deixada ao sistema, a janela era colocada
        # baixa demais e o rodape acabava escondido pela barra de tarefas.
        esquerda = max(0, (self.winfo_screenwidth() - largura) // 2)
        return f"{largura}x{altura}+{esquerda}+20"

    # ------------------------------------------------------------ interface

    def _construir(self):
        self.grid_columnconfigure(0, weight=1)
        # O painel de detalhe tem uma altura minima garantida: e nele que estao
        # os botoes da capa, que nao podem ficar cortados em ecras mais baixos.
        self.grid_rowconfigure(2, weight=1, minsize=180)   # tabela
        self.grid_rowconfigure(3, weight=1, minsize=300)   # painel de detalhe

        self._construir_topo()
        self._construir_acoes()
        self._construir_tabela()
        self._construir_detalhe()
        self._construir_rodape()

    # Os dois passos principais levam a mesma largura, cada um na sua barra.
    LARGURA_PASSO = 190

    def _construir_topo(self):
        barra = ctk.CTkFrame(self, corner_radius=0)
        barra.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        barra.grid_columnconfigure(1, weight=1)

        canto = ctk.CTkFrame(barra, fg_color="transparent", border_width=0)
        canto.grid(row=0, column=0, padx=(12, 10), pady=8)
        self._por_logo(canto)
        ctk.CTkLabel(canto, text="FOLDER", font=tema.titulo(),
                     text_color=tema.TEXTO_FRACO).pack(side="left", padx=(8, 0))

        self.var_pasta = ctk.StringVar()
        ctk.CTkEntry(barra, textvariable=self.var_pasta, height=28,
                     font=tema.fonte(12),
                     placeholder_text="Pick the folder with the music you want to work on").grid(
            row=0, column=1, sticky="ew", pady=10)

        ctk.CTkButton(barra, text="Browse...", width=110, height=28,
                      font=tema.fonte(12),
                      command=self._escolher_pasta).grid(row=0, column=2, padx=8, pady=10)

        # O I'M FEELING LAZY faz o percurso inteiro sem parar: analisa a
        # pasta, marca todas as musicas, procura as tags, aceita a primeira
        # sugestao de cada uma, poe o nome "Artista - Titulo (Mistura)" e
        # grava. So pergunta uma vez, antes de escrever nos ficheiros. Fica
        # aqui, na ponta da barra da pasta: escolhe-se a pasta e carrega-se
        # ao lado, sem passar pelos passos um a um.
        self.btn_auto = ctk.CTkButton(
            barra, text="I'M FEELING LAZY", width=self.LARGURA_PASSO, height=30,
            font=tema.titulo(12),
            fg_color=tema.VERDE, hover_color=tema.VERDE_ALTO,
            text_color=tema.TEXTO_CLARO, command=self._auto)
        self.btn_auto.grid(row=0, column=3, padx=(0, 14), pady=10)

    def _construir_acoes(self):
        barra = ctk.CTkFrame(self, corner_radius=0)
        barra.grid(row=1, column=0, sticky="ew")
        barra.grid_columnconfigure(3, weight=1)

        # Toda a barra numa linha so: os dois passos principais a abrir, a
        # barra de progresso a seguir, o estado a ocupar o meio e as chaves na
        # ponta. Ja nao ha caixas para escolher onde procurar - procura-se
        # sempre em todas as fontes que tenham as chaves postas.
        # Os dois botoes amarelos da janela ficam a par, na mesma barra e pela
        # ordem por que se usam: primeiro o SCAN FOLDER, depois o SEARCH TAGS.
        # Levam a mesma largura - sao passos iguais, sem parecer que um manda
        # mais do que o outro.
        self.btn_analisar = ctk.CTkButton(
            barra, text="SCAN FOLDER", width=self.LARGURA_PASSO, height=30,
            font=tema.titulo(12),
            fg_color=tema.DESTAQUE, hover_color=tema.DESTAQUE_ALTO,
            text_color=tema.TEXTO_ESCURO, command=self._analisar)
        self.btn_analisar.grid(row=0, column=0, padx=(14, 6), pady=10)

        self.btn_identificar = ctk.CTkButton(
            barra, text="SEARCH TAGS", width=self.LARGURA_PASSO, height=30,
            font=tema.titulo(12),
            fg_color=tema.DESTAQUE, hover_color=tema.DESTAQUE_ALTO,
            text_color=tema.TEXTO_ESCURO,
            # Comeca desligado (so se pode procurar depois de analisar), e o
            # customtkinter apaga sozinho a letra dos botoes desligados. Sem
            # isto, ficava com a letra mais fraca do que o Scan Folder.
            text_color_disabled=tema.TEXTO_ESCURO,
            command=self._identificar, state="disabled")
        self.btn_identificar.grid(row=0, column=1, padx=(0, 6), pady=10)

        self.progresso = ctk.CTkProgressBar(barra, width=240, height=10)
        self.progresso.set(0)
        self.progresso.grid(row=0, column=2, padx=12, pady=10)

        self.var_estado = ctk.StringVar(value="")
        ctk.CTkLabel(barra, textvariable=self.var_estado, anchor="w",
                     font=tema.fonte(12), text_color=tema.TEXTO_FRACO).grid(
            row=0, column=3, sticky="ew", padx=(6, 14))

        # O botao das chaves fica na ponta direita: so se mexe nele uma vez,
        # no principio, e no meio do resto so estava a atrapalhar.
        self.btn_chaves = ctk.CTkButton(barra, text="Set up keys", width=145,
                                        height=26, font=tema.fonte(12),
                                        command=self._configurar_chaves)
        self.btn_chaves.grid(row=0, column=4, padx=(0, 14), pady=10)

        # Este aviso fica: diz de que fontes faltam as chaves, e portanto em
        # que fontes a procura nao vai passar. Sem ele so se perceberia o
        # problema ao carregar em Search Tags. Fica por baixo, e nao ao lado,
        # para nao empurrar nada quando aparece e desaparece.
        self.var_aviso_fontes = ctk.StringVar(value="")
        ctk.CTkLabel(barra, textvariable=self.var_aviso_fontes, anchor="w",
                     font=tema.fonte(11), text_color=tema.AVISO).grid(
            row=1, column=0, columnspan=5, sticky="ew", padx=14, pady=(0, 6))
        self._mudou_fontes()

    def _construir_tabela(self):
        moldura = ctk.CTkFrame(self)
        moldura.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 6))
        moldura.grid_columnconfigure(0, weight=1)
        moldura.grid_rowconfigure(1, weight=1)

        topo = ctk.CTkFrame(moldura, fg_color="transparent", border_width=0)
        topo.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 0))
        ctk.CTkLabel(topo, text="TRACKS IN THE FOLDER", font=tema.titulo(),
                     text_color=tema.TEXTO_FRACO).pack(side="left", padx=(2, 12))

        # No canto oposto, a procura dentro da pasta. Nao vai a Internet: so
        # esconde da lista as musicas que nao tem aquelas letras no nome, no
        # artista, no titulo, no album ou no ano. Campo vazio = ve-se tudo.
        # Empacotados pela direita e por isso ao contrario: o botao primeiro,
        # para ficar mesmo no canto, e a caixa a seguir, a esquerda dele.
        self.var_procura = ctk.StringVar(value="")
        ctk.CTkButton(topo, text="Search", width=90, height=26,
                      font=tema.fonte(12),
                      command=self._procurar_na_lista).pack(side="right")
        caixa_procura = ctk.CTkEntry(
            topo, textvariable=self.var_procura, width=240, height=26,
            font=tema.fonte(12),
            placeholder_text="filter by name, artist, title, album, year")
        caixa_procura.pack(side="right", padx=6)
        # Filtra enquanto se escreve, e o Enter faz o mesmo que o botao - para
        # quem escreve e carrega logo em Enter sem olhar para o lado.
        caixa_procura.bind("<KeyRelease>", lambda e: self._procurar_na_lista())
        caixa_procura.bind("<Return>", lambda e: self._procurar_na_lista())
        # Escape limpa e volta a mostrar a pasta toda.
        caixa_procura.bind("<Escape>", lambda e: self._limpar_procura())

        self._estilo_tabela()
        # "tree headings" (em vez de so "headings") acende a coluna especial
        # da esquerda, que e a unica que aceita uma imagem por linha. E la que
        # vai o botao de tocar.
        self.tabela = ttk.Treeview(
            moldura, columns=[c[0] for c in COLUNAS_TABELA],
            show="tree headings", selectmode="browse", style="Musica.Treeview")
        self._criar_icones()
        self.tabela.heading("#0", text="")
        # A largura leva o espaco do indicador a somar: a lista desenha a
        # imagem depois dele, e sem esta folga a ponta da forma de onda ficava
        # cortada - os ultimos segundos da musica nao se conseguiam clicar.
        largura_zero = self.COLUNA_L + self.ESPACO_INDICADOR
        self.tabela.column("#0", width=largura_zero, minwidth=largura_zero,
                           stretch=False, anchor="w")
        for chave, titulo, largura in COLUNAS_TABELA:
            self.tabela.heading(chave, text=titulo,
                                command=lambda c=chave: self._ordenar(c))
            self.tabela.column(chave, width=largura,
                               anchor="center" if chave in ("marca", "ano", "duracao",
                                                            "formato", "bitrate",
                                                            "tamanho",
                                                            "qualidade") else "w")
        self.tabela.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        scroll = ttk.Scrollbar(moldura, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=scroll.set)
        scroll.grid(row=1, column=1, sticky="ns", pady=6, padx=(0, 6))

        # A lista fica limpa: a UNICA linha com fundo pintado e a que esta
        # selecionada. As musicas com alteracoes por gravar, e as com erro,
        # distinguem-se apenas pela cor das letras - assim continua a ver-se
        # o que esta por gravar sem a lista ficar cheia de barras.
        self.tabela.tag_configure("alterado", foreground=tema.ALTERADO_TEXTO)
        self.tabela.tag_configure("erro", foreground=tema.ERRO_TEXTO)

        self.tabela.bind("<<TreeviewSelect>>", self._mudou_selecao)
        self.tabela.bind("<Button-1>", self._clique_tabela)

        # Marcar tudo / desmarcar tudo fica por baixo da lista: e sobre a lista
        # que agem, e assim ficam ao pe do que mudam em vez de na linha do
        # titulo. Os dois com a mesma largura - sao o mesmo gesto, ao contrario.
        rodape_lista = ctk.CTkFrame(moldura, fg_color="transparent",
                                    border_width=0)
        rodape_lista.grid(row=2, column=0, columnspan=2, sticky="ew",
                          padx=6, pady=(0, 6))
        LARGURA_MARCAR = 124
        ctk.CTkButton(rodape_lista, text="Select all", width=LARGURA_MARCAR,
                      height=26, font=tema.fonte(12),
                      command=lambda: self._marcar_todas(True)).pack(side="left")
        ctk.CTkButton(rodape_lista, text="Select none", width=LARGURA_MARCAR,
                      height=26, font=tema.fonte(12),
                      command=lambda: self._marcar_todas(False)).pack(
            side="left", padx=6)

    def _estilo_tabela(self):
        tema.estilizar_tabela(ttk.Style())

    # A coluna da esquerda leva, numa so imagem: o botao de tocar e, a seguir,
    # a forma de onda da musica. E uma imagem so porque uma linha da lista so
    # aceita uma imagem - e por isso que o clique tem de ser desmontado pela
    # posicao do rato (ver _clique_tabela).
    ICONE = 18          # lado do botao de tocar
    ONDA_L = 168        # largura da forma de onda
    ONDA_A = 24         # altura da forma de onda
    BARRAS = 56         # quantas barras tem o desenho (3 pixeis cada)
    INTERVALO = 5       # espaco entre o botao e a onda
    COLUNA_L = ICONE + INTERVALO + ONDA_L + 8
    # Folga para o espaco que a lista reserva a esquerda de cada linha (ver
    # _inicio_da_imagem). So serve para a coluna ser larga que baste; onde a
    # imagem comeca mesmo e perguntado a lista, nao adivinhado daqui.
    ESPACO_INDICADOR = 24

    def _criar_icones(self):
        """Prepara os desenhos do botao de tocar e de parar.

        Sao desenhados em codigo, e nao lidos de ficheiros de imagem, para a
        app nao depender de imagens soltas que se possam perder.
        """
        from PIL import Image, ImageDraw

        def quadrado(desenhar_simbolo):
            lado = self.ICONE
            img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            # Quadrado amarelo de cantos vivos, como o resto da app. O
            # contorno escuro e preciso: a linha selecionada tambem fica
            # amarela, e sem ele o botao desaparecia dentro dela.
            d.rectangle([0, 0, lado - 1, lado - 1],
                        fill=tema.DESTAQUE, outline=tema.TEXTO_ESCURO, width=1)
            desenhar_simbolo(d, lado)
            return img

        def triangulo(d, lado):
            m = lado * 0.28
            d.polygon([(m, m * 0.85), (m, lado - m * 0.85), (lado - m * 0.9, lado / 2)],
                      fill=tema.TEXTO_ESCURO)

        def barra(d, lado):
            m = lado * 0.31
            d.rectangle([m, m, lado - m - 1, lado - m - 1], fill=tema.TEXTO_ESCURO)

        self._botao_tocar = quadrado(triangulo)
        self._botao_parar = quadrado(barra)
        self._imagens_linha = {}      # iid -> a imagem que la esta agora
        self._ondas_pedidas = set()   # ondas a ser calculadas NESTE momento

        # Duas de cada vez. Cada onda manda o VLC descodificar a musica; com
        # uma pasta grande, lancar tudo ao mesmo tempo poria dezenas de VLC
        # a disputar a maquina, e alguns falhavam.
        #
        # As tarefas correm em duas linhas de trabalho "daemon": quando se
        # fecha a app, elas morrem com ela. Ficaram assim de proposito - com
        # a fila normal do Python, a janela fechava mas o programa continuava
        # a correr por tras a espera que as ondas acabassem.
        self._fila_ondas: queue.Queue = queue.Queue()
        for n in range(2):
            threading.Thread(target=self._trabalhar_ondas, daemon=True,
                             name=f"onda{n}").start()

    def _trabalhar_ondas(self):
        while True:
            tarefa = self._fila_ondas.get()
            try:
                tarefa()
            except Exception:
                pass          # uma onda que falhe nunca deve parar a fila

    @staticmethod
    def _reduzir(valores, quantos):
        """Junta os valores em menos barras, ficando com o pico de cada grupo.

        Usa-se o pico (e nao a media) para os momentos altos nao se perderem
        na juncao - e o que mantem a forma reconhecivel.
        """
        if len(valores) <= quantos:
            return valores
        tamanho = len(valores) / quantos
        return [max(valores[int(i * tamanho):max(int((i + 1) * tamanho),
                                                 int(i * tamanho) + 1)])
                for i in range(quantos)]

    def _cor(self, texto: str, alfa=255):
        """De "#rrggbb" para o formato que o desenho usa."""
        t = texto.lstrip("#")
        return (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16), alfa)

    def _desenhar_linha(self, ficha, progresso=0.0):
        """A imagem da coluna da esquerda: botao + forma de onda."""
        from PIL import Image, ImageDraw, ImageTk

        a_tocar = ficha["caminho"] == self._a_tocar
        altura = max(self.ICONE, self.ONDA_A)
        img = Image.new("RGBA", (self.COLUNA_L, altura), (0, 0, 0, 0))

        botao = self._botao_parar if a_tocar else self._botao_tocar
        img.paste(botao, (0, (altura - self.ICONE) // 2), botao)

        d = ImageDraw.Draw(img)
        x0 = self.ICONE + self.INTERVALO
        meio = altura / 2
        onda = ficha.get("onda")

        # Fundo da barra, para se perceber onde se pode clicar mesmo antes de
        # a forma de onda estar calculada.
        d.rectangle([x0, 0, x0 + self.ONDA_L - 1, altura - 1],
                    fill=self._cor(tema.CAIXA))

        limite = x0 + int(self.ONDA_L * progresso)
        if onda:
            # Menos barras e mais grossas do que os valores guardados: com uma
            # barra por valor, 150 riscos em 168 pixeis liam-se como um borrao.
            barras = self._reduzir(onda, self.BARRAS)
            largura = self.ONDA_L / len(barras)
            for i, valor in enumerate(barras):
                x = x0 + i * largura
                metade = max(0.5, valor * (altura / 2 - 2))
                # O que ja passou fica amarelo; o resto fica cinzento.
                cor = tema.DESTAQUE if (a_tocar and x <= limite) else "#7a7a7a"
                d.rectangle([x, meio - metade, x + largura - 1.4, meio + metade],
                            fill=self._cor(cor))
        else:
            # Ainda sem forma de onda: uma linha ao meio, que ja serve de
            # barra de progresso e mostra que da para clicar.
            d.rectangle([x0, meio - 1, x0 + self.ONDA_L - 1, meio],
                        fill=self._cor("#4a4a4a"))
            if a_tocar:
                d.rectangle([x0, meio - 1, limite, meio], fill=self._cor(tema.DESTAQUE))

        if a_tocar:
            # A agulha, para se ver bem onde vai a musica.
            d.rectangle([limite, 0, limite + 1, altura - 1],
                        fill=self._cor(tema.TEXTO))

        return ImageTk.PhotoImage(img)

    # Largura da coluna do artwork. Tem de dar para a capa atual e para as
    # quatro colunas de sugestoes a seguir, sem apertar.
    LARGURA_ARTWORK = 530
    # Folga entre as caixas das capas e a borda do painel, para nao ficarem
    # em cima da linha.
    MARGEM_ARTWORK = 10

    def _construir_detalhe(self):
        moldura = ctk.CTkFrame(self)
        moldura.grid(row=3, column=0, sticky="nsew", padx=12, pady=6)
        moldura.grid_columnconfigure(0, weight=1)
        # A coluna do artwork nao estica, mas tem um minimo garantido: e ela
        # que fixa a largura do painel das capas. Sem isto, a coluna encolhia
        # ate ao tamanho do que la estava dentro e o width= da moldura era
        # ignorado.
        moldura.grid_columnconfigure(1, minsize=self.LARGURA_ARTWORK)
        moldura.grid_rowconfigure(1, weight=1)

        # A linha de cima leva as mesmas margens do quadro dos campos que fica
        # por baixo, e nada dela passa para o lado do artwork: comeca e acaba
        # exatamente onde esse quadro comeca e acaba. Os botoes do nome estao
        # na propria linha, a direita - e por isso que a caixa do nome ficou
        # mais curta do que era.
        cabeca = ctk.CTkFrame(moldura, fg_color="transparent", border_width=0)
        cabeca.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=(8, 2))
        cabeca.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(cabeca, text="FILE", anchor="w", font=tema.titulo(),
                     text_color=tema.TEXTO_FRACO).grid(row=0, column=0, padx=(0, 10))

        # O nome do ficheiro e editavel: a mudanca so acontece no disco quando
        # se carrega em Gravar Metadata, como tudo o resto.
        self.entrada_ficheiro = ctk.CTkEntry(cabeca, height=28, font=tema.fonte(12))
        self.entrada_ficheiro.grid(row=0, column=1, sticky="ew")
        self.entrada_ficheiro.bind("<KeyRelease>", lambda e: self._editou_nome())

        # A linha de detalhes vai em tres pedacos porque o do meio - o bitrate -
        # muda de cor sozinho quando a musica esta abaixo de MINIMO_KBPS. Uma
        # etiqueta so tem uma cor para o texto todo, dai a divisao.
        detalhe = ctk.CTkFrame(cabeca, fg_color="transparent", border_width=0)
        detalhe.grid(row=0, column=2, padx=(12, 0))

        self.var_detalhe = ctk.StringVar(value="No track selected")
        ctk.CTkLabel(detalhe, textvariable=self.var_detalhe, anchor="w",
                     font=tema.fonte(11),
                     text_color=tema.TEXTO_FRACO).pack(side="left")

        self.var_bitrate = ctk.StringVar(value="")
        self.etiqueta_bitrate = ctk.CTkLabel(
            detalhe, textvariable=self.var_bitrate, anchor="w",
            font=tema.fonte(11), text_color=tema.TEXTO_FRACO)
        self.etiqueta_bitrate.pack(side="left")

        self.var_detalhe_fim = ctk.StringVar(value="")
        ctk.CTkLabel(detalhe, textvariable=self.var_detalhe_fim, anchor="w",
                     font=tema.fonte(11),
                     text_color=tema.TEXTO_FRACO).pack(side="left")

        # Depois de aceitar as sugestoes, este botao poe o nome do ficheiro
        # igual as tags: "Artista - Titulo".
        ctk.CTkButton(cabeca, text="Rename file", width=100,
                      height=28, font=tema.fonte(12),
                      command=self._nome_pelas_tags).grid(
            row=0, column=3, padx=(12, 0))

        # Desfaz o botao do lado, repondo o nome que la estava antes.
        self.botao_undo_nome = ctk.CTkButton(
            cabeca, text="Undo", width=60, height=28, state="disabled",
            font=tema.fonte(12), command=self._desfazer_nome)
        self.botao_undo_nome.grid(row=0, column=4, padx=(6, 0))

        # Quadro normal, e nao um com barra de deslocamento: os campos cabem
        # todos, e a barra ao lado dos botoes so estava a ocupar espaco.
        campos = ctk.CTkFrame(moldura, height=170)
        # Folga em cima para a primeira linha nao ficar colada ao campo do
        # nome do ficheiro, que esta mesmo por cima.
        campos.grid(row=1, column=0, sticky="nsew", padx=(12, 6), pady=(8, 10))
        # As colunas que esticam sao as duas que levam texto: a caixa de
        # edicao (1) e a sugestao (5). Pelo meio delas ficam os tres botoes de
        # cada campo, que sao sempre do mesmo tamanho.
        campos.grid_columnconfigure(1, weight=1)
        campos.grid_columnconfigure(5, weight=1)

        # De um lado o que esta gravado no ficheiro, do outro o que veio da
        # Internet - cada coluna com o seu nome por cima, para se perceber de
        # imediato qual e qual.
        ctk.CTkLabel(campos, text="ORIGINAL FILE TAGS", font=tema.titulo(),
                     text_color=tema.TEXTO_FRACO).grid(
            row=0, column=1, sticky="w", padx=6, pady=(8, 2))

        self.var_cabecalho_sugestao = ctk.StringVar(value="SUGGESTED FROM THE INTERNET")
        ctk.CTkLabel(campos, textvariable=self.var_cabecalho_sugestao,
                     font=tema.titulo(),
                     text_color=tema.TEXTO_FRACO).grid(
            row=0, column=5, sticky="w", padx=(6, 8), pady=(8, 2))

        # Por cima dos botoes de cada campo, os dois que fazem o mesmo mas para
        # todos de uma vez. Cada um fica exatamente na coluna do seu: o
        # "use all" por cima dos "use", o "undo" por cima dos "undo". Assim
        # ve-se pela vertical o que cada um faz, sem ler.
        # O espaco por baixo e o mesmo que ha entre as linhas de botoes de
        # cada campo (2 em baixo + 2 em cima da linha seguinte). A folga de
        # cima e para os botoes nao ficarem encostados ao rebordo do quadro; as
        # etiquetas do lado levam a mesma, para a linha nao ficar desalinhada.
        self.botao_usar_tudo = ctk.CTkButton(
            campos, text="use all", width=52, height=26, font=tema.fonte(11),
            command=self._usar_tudo)
        self.botao_usar_tudo.grid(row=0, column=2, sticky="ew",
                                  padx=(2, 2), pady=(8, 2))

        self.botao_undo_tudo = ctk.CTkButton(
            campos, text="undo all", width=52, height=26, font=tema.fonte(11),
            state="disabled", command=self._desfazer_tudo)
        self.botao_undo_tudo.grid(row=0, column=4, sticky="ew",
                                  padx=(2, 2), pady=(8, 2))

        for i, campo in enumerate(CAMPOS_EDITAVEIS, start=1):
            ctk.CTkLabel(campos, text=ETIQUETAS[campo].upper(), anchor="e", width=120,
                         font=tema.fonte(11), text_color=tema.TEXTO_FRACO).grid(
                row=i, column=0, sticky="e", padx=(4, 8), pady=2)

            entrada = ctk.CTkEntry(campos, height=26, font=tema.fonte(12))
            entrada.grid(row=i, column=1, sticky="ew", padx=6, pady=2)
            entrada.bind("<KeyRelease>", lambda e, c=campo: self._editou(c))
            # Guarda-se o valor de quando se comeca a escrever, para o undo
            # poder repor tudo o que se escreveu de uma vez - e nao letra a
            # letra, que nao serviria de nada.
            entrada.bind("<FocusIn>", lambda e, c=campo: self._guardar_anterior(c))
            self.entradas[campo] = entrada

            # Os tres botoes ficam todos juntos entre a caixa e a sugestao: e
            # ali que se mexe no campo, e o "use" aponta mesmo do que veio da
            # Internet para dentro da caixa.
            ctk.CTkButton(campos, text="use", width=52, height=26,
                          font=tema.fonte(11),
                          command=lambda c=campo: self._usar_sugestao(c)).grid(
                row=i, column=2, padx=(2, 2), pady=2)

            # O artista e o titulo nao levam "blank": sao os dois campos que
            # nunca interessa deixar vazios, e e deles que sai o nome do
            # ficheiro. Evita-se assim apaga-los por engano.
            if campo not in SEM_BLANK:
                ctk.CTkButton(campos, text="blank", width=58, height=26,
                              font=tema.fonte(11),
                              hover_color=tema.VERMELHO,
                              command=lambda c=campo: self._apagar_campo(c)).grid(
                    row=i, column=3, padx=(2, 2), pady=2)

            botao = ctk.CTkButton(campos, text="undo", width=52, height=26,
                                  font=tema.fonte(11), state="disabled",
                                  command=lambda c=campo: self._desfazer_campo(c))
            botao.grid(row=i, column=4, padx=(2, 2), pady=2)
            self.botoes_undo[campo] = botao

            sugestao = ctk.CTkLabel(campos, text="", anchor="w", font=tema.fonte(12),
                                    text_color=tema.SUGESTAO)
            sugestao.grid(row=i, column=5, sticky="ew", padx=(6, 8), pady=2)
            self.sugestoes_txt[campo] = sugestao

        lateral = ctk.CTkFrame(moldura, width=self.LARGURA_ARTWORK)
        lateral.grid(row=1, column=1, sticky="nsew", padx=(6, 12), pady=(8, 10))
        # As duas: os filhos daqui usam pack, e o grid_propagate sozinho so
        # trava quem usa grid. Sem o pack_propagate, a moldura encolhia ate ao
        # tamanho do que la esta dentro e as caixas ficavam coladas a borda.
        lateral.grid_propagate(False)
        lateral.pack_propagate(False)

        # Ja nao ha menu de hipoteses: fica a melhor sugestao de cada fonte,
        # a que tem mais confianca. Qual foi diz-se no cabecalho da coluna das
        # sugestoes ("SUGGESTED BY ..."); o resto corrige-se a mao.
        ctk.CTkLabel(lateral, text="ARTWORK - CLICK TO PICK", font=tema.titulo(),
                     text_color=tema.TEXTO_FRACO).pack(pady=(10, 2))

        # A capa que o ficheiro ja tem fica a esquerda, sozinha e grande: e a
        # que esta em jogo, e e com ela que as outras se comparam. As oito
        # hipoteses ficam ao lado, numa grelha de quatro por linha, todas do
        # mesmo tamanho. Clicar numa escolhe-a (so fica gravada no fim).
        #
        # Lado a lado, e nao umas por cima das outras, porque a altura deste
        # painel e o que e: em pe, as duas linhas de hipoteses nao cabiam sem
        # tirar altura a lista das musicas.
        self.molduras_capa, self.imagens_capa, self.legendas_capa = [], [], []

        def caixa_capa(pai, indice, **colocar):
            lado = self.LADOS_CAPA[indice]
            moldura = ctk.CTkFrame(pai, fg_color="transparent", border_width=0)
            if "row" in colocar:
                moldura.grid(padx=2, pady=1, **colocar)
            else:
                moldura.pack(side="left", padx=2)
            imagem = ctk.CTkLabel(moldura, text="-", width=lado, height=lado,
                                  font=tema.fonte(12),
                                  text_color=tema.TEXTO_FRACO,
                                  fg_color=tema.CAIXA)
            imagem.pack(padx=3, pady=(3, 1))
            legenda = ctk.CTkLabel(moldura, text="", height=13,
                                   text_color=tema.TEXTO_FRACO,
                                   font=tema.fonte(10))
            legenda.pack(padx=3, pady=(0, 3))
            for widget in (imagem, legenda):
                widget.bind("<Button-1>", lambda e, k=indice: self._escolher_capa_slot(k))
            imagem.bind("<Enter>", lambda e, k=indice: self._ampliar_capa(k))
            imagem.bind("<Leave>", lambda e: self._fechar_ampliacao())
            self.molduras_capa.append(moldura)
            self.imagens_capa.append(imagem)
            self.legendas_capa.append(legenda)

        corpo = ctk.CTkFrame(lateral, fg_color="transparent", border_width=0)
        corpo.pack(padx=self.MARGEM_ARTWORK, pady=(0, 2))

        atual = ctk.CTkFrame(corpo, fg_color="transparent", border_width=0)
        atual.pack(side="left", padx=(0, 6), anchor="n")
        caixa_capa(atual, 0)

        grelha = ctk.CTkFrame(corpo, fg_color="transparent", border_width=0)
        grelha.pack(side="left", anchor="n")
        for indice in range(1, self.N_SUGESTOES_CAPA + 1):
            caixa_capa(grelha, indice,
                       row=(indice - 1) // self.CAPAS_POR_LINHA,
                       column=(indice - 1) % self.CAPAS_POR_LINHA)

        self.var_capa_estado = ctk.StringVar(value="")
        ctk.CTkLabel(lateral, textvariable=self.var_capa_estado, height=15,
                     font=tema.fonte(11), text_color=tema.TEXTO_FRACO,
                     wraplength=self.LARGURA_ARTWORK - 30).pack(pady=(0, 2))

        botoes_capa = ctk.CTkFrame(lateral, fg_color="transparent", border_width=0)
        botoes_capa.pack(pady=(0, 6))
        # Os dois iguais e pequenos: sao as duas maneiras de mexer na capa, e
        # nenhuma manda mais do que a outra. Pequenos porque quem manda neste
        # painel sao as capas - estes so la estao para quando fazem falta.
        LARGURA_CAPA = 118
        ctk.CTkButton(botoes_capa, text="Pick image from PC",
                      width=LARGURA_CAPA, height=24, font=tema.fonte(11),
                      command=self._escolher_capa).pack(side="left", padx=(0, 4))

        # Deixa a musica sem capa nenhuma. Como tudo o resto, so mexe mesmo no
        # ficheiro no Gravar Metadata.
        self.btn_remover_capa = ctk.CTkButton(
            botoes_capa, text="Remove artwork", width=LARGURA_CAPA, height=24,
            font=tema.fonte(11), hover_color=tema.VERMELHO,
            command=self._remover_capa)
        self.btn_remover_capa.pack(side="left", padx=(4, 0))

    def _construir_rodape(self):
        barra = ctk.CTkFrame(self, corner_radius=0)
        barra.grid(row=4, column=0, sticky="ew")

        self.btn_gravar = ctk.CTkButton(
            barra, text="SAVE TAGS and GO", width=225, height=34,
            font=tema.titulo(13),
            fg_color=tema.VERDE, hover_color=tema.VERDE_ALTO,
            text_color=tema.TEXTO_CLARO,
            command=self._gravar, state="disabled")
        self.btn_gravar.pack(side="left", padx=(14, 8), pady=10)

        # A GPL pede que um programa interativo mostre os avisos legais a quem
        # o usa. E o que esta janela faz. Fica no canto oposto ao Save Tags:
        # e o botao que nunca se quer carregar por engano.
        ctk.CTkButton(barra, text="About", width=80, height=34,
                      font=tema.fonte(12),
                      command=self._sobre).pack(side="right", padx=(4, 14),
                                                pady=10)

        self.var_resumo = ctk.StringVar(value="")
        ctk.CTkLabel(barra, textvariable=self.var_resumo, anchor="e",
                     font=tema.fonte(12), text_color=tema.TEXTO_FRACO).pack(
            side="right", padx=14)

    # ------------------------------------------------------------- utilidades

    def _fontes_escolhidas(self) -> list[str]:
        """Procura-se sempre em todas as fontes que estejam prontas a usar."""
        return [nome for nome in self._ordem_das_fontes()
                if identificador.FONTES[nome].disponivel()]

    # A ordem por que as fontes aparecem na barra. E so a ordem de quem ve: a
    # ordem de preferencia quando as fontes empatam continua a ser a do
    # identificador.py, que nao se mexe daqui.
    ORDEM_FONTES = ("Beatport", "Spotify", "Discogs", "MusicBrainz")

    def _ordem_das_fontes(self) -> list[str]:
        """As fontes pela ordem de cima, sem perder nenhuma se um dia mudarem."""
        conhecidas = list(identificador.FONTES)
        ordenadas = [n for n in self.ORDEM_FONTES if n in conhecidas]
        return ordenadas + [n for n in conhecidas if n not in ordenadas]

    def _mudou_fontes(self):
        por_configurar = [nome for nome in self._ordem_das_fontes()
                          if not identificador.FONTES[nome].disponivel()]
        self.var_aviso_fontes.set(
            f"{', '.join(por_configurar)}: keys not set up yet"
            if por_configurar else "")
        por_ligar = [n for n in ("Spotify", "Discogs")
                     if not identificador.FONTES[n].disponivel()]
        self.btn_chaves.configure(
            text="Set up keys" if por_ligar else "Keys are set up")

    def _configurar_chaves(self):
        """Spotify e Discogs precisam de chaves gratuitas que so o utilizador
        pode criar. O Beatport e a MusicBrainz nao precisam de nada."""
        janela = ctk.CTkToplevel(self)
        janela.title("Search source keys")
        janela.geometry("620x620")
        janela.transient(self)
        janela.grab_set()

        var_resultado = ctk.StringVar(value="")

        # ------------------------------------------------------------ Spotify
        caixa_s = ctk.CTkFrame(janela)
        caixa_s.pack(fill="x", padx=14, pady=(14, 8))

        ctk.CTkLabel(caixa_s, text="SPOTIFY", font=tema.titulo(13),
                     text_color=tema.DESTAQUE).pack(anchor="w",
                                                    padx=12, pady=(8, 0))
        ctk.CTkLabel(
            caixa_s, justify="left", wraplength=560,
            text="1. Go to  developer.spotify.com/dashboard  and sign in with your "
                 "usual account.\n"
                 "2. 'Create app'. Any name and description will do.\n"
                 "3. For 'Redirect URI' put  http://localhost  (it is never used, "
                 "but the form requires it).\n"
                 "4. Tick 'Web API' and create.\n"
                 "5. Under Settings, copy the Client ID and Client Secret here."
        ).pack(anchor="w", padx=12, pady=(2, 6))

        id_atual, segredo_atual = fonte_spotify.credenciais()
        ctk.CTkLabel(caixa_s, text="Client ID").pack(anchor="w", padx=12)
        entrada_id = ctk.CTkEntry(caixa_s, width=560)
        entrada_id.insert(0, id_atual)
        entrada_id.pack(padx=12, pady=(0, 4))
        ctk.CTkLabel(caixa_s, text="Client Secret").pack(anchor="w", padx=12)
        entrada_segredo = ctk.CTkEntry(caixa_s, width=560, show="*")
        entrada_segredo.insert(0, segredo_atual)
        entrada_segredo.pack(padx=12, pady=(0, 10))

        # ------------------------------------------------------------ Discogs
        caixa_d = ctk.CTkFrame(janela)
        caixa_d.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(caixa_d, text="DISCOGS", font=tema.titulo(13),
                     text_color=tema.DESTAQUE).pack(anchor="w",
                                                    padx=12, pady=(8, 0))
        ctk.CTkLabel(
            caixa_d, justify="left", wraplength=560,
            text="1. Go to  discogs.com/settings/developers  and sign in.\n"
                 "2. Click 'Generate new token'.\n"
                 "3. Copy the token here."
        ).pack(anchor="w", padx=12, pady=(2, 6))

        ctk.CTkLabel(caixa_d, text="Personal token").pack(anchor="w", padx=12)
        entrada_token = ctk.CTkEntry(caixa_d, width=560, show="*")
        entrada_token.insert(0, fonte_discogs.token())
        entrada_token.pack(padx=12, pady=(0, 10))

        ctk.CTkLabel(
            janela, wraplength=580, text_color=tema.TEXTO_FRACO, justify="left",
            text="The keys are kept on this computer only, in credenciais.json. "
                 "They give no access to your accounts - they only search public "
                 "catalogues. You can fill in just one of the two."
        ).pack(padx=16, pady=(2, 4), anchor="w")

        ctk.CTkLabel(janela, textvariable=var_resultado, wraplength=580).pack()

        def gravar():
            cid = entrada_id.get().strip()
            segredo = entrada_segredo.get().strip()
            tok = entrada_token.get().strip()
            feitos, problemas = [], []

            if cid and segredo:
                var_resultado.set("Checking with Spotify...")
                janela.update_idletasks()
                ok, mensagem = fonte_spotify.testar_credenciais(cid, segredo)
                if ok:
                    fonte_spotify.guardar_credenciais(cid, segredo)
                    feitos.append("Spotify")
                else:
                    problemas.append(f"Spotify: {mensagem}")
            elif cid or segredo:
                problemas.append("Spotify: one of the two fields is missing")

            if tok:
                var_resultado.set("Checking with Discogs...")
                janela.update_idletasks()
                ok, mensagem = fonte_discogs.testar_token(tok)
                if ok:
                    fonte_discogs.guardar_token(tok)
                    feitos.append("Discogs")
                else:
                    problemas.append(f"Discogs: {mensagem}")

            if not feitos and not problemas:
                var_resultado.set("Nothing filled in.")
                return

            identificador.limpar_cache()
            self._mudou_fontes()
            if problemas:
                var_resultado.set(" | ".join(problemas))
                if feitos:
                    messagebox.showinfo("Keys", f"Saved: {', '.join(feitos)}.")
                return

            janela.destroy()
            messagebox.showinfo("Keys",
                                f"Saved and working: {', '.join(feitos)}.")

        botoes = ctk.CTkFrame(janela, fg_color="transparent", border_width=0)
        botoes.pack(pady=10)
        ctk.CTkButton(botoes, text="Test and save", height=30,
                      fg_color=tema.DESTAQUE, hover_color=tema.DESTAQUE_ALTO,
                      text_color=tema.TEXTO_ESCURO,
                      command=gravar).pack(side="left", padx=6)
        ctk.CTkButton(botoes, text="Close", height=30,
                      command=janela.destroy).pack(side="left", padx=6)

        janela.after(200, janela.lift)

    def _escolher_pasta(self):
        inicial = self.var_pasta.get() or str(Path.home())
        pasta = filedialog.askdirectory(title="Pick the folder with the music",
                                        initialdir=inicial)
        if pasta:
            self.var_pasta.set(pasta)
            armazenamento.guardar(ultima_pasta=pasta)
            self._analisar()

    def _ocupado(self, sim: bool):
        self.a_trabalhar = sim
        estado = "disabled" if sim else "normal"
        self.btn_analisar.configure(state=estado)
        self.btn_auto.configure(state=estado)
        self.btn_identificar.configure(
            state="normal" if (not sim and self.fichas) else "disabled")
        self.btn_gravar.configure(
            state="normal" if (not sim and self.fichas) else "disabled")

    # ----------------------------------------------------------------- analise

    def _analisar(self):
        pasta = self.var_pasta.get().strip()
        if not pasta or not Path(pasta).is_dir():
            messagebox.showwarning("Invalid folder",
                                   "Pick a folder that exists first.")
            return
        if self.a_trabalhar:
            return

        armazenamento.guardar(ultima_pasta=pasta)
        self.cancelar.clear()
        self._ocupado(True)
        self.progresso.set(0)
        self.var_estado.set("Reading the files...")

        def trabalho():
            try:
                fichas = scanner.analisar(
                    pasta,
                    progresso=lambda i, t, n: self.fila.put(("progresso", (i, t, n))),
                    cancelado=self.cancelar.is_set,
                )
                self.fila.put(("analise_pronta", fichas))
            except Exception:
                self.fila.put(("erro", traceback.format_exc()))

        threading.Thread(target=trabalho, daemon=True).start()

    def _identificar(self):
        if not self.fichas or self.a_trabalhar:
            return
        alvos = [f for f in self.fichas if f["marcado"] and not f.get("erro")]
        if not alvos:
            alvos = [f for f in self.fichas if not f.get("erro")]
        if not alvos:
            return

        fontes = self._fontes_escolhidas()
        if not fontes:
            messagebox.showwarning(
                "No sources",
                "There is no search source ready to use.\n\n"
                "Click 'Set up keys' and enter the keys first.")
            return

        self.cancelar.clear()
        self._ocupado(True)
        self.progresso.set(0)
        self.var_estado.set(f"Searching {' and '.join(fontes)}...")

        def trabalho():
            try:
                total = len(alvos)
                ativas = list(fontes)
                seguidas: dict[str, int] = {}

                for i, ficha in enumerate(alvos, start=1):
                    if self.cancelar.is_set():
                        break

                    avarias: list[tuple[str, str]] = []
                    try:
                        sugestoes = identificador.identificar(
                            ficha, fontes=ativas, falhas=avarias)
                        if sugestoes:
                            identificador.preencher_genero(sugestoes[0])
                    except identificador.SemLigacao:
                        sugestoes = []
                    except Exception:
                        sugestoes = []

                    # Uma fonte avariada nao pode parar a identificacao das
                    # restantes musicas: ao fim de tres falhas seguidas,
                    # desliga-se para o resto desta passagem e avisa-se.
                    fontes_com_avaria = {f for f, _ in avarias}
                    for nome in list(ativas):
                        if nome in fontes_com_avaria:
                            seguidas[nome] = seguidas.get(nome, 0) + 1
                            if seguidas[nome] >= 3:
                                ativas.remove(nome)
                                motivo = next(m for f, m in avarias if f == nome)
                                self.fila.put(("fonte_desligada", (nome, motivo)))
                        else:
                            seguidas[nome] = 0

                    if not ativas:
                        self.fila.put((
                            "erro_ligacao",
                            "No source is answering. Check your Internet "
                            "connection."))
                        break
                    self.fila.put(("sugestoes", (ficha["caminho"], sugestoes)))

                    # A capa vem sozinha, para o utilizador nao ter de a ir
                    # buscar musica a musica. So para ficheiros que ainda nao
                    # tem capa: nunca substituimos uma que ja la esteja.
                    if sugestoes and not ficha.get("tem_capa"):
                        dados = identificador.descarregar_capa(sugestoes[0])
                        if dados:
                            self.fila.put(("capa", (ficha["caminho"], dados)))

                    self.fila.put(("progresso", (i, total, ficha["ficheiro"])))
                self.fila.put(("identificacao_pronta", None))
            except Exception:
                self.fila.put(("erro", traceback.format_exc()))

        threading.Thread(target=trabalho, daemon=True).start()

    # ------------------------------------------------------------- automatico

    # Campos que o modo automatico esvazia sempre. Nao e falta de informacao:
    # o album que as fontes devolvem e o da edicao onde a faixa calhou sair, e
    # o comentario vem cheio de lixo de quem exportou o ficheiro.
    CAMPOS_AUTO_VAZIOS = ("album", "comentario")

    def _auto(self):
        """Faz tudo de seguida: scan, procura, aceitar sugestoes, nome, gravar.

        Cada passo corre num fio e avisa pela fila quando acaba; e ai, em
        _processar_fila, que se passa ao passo seguinte enquanto
        self.automatico estiver ligado.
        """
        if self.a_trabalhar:
            return
        if not self._fontes_escolhidas():
            messagebox.showwarning(
                "No sources",
                "There is no search source ready to use.\n\n"
                "Click 'Set up keys' and enter the keys first.")
            return
        self.automatico = True
        self._analisar()
        # _analisar recusa-se (pasta invalida) sem passar pela fila: nao se
        # pode ficar com o modo ligado a espera de um passo que nao vem.
        if not self.a_trabalhar:
            self.automatico = False

    def _auto_depois_de_analisar(self):
        if not self.fichas:
            self.automatico = False
            return
        self._marcar_todas(True)
        self._identificar()
        if not self.a_trabalhar:
            self.automatico = False

    def _auto_depois_de_procurar(self):
        self.automatico = False
        sem_sugestao = []
        sem_nome = []
        for ficha in self.fichas:
            if not ficha["marcado"]:
                continue
            sugestoes = ficha.get("sugestoes") or []
            if not sugestoes:
                sem_sugestao.append(ficha["ficheiro"])
                ficha["marcado"] = False
                self._atualizar_linha(ficha)
                continue
            sugestao = sugestoes[0]
            for campo in CAMPOS_EDITAVEIS:
                valor = sugestao.get(campo, "")
                if valor:
                    ficha["valores"][campo] = valor
            # A tag Title diz o mesmo que o nome do ficheiro: leva sempre a
            # mistura no fim, e "(Original Mix)" quando a sugestao nao traz
            # nenhuma.
            ficha["valores"]["titulo"] = escritor.titulo_com_mistura(
                ficha["valores"].get("titulo", ""))
            # Estes vao vazios de proposito: um campo vazio, ao gravar, apaga
            # a tag do ficheiro.
            for campo in self.CAMPOS_AUTO_VAZIOS:
                ficha["valores"][campo] = ""
            try:
                ficha["nome_novo"] = escritor.nome_com_mistura(
                    ficha["valores"].get("artista", ""),
                    ficha["valores"].get("titulo", ""), ficha["caminho"])
            except escritor.ErroEscrita as e:
                # As tags dessa musica gravam-se na mesma; o nome e que fica
                # como esta. Ninguem adivinha isso a olhar para a tabela, por
                # isso vai para o aviso do fim.
                ficha["nome_novo"] = ""
                sem_nome.append(f"{ficha['ficheiro']}: {e}")
            if ficha["nome_novo"] == ficha["ficheiro"]:
                ficha["nome_novo"] = ""
            self._atualizar_linha(ficha)

        repetidos = self._auto_largar_nomes_repetidos()

        # As caixas do painel mostram ainda os valores antigos; se ficassem
        # assim, o _guardar_edicoes de _gravar escrevia-os por cima.
        if self.ficha_atual:
            self._mostrar_detalhe(self.ficha_atual)

        # Tudo o que o AUTO nao conseguiu fazer sai num aviso so, antes de se
        # perguntar se se grava: e a ultima vez que se pode dizer que nao.
        avisos = []
        if sem_sugestao:
            avisos.append(
                f"{len(sem_sugestao)} tracks got no suggestion and are not "
                "going to be touched:\n" + self._lista_curta(sem_sugestao))
        if sem_nome:
            avisos.append(
                f"{len(sem_nome)} tracks keep the file name they have (the "
                "tags are saved all the same):\n" + self._lista_curta(sem_nome))
        if repetidos:
            avisos.append(
                f"{len(repetidos)} tracks keep the file name they have, "
                "because two of them would end up with the same one:\n"
                + self._lista_curta(repetidos))
        if avisos:
            messagebox.showwarning("Left out", "\n\n".join(avisos))
        self._gravar()

    def _auto_largar_nomes_repetidos(self) -> list[str]:
        """Larga as renomeacoes que dariam dois ficheiros com o mesmo nome.

        O escritor.nome_com_mistura so sabe o que ja esta no disco; nao sabe
        dos nomes que as outras musicas deste mesmo lote estao a pedir. Sem
        isto, dois ficheiros com a mesma sugestao pediam o mesmo nome: o
        primeiro renomeava e o segundo rebentava a meio da gravacao, ja com as
        tags escritas.

        Compara-se contra os nomes que vao existir no fim - o nome novo de
        quem muda, o de agora de quem nao muda - e larga-se uma renomeacao de
        cada vez, recomecando: largar uma devolve o nome antigo a lista dos
        ocupados, e isso pode desfazer o encaixe da seguinte.
        """
        largadas: list[str] = []
        while True:
            ocupados = {f["ficheiro"].lower() for f in self.fichas
                        if not f.get("nome_novo")}
            for ficha in self.fichas:
                novo = ficha.get("nome_novo")
                if not novo:
                    continue
                if novo.lower() in ocupados:
                    largadas.append(f"{ficha['ficheiro']}  ->  {novo}")
                    ficha["nome_novo"] = ""
                    self._atualizar_linha(ficha)
                    break
                ocupados.add(novo.lower())
            else:
                return largadas

    @staticmethod
    def _lista_curta(nomes, quantos: int = 12) -> str:
        """A lista para dentro de um aviso, cortada quando e comprida demais."""
        lista = "\n".join(f"  - {n}" for n in nomes[:quantos])
        if len(nomes) > quantos:
            lista += f"\n  ... and {len(nomes) - quantos} more"
        return lista

    def _processar_fila(self):
        try:
            while True:
                tipo, dados = self.fila.get_nowait()

                if tipo == "progresso":
                    feitos, total, nome = dados
                    self.progresso.set(feitos / total if total else 0)
                    self.var_estado.set(f"{feitos} of {total} - {nome}")

                elif tipo == "analise_pronta":
                    self._receber_fichas(dados)
                    if self.automatico:
                        self._auto_depois_de_analisar()

                elif tipo == "sugestoes":
                    caminho, sugestoes = dados
                    ficha = next((f for f in self.fichas if f["caminho"] == caminho), None)
                    if ficha is not None:
                        ficha["sugestoes"] = sugestoes
                        ficha["indice_sugestao"] = 0
                        # As capas em cache eram das hipoteses da procura
                        # anterior. Sem as largar, a caixa 3 (por exemplo)
                        # passava a dizer a fonte nova mas continuava a
                        # mostrar - e a dar, a quem la clicasse - a imagem da
                        # procura antiga.
                        ficha["capas_sugeridas"] = {}
                        ficha["capas_a_caminho"] = set()
                        # Se a capa por gravar tinha vindo de uma dessas
                        # caixas, deixa de ter dono: larga-se, como ja se
                        # larga a sugestao de tags escolhida. Uma capa
                        # escolhida do PC, ou a marca de remover, nao vem das
                        # hipoteses e fica.
                        if isinstance(ficha.get("capa_escolhida"), int)                                 and ficha["capa_escolhida"] > 0:
                            ficha["capa_nova"] = None
                            ficha["capa_escolhida"] = 0
                        self._atualizar_linha(ficha)

                elif tipo == "capa":
                    caminho, dados = dados
                    ficha = next((f for f in self.fichas if f["caminho"] == caminho), None)
                    if ficha is not None and ficha.get("capa_nova") is None:
                        ficha["capa_nova"] = dados
                        ficha["capa_escolhida"] = 1
                        ficha.setdefault("capas_sugeridas", {})[1] = dados
                        self._atualizar_linha(ficha)
                        if ficha is self.ficha_atual:
                            self._mostrar_capas(ficha)

                elif tipo == "capa_slot":
                    caminho, indice, dados = dados
                    ficha = next((f for f in self.fichas if f["caminho"] == caminho), None)
                    if ficha is not None:
                        ficha.setdefault("capas_sugeridas", {})[indice] = dados
                        # Chegou: sai da lista do que vai a caminho.
                        ficha.setdefault("capas_a_caminho", set()).discard(indice)
                        if ficha is self.ficha_atual:
                            self._mostrar_capas(ficha)

                elif tipo == "identificacao_pronta":
                    self._ocupado(False)
                    capas = sum(1 for f in self.fichas if f.get("capa_nova") is not None)
                    self.var_estado.set(
                        "Suggestions ready"
                        + (f" ({capas} artwork images found)" if capas else "")
                        + ". Click a track to review and approve.")
                    if self.ficha_atual:
                        self._mostrar_detalhe(self.ficha_atual)
                    if self.automatico:
                        self._auto_depois_de_procurar()

                elif tipo == "fonte_desligada":
                    nome, motivo = dados
                    aviso = (f"{nome} failed three times in a row and was turned "
                             f"off for this search.\n\n{motivo}\n\n"
                             "The other sources carry on as normal.")
                    if nome in identificador.FONTES_FRAGEIS:
                        aviso += ("\n\nThis source uses an unofficial route: it "
                                  "is normal for it to stop working when the "
                                  "site changes.")
                    messagebox.showwarning(f"{nome} unavailable", aviso)

                elif tipo == "erro_ligacao":
                    # A procura parou a meio: as musicas que faltavam nao
                    # sao "sem sugestao", ficaram por procurar. O AUTO nao
                    # pode gravar uma parte e deixar a outra como esta.
                    self.automatico = False
                    messagebox.showwarning(
                        "No connection",
                        f"Could not reach the search sources.\n\n{dados}\n\n"
                        "You can carry on editing the tags by hand.")

                elif tipo == "erro":
                    self.automatico = False
                    self._ocupado(False)
                    messagebox.showerror("Unexpected error", dados)

        except queue.Empty:
            pass
        self.after(100, self._processar_fila)

    def _receber_fichas(self, fichas):
        self.fichas = []
        for f in fichas:
            f["marcado"] = False
            f["sugestoes"] = []
            f["indice_sugestao"] = 0
            f["capa_nova"] = None
            f["capa_escolhida"] = 0          # 0 = fica a capa que ja la esta
            f["capas_sugeridas"] = {}
            f["capas_a_caminho"] = set()
            f["nome_novo"] = ""
            f["valores"] = {c: f.get(c, "") for c in CAMPOS_EDITAVEIS}
            f["originais"] = dict(f["valores"])
            self.fichas.append(f)

        self._ocupado(False)
        self._preencher_tabela()
        self.var_estado.set(
            f"{len(self.fichas)} files read."
            + (" Click Search Tags." if self.fichas else "")
        )
        if not self.fichas:
            messagebox.showinfo(
                "Empty folder",
                "No music files found directly in this folder.\n\n"
                "Remember: the app only looks at the folder you picked, it does "
                "not go into subfolders.")

    # ----------------------------------------------------------------- tabela

    # ------------------------------------------------- procura dentro da pasta

    @staticmethod
    def _texto_de_procura(ficha) -> str:
        """Tudo aquilo por onde se pode procurar uma musica, num so texto."""
        v = ficha["valores"]
        return " ".join(str(x) for x in (
            ficha.get("nome_novo") or ficha["ficheiro"],
            v.get("artista", ""), v.get("titulo", ""),
            v.get("album", ""), v.get("ano", ""))).lower()

    def _fichas_a_mostrar(self) -> list:
        """As musicas que passam no filtro da caixa de procura.

        Sem filtro sao todas. As que ficam de fora **nao sao apagadas**: so
        deixam de se ver na lista, e voltam assim que a caixa fica vazia.
        """
        procura = getattr(self, "var_procura", None)
        palavras = procura.get().strip().lower().split() if procura else []
        if not palavras:
            return list(self.fichas)
        # Varias palavras = tem de ter todas, em qualquer ordem: assim
        # "daft harder" encontra a musica sem se saber de cor o nome inteiro.
        return [f for f in self.fichas
                if all(p in self._texto_de_procura(f) for p in palavras)]

    def _procurar_na_lista(self):
        self._preencher_tabela()

    def _limpar_procura(self):
        self.var_procura.set("")
        self._preencher_tabela()

    def _preencher_tabela(self):
        self.tabela.delete(*self.tabela.get_children())
        self.por_id.clear()
        visiveis = self._fichas_a_mostrar()
        # Comparadas por identidade e nao por conteudo: duas musicas podem ter
        # exatamente as mesmas tags e nao sao a mesma linha.
        a_ver = {id(f) for f in visiveis}
        # Quem fica de fora perde o "iid": aquela linha ja nao existe na
        # tabela, e sem isto o _atualizar_linha ia mexer numa linha apagada.
        for ficha in self.fichas:
            if id(ficha) not in a_ver:
                ficha.pop("iid", None)
        for ficha in visiveis:
            iid = self.tabela.insert("", "end", values=self._valores_linha(ficha),
                                     image=self._icone_da_ficha(ficha))
            ficha["iid"] = iid
            self.por_id[iid] = ficha
            self._aplicar_etiqueta(ficha)
        self._atualizar_resumo()

    @staticmethod
    def _bitrate_texto(ficha) -> str:
        taxa = ficha.get("bitrate") or 0
        return f"{round(taxa / 1000)} kbps" if taxa else ""

    @staticmethod
    def _qualidade_texto(ficha) -> str:
        """A coluna Quality, logo a seguir ao tamanho.

        Fica vazia quando o bitrate nao se consegue ler: dizer que uma musica
        e ma sem se saber nada dela seria um aviso falso.
        """
        if not (ficha.get("bitrate") or 0):
            return ""
        return MA if _taxa_baixa(ficha) else BOA

    def _valores_linha(self, ficha) -> list:
        v = ficha["valores"]
        return [
            MARCADO if ficha["marcado"] else DESMARCADO,
            ficha.get("nome_novo") or ficha["ficheiro"],
            v.get("artista", ""),
            v.get("titulo", ""),
            v.get("album", ""),
            v.get("ano", ""),
            duracao_texto(ficha.get("duracao", 0)),
            ficha.get("formato", ""),
            self._bitrate_texto(ficha),
            tamanho_texto(ficha.get("tamanho", 0)),
            self._qualidade_texto(ficha),
        ]

    def _atualizar_linha(self, ficha):
        if "iid" in ficha and self.tabela.exists(ficha["iid"]):
            self.tabela.item(ficha["iid"], values=self._valores_linha(ficha),
                             image=self._icone_da_ficha(ficha))
            self._aplicar_etiqueta(ficha)
        self._atualizar_resumo()

    def _icone_da_ficha(self, ficha):
        """A imagem da coluna da esquerda, guardada para nao ser deitada fora.

        O tkinter nao segura as imagens: se a referencia se perder, a linha
        fica em branco. Por isso guarda-se cada uma por linha.
        """
        progresso = leitor.posicao() if ficha["caminho"] == self._a_tocar else 0.0
        imagem = self._desenhar_linha(ficha, progresso)
        self._imagens_linha[ficha.get("iid", id(ficha))] = imagem
        self._pedir_onda(ficha)
        return imagem

    def _pedir_onda(self, ficha):
        """Manda calcular a forma de onda em fundo, se ainda nao estiver a ser.

        O conjunto `_ondas_pedidas` guarda APENAS os pedidos que estao a
        decorrer neste momento, e o caminho e retirado assim que acabam. Ja
        foi ao contrario - guardava tudo para sempre - e o resultado era que
        depois de gravar tags (que faz a app reanalisar a pasta) as ondas
        desapareciam todas e nunca mais voltavam.
        """
        if ficha.get("onda") is not None or not ondas.disponivel():
            return
        chave = ficha["caminho"]
        if chave in self._ondas_pedidas:
            return
        self._ondas_pedidas.add(chave)

        def trabalho():
            try:
                valores = ondas.picos(chave)
            except Exception:
                valores = None
            # A interface so pode ser tocada na linha principal.
            self.after(0, lambda: self._onda_pronta(chave, valores))

        self._fila_ondas.put(trabalho)

    def _onda_pronta(self, caminho, valores):
        self._ondas_pedidas.discard(caminho)
        for ficha in self.fichas:
            if ficha["caminho"] == caminho:
                # Lista vazia (e nao None) marca "ja se tentou, nao deu" -
                # senao pedia-se a mesma onda impossivel a cada redesenho.
                ficha["onda"] = valores or []
                if self.tabela.exists(ficha.get("iid", "")):
                    self.tabela.item(ficha["iid"], image=self._icone_da_ficha(ficha))
                return

    def _aplicar_etiqueta(self, ficha):
        # Na linha selecionada nao se poe cor nenhuma nas letras: o fundo da
        # selecao e amarelo, e letras amarelas por cima dele desapareciam.
        if self.tabela.selection() and ficha.get("iid") in self.tabela.selection():
            etiquetas = ()
        elif ficha.get("erro"):
            etiquetas = ("erro",)
        elif self._tem_alteracoes(ficha):
            etiquetas = ("alterado",)
        else:
            etiquetas = ()
        self.tabela.item(ficha["iid"], tags=etiquetas)

    def _tem_alteracoes(self, ficha) -> bool:
        """Alteracoes que o utilizador fez e ainda nao gravou.

        E isto que realca a linha a amarelo. A limpeza da numeracao de faixa
        e disco nao entra aqui de proposito: como se aplica a toda a gente,
        realcar por causa dela pintava a lista inteira e nao dizia nada.
        """
        if (ficha.get("capa_nova") is not None or ficha.get("nome_novo")
                or ficha.get("capa_escolhida") == "remover"):
            return True
        return any(ficha["valores"].get(c, "") != ficha["originais"].get(c, "")
                   for c in CAMPOS_EDITAVEIS)

    def _ha_que_gravar(self, ficha) -> bool:
        """Ha mesmo algo a escrever no ficheiro, realce a parte."""
        return (self._tem_alteracoes(ficha)
                or any(ficha.get(c) for c in CAMPOS_REMOVIDOS))

    def _atualizar_resumo(self):
        marcadas = sum(1 for f in self.fichas if f["marcado"])
        alteradas = sum(1 for f in self.fichas if self._ha_que_gravar(f))
        tamanho = sum(int(f.get("tamanho") or 0) for f in self.fichas)
        fracas = sum(1 for f in self.fichas if _taxa_baixa(f))
        resumo = (f"{len(self.fichas)} tracks | {tamanho_texto(tamanho)} | "
                  f"{marcadas} selected | {alteradas} to save")
        # Com a procura ligada ha musicas escondidas: diz-se quantas se veem,
        # para nao parecer que desapareceram da pasta.
        vistas = len(self.tabela.get_children())
        if vistas != len(self.fichas):
            resumo += f" | showing {vistas}"
        if fracas:
            resumo += f" | {fracas} below {MINIMO_KBPS} kbps"
        self.var_resumo.set(resumo)

    def _clique_tabela(self, evento):
        regiao = self.tabela.identify_region(evento.x, evento.y)

        # O botao de tocar e a forma de onda vivem na coluna especial da
        # esquerda, que o tkinter chama "tree". Como as duas coisas sao uma
        # so imagem, e a posicao do rato que diz em qual delas se carregou.
        if regiao == "tree":
            iid = self.tabela.identify_row(evento.y)
            ficha = self.por_id.get(iid)
            if ficha:
                dentro = evento.x - self._inicio_da_imagem(iid)
                if dentro < self.ICONE + self.INTERVALO / 2:
                    self._alternar_leitura(ficha)
                else:
                    self._saltar_na_onda(ficha, dentro)
            return "break"

        if regiao != "cell":
            return
        if self.tabela.identify_column(evento.x) != "#1":
            return
        iid = self.tabela.identify_row(evento.y)
        ficha = self.por_id.get(iid)
        if ficha:
            ficha["marcado"] = not ficha["marcado"]
            self._atualizar_linha(ficha)
            return "break"

    # ------------------------------------------------------------ ouvir

    def _inicio_da_imagem(self, iid) -> int:
        """Onde comeca mesmo o desenho (botao + onda) dentro daquela linha.

        A lista reserva um espaco a esquerda de cada linha para o sinal de
        abrir/fechar, e so depois desenha a imagem. Esse espaco nao e sempre
        o mesmo - muda com o tema e com o tamanho da letra - por isso
        pergunta-se a lista onde e que a imagem esta, em vez de o adivinhar.

        Adivinha-lo custou caro: a app dava 2 pixeis, o valor real eram 17, e
        o clique no meio do botao de parar caia ja dentro da forma de onda. A
        musica, em vez de parar, saltava para o inicio e continuava a tocar.
        """
        try:
            caixa = self.tabela.bbox(iid, "#0")
        except Exception:
            caixa = None
        if not caixa:
            # A linha nao esta a vista (nem devia ter sido clicada): fica-se
            # pelo ultimo espaco medido.
            return self.MARGEM_IMAGEM
        meio = caixa[1] + caixa[3] // 2
        for x in range(caixa[0], caixa[0] + caixa[2]):
            if self.tabela.identify_element(x, meio) == "image":
                self.MARGEM_IMAGEM = x - caixa[0]
                return x
        return caixa[0] + self.MARGEM_IMAGEM

    # O espaco medido da ultima vez, para quando nao houver como perguntar.
    MARGEM_IMAGEM = 2

    def _saltar_na_onda(self, ficha, dentro_x):
        """Clicar na forma de onda salta para esse ponto da musica."""
        inicio = self.ICONE + self.INTERVALO
        fraccao = (dentro_x - inicio) / self.ONDA_L
        fraccao = min(0.999, max(0.0, fraccao))

        if ficha["caminho"] != self._a_tocar:
            # Ainda nao esta a tocar: comeca a tocar ja nesse ponto.
            self._alternar_leitura(ficha)
            if ficha["caminho"] != self._a_tocar:
                return          # nao arrancou; nada a saltar

        if leitor.saltar_para(fraccao):
            self._repintar_botoes(ficha["caminho"])

    def _alternar_leitura(self, ficha):
        """Carregar no botao: toca esta musica, ou cala-a se ja for esta."""
        if ficha["caminho"] == self._a_tocar:
            self._parar_leitura()
            return
        try:
            como = leitor.tocar(ficha["caminho"])
        except leitor.ErroLeitura as e:
            messagebox.showwarning("Could not play", str(e), parent=self)
            return

        anterior, self._a_tocar = self._a_tocar, ficha["caminho"]
        self._repintar_botoes(anterior, ficha["caminho"])

        if como == "externo":
            # Abriu no leitor de musica do utilizador: daqui nao se controla,
            # por isso o botao nao pode ficar em "a tocar".
            self._a_tocar = ""
            self._repintar_botoes(ficha["caminho"])
            self.var_estado.set(f"{ficha['ficheiro']}: opened in your music player.")
        else:
            self.var_estado.set(f"Playing: {ficha['ficheiro']}")
            self._comecar_a_vigiar()

    def _parar_leitura(self):
        self._parar_de_vigiar()
        leitor.parar()
        anterior, self._a_tocar = self._a_tocar, ""
        if anterior:
            self._repintar_botoes(anterior)
            self.var_estado.set("Stopped.")

    def _repintar_botoes(self, *caminhos):
        for ficha in self.fichas:
            if ficha["caminho"] in caminhos and self.tabela.exists(ficha.get("iid", "")):
                self.tabela.item(ficha["iid"], image=self._icone_da_ficha(ficha))

    # Quanto tempo se da ao leitor para arrancar antes de se acreditar que
    # uma musica acabou. Ao trocar de musica, o VLC passa por um instante em
    # que ainda esta a abrir o ficheiro e responde que nao esta a tocar; sem
    # esta folga, a app dava a musica nova como terminada logo a nascenca.
    ARRANQUE = 1.5

    def _comecar_a_vigiar(self):
        """Fica de olho na musica para o botao voltar sozinho ao fim."""
        import time
        self._parar_de_vigiar()          # nunca mais do que um vigilante
        self._tocar_desde = time.monotonic()
        self._vigia = self.after(500, self._vigiar_leitura)

    def _parar_de_vigiar(self):
        vigia = getattr(self, "_vigia", None)
        if vigia is not None:
            try:
                self.after_cancel(vigia)
            except Exception:
                pass
        self._vigia = None

    def _vigiar_leitura(self):
        """Quando a musica chega ao fim, o botao volta sozinho a "tocar"."""
        import time
        self._vigia = None
        if not self._a_tocar:
            return
        arrancou_ha = time.monotonic() - getattr(self, "_tocar_desde", 0)
        if not leitor.a_tocar() and arrancou_ha > self.ARRANQUE:
            terminada = self._a_tocar
            self._a_tocar = ""
            self._repintar_botoes(terminada)
            self.var_estado.set("Track finished.")
            return
        # Redesenha a linha para a agulha ir andando pela forma de onda.
        self._repintar_botoes(self._a_tocar)
        self._vigia = self.after(250, self._vigiar_leitura)

    def _marcar_todas(self, valor: bool):
        for ficha in self.fichas:
            if valor and ficha.get("erro"):
                continue
            ficha["marcado"] = valor
            self._atualizar_linha(ficha)

    def _ordenar(self, coluna):
        if coluna == "marca" or not self.fichas:
            return
        # Estas leem-se da ficha e nao das tags. O bitrate e o tamanho ordenam
        # pelo numero, nao pelo texto: senao "9 MB" vinha depois de "45 MB".
        # A coluna Quality ordena pelo bitrate, e nao pelas palavras: assim as
        # "BAD TO PLAY" ficam todas juntas, das piores para as melhores.
        chaves = {"ficheiro": "ficheiro", "formato": "formato", "duracao": "duracao",
                  "bitrate": "bitrate", "tamanho": "tamanho", "qualidade": "bitrate"}
        estado = getattr(self, "_ordem_invertida", {})
        invertida = not estado.get(coluna, False)
        estado[coluna] = invertida
        self._ordem_invertida = estado

        def chave(f):
            if coluna in chaves:
                v = f.get(chaves[coluna], "")
                if coluna in ("bitrate", "tamanho", "qualidade"):
                    return int(v or 0)
                return v if isinstance(v, (int, float)) else str(v).lower()
            return str(f["valores"].get(coluna, "")).lower()

        self.fichas.sort(key=chave, reverse=invertida)
        self._preencher_tabela()

    # ---------------------------------------------------------------- detalhe

    def _mudou_selecao(self, _evento=None):
        anterior = self.ficha_atual
        self._guardar_edicoes()
        selecao = self.tabela.selection()
        if not selecao:
            return
        ficha = self.por_id.get(selecao[0])
        if ficha:
            self.ficha_atual = ficha
            # A linha que deixou de estar selecionada volta a poder mostrar a
            # cor de "por gravar"; a nova deixa de a mostrar.
            for f in (anterior, ficha):
                if f is not None and self.tabela.exists(f.get("iid", "")):
                    self._aplicar_etiqueta(f)
            self._mostrar_detalhe(ficha)

    def _guardar_edicoes(self):
        """As caixas de texto sao a fonte da verdade enquanto a linha esta aberta."""
        if not self.ficha_atual:
            return
        for campo, entrada in self.entradas.items():
            self.ficha_atual["valores"][campo] = entrada.get().strip()

        nome = self.entrada_ficheiro.get().strip()
        self.ficha_atual["nome_novo"] = (
            nome if nome and nome != self.ficha_atual["ficheiro"] else "")

        self._atualizar_linha(self.ficha_atual)

    def _editou(self, campo):
        if self.ficha_atual:
            self._guardar_edicoes()
            self._atualizar_undo_campo(campo)

    def _editou_nome(self):
        if self.ficha_atual:
            self._guardar_edicoes()

    def _nome_pelas_tags(self):
        """Poe no campo Ficheiro o nome "Artista - Titulo", a partir das tags.

        Usa o que esta nas caixas neste momento - ou seja, ja com as sugestoes
        que o utilizador aceitou. Como tudo o resto, so muda no disco quando
        se carregar em Gravar Metadata.
        """
        if not self.ficha_atual:
            return
        self._guardar_edicoes()
        valores = self.ficha_atual["valores"]
        try:
            nome = escritor.nome_a_partir_das_tags(
                valores.get("artista", ""), valores.get("titulo", ""),
                self.ficha_atual["caminho"])
        except escritor.ErroEscrita as e:
            messagebox.showwarning("File name", str(e), parent=self)
            return

        # Guarda o que la estava, para o Undo poder repor.
        self.ficha_atual["nome_antes"] = self.entrada_ficheiro.get()
        self._por_no_campo_nome(nome)

    def _desfazer_nome(self):
        """Repoe o nome que estava antes de se carregar em Alterar nome."""
        ficha = self.ficha_atual
        if not ficha or ficha.get("nome_antes") is None:
            return
        anterior = ficha.pop("nome_antes")
        self._por_no_campo_nome(anterior)

    def _por_no_campo_nome(self, nome):
        self.entrada_ficheiro.delete(0, "end")
        self.entrada_ficheiro.insert(0, nome)
        self._guardar_edicoes()
        self._atualizar_botao_undo()

    def _atualizar_botao_undo(self):
        ha_que_desfazer = bool(self.ficha_atual
                               and self.ficha_atual.get("nome_antes") is not None)
        self.botao_undo_nome.configure(
            state="normal" if ha_que_desfazer else "disabled")

    def _mostrar_detalhe(self, ficha):
        self.var_detalhe.set(
            f"{ficha['formato']} | {duracao_texto(ficha.get('duracao', 0))} | ")

        taxa = round((ficha.get("bitrate") or 0) / 1000)
        baixa = _taxa_baixa(ficha)
        veredicto = self._qualidade_texto(ficha)
        self.var_bitrate.set(f"{taxa} kbps" + (f"  {veredicto}" if veredicto else ""))
        self.etiqueta_bitrate.configure(
            text_color=tema.TAXA_BAIXA if baixa else tema.TEXTO_FRACO)

        fim = f" | {tamanho_texto(ficha.get('tamanho', 0))}"
        if ficha.get("erro"):
            fim += f"  |  ERROR: {ficha['erro']}"
        self.var_detalhe_fim.set(fim)

        self.entrada_ficheiro.delete(0, "end")
        self.entrada_ficheiro.insert(0, ficha.get("nome_novo") or ficha["ficheiro"])
        # O Undo e por musica: so fica ativo se esta tiver mesmo o que desfazer.
        self._atualizar_botao_undo()

        for campo, entrada in self.entradas.items():
            entrada.delete(0, "end")
            entrada.insert(0, ficha["valores"].get(campo, ""))
        # O undo de cada campo e por musica: ao mudar de faixa, os botoes
        # passam a reflectir o que ha para desfazer nessa.
        self._atualizar_undo_campo()

        sugestoes = ficha.get("sugestoes") or []
        if sugestoes:
            atual = sugestoes[ficha.get("indice_sugestao", 0)]
            self.var_cabecalho_sugestao.set(
                f"SUGGESTED BY {atual.get('fonte', '?').upper()}"
                + (f"  ({atual['etiqueta']})" if atual.get("etiqueta") else ""))
            for campo, etiqueta in self.sugestoes_txt.items():
                valor = atual.get(campo, "")
                # Todas as sugestoes na mesma cor, mesmo as duvidosas: a duvida
                # continua a ver-se no cabecalho.
                etiqueta.configure(
                    text=valor or "-",
                    text_color=tema.SUGESTAO if valor else tema.TEXTO_FRACO)
        else:
            self.var_cabecalho_sugestao.set("SUGGESTED FROM THE INTERNET")
            for etiqueta in self.sugestoes_txt.values():
                etiqueta.configure(text="", text_color=tema.TEXTO_FRACO)

        self._mostrar_capas(ficha)

    def _sugestao_ativa(self):
        ficha = self.ficha_atual
        if not ficha:
            return None
        sugestoes = ficha.get("sugestoes") or []
        if not sugestoes:
            return None
        return sugestoes[ficha.get("indice_sugestao", 0)]

    # ------------------------------------------------- desfazer campo a campo

    def _anteriores(self) -> dict:
        """Os valores a repor pelo undo, guardados por musica."""
        if not self.ficha_atual:
            return {}
        return self.ficha_atual.setdefault("anterior_campo", {})

    def _guardar_anterior(self, campo):
        """Marca o valor atual como sendo o que o undo repoe."""
        if not self.ficha_atual:
            return
        anteriores = self._anteriores()
        if campo not in anteriores:
            anteriores[campo] = self.entradas[campo].get()
            self._atualizar_undo_campo(campo)

    def _desfazer_campo(self, campo):
        anteriores = self._anteriores()
        if campo not in anteriores:
            return
        valor = anteriores.pop(campo)
        self.entradas[campo].delete(0, "end")
        self.entradas[campo].insert(0, valor)
        self._guardar_edicoes()
        self._atualizar_undo_campo(campo)

    def _atualizar_undo_campo(self, campo=None):
        """Acende o undo so nos campos que tem mesmo algo para desfazer."""
        anteriores = self._anteriores()
        campos = [campo] if campo else list(self.botoes_undo)
        for c in campos:
            botao = self.botoes_undo.get(c)
            if botao is None:
                continue
            # Nao vale a pena acender se o valor guardado e igual ao que la
            # esta: nao havia nada a desfazer.
            ha = c in anteriores and anteriores[c] != self.entradas[c].get()
            botao.configure(state="normal" if ha else "disabled")

        # O undo de cima acende se houver algo para desfazer em qualquer campo.
        geral = getattr(self, "botao_undo_tudo", None)
        if geral is not None:
            algum = any(c in anteriores and anteriores[c] != self.entradas[c].get()
                        for c in self.botoes_undo)
            geral.configure(state="normal" if algum else "disabled")

    def _usar_sugestao(self, campo):
        sugestao = self._sugestao_ativa()
        if not sugestao:
            return
        valor = sugestao.get(campo, "")
        if not valor:
            return
        self._guardar_anterior(campo)
        self.entradas[campo].delete(0, "end")
        self.entradas[campo].insert(0, valor)
        self._guardar_edicoes()
        self._atualizar_undo_campo(campo)

    def _apagar_campo(self, campo):
        """Esvazia o campo. Ao gravar, um campo vazio apaga a tag do ficheiro."""
        if not self.ficha_atual:
            return
        self._guardar_anterior(campo)
        self.entradas[campo].delete(0, "end")
        self._guardar_edicoes()
        self._atualizar_undo_campo(campo)

    def _usar_tudo(self):
        sugestao = self._sugestao_ativa()
        if not sugestao:
            return
        for campo in CAMPOS_EDITAVEIS:
            valor = sugestao.get(campo, "")
            if valor:
                self._guardar_anterior(campo)
                self.entradas[campo].delete(0, "end")
                self.entradas[campo].insert(0, valor)
        self._guardar_edicoes()
        self._atualizar_undo_campo()

    def _desfazer_tudo(self):
        """Desfaz de uma vez o que os undo de cada campo desfariam um a um.

        Serve sobretudo para desfazer o "usar tudo", mas apanha tudo o que
        estiver por desfazer nesta musica - incluindo o que tenhas escrito a
        mao ou apagado com o "blank".
        """
        for campo in list(self.botoes_undo):
            self._desfazer_campo(campo)
        self._atualizar_undo_campo()

    # ------------------------------------------------------------------ capas

    # Quantas hipoteses de capa se mostram, e quantas por linha na grelha.
    # Oito e o limite do que o identificador devolve (LIMITE_CANDIDATOS).
    N_SUGESTOES_CAPA = 8
    CAPAS_POR_LINHA = 4

    # O lado de cada caixa: a atual e bem maior do que as hipoteses, que sao
    # todas iguais entre si.
    LADOS_CAPA = (150,) + (74,) * N_SUGESTOES_CAPA

    def _miniatura(self, dados: bytes, lado: int = 74):
        """A imagem pronta a mostrar. Quem chama e que guarda a referencia."""
        try:
            import io
            from PIL import Image
            imagem = Image.open(io.BytesIO(dados))
            return ctk.CTkImage(light_image=imagem, dark_image=imagem,
                                size=(lado, lado))
        except Exception:
            return None

    def _garantir_capas_sugeridas(self, ficha):
        """Vai buscar, em segundo plano, as capas das melhores hipoteses.

        Cada capa que chega manda repintar o painel, e repintar passa por
        aqui outra vez. Sem o registo do que ja vai a caminho, essa segunda
        passagem lancava um fio novo para as que faltavam - e esse fio, ao
        entregar, lancava outro. Com oito hipoteses eram 255 downloads em vez
        de oito. Por isso um indice so e pedido uma vez.
        """
        sugestoes = (ficha.get("sugestoes") or [])[:self.N_SUGESTOES_CAPA]
        cache = ficha.setdefault("capas_sugeridas", {})
        a_caminho = ficha.setdefault("capas_a_caminho", set())
        pendentes = [(i + 1, s) for i, s in enumerate(sugestoes)
                     if (i + 1) not in cache and (i + 1) not in a_caminho]
        if not pendentes:
            return
        a_caminho.update(indice for indice, _ in pendentes)
        caminho = ficha["caminho"]

        def buscar():
            for indice, sugestao in pendentes:
                dados = identificador.descarregar_capa(sugestao)
                self.fila.put(("capa_slot", (caminho, indice, dados or b"")))

        threading.Thread(target=buscar, daemon=True).start()

    def _mostrar_capas(self, ficha):
        """Desenha as caixas todas: a capa atual e as hipoteses encontradas."""
        cache = ficha.setdefault("capas_sugeridas", {})
        escolhida = ficha.get("capa_escolhida", 0)
        sugestoes = (ficha.get("sugestoes") or [])[:self.N_SUGESTOES_CAPA]

        # Caixa 0: o que esta no ficheiro, a imagem escolhida do PC, ou vazia
        # se a capa estiver marcada para ser removida.
        if escolhida == "remover":
            self._pintar_slot(0, None, "removing")
        elif escolhida == "pc" and ficha.get("capa_nova"):
            self._pintar_slot(0, ficha["capa_nova"], "from your PC")
        else:
            self._pintar_slot(0, capa_do_ficheiro(ficha["caminho"]), "current")

        for indice in range(1, self.N_SUGESTOES_CAPA + 1):
            if indice > len(sugestoes):
                self._pintar_slot(indice, None, "")
                continue
            fonte = sugestoes[indice - 1].get("fonte", "")[:8]
            dados = cache.get(indice)
            if dados is None:
                self._pintar_slot(indice, None, "fetching...")
            elif dados:
                self._pintar_slot(indice, dados, fonte)
            else:
                self._pintar_slot(indice, None, "no artwork")

        for indice, moldura in enumerate(self.molduras_capa):
            ativa = ((indice == 0 and escolhida in (0, "pc", "remover"))
                     or indice == escolhida)
            # A vermelho quando o que esta escolhido e ficar sem capa.
            cor = tema.VERMELHO if escolhida == "remover" else tema.DESTAQUE
            moldura.configure(fg_color=cor if ativa else "transparent")

        if escolhida == "remover":
            self.var_capa_estado.set(
                "artwork to be REMOVED - only goes on Save Tags and Go "
                "(click the box above to cancel)")
        elif ficha.get("capa_nova") is not None:
            self.var_capa_estado.set("NEW artwork - only written on Save Tags and Go")
        elif ficha.get("tem_capa"):
            self.var_capa_estado.set("keeping the artwork already in the file")
        else:
            self.var_capa_estado.set("this file has no artwork")

        self._garantir_capas_sugeridas(ficha)

    def _pintar_slot(self, indice, dados, legenda):
        imagem = self._miniatura(dados, self.LADOS_CAPA[indice]) if dados else None
        caixa = self.imagens_capa[indice]
        # A imagem que esta caixa tinha antes deixa de ser precisa: guardar so
        # a nova deixa a antiga ser libertada.
        if imagem is not None:
            self.imagens_capa_ref[indice] = imagem
            caixa.configure(image=imagem, text="")
        else:
            self.imagens_capa_ref.pop(indice, None)
            caixa.configure(image=None, text="-" if not legenda else "")
            self._limpar_imagem(caixa)
        self.legendas_capa[indice].configure(text=legenda)

    @staticmethod
    def _limpar_imagem(caixa):
        """Deixa a caixa mesmo vazia.

        O customtkinter, quando se lhe passa `image=None`, guarda o None mas
        nao chega a mandar limpar a imagem que ja la estava - so trata do
        caso em que ha imagem nova. O resultado era ficar-se a ver a capa da
        musica anterior numa musica que nao tem capa nenhuma. Limpa-se por
        baixo, na etiqueta que ele usa por dentro.
        """
        try:
            caixa._label.configure(image="")
        except Exception:
            pass          # se um dia mudarem o customtkinter, nao se estraga nada

    # Ampliacao ao passar o rato, sobre o tamanho da caixa: as hipoteses vao a
    # 74 x 5 = 370px. A atual daria 150 x 5 = 750px, que ja nao cabe em muitos
    # ecras - por isso ha um tecto.
    AMPLIACAO = 5
    AMPLIACAO_MAXIMA = 560

    def _dados_do_slot(self, indice) -> bytes | None:
        ficha = self.ficha_atual
        if not ficha:
            return None
        if indice == 0:
            if ficha.get("capa_escolhida") == "remover":
                return None          # marcada para sair: nao ha o que ampliar
            if ficha.get("capa_escolhida") == "pc" and ficha.get("capa_nova"):
                return ficha["capa_nova"]
            return capa_do_ficheiro(ficha["caminho"])
        return ficha.get("capas_sugeridas", {}).get(indice) or None

    def _ampliar_capa(self, indice):
        """Mostra a capa ao dobro do tamanho, ao lado da caixa."""
        self._fechar_ampliacao()
        dados = self._dados_do_slot(indice)
        if not dados:
            return

        lado = min(self.LADOS_CAPA[indice] * self.AMPLIACAO,
                   self.AMPLIACAO_MAXIMA)
        try:
            import io
            from PIL import Image
            imagem = Image.open(io.BytesIO(dados))
            grande = ctk.CTkImage(light_image=imagem, dark_image=imagem,
                                  size=(lado, lado))
        except Exception:
            return

        caixa = self.imagens_capa[indice]
        janela = ctk.CTkToplevel(self)
        janela.overrideredirect(True)          # sem barra de titulo
        janela.attributes("-topmost", True)

        # O customtkinter multiplica pela escala do ecra o TAMANHO que se
        # passa ao geometry(), mas nao a POSICAO. Para saber onde a janela
        # vai mesmo ficar - e nao a deixar sair do ecra - temos de contar
        # com essa escala. Com a ampliacao a 500% isto ja se nota.
        try:
            escala = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            escala = 1.0
        ocupa = int(round((lado + 8) * escala))

        # Por cima da caixa, mas sem sair do ecra.
        x = caixa.winfo_rootx() - (ocupa - caixa.winfo_width()) // 2
        y = caixa.winfo_rooty() - ocupa - 8
        if y < 4:
            # Nao cabe por cima: tenta por baixo.
            y = caixa.winfo_rooty() + caixa.winfo_height() + 8
        x = max(4, min(x, self.winfo_screenwidth() - ocupa - 4))
        y = max(4, min(y, self.winfo_screenheight() - ocupa - 4))
        janela.geometry(f"{lado + 8}x{lado + 8}+{x}+{y}")

        etiqueta = ctk.CTkLabel(janela, image=grande, text="")
        etiqueta.pack(padx=4, pady=4)
        etiqueta.bind("<Button-1>", lambda e, k=indice: self._escolher_capa_slot(k))

        self._imagem_ampliada = grande
        self._ampliacao = janela

    def _fechar_ampliacao(self):
        janela = getattr(self, "_ampliacao", None)
        if janela is not None:
            try:
                janela.destroy()
            except Exception:
                pass
            self._ampliacao = None

    def _escolher_capa_slot(self, indice):
        ficha = self.ficha_atual
        if not ficha:
            return
        if indice == 0:
            ficha["capa_nova"] = None
            ficha["capa_escolhida"] = 0
        else:
            dados = ficha.get("capas_sugeridas", {}).get(indice)
            if not dados:
                return          # ainda a obter, ou esta hipotese nao tem capa
            ficha["capa_nova"] = dados
            ficha["capa_escolhida"] = indice
        self._fechar_ampliacao()
        self._mostrar_capas(ficha)
        self._atualizar_linha(ficha)

    def _remover_capa(self):
        """Marca a musica para ficar sem capa nenhuma.

        Nao mexe no ficheiro agora: fica a marca, a caixa de cima passa a
        dizer "a remover", e a capa so desaparece mesmo no Gravar Metadata.
        Para desistir, clica na caixa de cima (`atual`).
        """
        ficha = self.ficha_atual
        if not ficha:
            return
        if not ficha.get("tem_capa") and not ficha.get("capa_nova"):
            messagebox.showinfo("No artwork",
                                "This track has no artwork to remove.")
            return
        ficha["capa_nova"] = None
        ficha["capa_escolhida"] = "remover"
        self._fechar_ampliacao()
        self._mostrar_capas(ficha)
        self._atualizar_linha(ficha)

    def _escolher_capa(self):
        if not self.ficha_atual:
            return
        caminho = filedialog.askopenfilename(
            title="Pick the artwork image",
            filetypes=[("Images", "*.jpg *.jpeg *.png"), ("All files", "*.*")])
        if not caminho:
            return
        try:
            self.ficha_atual["capa_nova"] = Path(caminho).read_bytes()
        except OSError as e:
            messagebox.showerror("Error", f"Could not read the image:\n{e}")
            return
        self.ficha_atual["capa_escolhida"] = "pc"
        self._mostrar_capas(self.ficha_atual)
        self._atualizar_linha(self.ficha_atual)

    # ---------------------------------------------------------------- gravacao

    def _gravar(self):
        # Enquanto uma musica toca, o ficheiro esta aberto e o Windows nao
        # deixa altera-lo nem mudar-lhe o nome. Cala-se primeiro.
        self._parar_leitura()
        self._guardar_edicoes()
        alvos = [f for f in self.fichas if f["marcado"] and self._ha_que_gravar(f)]

        if not alvos:
            marcadas = sum(1 for f in self.fichas if f["marcado"])
            messagebox.showinfo(
                "Nothing to save",
                "None of the selected tracks has unsaved changes."
                if marcadas else
                "Select the tracks you want to save first, in the box next to "
                "the yellow play button.")
            return

        nomes = "\n".join(f"  - {f['ficheiro']}" for f in alvos[:12])
        if len(alvos) > 12:
            nomes += f"\n  ... and {len(alvos) - 12} more"
        if not messagebox.askyesno(
                "Confirm save",
                f"{len(alvos)} audio files are about to be changed:\n\n{nomes}\n\n"
                "Track number, disc number and album artist are always "
                "removed.\n\n"
                "No copy of the original is kept: this cannot be undone.\n\n"
                "Continue?"):
            return

        gravados, renomeados, falhados = 0, 0, []
        for ficha in alvos:
            try:
                escritor.gravar(
                    ficha["caminho"], ficha["valores"],
                    capa_nova=ficha.get("capa_nova"),
                    remover_capa=ficha.get("capa_escolhida") == "remover")
                gravados += 1
                ficha["originais"] = dict(ficha["valores"])
                for c in CAMPOS_REMOVIDOS:
                    ficha[c] = ""
                ficha["capa_nova"] = None
                ficha["capa_escolhida"] = 0
                ficha["tem_capa"] = bool(capa_do_ficheiro(ficha["caminho"]))
            except Exception as e:
                falhados.append(f"{ficha['ficheiro']}: {e}")
                continue

            # O nome muda no fim: as tags ja estao escritas e a copia de
            # seguranca acompanha o ficheiro.
            if ficha.get("nome_novo"):
                try:
                    novo = escritor.renomear(ficha["caminho"], ficha["nome_novo"])
                    ficha["caminho"] = str(novo)
                    ficha["ficheiro"] = novo.name
                    ficha["nome_novo"] = ""
                    renomeados += 1
                except Exception as e:
                    falhados.append(f"{ficha['ficheiro']} (rename): {e}")

            self._atualizar_linha(ficha)

        if self.ficha_atual:
            self._mostrar_detalhe(self.ficha_atual)

        mensagem = f"{gravados} files saved."
        if renomeados:
            mensagem += f" {renomeados} were renamed."
        if falhados:
            mensagem += "\n\nCould not save:\n" + "\n".join(falhados[:10])
            messagebox.showwarning("Finished with warnings", mensagem)
        else:
            messagebox.showinfo("Saved", mensagem)
        self.var_estado.set(mensagem.splitlines()[0])

    # Nao ha aqui nenhum "reverter", nem ha o que reverter: a app deixou de
    # guardar copias dos ficheiros de audio. Em _backup_tags fica so o
    # historico.log, a dizer o que foi mudado.

    # ------------------------------------------------------------------ sobre

    def _sobre(self):
        """Quem fez a app, sob que licenca, e onde esta o codigo.

        Nao e enfeite: a GPL-3 pede que um programa interativo mostre estes
        avisos a quem o usa, e que se diga a quem recebe o programa que tem
        direito ao codigo-fonte.
        """
        janela = ctk.CTkToplevel(self)
        janela.title(f"About {identidade.NOME}")
        janela.geometry("560x350")
        janela.transient(self)
        janela.grab_set()

        topo = ctk.CTkFrame(janela, fg_color="transparent", border_width=0)
        topo.pack(pady=(18, 4))
        self._por_logo(topo)
        ctk.CTkLabel(topo, text=f"{identidade.NOME} {identidade.VERSAO}",
                     font=tema.titulo(16)).pack(side="left", padx=10)

        ctk.CTkLabel(janela, text=identidade.DESCRICAO, font=tema.fonte(12),
                     text_color=tema.TEXTO_FRACO).pack()

        texto = (
            f"Copyright (C) {identidade.ANO} {identidade.AUTOR}\n\n"
            "This program is free software: you can redistribute it and/or\n"
            "modify it under the terms of the GNU General Public License as\n"
            "published by the Free Software Foundation, either version 3 of\n"
            "the License, or (at your option) any later version.\n\n"
            "This program is distributed in the hope that it will be useful,\n"
            "but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.\n\n"
            f"{identidade.LICENCA_URL}\n\n"
            "The full licence is in the LICENSE file, and the libraries used\n"
            "are listed in THIRD-PARTY.md.\n\n"
            "You have the right to the source code of this program: it is in\n"
            "the 'codigo-fonte' folder, installed next to the program itself."
        )
        ctk.CTkLabel(janela, text=texto, justify="left", font=tema.fonte(11),
                     text_color=tema.TEXTO_FRACO).pack(padx=20, pady=12)

        ctk.CTkButton(janela, text="Close", height=30, width=110,
                      command=janela.destroy).pack(pady=(0, 14))
        janela.after(200, janela.lift)

    # -------------------------------------------------------- saidas e ajuda

    def _relatorio(self, funcao, titulo):
        if not self.fichas:
            messagebox.showinfo("No data", "Scan a folder first.")
            return
        janela = ctk.CTkToplevel(self)
        janela.title(titulo)
        janela.geometry("760x560")
        janela.transient(self)
        caixa = ctk.CTkTextbox(janela, font=ctk.CTkFont(family="Consolas", size=12))
        caixa.pack(fill="both", expand=True, padx=10, pady=10)
        caixa.insert("1.0", funcao(self.fichas))
        caixa.configure(state="disabled")
        janela.after(200, janela.lift)

    def _fechar(self):
        leitor.parar()          # nao deixar musica a tocar depois de sair
        try:
            armazenamento.guardar(janela=self.geometry(),
                                  ultima_pasta=self.var_pasta.get().strip())
        except Exception:
            pass
        self.cancelar.set()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
