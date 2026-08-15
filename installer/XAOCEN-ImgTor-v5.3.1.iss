; Inno Setup installer for XAOCEN ImgTor v5.3.1.
; All application, shortcut and uninstaller icons come from the single
; project resource: ..\resources\xaocen-imgtor.ico.

#define AppName "XAOCEN ImgTor"
#define AppVersion "5.3.1"
#define AppExeName "XAOCEN-ImgTor-v5.3.1.exe"
#define AppPublisher "XAOCEN STUDIO"
#define AppURL "https://github.com/siycaoxgh/xaocen-imgtor"

[Setup]
AppId={{D4B9A2DB-7A7E-4A7D-9D34-6D3F7D3E5D31}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\XAOCEN ImgTor
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\release\v{#AppVersion}
OutputBaseFilename=XAOCEN-ImgTor-v{#AppVersion}-setup
SetupIconFile=..\resources\xaocen-imgtor.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} installer
VersionInfoProductName={#AppName}
LicenseFile=..\LICENSE

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\NOTICE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\FFMPEG_SETUP.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Comment: "{#AppName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标："; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent
