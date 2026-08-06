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
"""Tocar uma musica dentro da app, para se ouvir antes de gravar as tags.

Nao ha uma so maneira de tocar audio em Python que funcione com todos os
formatos, por isso ha tres, tentadas por esta ordem:

1. **VLC** - toca tudo (mp3, flac, m4a, ogg, wma, wav, aiff) e deixa parar a
   meio. E o caminho normal. Precisa do VLC instalado no computador e do
   pacote `python-vlc`.
2. **O leitor do proprio Windows (MCI)** - nao precisa de instalar nada, mas
   so da conta de MP3 e WAV.
3. **O leitor de musica do utilizador** - abre o ficheiro no programa que
   estiver associado. Funciona sempre, mas ja e fora da app: nao da para
   parar daqui.

Toca-se uma musica de cada vez: pedir outra para a anterior.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path


class ErroLeitura(Exception):
    """Nao foi possivel tocar - com uma explicacao para o utilizador."""


# --------------------------------------------------------------------- VLC

_vlc = None
_vlc_falhou = False
_vlc_modulo = None


def _motor_vlc():
    """Carrega o VLC a primeira vez que faz falta. None se nao der."""
    global _vlc, _vlc_falhou, _vlc_modulo
    if _vlc is not None or _vlc_falhou:
        return _vlc
    try:
        import vlc
        # --no-video: alguns m4a trazem imagem, e nao queremos janelas a abrir.
        _vlc = vlc.Instance("--no-video", "--quiet")
        if _vlc is None:
            raise RuntimeError("o VLC nao arrancou")
        _vlc_modulo = vlc
    except Exception:
        _vlc_falhou = True
        _vlc = None
    return _vlc


_vlc_jogador = None


def _jogador_vlc():
    """O leitor do VLC, criado a primeira vez e depois sempre o mesmo.

    Criar um leitor novo a cada musica deixava os anteriores pendurados a
    segurar a placa de som, e a partir da segunda ou terceira musica o som
    deixava de sair.
    """
    global _vlc_jogador
    if _vlc_jogador is None:
        motor = _motor_vlc()
        if motor is None:
            return None
        try:
            _vlc_jogador = motor.media_player_new()
        except Exception:
            return None
    return _vlc_jogador


def _vlc_ocupado(jogador) -> bool:
    """O VLC ja aceitou a musica e esta a trata-la.

    Nao chega perguntar is_playing(): logo a seguir ao play() o VLC ainda
    esta a abrir o ficheiro, responde que nao esta a tocar, e a app julgava
    que tinha falhado. Os estados de arranque contam como "a tocar".
    """
    try:
        estado = jogador.get_state()
    except Exception:
        return False
    e = _vlc_modulo.State
    return estado in (e.Opening, e.Buffering, e.Playing)


# --------------------------------------------------------------------- MCI

_winmm = None


def _mci(comando: str) -> tuple[int, str]:
    global _winmm
    if _winmm is None:
        _winmm = ctypes.WinDLL("winmm")
        _winmm.mciSendStringW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR,
                                          wintypes.UINT, wintypes.HANDLE]
    buf = ctypes.create_unicode_buffer(512)
    erro = _winmm.mciSendStringW(comando, buf, 512, None)
    return erro, buf.value


ALIAS = "metadatamusicas"


# ------------------------------------------------------------------ estado

_caminho_atual: str = ""
_como: str = ""          # "vlc", "mci" ou "externo"
_jogador = None          # o media player do VLC, quando e esse o caminho


def a_tocar() -> str:
    """O ficheiro que esta a tocar agora, ou "" se nao houver nenhum.

    So conta o que a app controla: se a musica foi aberta no leitor do
    utilizador, daqui nao se sabe se ainda toca, e devolve "".
    """
    if not _caminho_atual:
        return ""
    if _como == "vlc":
        return _caminho_atual if _vlc_ocupado(_jogador) else ""
    if _como == "mci":
        _, modo = _mci(f"status {ALIAS} mode")
        return _caminho_atual if modo == "playing" else ""
    return ""


def posicao() -> float:
    """Em que ponto da musica vai, de 0 (inicio) a 1 (fim).

    Devolve 0 quando nao ha nada a tocar ou quando a musica esta a ser tocada
    no leitor do utilizador, onde daqui nao se sabe nada.
    """
    if _como == "vlc" and _jogador is not None:
        try:
            valor = _jogador.get_position()
        except Exception:
            return 0.0
        return min(1.0, max(0.0, valor)) if valor and valor > 0 else 0.0
    if _como == "mci":
        _, pos = _mci(f"status {ALIAS} position")
        _, fim = _mci(f"status {ALIAS} length")
        if pos.isdigit() and fim.isdigit() and int(fim) > 0:
            return min(1.0, int(pos) / int(fim))
    return 0.0


def saltar_para(fraccao: float) -> bool:
    """Salta para um ponto da musica (0 a 1). False se nao for possivel."""
    fraccao = min(1.0, max(0.0, float(fraccao)))
    if _como == "vlc" and _jogador is not None:
        try:
            _jogador.set_position(fraccao)
            return True
        except Exception:
            return False
    if _como == "mci":
        _, fim = _mci(f"status {ALIAS} length")
        if fim.isdigit() and int(fim) > 0:
            destino = int(int(fim) * fraccao)
            erro, _ = _mci(f"play {ALIAS} from {destino}")
            return not erro
    return False


def parar():
    """Cala o que estiver a tocar. Nunca levanta excecao."""
    global _caminho_atual, _como, _jogador
    try:
        if _como == "vlc" and _jogador is not None:
            _jogador.stop()
        elif _como == "mci":
            _mci(f"close {ALIAS}")
    except Exception:
        pass
    _caminho_atual, _como, _jogador = "", "", None


def tocar(caminho) -> str:
    """Toca o ficheiro. Devolve como foi tocado: vlc, mci ou externo.

    Levanta ErroLeitura se nenhuma das tres maneiras resultar.
    """
    global _caminho_atual, _como, _jogador

    p = Path(caminho)
    if not p.exists():
        raise ErroLeitura("the file is no longer where it was")

    parar()

    # 1. VLC. Reaproveita-se sempre o mesmo leitor: criar um novo a cada
    # musica deixava o anterior pendurado a segurar a placa de som.
    motor = _motor_vlc()
    jogador = _jogador_vlc()
    if motor is not None and jogador is not None:
        try:
            jogador.set_media(motor.media_new_path(str(p)))
            if jogador.play() == 0:          # 0 = aceite
                _caminho_atual, _como, _jogador = str(p), "vlc", jogador
                return "vlc"
        except Exception:
            pass

    # 2. O leitor do Windows (so MP3 e WAV)
    _mci(f"close {ALIAS}")
    erro, _ = _mci(f'open "{p}" alias {ALIAS}')
    if not erro:
        erro, _ = _mci(f"play {ALIAS}")
        if not erro:
            _caminho_atual, _como, _jogador = str(p), "mci", None
            return "mci"
        _mci(f"close {ALIAS}")

    # 3. O leitor de musica do utilizador
    try:
        os.startfile(str(p))          # so existe no Windows
    except Exception as e:
        raise ErroLeitura(
            f"could not play this file ({e}). "
            "Try opening it in your music player.") from e
    _caminho_atual, _como, _jogador = str(p), "externo", None
    return "externo"


def descricao_motor() -> str:
    """Para dizer ao utilizador o que e que esta a tocar as musicas."""
    if _motor_vlc() is not None:
        return "VLC"
    return "Windows player (MP3 and WAV only; the rest opens in your player)"
