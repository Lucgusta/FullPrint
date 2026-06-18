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
; Node.js portatil baixado quando o usuario aceita (recurso "Interpretar ZPL").
; LTS; bump aqui quando quiser atualizar.
#define NodeVersion "20.18.1"
#define NodeZipName "node-v" + NodeVersion + "-win-x64.zip"
#define NodeUrl "https://nodejs.org/dist/v" + NodeVersion + "/" + NodeZipName

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

[UninstallDelete]
; Node.js portatil baixado pelo instalador (nao entra no [Files], entao precisa
; ser removido explicitamente na desinstalacao).
Type: filesandordirs; Name: "{app}\node"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
; Abre o app ao terminar -- pulado em instalacao silenciosa (auto-update).
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
{ ------------------------------------------------------------------------------
  Node.js: o FullPrint usa o Node para INTERPRETAR ZPL (preview "Interpretar
  ZPL"). A impressao e o preview de bitmap nao dependem dele. Se o Node nao for
  encontrado, perguntamos ao usuario e, com o aceite, baixamos a versao portatil
  oficial para {app}\node (sem admin, sem mexer no PATH). O app procura o Node
  nessa pasta automaticamente (src/core/zpl_renderer.py -> node_executable()).
------------------------------------------------------------------------------ }

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if ProgressMax > 0 then
    WizardForm.StatusLabel.Caption :=
      'Baixando Node.js... ' + IntToStr(Integer((Progress * 100) div ProgressMax)) + '%';
  Result := True;  { True = continuar o download }
end;

{ Node ja disponivel no PATH do sistema? }
function NodeNoPath(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if Exec('cmd.exe', '/C where node >nul 2>nul', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Result := (ResultCode = 0);
end;

{ Node portatil ja instalado junto ao app (instalacao anterior)? }
function NodeJuntoAoApp(): Boolean;
begin
  Result := DirExists(ExpandConstant('{app}\node'));
end;

procedure InstalarNodePortatil();
var
  ZipPath, NodeDir, PsArgs: String;
  ResultCode: Integer;
begin
  NodeDir := ExpandConstant('{app}\node');
  ZipPath := ExpandConstant('{tmp}\{#NodeZipName}');

  WizardForm.StatusLabel.Caption := 'Baixando Node.js (~30 MB)...';
  try
    DownloadTemporaryFile('{#NodeUrl}', '{#NodeZipName}', '', @OnDownloadProgress);
  except
    MsgBox('Falha ao baixar o Node.js:' + #13#10 + GetExceptionMessage + #13#10 + #13#10 +
           'Voce pode instalar o Node.js manualmente depois (nodejs.org); o restante do FullPrint funciona normalmente.',
           mbError, MB_OK);
    exit;
  end;

  WizardForm.StatusLabel.Caption := 'Instalando Node.js...';
  ForceDirectories(NodeDir);
  { Win10+ tem PowerShell 5.1 com Expand-Archive; extracao sem admin. }
  PsArgs := '-NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath ''' +
            ZipPath + ''' -DestinationPath ''' + NodeDir + ''' -Force"';
  if (not Exec('powershell.exe', PsArgs, '', SW_HIDE, ewWaitUntilTerminated, ResultCode)) or (ResultCode <> 0) then
  begin
    MsgBox('Nao foi possivel extrair o Node.js (codigo ' + IntToStr(ResultCode) + ').' + #13#10 +
           'O recurso "Interpretar ZPL" ficara indisponivel ate instalar o Node.js manualmente.',
           mbError, MB_OK);
    exit;
  end;

  MsgBox('Node.js instalado com sucesso. O recurso "Interpretar ZPL" esta pronto para uso.', mbInformation, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Resposta: Integer;
begin
  if CurStep <> ssPostInstall then
    exit;
  { Auto-update roda silencioso: nunca interrompe com perguntas. }
  if WizardSilent then
    exit;
  { Ja tem Node (no PATH ou portatil de uma instalacao anterior)? Nada a fazer. }
  if NodeNoPath() or NodeJuntoAoApp() then
    exit;

  Resposta := MsgBox(
    'O FullPrint usa o Node.js para INTERPRETAR ZPL e mostrar o preview real das etiquetas (recurso "Interpretar ZPL").' + #13#10 + #13#10 +
    'O Node.js nao foi encontrado neste computador.' + #13#10 + #13#10 +
    'Deseja baixar e instalar o Node.js agora? (cerca de 30 MB, nao requer administrador)' + #13#10 +
    'A impressao e o preview de imagem funcionam mesmo sem o Node.',
    mbConfirmation, MB_YESNO);

  if Resposta = IDYES then
    InstalarNodePortatil();
end;
