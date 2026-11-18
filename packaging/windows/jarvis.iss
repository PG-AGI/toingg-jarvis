; Inno Setup script. Build: iscc /DAppVersion=0.1.0 packaging\windows\jarvis.iss
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6C1E5E0A-4B0B-4F0E-9D0B-7A3B1C2D4E5F}
AppName=Toingg Jarvis
AppVersion={#AppVersion}
AppPublisher=PG-AGI
DefaultDirName={localappdata}\Toingg Jarvis
DefaultGroupName=Toingg Jarvis
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=toingg-jarvis-{#AppVersion}-setup
Compression=lzma
SolidCompression=yes
; The app writes config.json next to its code, so it installs per-user.

[Files]
Source: "..\..\jarvis_launcher.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\native_file_manager.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\pipecat_gemini_tools.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\browserClient.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\jarvis_visual.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\jarvis_web.html"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\config.example.json"; DestDir: "{app}"; DestName: "config.json"; Flags: onlyifdoesntexist
Source: "..\..\JARVIS.bat"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Toingg Jarvis"; Filename: "{app}\JARVIS.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\Toingg Jarvis"; Filename: "{app}\JARVIS.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"
