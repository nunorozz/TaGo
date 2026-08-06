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
"""Transforma o codigo num programa que arranca sozinho, sem Python instalado.

Sao dois passos:

1. O **PyInstaller** faz o programa. Fica em `dist\\TaGo\\`: uma pasta com o
   `TaGo.exe` la dentro e tudo o que ele precisa.
2. O **Inno Setup** embrulha essa pasta num unico `Output\\TaGo-Setup-1.0.exe`
   - o instalador a serio, com assistente, licenca, atalhos, e entrada em
   "Aplicacoes e funcionalidades" do Windows para desinstalar. A receita esta
   em `instalador\\TaGo.iss`.

Se o Inno Setup nao estiver instalado, o passo 2 e saltado com um aviso e fica
na mesma o `dist\\Instalar TaGo.bat`, que faz o mesmo de maneira mais simples.

Faz-se uma PASTA e nao um unico ficheiro .exe de proposito: em ficheiro unico
o Windows tem de desempacotar tudo de cada vez que se abre a app, e o arranque
passa de instantaneo a varios segundos.

Duas coisas NAO vao la para dentro, e e importante que assim seja:

- As chaves das fontes de pesquisa (`credenciais.json`) e as definicoes. Vivem
  na pasta pessoal de quem usa a app (%APPDATA%\\TaGo) e sao dela - ver
  dados.py. Se fossem no pacote, qualquer copia da app levava as chaves atras.
- O VLC. E ele que toca as musicas e que le as formas de onda, mas e um
  programa a parte, com licenca propria, e tem de estar instalado no
  computador. Sem ele a app abre na mesma; so nao toca nem desenha as ondas.

Correr com:  python empacotar.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import identidade

PASTA = Path(__file__).parent
NOME = identidade.NOME
ICONE = PASTA / "recursos" / "tago.ico"

# Modulos que o PyInstaller nao descobre sozinho porque nao aparecem escritos
# num "import" normal - sao carregados so quando fazem falta.
ESCONDIDOS = [
    "mutagen.mp3", "mutagen.flac", "mutagen.mp4", "mutagen.oggvorbis",
    "mutagen.asf", "mutagen.aiff", "mutagen.wave", "mutagen.id3",
    "PIL._tkinter_finder",
]


def apagar(pasta: Path):
    if pasta.exists():
        shutil.rmtree(pasta, ignore_errors=True)


def empacotar() -> Path:
    apagar(PASTA / "build")
    apagar(PASTA / "dist")

    comando = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", NOME,
        "--windowed",                 # sem janela preta de consola atras
        "--add-data", f"{PASTA / 'recursos'}{os.pathsep}recursos",
        # O customtkinter traz os seus temas e letras em ficheiros soltos; sem
        # isto o executavel arranca e rebenta a procura-los.
        "--collect-data", "customtkinter",
        "--collect-data", "certifi",
    ]
    if ICONE.exists():
        comando += ["--icon", str(ICONE)]
    for modulo in ESCONDIDOS:
        comando += ["--hidden-import", modulo]
    comando.append(str(PASTA / "app.py"))      # o ficheiro vai sempre no fim

    print("A empacotar - demora um bom par de minutos.\n")
    subprocess.run(comando, check=True)

    destino = PASTA / "dist" / NOME
    # A licenca tem de acompanhar o programa: e o que a GPL pede a quem o
    # distribui.
    for ficheiro in ("LICENSE", "THIRD-PARTY.md", "README.md"):
        origem = PASTA / ficheiro
        if origem.exists():
            shutil.copy2(origem, destino / ficheiro)

    instalador = PASTA / "instalador" / "Instalar TaGo.bat"
    if instalador.exists():
        shutil.copy2(instalador, PASTA / "dist" / instalador.name)
    return destino


# ------------------------------------------------------- o instalador a serio

def _compilador() -> Path | None:
    """O ISCC.exe do Inno Setup, onde quer que ele tenha ficado."""
    sitios = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6",
        Path(r"C:\Program Files (x86)\Inno Setup 6"),
        Path(r"C:\Program Files\Inno Setup 6"),
    ]
    for sitio in sitios:
        exe = sitio / "ISCC.exe"
        if exe.exists():
            return exe
    return None


def fazer_setup() -> Path | None:
    """Embrulha a pasta dist\\TaGo num unico instalador. None se nao der."""
    iscc = _compilador()
    if iscc is None:
        print("\nO Inno Setup nao esta instalado - fica so a pasta dist\\.")
        print("Para ter o instalador num ficheiro so:")
        print("    winget install JRSoftware.InnoSetup")
        return None

    receita = PASTA / "instalador" / "TaGo.iss"
    saida = PASTA / "Output" / f"{NOME}-Setup-{identidade.VERSAO}.exe"
    apagar(PASTA / "Output")

    print("\nA fazer o instalador...\n")
    subprocess.run([str(iscc), f"/DVersao={identidade.VERSAO}", str(receita)],
                   check=True)
    return saida if saida.exists() else None


if __name__ == "__main__":
    pasta = empacotar()
    setup = fazer_setup()

    print(f"\nPrograma:   {pasta}")
    if setup:
        print(f"Instalador: {setup}")
        print("\nE este unico ficheiro que se da a quem quiser instalar a app.")
    else:
        print(f"Instalar com: {pasta.parent / 'Instalar TaGo.bat'}")
