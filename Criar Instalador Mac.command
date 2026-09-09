#!/bin/bash
# Constroi a app e faz o disco: Output/TaGo-<versao>.dmg
# No Finder, duplo-clique neste ficheiro. Demora alguns minutos.
#
# Se o Mac disser que nao tem permissao para o correr, e porque o ficheiro
# perdeu a marca de executavel (acontece quando vem de um zip ou do Windows).
# Resolve-se uma vez, na Terminal:
#     chmod +x "Criar Instalador Mac.command"
cd "$(dirname "$0")" || exit 1

PY=""
for tentativa in python3.12 python3 python; do
    if command -v "$tentativa" >/dev/null 2>&1; then
        PY="$tentativa"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "Nao encontrei o Python neste Mac."
    echo "Instala-o com:  brew install python@3.12"
    echo "(ou de python.org, se nao tiveres o Homebrew)"
    read -r -p "Carrega em Enter para fechar."
    exit 1
fi

if ! "$PY" -m PyInstaller --version >/dev/null 2>&1; then
    echo "A instalar o PyInstaller, que e quem faz a app..."
    "$PY" -m pip install pyinstaller || exit 1
fi

"$PY" empacotar_mac.py
codigo=$?

if [ $codigo -ne 0 ]; then
    echo
    echo "Alguma coisa correu mal."
fi

read -r -p "Carrega em Enter para fechar."
exit $codigo
