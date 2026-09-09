; TaGo - Music Tag Editor
; Copyright (C) 2026 Nuno Rozz - GNU General Public License v3 or later
;
; Receita do Setup, para o Inno Setup. Nao se corre a mao: quem o compila e o
; empacotar.py, que primeiro constroi a app com o PyInstaller e so depois
; chama o compilador daqui, ja com a versao e os caminhos certos.
;
; O que este Setup faz de diferente do .bat que havia antes:
;   - assistente com licenca (a GPL pede que ela acompanhe o programa),
;   - escolha da pasta e dos atalhos,
;   - aparece em "Aplicacoes e funcionalidades" do Windows, com desinstalador,
;   - ao actualizar, fecha a app se estiver aberta e substitui sem deixar
;     restos da versao anterior.
;
; Instala na pasta pessoal e nao em "Program Files": assim nao pede
; permissoes de administrador (PrivilegesRequired=lowest). Quem quiser
; instalar para todos os utilizadores pode escolher isso na primeira janela.

#define Nome        "TaGo"
#ifndef Versao
  #define Versao    "2.0"
#endif
#define Autor       "Nuno Rozz"
#define Descricao   "Music Tag Editor"
#ifndef Origem
  #define Origem    "..\dist\TaGo"
#endif
#ifndef Raiz
  #define Raiz      ".."
#endif

[Setup]
; Este numero identifica a app para o Windows. NAO se muda entre versoes: e
; por ele que o Setup sabe que esta a actualizar e nao a instalar de novo.
AppId={{A7C6F1E4-3B92-4F58-9D21-5E8A0C7B4D63}
AppName={#Nome}
AppVersion={#Versao}
AppVerName={#Nome} {#Versao}
AppPublisher={#Autor}
VersionInfoDescription={#Nome} - {#Descricao}
VersionInfoVersion={#Versao}.0.0

DefaultDirName={autopf}\{#Nome}
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
LicenseFile={#Raiz}\LICENSE
InfoAfterFile={#Raiz}\THIRD-PARTY.md

; "lowest" = instala sem pedir administrador, na pasta do utilizador. Quem
; quiser para todos os utilizadores escolhe-o na primeira janela do Setup.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

OutputDir={#Raiz}\Output
OutputBaseFilename={#Nome}-Setup-{#Versao}
SetupIconFile={#Raiz}\recursos\tago.ico
UninstallDisplayIcon={app}\{#Nome}.exe
UninstallDisplayName={#Nome} {#Versao}

Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

; A app so foi feita e testada em Windows 10 e 11.
MinVersion=10.0

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"

[Files]
; A pasta inteira que o PyInstaller fez. O executavel vem a parte so para
; poder levar a marca de "ficheiro principal".
Source: "{#Origem}\{#Nome}.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Origem}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; A licenca tem de acompanhar o programa: e o que a GPL pede a quem distribui.
Source: "{#Raiz}\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Raiz}\THIRD-PARTY.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#Raiz}\README.md"; DestDir: "{app}"; Flags: ignoreversion

; NADA daqui leva chaves nem definicoes: essas vivem em %APPDATA%\TaGo, sao de
; quem usa a app, e nunca entram no Setup.

[Icons]
Name: "{group}\{#Nome}"; Filename: "{app}\{#Nome}.exe"; \
    Comment: "{#Nome} - {#Descricao}"
Name: "{group}\{cm:UninstallProgram,{#Nome}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Nome}.exe"; \
    Comment: "{#Nome} - {#Descricao}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#Nome}.exe"; Description: "{cm:LaunchProgram,{#Nome}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; O PyInstaller deixa ficheiros .pyc gerados no primeiro arranque; sem isto a
; pasta ficava para tras vazia mas existente.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"
Type: dirifempty; Name: "{app}"

[Code]
{ Se a app estiver a correr, os ficheiros estao presos e a instalacao falhava a
  meio. Pergunta-se, e so se fecha com autorizacao. }
function AppAberta(): Boolean;
var
  codigo: Integer;
begin
  Result := Exec('cmd.exe',
    '/c tasklist /fi "imagename eq {#Nome}.exe" | find /i "{#Nome}.exe"',
    '', SW_HIDE, ewWaitUntilTerminated, codigo) and (codigo = 0);
end;

function FecharApp(): Boolean;
var
  codigo: Integer;
begin
  Result := True;
  if not AppAberta() then
    Exit;
  if MsgBox('O {#Nome} esta aberto e tem de ser fechado para continuar.'#13#10 +
            'Fechar agora?', mbConfirmation, MB_YESNO) = IDNO then
  begin
    Result := False;
    Exit;
  end;
  Exec('taskkill.exe', '/im {#Nome}.exe /f', '', SW_HIDE,
       ewWaitUntilTerminated, codigo);
  Sleep(1500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if not FecharApp() then
    Result := 'A instalacao foi cancelada porque o {#Nome} continua aberto.';
end;

function InitializeUninstall(): Boolean;
begin
  Result := FecharApp();
end;

{ O VLC e um programa a parte, com licenca propria: nao pode vir dentro deste
  Setup. Sem ele a app abre, mas nao toca as musicas nem desenha as ondas. }
function TemVLC(): Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf64}\VideoLAN\VLC\vlc.exe')) or
            FileExists(ExpandConstant('{commonpf32}\VideoLAN\VLC\vlc.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and (not TemVLC()) then
    MsgBox('Nao encontrei o VLC neste computador.'#13#10#13#10 +
           'O {#Nome} abre na mesma, mas so toca as musicas e desenha as ' +
           'formas de onda com o VLC instalado.'#13#10#13#10 +
           'Pode instalar-se depois, a partir de videolan.org.',
           mbInformation, MB_OK);
end;
