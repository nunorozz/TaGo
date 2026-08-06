@echo off
rem ---------------------------------------------------------------------
rem  Instalar o TaGo neste computador.
rem
rem  Copia a app para a pasta pessoal do utilizador (nao para Program Files:
rem  assim nao pede permissoes de administrador) e cria os atalhos.
rem
rem  Nao mexe em musicas, nem em definicoes, nem nas chaves das fontes de
rem  pesquisa: essas ficam em %APPDATA%\TaGo e sobrevivem a instalacao, a
rem  desinstalacao e as actualizacoes.
rem ---------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "ORIGEM=%~dp0TaGo"
set "DESTINO=%LOCALAPPDATA%\Programs\TaGo"
set "MENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs"

if not exist "%ORIGEM%\TaGo.exe" (
    echo Nao encontrei a pasta TaGo ao lado deste ficheiro.
    echo Este instalador tem de ficar na mesma pasta que a pasta TaGo.
    echo.
    pause
    exit /b 1
)

echo Instalar o TaGo em:
echo     %DESTINO%
echo.

rem Se a app estiver aberta, os ficheiros estao presos e a copia falhava a
rem meio, deixando uma instalacao pela metade. Fecha-se primeiro.
tasklist /fi "imagename eq TaGo.exe" | find /i "TaGo.exe" >nul
if not errorlevel 1 (
    echo O TaGo esta aberto. A fechar...
    taskkill /im TaGo.exe /f >nul 2>&1
    rem Esperar 2 segundos. Faz-se com o ping e nao com o "timeout" porque o
    rem timeout rebenta quando o .bat e corrido sem teclado a serio (por
    rem exemplo a partir de outro programa).
    ping -n 3 127.0.0.1 >nul
)

if exist "%DESTINO%" (
    echo Ja existia uma versao instalada. A substituir...
    rmdir /s /q "%DESTINO%"
)

mkdir "%DESTINO%" 2>nul
xcopy "%ORIGEM%" "%DESTINO%" /e /i /q /y >nul
if errorlevel 1 (
    echo.
    echo Nao foi possivel copiar os ficheiros.
    pause
    exit /b 1
)

copy /y "%~f0" "%DESTINO%\Instalar TaGo.bat" >nul 2>&1

rem Os atalhos fazem-se pelo PowerShell: o .bat sozinho nao sabe criar .lnk.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=New-Object -ComObject WScript.Shell;" ^
  "foreach ($p in @([Environment]::GetFolderPath('Desktop'), '%MENU%')) {" ^
  "  $a=$s.CreateShortcut((Join-Path $p 'TaGo.lnk'));" ^
  "  $a.TargetPath='%DESTINO%\TaGo.exe';" ^
  "  $a.WorkingDirectory='%DESTINO%';" ^
  "  $a.IconLocation='%DESTINO%\TaGo.exe,0';" ^
  "  $a.Description='TaGo - Music Tag Editor';" ^
  "  $a.Save() }" >nul

rem Deixa ao lado da app a maneira de a tirar do computador.
> "%DESTINO%\Desinstalar TaGo.bat" echo @echo off
>> "%DESTINO%\Desinstalar TaGo.bat" echo rem Tira o TaGo do computador. As definicoes e as chaves ficam em
>> "%DESTINO%\Desinstalar TaGo.bat" echo rem %%APPDATA%%\TaGo - apagar a mao se nao forem mesmo precisas.
>> "%DESTINO%\Desinstalar TaGo.bat" echo taskkill /im TaGo.exe /f ^>nul 2^>^&1
>> "%DESTINO%\Desinstalar TaGo.bat" echo del "%%USERPROFILE%%\Desktop\TaGo.lnk" ^>nul 2^>^&1
>> "%DESTINO%\Desinstalar TaGo.bat" echo del "%MENU%\TaGo.lnk" ^>nul 2^>^&1
>> "%DESTINO%\Desinstalar TaGo.bat" echo echo O TaGo foi removido.
>> "%DESTINO%\Desinstalar TaGo.bat" echo ping -n 4 127.0.0.1 ^>nul
>> "%DESTINO%\Desinstalar TaGo.bat" echo start "" cmd /c rmdir /s /q "%DESTINO%"

echo.
echo Instalado. Ha um atalho no ambiente de trabalho e no menu Iniciar.
echo.

rem O VLC nao vem com a app (e um programa a parte, com licenca propria).
if exist "%ProgramFiles%\VideoLAN\VLC\vlc.exe" goto :fim
if exist "%ProgramFiles(x86)%\VideoLAN\VLC\vlc.exe" goto :fim
echo AVISO: nao encontrei o VLC neste computador.
echo A app abre na mesma, mas nao toca as musicas nem desenha as ondas.
echo Instala-o com:  winget install VideoLAN.VLC
echo.

:fim
pause
