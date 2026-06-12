; Inno Setup script do FullPrint.
;
; Compilar a partir da RAIZ do repositorio, passando a versao via /D:
;     ISCC.exe /DAppVersion=1.2.0 packaging\installer.iss
;
; Gera packaging\dist_installer\FullPrintSetup.exe.
;
; Pre-requisitos no diretorio (produzidos pelo CI antes de compilar):
;   dist\FullPrint\            <- saida do PyInstaller (one-folder)

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#define MyAppName "FullPrint"
#define MyAppPublisher "MeF Enxovais"
#define MyAppExeName "FullPrint.exe"

[Setup]
; AppId FIXO -> reinstalar por cima faz upgrade in-place (base do auto-update).
AppId={{8F3C2A9E-4D7B-4A1C-9E2F-1B6D5C0A7E34}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher={#MyAppPublisher}
; Instala em %LOCALAPPDATA% -> NAO precisa de admin -> update silencioso sem UAC.
DefaultDirName={localappdata}\{#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
; Paths relativos a este .iss (packaging\) resolvem a partir da raiz do repo.
SourceDir=..
OutputDir=packaging\dist_installer
OutputBaseFilename=FullPrintSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Fecha o app aberto antes de atualizar e nao reabre sozinho.
CloseApplications=yes
RestartApplications=no
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "dist\FullPrint\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; Versoes <= 0.1.x embarcavam o Tesseract OCR (~100MB). O OCR foi removido na
; 0.2.0; limpa a pasta orfa no upgrade in-place.
Type: filesandordirs; Name: "{app}\tesseract"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
; Abre o app ao terminar -- pulado em instalacao silenciosa (auto-update).
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
