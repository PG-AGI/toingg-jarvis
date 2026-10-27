; Inno Setup script for the Windows installer. installers/build.py runs it as:
;   ISCC /DAppVersion=<ver> /DAppSourceDir=<pyinstaller dir> /DOutputDir=<dir> /DOutputBaseFilename=<name> jarvis.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppSourceDir
  #define AppSourceDir "..\..\build\pyinstaller\dist\toingg-jarvis"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "toingg-jarvis-setup"
#endif

#define AppName "Toingg JARVIS"
#define AppExe "toingg-jarvis.exe"

[Setup]
; Keep AppId fixed: it is how a newer installer finds and upgrades an existing install.
AppId={{6F1C2E9A-4B7D-4E3A-9C55-2D8B1A7E0F41}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PG-AGI
AppPublisherURL=https://github.com/PG-AGI/toingg-jarvis
AppSupportURL=https://github.com/PG-AGI/toingg-jarvis/issues
AppUpdatesURL=https://github.com/PG-AGI/toingg-jarvis/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install by default (no admin prompt); users can still pick all users.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
LicenseFile=..\..\LICENSE
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; Drop files left over from an older version before copying the new one.
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autoprograms}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
