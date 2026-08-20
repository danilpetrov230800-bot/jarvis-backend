#define MyAppName "NOVA"
#define MyAppVersion "1.5.0"
#define MyAppPublisher "NOVA"
#define MyAppURL "https://github.com/danilpetrov230800-bot/jarvis-backend"

[Setup]
AppId={{8F3C2A91-7B6E-4D12-9C44-1A2B3C4D5E6F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\NOVA
DefaultGroupName=NOVA
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=NOVA-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=NOVA
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut"; GroupDescription: "Shortcuts"; Flags: checkedonce

[Files]
Source: "..\dist\NOVA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NOVA"; Filename: "{app}\NOVA.vbs"; WorkingDir: "{app}"
Name: "{group}\NOVA Debug"; Filename: "{app}\NOVA.bat"; WorkingDir: "{app}"
Name: "{group}\Uninstall NOVA"; Filename: "{uninstallexe}"
Name: "{autodesktop}\NOVA"; Filename: "{app}\NOVA.vbs"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\NOVA.vbs"; Description: "Launch NOVA"; Flags: nowait postinstall skipifsilent
