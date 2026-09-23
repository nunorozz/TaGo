@echo off
rem Constroi o programa e faz o instalador: Output\TaGo-Setup-3.0.exe
rem Basta duplo-clique neste ficheiro. Demora alguns minutos.
cd /d "%~dp0"

set PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe
if exist "%PY%" goto :construir

where python.exe >nul 2>&1
if %errorlevel%==0 (
    set PY=python.exe
    goto :construir
)

echo Nao encontrei o Python neste computador.
echo Instala-o com:  winget install Python.Python.3.12
pause
exit /b 1

:construir
"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo A instalar o PyInstaller, que e quem faz o executavel...
    "%PY%" -m pip install pyinstaller
)

rem O Inno Setup e quem embrulha tudo num unico instalador. Sem ele o
rem empacotar.py avisa e deixa na mesma a pasta dist\ pronta a usar.
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" goto :correr
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" goto :correr
echo.
echo O Inno Setup nao esta instalado - e ele que faz o instalador.
echo A instalar...
winget install --id JRSoftware.InnoSetup --accept-source-agreements --accept-package-agreements

:correr
"%PY%" "%~dp0empacotar.py"
if errorlevel 1 (
    echo.
    echo Alguma coisa correu mal.
    pause
    exit /b 1
)

pause
