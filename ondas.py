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
"""Forma de onda de um ficheiro de audio, para desenhar na lista.

Para saber o desenho de uma musica e preciso descodificar o audio todo. Quem
faz isso aqui e o **VLC**, que ja esta instalado: converte-se a musica para um
WAV pequeno e temporario (mono, 4000 amostras por segundo - chega de sobra
para um desenho de 150 pixeis), leem-se os picos, e o WAV e deitado fora.

Demora menos de um segundo por musica, mas mesmo assim o resultado fica
guardado em `cache_ondas.json`: assim so se faz uma vez por ficheiro. Se o
ficheiro for alterado (a app grava tags nele), a chave da cache muda sozinha
e a onda e recalculada.
"""
from __future__ import annotations

import array
import json
import subprocess
import tempfile
import uuid
import wave
from pathlib import Path

import dados

FICHEIRO_CACHE = dados.ficheiro("cache_ondas.json")

TAXA = 4000          # amostras por segundo depois de convertido
PICOS = 150          # quantas barras tem o desenho
SEM_JANELA = 0x08000000      # nao abrir consola do VLC no Windows

_cache: dict | None = None
_falhados: set[str] = set()      # so nesta sessao - ver picos()


# ------------------------------------------------------------------ o VLC

def _vlc_exe() -> str | None:
    for sitio in (r"C:\Program Files\VideoLAN\VLC\vlc.exe",
                  r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"):
        if Path(sitio).exists():
            return sitio
    return None


def disponivel() -> bool:
    return _vlc_exe() is not None


# ---------------------------------------------------------------- a cache

def _carregar_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(FICHEIRO_CACHE.read_text("utf-8"))
        except Exception:
            _cache = {}
    return _cache


def _guardar_cache():
    try:
        FICHEIRO_CACHE.write_text(json.dumps(_carregar_cache()), "utf-8")
    except Exception:
        pass          # a cache e um luxo; nunca deve estragar o resto


def _chave(caminho: Path) -> str:
    """Muda sempre que o ficheiro muda, para a onda nao ficar desatualizada."""
    try:
        st = caminho.stat()
        return f"{caminho}|{int(st.st_mtime)}|{st.st_size}"
    except OSError:
        return str(caminho)


# ------------------------------------------------------------------ calculo

def _converter(caminho: Path) -> Path | None:
    """Converte para um WAV pequeno e temporario. None se nao der."""
    vlc = _vlc_exe()
    if vlc is None:
        return None

    # O nome do destino nunca pode vir do nome da musica: a virgula (e outros
    # caracteres) partem a cadeia de opcoes do VLC, e a conversao falhava sem
    # dizer porque. Um nome inventado resolve.
    destino = Path(tempfile.gettempdir()) / f"onda_{uuid.uuid4().hex}.wav"
    comando = [
        vlc, "-I", "dummy", "--no-video", "--quiet", str(caminho),
        "--sout",
        f"#transcode{{acodec=s16l,channels=1,samplerate={TAXA}}}"
        f":standard{{access=file,mux=wav,dst={destino}}}",
        "vlc://quit",
    ]
    try:
        subprocess.run(comando, capture_output=True, timeout=180,
                       creationflags=SEM_JANELA)
    except Exception:
        destino.unlink(missing_ok=True)
        return None

    if not destino.exists() or destino.stat().st_size < 1000:
        destino.unlink(missing_ok=True)
        return None
    return destino


def _picos_do_wav(caminho: Path, quantos: int) -> list[float] | None:
    try:
        with wave.open(str(caminho)) as w:
            if w.getsampwidth() != 2:
                return None
            amostras = array.array("h", w.readframes(w.getnframes()))
    except Exception:
        return None

    if not amostras:
        return None

    # Um valor por bocado, pela media quadratica (RMS) e nao pelo pico.
    # Com o pico, qualquer musica moderna dava uma barra macica: em dois
    # segundos de musica ha sempre um pico no maximo. A RMS mostra o volume
    # medio, e e isso que da a forma reconhecivel - intro baixa, refrao alto.
    tamanho = max(1, len(amostras) // quantos)
    valores = []
    for i in range(quantos):
        bocado = amostras[i * tamanho:(i + 1) * tamanho]
        if not bocado:
            valores.append(0.0)
            continue
        # Nao e preciso somar tudo: umas centenas de amostras por bocado dao
        # o mesmo desenho e evitam varios milhoes de contas por musica.
        passo = max(1, len(bocado) // 400)
        usadas = bocado[::passo]
        valores.append((sum(a * a for a in usadas) / len(usadas)) ** 0.5)

    maximo = max(valores) or 1
    # A raiz levanta as partes baixas, senao so se via o refrao.
    return [(v / maximo) ** 0.65 for v in valores]


def picos(caminho, quantos: int = PICOS) -> list[float] | None:
    """Os picos da musica, entre 0 e 1. None se nao foi possivel calcular.

    Demora - deve ser chamada fora da interface, numa tarefa de fundo.
    """
    p = Path(caminho)
    chave = _chave(p)
    cache = _carregar_cache()

    guardado = cache.get(chave)
    if guardado:
        return [v / 255 for v in guardado]
    if chave in _falhados:
        return None          # ja falhou nesta sessao; nao insistir agora

    wav = _converter(p)
    valores = _picos_do_wav(wav, quantos) if wav else None
    if wav:
        wav.unlink(missing_ok=True)

    if not valores:
        # O insucesso fica so em memoria, e nao no ficheiro de cache. Uma
        # falha pode ser passageira (a maquina ocupada, o VLC a arrancar), e
        # se ficasse gravada essa musica nunca mais teria forma de onda.
        _falhados.add(chave)
        return None

    cache[chave] = [int(v * 255) for v in valores]
    _guardar_cache()
    return valores
