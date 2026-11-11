[Setup]
AppId={{B7432B92-54A1-4E39-9E71-88F092D5A013}}
AppName=ToinggJarvis
AppVersion=2.0.0
AppPublisher=PG-AGI
DefaultDirName={autopf}\ToinggJarvis
DefaultGroupName=ToinggJarvis
OutputDir=dist\installers
OutputBaseFilename=toingg-jarvis-setup-2.0.0-win64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\..\dist\toingg-jarvis.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\jarvis_web.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\jarvis_visual.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\config.example.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\ToinggJarvis"; Filename: "{app}\toingg-jarvis.exe"
Name: "{autodesktop}\ToinggJarvis"; Filename: "{app}\toingg-jarvis.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\toingg-jarvis.exe"; Description: "Launch ToinggJarvis"; Flags: nowait postinstall skipifsilent
