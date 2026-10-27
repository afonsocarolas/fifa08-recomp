; Setup for the PC build: the launcher and the recompiled game, without any game
; files. Players point the launcher at their own FIFA 08 disc files.
; Built by tools\build_setup.ps1, which fills the stage folder first.

#ifndef Stage
  #define Stage "..\out\setup\stage"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6C1E3F0A-4B8D-4E2A-9F57-0FA08C0FFEE8}
AppName=FIFA 08 Recomp
AppVersion={#AppVersion}
AppPublisher=afonsocarolas
AppPublisherURL=https://github.com/afonsocarolas/fifa08-recomp
DefaultDirName={autopf}\FIFA 08 Recomp
DefaultGroupName=FIFA 08 Recomp
DisableProgramGroupPage=yes
; Per-user install: the launcher and the game write their settings and logs
; next to themselves, which Program Files would not allow.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\out\setup
OutputBaseFilename=FIFA08-Recomp-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\FIFA08 Launcher.exe

[Messages]
WelcomeLabel2=This will install FIFA 08 Recomp [ver] on your computer.%n%nGame files are not included. You need your own FIFA 08 Xbox 360 disc files; after installing, open the launcher and choose the folder that has default.xex.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Stage}\launcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs
Source: "{#Stage}\bin\*"; DestDir: "{app}\bin"; Flags: ignoreversion recursesubdirs

[Dirs]
Name: "{app}\Game"

[Icons]
Name: "{group}\FIFA 08 Recomp"; Filename: "{app}\FIFA08 Launcher.exe"
Name: "{group}\Uninstall FIFA 08 Recomp"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FIFA 08 Recomp"; Filename: "{app}\FIFA08 Launcher.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FIFA08 Launcher.exe"; Description: "{cm:LaunchProgram,FIFA 08 Recomp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Settings and logs written after install. Game files the player copied into
; the Game folder are left alone.
Type: files; Name: "{app}\launcher.json"
Type: files; Name: "{app}\bin\*.log"
Type: files; Name: "{app}\bin\fifa08.toml"
