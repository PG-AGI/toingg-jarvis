#define MyAppName "J.A.R.V.I.S"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "PG-AGI"
#define MyAppExeName "JARVIS.exe"

[Setup]
AppId={{AA32BC9A-7F1D-49DE-A88D-98713E6E0913}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JARVIS
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename=JARVIS-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
