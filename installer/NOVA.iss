#define AppName "NOVA"
#ifndef AppVersion
  #define AppVersion "1.5.0"
#endif

[Setup]
AppId={{D56F7189-AAD7-4B55-9B5F-B287F4D520F2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=NOVA
DefaultDirName={autopf}\NOVA
DefaultGroupName=NOVA
OutputDir=..\dist
OutputBaseFilename=NOVA-Setup
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=NOVA
WizardStyle=modern
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"

[Files]
Source: "..\dist\NOVA\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\NOVA"; Filename: "{app}\NOVA.exe"
Name: "{autodesktop}\NOVA"; Filename: "{app}\NOVA.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\NOVA.exe"; Description: "Запустить NOVA"; Flags: nowait postinstall skipifsilent
