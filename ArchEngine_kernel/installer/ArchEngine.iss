; ArchEngine Installer Script
; Inno Setup 6.x required
; https://jrsoftware.org/isinfo.php

#define AppName "ArchEngine"
#define AppVersion "0.1.0"
#define AppPublisher "ArchEngine"
#define AppURL "https://archengine.com"
#define AppExeName "ArchEngine.exe"

[Setup]
; Application identity
AppId={{8A7E4F9C-3B2D-4E5F-A1C8-9D0E2F3B4A5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}

; Installation directories
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; Output settings
OutputDir=Output
OutputBaseFilename=ArchEngine-{#AppVersion}-Setup
; SetupIconFile=assets\icon.ico  ; Uncomment when icon.ico is available
UninstallDisplayIcon={app}\{#AppExeName}

; Compression settings (LZMA2 ultra for best compression)
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4

; Architecture requirements
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Privileges
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

; Appearance
WizardStyle=modern
WizardSizePercent=110

; Misc
AllowNoIcons=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "Associate .arch files with ArchEngine"; GroupDescription: "File associations:"

[Files]
; Main application files
Source: "..\build\Release\ArchEngine.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\build\Release\ArchEngineLib.dll"; DestDir: "{app}"; Flags: ignoreversion

; Shaders (required for rendering)
Source: "..\shaders\*.spv"; DestDir: "{app}\shaders"; Flags: ignoreversion

; Materials library
Source: "..\materials\*"; DestDir: "{app}\materials"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.bak,*_old*"

; HDRI environment maps (optional, for IBL lighting)
Source: "..\hdri\*"; DestDir: "{app}\hdri"; Flags: ignoreversion skipifsourcedoesntexist recursesubdirs

; Launcher and documentation
Source: "..\launch_archengine.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README_INSTALL.txt"; DestDir: "{app}"; DestName: "README.txt"; Flags: ignoreversion isreadme

; Sample/test building files
Source: "..\..\Shared\test_building.json"; DestDir: "{app}\samples"; Flags: ignoreversion
Source: "..\..\Shared\TestData\sample_building_complete.json"; DestDir: "{app}\samples"; Flags: ignoreversion
Source: "..\..\Shared\TestData\output\generated_building.json"; DestDir: "{app}\samples"; DestName: "QBD_Generated_House.json"; Flags: ignoreversion

; Runtime installers (extracted to temp, deleted after install)
Source: "..\dist\vulkan_runtime\VulkanRT-Installer.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "redist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not IsVCRuntimeInstalled

[Icons]
; Start menu shortcuts
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"

; Desktop shortcut (optional task)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; File association for .arch files (only if task selected)
Root: HKCR; Subkey: ".arch"; ValueType: string; ValueData: "ArchEngine.Project"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCR; Subkey: ".arch"; ValueName: "Content Type"; ValueType: string; ValueData: "application/x-archengine-project"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCR; Subkey: "ArchEngine.Project"; ValueType: string; ValueData: "ArchEngine Project File"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCR; Subkey: "ArchEngine.Project\DefaultIcon"; ValueType: string; ValueData: "{app}\{#AppExeName},0"; Tasks: fileassoc
Root: HKCR; Subkey: "ArchEngine.Project\shell"; ValueType: string; ValueData: "open"; Tasks: fileassoc
Root: HKCR; Subkey: "ArchEngine.Project\shell\open"; ValueType: string; ValueData: "Open with ArchEngine"; Tasks: fileassoc
Root: HKCR; Subkey: "ArchEngine.Project\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: fileassoc

; App registration for Windows
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{#AppExeName}"; ValueType: string; ValueData: "{app}\{#AppExeName}"; Flags: uninsdeletekey

[Run]
; Launch application after install (optional)
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(AppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Global variables
var
  VulkanCheckPage: TOutputMsgWizardPage;
  VCRuntimeCheckPage: TOutputMsgWizardPage;
  DependenciesChecked: Boolean;

// Check if Vulkan runtime is installed
function IsVulkanInstalled: Boolean;
begin
  // Check for vulkan-1.dll in System32 (primary location)
  Result := FileExists(ExpandConstant('{sys}\vulkan-1.dll'));

  // Also check in SysWOW64 for completeness
  if not Result then
    Result := FileExists(ExpandConstant('{syswow64}\vulkan-1.dll'));
end;

// Check if VC++ 2015-2022 Runtime is installed
function IsVCRuntimeInstalled: Boolean;
var
  Version: String;
  Installed: Cardinal;
begin
  Result := False;

  // Check for VC++ 2015-2022 x64 runtime
  if RegQueryDWordValue(HKLM, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
  begin
    Result := (Installed = 1);
  end;

  // Alternative registry path for newer versions
  if not Result then
  begin
    if RegQueryDWordValue(HKLM, 'SOFTWARE\Wow6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
    begin
      Result := (Installed = 1);
    end;
  end;

  // Check by looking for the actual DLL as fallback
  if not Result then
  begin
    Result := FileExists(ExpandConstant('{sys}\vcruntime140.dll')) and
              FileExists(ExpandConstant('{sys}\msvcp140.dll'));
  end;
end;

// Install Vulkan runtime
procedure InstallVulkanRuntime;
var
  ResultCode: Integer;
  InstallerPath: String;
begin
  InstallerPath := ExpandConstant('{tmp}\VulkanRT-Installer.exe');

  if FileExists(InstallerPath) then
  begin
    WizardForm.StatusLabel.Caption := 'Installing Vulkan Runtime...';

    // Run Vulkan installer with UI (not silent) so user can see progress and any errors
    // Using empty string for parameters runs the installer normally with its GUI
    if not Exec(InstallerPath, '', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
    begin
      MsgBox('Failed to run Vulkan Runtime installer. Error code: ' + IntToStr(ResultCode) + #13#10 +
             'Please install Vulkan Runtime manually from https://vulkan.lunarg.com/',
             mbError, MB_OK);
    end
    else if ResultCode <> 0 then
    begin
      MsgBox('Vulkan Runtime installer returned error code: ' + IntToStr(ResultCode) + #13#10 +
             'Installation may have failed. If ArchEngine does not work, please install Vulkan Runtime manually.',
             mbInformation, MB_OK);
    end;
  end
  else
  begin
    MsgBox('Vulkan Runtime installer not found.' + #13#10 +
           'Please install Vulkan Runtime manually from https://vulkan.lunarg.com/',
           mbError, MB_OK);
  end;
end;

// Install VC++ runtime
procedure InstallVCRuntime;
var
  ResultCode: Integer;
  InstallerPath: String;
begin
  InstallerPath := ExpandConstant('{tmp}\vc_redist.x64.exe');

  if FileExists(InstallerPath) then
  begin
    WizardForm.StatusLabel.Caption := 'Installing Visual C++ Runtime...';

    // Run VC++ installer quietly (shows progress but no prompts)
    if not Exec(InstallerPath, '/quiet /norestart', '', SW_SHOW, ewWaitUntilTerminated, ResultCode) then
    begin
      MsgBox('Failed to run Visual C++ Runtime installer. Error code: ' + IntToStr(ResultCode) + #13#10 +
             'Please install Visual C++ 2015-2022 Redistributable (x64) manually.',
             mbError, MB_OK);
    end
    else if (ResultCode <> 0) and (ResultCode <> 3010) then // 3010 = success, reboot required
    begin
      MsgBox('Visual C++ Runtime installer returned code: ' + IntToStr(ResultCode) + #13#10 +
             'Installation may have failed. If ArchEngine does not work, please install VC++ Runtime manually.',
             mbInformation, MB_OK);
    end;
  end
  else
  begin
    MsgBox('Visual C++ Runtime installer not found in package.' + #13#10 +
           'Please install Visual C++ 2015-2022 Redistributable (x64) manually from Microsoft.',
           mbError, MB_OK);
  end;
end;

// Check and install dependencies
procedure CheckAndInstallDependencies;
var
  NeedVulkan, NeedVCRuntime: Boolean;
  Message: String;
begin
  NeedVulkan := not IsVulkanInstalled;
  NeedVCRuntime := not IsVCRuntimeInstalled;

  // If dependencies are missing, ask user
  if NeedVulkan or NeedVCRuntime then
  begin
    Message := 'The following required components are missing:' + #13#10#13#10;

    if NeedVulkan then
      Message := Message + '  - Vulkan Runtime' + #13#10;
    if NeedVCRuntime then
      Message := Message + '  - Visual C++ 2015-2022 Runtime (x64)' + #13#10;

    Message := Message + #13#10 + 'Would you like to install them now?';

    if MsgBox(Message, mbConfirmation, MB_YESNO) = IDYES then
    begin
      if NeedVulkan then
        InstallVulkanRuntime;
      if NeedVCRuntime then
        InstallVCRuntime;
    end
    else
    begin
      MsgBox('ArchEngine requires these components to run.' + #13#10 +
             'The application may not work correctly without them.' + #13#10#13#10 +
             'You can install them later from:' + #13#10 +
             '  - Vulkan: https://vulkan.lunarg.com/' + #13#10 +
             '  - VC++ Runtime: https://aka.ms/vs/17/release/vc_redist.x64.exe',
             mbInformation, MB_OK);
    end;
  end;
end;

// Called after installation completes
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    CheckAndInstallDependencies;
  end;
end;

// Initialize setup
function InitializeSetup: Boolean;
begin
  Result := True;
  DependenciesChecked := False;
end;

// Custom message for uninstall
function InitializeUninstall: Boolean;
begin
  Result := True;
end;

// Notify user about what will be removed
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Optionally clean up user data
    if MsgBox('Would you like to remove user settings and cached data?' + #13#10 +
              '(Render outputs and project files will NOT be deleted)',
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree(ExpandConstant('{localappdata}\ArchEngine'), True, True, True);
    end;
  end;
end;
