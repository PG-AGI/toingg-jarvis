; Target path in repo: packaging/windows/jarvis_installer.iss
; Build with Inno Setup: iscc packaging\windows\jarvis_installer.iss

#define MyAppName "Toingg J.A.R.V.I.S"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "PG-AGI"
#define MyAppURL "https://github.com/PG-AGI/toingg-jarvis"
#define MyAppExeName "toingg-jarvis.exe"

[Setup]
AppId={{7A9E41C2-58B3-4F29-9A67-8B1E2D3C4F50}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\ToinggJarvis
DefaultGroupName={#MyAppName}
OutputDir=..\..\dist\installers
OutputBaseFilename=toingg-jarvis-setup-{#MyAppVersion}-win64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\..\dist\toingg-jarvis\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
