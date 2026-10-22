#define MyAppName "JARVIS"
#define MyAppVersion "2.0.0"

[Setup]
AppId={{33F4728B-8CD7-4BBD-B189-8E8B8CB31E5D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=PG-AGI
DefaultDirName={localappdata}\Programs\JARVIS
DefaultGroupName=JARVIS
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist\installers
OutputBaseFilename=JARVIS-Windows-Setup
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\JARVIS.exe
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\..\dist\JARVIS\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Icons]
Name: "{group}\JARVIS"; Filename: "{app}\JARVIS.exe"
Name: "{autodesktop}\JARVIS"; Filename: "{app}\JARVIS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\JARVIS.exe"; Description: "Launch JARVIS"; Flags: nowait postinstall skipifsilent
