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
"""Desenha o logo do TaGo e grava-o em `recursos/`.

Corre-se a mao, so quando o logo mudar:  python criar_logo.py

O original e um SVG (`tago-logo-v3.svg`), mas a app nao o pode usar
directamente: o tkinter nao le SVG, e uma biblioteca so para isso era uma
dependencia a mais para instalar no computador de cada pessoa. Como o desenho
sao seis rectangulos e uma palavra, e desenhado aqui com a mesma biblioteca
que a app ja usa para as capas, e fica gravado em PNG e ICO.

Desenha-se quatro vezes maior e depois reduz-se: e o que da os cantos
redondos e as letras sem serrilha.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RECURSOS = Path(__file__).parent / "recursos"

LADO = 600            # o mesmo viewBox do SVG
ESCALA = 4            # desenha-se a 2400 e reduz-se

AMARELO = "#F2D024"   # o mesmo amarelo do resto da app (tema.DESTAQUE)
FUNDO_TOPO = (10, 15, 12)
FUNDO_BASE = (0, 0, 0)
RAIO = 90

# x, y, largura, altura - copiados um a um do SVG.
BARRAS = [
    (215, 230, 20, 40),
    (245, 170, 20, 100),
    (275, 200, 20, 70),
    (305, 140, 20, 130),
    (335, 210, 20, 60),
    (365, 175, 20, 95),
]

PALAVRA = "TAGO"
TEXTO_X = 302         # centro
TEXTO_BASE = 317      # linha de base
TEXTO_TAMANHO = 50
ESPACAMENTO = 5       # o letter-spacing do SVG

# Quanto da largura do quadrado a marca ocupa no logo completo. No SVG sao
# 28%, que num icone pequeno nao se ve; 72% e o costume num icone.
OCUPACAO = 0.72

TIPOS = ["C:/Windows/Fonts/ariblk.ttf",      # Arial Black, como no SVG
         "C:/Windows/Fonts/arialbd.ttf"]     # Arial Bold, se a outra faltar


def _letra(tamanho: int):
    for caminho in TIPOS:
        try:
            return ImageFont.truetype(caminho, tamanho)
        except OSError:
            continue
    return ImageFont.load_default()


def _marca(n: int, k: float) -> Image.Image:
    """So as barras e a palavra, nas posicoes do SVG, sobre nada."""
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    for x, y, largura, altura in BARRAS:
        d.rectangle([x * k, y * k, (x + largura) * k - 1, (y + altura) * k - 1],
                    fill=AMARELO)

    # A palavra, letra a letra por causa do espacamento entre elas.
    letra = _letra(int(TEXTO_TAMANHO * k))
    espaco = ESPACAMENTO * k
    larguras = [d.textlength(c, font=letra) for c in PALAVRA]
    total = sum(larguras) + espaco * (len(PALAVRA) - 1)
    x = TEXTO_X * k - total / 2
    for c, w in zip(PALAVRA, larguras):
        d.text((x, TEXTO_BASE * k), c, font=letra, fill=AMARELO, anchor="ls")
        x += w + espaco

    return img


def _fundo(n: int, k: float) -> Image.Image:
    """O quadrado de cantos redondos, do degrade do SVG."""
    fundo = Image.new("RGBA", (n, n))
    pintar = ImageDraw.Draw(fundo)
    for y in range(n):
        p = y / max(1, n - 1)
        cor = tuple(int(FUNDO_TOPO[i] + (FUNDO_BASE[i] - FUNDO_TOPO[i]) * p)
                    for i in range(3))
        pintar.line([(0, y), (n, y)], fill=cor + (255,))

    mascara = Image.new("L", (n, n), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(
        [0, 0, n - 1, n - 1], radius=int(RAIO * k), fill=255)

    quadrado = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    quadrado.paste(fundo, (0, 0), mascara)
    return quadrado


def desenhar(lado: int = LADO, com_fundo: bool = True,
             centrar: bool = True) -> Image.Image:
    """O logo completo.

    No SVG a marca esta acima do centro do quadrado e ocupa pouco mais de um
    quarto da largura - o resto e vazio. No PNG grande passava, mas num icone
    de 16 pixeis na barra de tarefas sobravam quatro pixeis de desenho e nao
    se percebia nada. Com `centrar`, a marca e recortada ao que esta mesmo
    pintado, ampliada ate OCUPACAO da largura, e posta ao meio.

    A ampliacao e feita a desenhar outra vez maior, e nao a esticar o que ja
    estava desenhado: assim os cantos e as letras continuam limpos.
    """
    n = lado * ESCALA
    k = n / LADO          # de coordenadas do SVG para as do desenho

    img = _fundo(n, k) if com_fundo else Image.new("RGBA", (n, n), (0, 0, 0, 0))
    marca = _marca(n, k)

    if not centrar:
        img.alpha_composite(marca)
        return img.resize((lado, lado), Image.LANCZOS)

    caixa = marca.getbbox()          # so o que esta mesmo pintado
    maior = max(caixa[2] - caixa[0], caixa[3] - caixa[1])
    fator = (n * OCUPACAO) / maior
    if abs(fator - 1) > 0.01:
        maior_n = int(n * fator) + 4
        marca = _marca(maior_n, k * fator)
        caixa = marca.getbbox()

    recorte = marca.crop(caixa)
    img.paste(recorte, ((n - recorte.width) // 2,
                        (n - recorte.height) // 2), recorte)
    return img.resize((lado, lado), Image.LANCZOS)


def desenhar_marca(altura: int = 256) -> Image.Image:
    """So as barras e a palavra, sem o fundo escuro e sem margens.

    E esta que vai para a barra da app. O logo completo tem quase metade da
    altura vazia por baixo, e a essa escala a palavra TAGO ficava um borrao;
    recortado, ocupa o espaco todo e le-se.
    """
    img = desenhar(LADO, com_fundo=False, centrar=False)
    caixa = img.getbbox()          # so o que esta mesmo pintado
    marca = img.crop(caixa)
    # Uma folga a toda a volta, para nao ficar encostado ao que esta ao lado.
    folga = max(2, marca.height // 12)
    com_folga = Image.new("RGBA", (marca.width + folga * 2,
                                   marca.height + folga * 2), (0, 0, 0, 0))
    com_folga.paste(marca, (folga, folga), marca)
    largura = round(com_folga.width * altura / com_folga.height)
    return com_folga.resize((largura, altura), Image.LANCZOS)


def main():
    RECURSOS.mkdir(exist_ok=True)
    grande = desenhar(512)
    grande.save(RECURSOS / "logo.png")
    desenhar_marca(256).save(RECURSOS / "logo_barra.png")

    # O icone da janela e do executavel leva varios tamanhos dentro do mesmo
    # ficheiro: o Windows escolhe o que precisa em cada sitio.
    grande.save(RECURSOS / "tago.ico",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                       (64, 64), (128, 128), (256, 256)])

    print("gravado em", RECURSOS)
    for f in sorted(RECURSOS.iterdir()):
        print(f"  {f.name:12} {f.stat().st_size:>8} bytes")


if __name__ == "__main__":
    main()
