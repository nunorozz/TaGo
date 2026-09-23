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
"""Faz a versao macOS: o `TaGo.app` e um `.dmg` para o entregar.

O irmao deste ficheiro e o `empacotar.py`, que faz a versao Windows. A logica
de fundo e a mesma e vem de la (a lista do codigo-fonte, os modulos que o
PyInstaller nao descobre, a verificacao dos segredos); o que muda e o embrulho:

1. O **PyInstaller** faz `dist/TaGo.app` - um bundle, que no Finder aparece
   como um so ficheiro e se arrasta para a pasta Aplicacoes.
2. O **hdiutil**, que ja vem no macOS, poe esse bundle num
   `Output/TaGo-3.0.dmg` com um atalho para a pasta Aplicacoes ao lado - a
   janela de instalacao que toda a gente conhece no Mac.

**Isto tem de correr num Mac.** O PyInstaller nao constroi para um sistema a
partir de outro: ele embrulha o Python, o Tk e as bibliotecas da maquina onde
esta, por isso um `.app` so se faz no macOS. Correr isto no Windows nao da um
`.app` meio feito - para logo.

Tambem vale a pena saber, antes de o entregar a alguem:

- **O bundle nao vai assinado.** Sem uma conta Apple Developer para assinar e
  notarizar, o Gatekeeper recusa-o e diz que a app "esta danificada" - que e
  mentira, mas e o que ele diz. Quem o instalar tem de abrir a primeira vez
  pelo botao direito -> Abrir, ou correr uma vez:
      xattr -dr com.apple.quarantine /Applications/TaGo.app
- **O VLC faz mais falta aqui do que no Windows.** O leitor de reserva do
  Windows (o MCI) nao existe no macOS: sem o VLC instalado, carregar em play
  abre a musica no leitor do sistema e a app nao a controla.
- **Intel ou Apple Silicon**: o que sai daqui serve a arquitetura do Mac onde
  foi feito. Para um ficheiro que sirva os dois, ve a nota no fim do ficheiro.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import empacotar          # a versao Windows, de onde vem o que e comum
import identidade

PASTA = Path(__file__).parent
NOME = identidade.NOME
VERSAO = identidade.VERSAO
ICONE = PASTA / "recursos" / "tago.icns"

# O nome pelo qual o macOS conhece a app por dentro. Convencao da Apple: ao
# contrario do dominio de quem a fez. Nao se muda depois de distribuida - e
# por ele que o sistema sabe que uma versao nova e a mesma app.
IDENTIFICADOR = "com.nunorozz.tago"


def _exigir_macos():
    if sys.platform != "darwin":
        raise SystemExit(
            "Isto so corre num Mac.\n"
            "O PyInstaller nao constroi para um sistema a partir de outro: o\n"
            "TaGo.app tem de ser feito no proprio macOS.\n"
            "Para a versao Windows, corre o empacotar.py."
        )


def construir_app() -> Path:
    """Corre o PyInstaller e devolve o caminho do TaGo.app."""
    empacotar.apagar(PASTA / "build")
    empacotar.apagar(PASTA / "dist")

    comando = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", NOME,
        "--windowed",                 # e isto que faz um .app e nao um binario
        "--osx-bundle-identifier", IDENTIFICADOR,
        "--add-data", f"{PASTA / 'recursos'}{os.pathsep}recursos",
        # O customtkinter traz os seus temas e letras em ficheiros soltos; sem
        # isto o executavel arranca e rebenta a procura-los.
        "--collect-data", "customtkinter",
        "--collect-data", "certifi",
    ]
    if ICONE.exists():
        comando += ["--icon", str(ICONE)]
    else:
        print("  aviso: falta o recursos/tago.icns - corre antes o"
              " criar_logo.py, senao fica o icone do Python")
    for modulo in empacotar.ESCONDIDOS:
        comando += ["--hidden-import", modulo]
    comando.append(str(PASTA / "app.py"))      # o ficheiro vai sempre no fim

    print("A empacotar - demora um bom par de minutos.\n")
    subprocess.run(comando, check=True)

    app = PASTA / "dist" / f"{NOME}.app"
    if not app.is_dir():
        raise SystemExit(f"O PyInstaller nao deixou nenhum {app.name} em dist/")
    return app


def encher_bundle(app: Path):
    """Poe a licenca e o codigo-fonte dentro do proprio .app.

    Vao para Contents/Resources, que e onde o macOS guarda o que acompanha uma
    app. A razao e a mesma da versao Windows: a GPL obriga a que quem recebe o
    programa receba tambem o codigo daquela versao, e como o TaGo se entrega em
    mao, o sitio certo para ele e dentro do que se entrega.
    """
    recursos = app / "Contents" / "Resources"
    recursos.mkdir(parents=True, exist_ok=True)

    for ficheiro in ("LICENSE", "THIRD-PARTY.md", "README.md"):
        origem = PASTA / ficheiro
        if origem.exists():
            shutil.copy2(origem, recursos / ficheiro)

    # A mesma funcao da versao Windows: mesma lista de ficheiros, e a mesma
    # verificacao que rebenta o empacotamento se um segredo la for parar.
    empacotar.copiar_fonte(recursos)


def fazer_dmg(app: Path) -> Path:
    """Embrulha o .app num disco, com o atalho para as Aplicacoes ao lado."""
    saida = PASTA / "Output"
    saida.mkdir(exist_ok=True)
    dmg = saida / f"{NOME}-{VERSAO}.dmg"
    if dmg.exists():
        dmg.unlink()

    # O hdiutil faz o disco a partir de uma pasta. Monta-se essa pasta com o
    # que se quer ver na janela: a app, e um atalho para /Applications para
    # onde ela se arrasta.
    palco = PASTA / "build" / "dmg"
    empacotar.apagar(palco)
    palco.mkdir(parents=True)
    shutil.copytree(app, palco / app.name, symlinks=True)
    os.symlink("/Applications", palco / "Applications")

    print("\nA fazer o disco...")
    subprocess.run([
        "hdiutil", "create",
        "-volname", f"{NOME} {VERSAO}",
        "-srcfolder", str(palco),
        "-ov",                    # por cima, se ja existir
        "-format", "UDZO",        # comprimido e so de leitura
        str(dmg),
    ], check=True)

    empacotar.apagar(palco)
    return dmg


def main():
    _exigir_macos()
    app = construir_app()
    encher_bundle(app)
    dmg = fazer_dmg(app)

    print(f"\n\nApp:   {app}")
    print(f"Disco: {dmg}")
    print("\nE este .dmg que se da a quem quiser instalar a app no Mac.")
    print("\nNa primeira vez, quem o abrir tem de usar o botao direito ->")
    print("Abrir: o bundle nao vai assinado e o Gatekeeper barra-o de outra")
    print("maneira. E convem ter o VLC instalado, senao a app abre mas nao")
    print("toca as musicas: brew install --cask vlc")


if __name__ == "__main__":
    main()


# Para um ficheiro que sirva Macs Intel e Apple Silicon ao mesmo tempo, o
# PyInstaller aceita --target-arch universal2 - mas so funciona se o Python e
# *todas* as bibliotecas instaladas tambem forem universal2, o que raramente
# acontece com o que vem do pip. O caminho simples e fazer uma build em cada
# maquina e entregar dois .dmg.
