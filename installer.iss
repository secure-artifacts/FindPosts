; Inno Setup Script - Pinterest 高清图片爬取工具
; 生成带开始菜单、桌面快捷方式、卸载程序的正式安装包

#define MyAppName      "Pinterest 爬取工具"
#define MyAppVersion   "1.0.4"
#define MyAppPublisher "secure-artifacts"
#define MyAppURL       "https://github.com/secure-artifacts/FindPosts"
#define MyAppExeName   "PinterestCrawler.exe"

[Setup]
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
; 安装包输出
OutputDir=installer_output
OutputBaseFilename=PinterestCrawler_Setup_{#MyAppVersion}
SetupIconFile=log.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; 需要管理员权限
PrivilegesRequired=admin
; 支持 Windows 10/11
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 卸载图标
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english";          MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "创建桌面快捷方式(&D)";      GroupDescription: "附加图标:"; Flags: unchecked
Name: "quicklaunchicon"; Description: "创建快速启动栏快捷方式(&Q)"; GroupDescription: "附加图标:"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; 主程序
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; 开始菜单
Name: "{group}\{#MyAppName}";                          Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}";                    Filename: "{uninstallexe}"
; 桌面（可选）
Name: "{autodesktop}\{#MyAppName}";                    Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 快速启动（可选）
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "立即启动 {#MyAppName}"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时清理程序生成的临时文件（不删除用户下载的图片）
Type: files;     Name: "{app}\*.log"
Type: dirifempty; Name: "{app}"
