; JARVIS Windows installer (Inno Setup 6) — bounty #13 Windows-only slice.
; Build:  iscc installer\jarvis.iss   (CI installs Inno via `choco install innosetup -y`)
; Input:  dist\JARVIS\*  (from `pyinstaller jarvis.spec`)

#define MyAppName "JARVIS"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "PG-AGI"
#define MyAppExeName "JARVIS.exe"

[Setup]
AppId={{8340A993-4BC9-414E-9F63-09DC74220AAC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\JARVIS
DefaultGroupName=JARVIS
OutputDir=Output
OutputBaseFilename=JARVIS-Setup-{#MyAppVersion}-Windows
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "..\dist\JARVIS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
; First install gets a starter config; never overwrite an existing one.
Source: "..\config.example.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\JARVIS"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\JARVIS"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a &desktop icon"; Flags: unchecked

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--version"; Description: "Verify the install (prints version)"; Flags: postinstall skipifsilent unchecked runhidden
