#define MyAppName "J.A.R.V.I.S"
#define MyAppVersion "0.0.0"
#define MyAppPublisher "PG-AGI"
#define MyAppExeName "JARVIS.bat"

[Setup]
AppId={{8A3C53C9-3CF2-4B1B-9A91-9D6B2B74151D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JARVIS
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=JARVIS-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\..\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion; Excludes: ".git\*,.github\*,dist\*,build\*,packaging\windows\Output\*,__pycache__\*,.pytest_cache\*,.browser-profile\*,.browser-profile-test\*"

[Icons]
Name: "{group}\J.A.R.V.I.S"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{commondesktop}\J.A.R.V.I.S"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch J.A.R.V.I.S"; Flags: nowait postinstall skipifsilent
