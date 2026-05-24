; Inno Setup Script - Pinterest 高清图片爬取工具

#ifndef MyAppVersion
  #define MyAppVersion "1.0.4"
#endif

#define MyAppName      "Pinterest 爬取工具"
#define MyAppPublisher "secure-artifacts"
#define MyAppURL       "https://github.com/secure-artifacts/FindPosts"
#define MyAppExeName   "PinterestCrawler.exe"

[Setup]
; AppId 固定不变 → Windows 将新版本识别为对旧版本的升级，无需手动卸载
AppId={{A3F2B8C4-1D2E-4F56-8A9B-C0D1E2F34567}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\PinterestCrawler
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=PinterestCrawler_Setup_{#MyAppVersion}
SetupIconFile=log.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; 允许普通用户安装/升级（不强制要求管理员）
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
; 安装前自动关闭正在运行的旧版本
CloseApplications=yes
CloseApplicationsFilter=*PinterestCrawler*
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "Launch {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files;      Name: "{app}\*.log"
Type: dirifempty; Name: "{app}"
