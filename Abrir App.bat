@echo off
rem Lanca a app sem janela de consola. Basta duplo-clique neste ficheiro.
cd /d "%~dp0"

set PY=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe
if exist "%PY%" goto :abrir

rem Se o Python estiver noutro sitio, tenta pelo PATH.
where pythonw.exe >nul 2>&1
if %errorlevel%==0 (
    set PY=pythonw.exe
    goto :abrir
)

echo Nao encontrei o Python neste computador.
echo Instala-o com:  winget install Python.Python.3.12
echo e depois:       pip install mutagen musicbrainzngs customtkinter Pillow requests
pause
exit /b 1

:abrir
start "" "%PY%" "%~dp0app.py"
