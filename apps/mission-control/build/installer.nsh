; theFactory Mission Control -- custom NSIS pages and hooks.
;
; Included by electron-builder (package.json build.nsis.include). Operator
; decisions of 2026-09-27 (docs/ELECTRON_INSTALLER.md):
;   * Docker Desktop: check and guide -- never install third-party software.
;   * Closing the window keeps the factory running in the tray (app side).
;   * Start with Windows: OFF by default, opt-in checkbox on the finish page.
;   * Uninstall: KEEP data by default; removing everything is an explicit,
;     twice-confirmed choice because the data includes audit evidence under
;     legal hold.
;
; The uninstaller never runs Docker itself: it asks the app, run as plain Node
; (ELECTRON_RUN_AS_NODE=1), to execute resources\maintenance\maintenance.js,
; whose progress lines stream into the uninstall log.

!include nsDialogs.nsh
!include LogicLib.nsh

; Must equal AUTOSTART_NAME in electron/main.ts: one registry value, one setting.
!define FACTORY_AUTOSTART_NAME "com.holygrail.mission-control"
!define FACTORY_RUN_KEY "Software\Microsoft\Windows\CurrentVersion\Run"
!define FACTORY_STARTUP_APPROVED_KEY "Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
!define FACTORY_DOCKER_URL "https://docs.docker.com/desktop/setup/install/windows-install/"

; Installer and uninstaller are compiled in separate passes with warnings as
; errors, so each pass declares only what it uses. Declared at file level: this
; file is included before any page is defined.
!ifdef BUILD_UNINSTALLER
  Var FactoryKeepRadio
  Var FactoryRemoveRadio
  Var FactoryRemoveData
!else
  Var FactoryPrereqDialog
  Var FactoryDockerLabel
  Var FactoryWslLabel
  Var FactoryHintLabel
!endif

; ---------------------------------------------------------------------------
; Installer: prerequisites page (after the install-location page)
; ---------------------------------------------------------------------------
; Page functions are defined inside the page macro: electron-builder inserts it
; after Modern UI is loaded, which MUI_HEADER_TEXT needs.
!macro customPageAfterChangeDir
Function FactoryPrereqPage
  ${If} ${isUpdated}
    Abort ; an update keeps the machine it already runs on
  ${EndIf}
  !insertmacro MUI_HEADER_TEXT "Prerequisites" "theFactory runs its services in Docker Desktop."
  nsDialogs::Create 1018
  Pop $FactoryPrereqDialog
  ${If} $FactoryPrereqDialog == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 24u "theFactory needs Docker Desktop with the WSL 2 backend. This installer checks for it but never installs third-party software for you."
  Pop $0
  ${NSD_CreateLabel} 0 32u 100% 12u ""
  Pop $FactoryDockerLabel
  ${NSD_CreateLabel} 0 48u 100% 12u ""
  Pop $FactoryWslLabel

  ${NSD_CreateButton} 0 70u 110u 16u "Get Docker Desktop"
  Pop $0
  ${NSD_OnClick} $0 FactoryOpenDockerDownload
  ${NSD_CreateButton} 118u 70u 70u 16u "Re-check"
  Pop $0
  ${NSD_OnClick} $0 FactoryRecheck

  ${NSD_CreateLabel} 0 96u 100% 36u "You can continue now and install Docker Desktop later: on first launch theFactory checks again and shows a status window while it downloads its services (several GB the first time)."
  Pop $FactoryHintLabel

  Call FactoryRefreshPrereqs
  nsDialogs::Show
FunctionEnd

Function FactoryPrereqLeave
FunctionEnd

  Page custom FactoryPrereqPage FactoryPrereqLeave
!macroend


!ifndef BUILD_UNINSTALLER

; Sets $0 to "running", "installed" or "missing".
Function FactoryDockerState
  nsExec::ExecToStack 'docker version --format "{{.Server.Version}}"'
  Pop $1
  Pop $2
  ${If} $1 == 0
    StrCpy $0 "running"
    Return
  ${EndIf}
  ${If} ${FileExists} "$PROGRAMFILES64\Docker\Docker\Docker Desktop.exe"
    StrCpy $0 "installed"
  ${Else}
    StrCpy $0 "missing"
  ${EndIf}
FunctionEnd

; Sets $0 to "ok" or "missing".
Function FactoryWslState
  nsExec::ExecToStack '"$SYSDIR\wsl.exe" --status'
  Pop $1
  Pop $2
  ${If} $1 == 0
    StrCpy $0 "ok"
  ${Else}
    StrCpy $0 "missing"
  ${EndIf}
FunctionEnd

Function FactoryRefreshPrereqs
  Call FactoryDockerState
  ${If} $0 == "running"
    ${NSD_SetText} $FactoryDockerLabel "Docker Desktop:  installed and running  (OK)"
  ${ElseIf} $0 == "installed"
    ${NSD_SetText} $FactoryDockerLabel "Docker Desktop:  installed, not running -- start it before first launch"
  ${Else}
    ${NSD_SetText} $FactoryDockerLabel "Docker Desktop:  NOT INSTALLED -- required to run the factory"
  ${EndIf}
  Call FactoryWslState
  ${If} $0 == "ok"
    ${NSD_SetText} $FactoryWslLabel "WSL 2:  available  (OK)"
  ${Else}
    ${NSD_SetText} $FactoryWslLabel "WSL 2:  not detected -- Docker Desktop's installer can enable it"
  ${EndIf}
FunctionEnd

Function FactoryOpenDockerDownload
  ExecShell "open" "${FACTORY_DOCKER_URL}"
FunctionEnd

Function FactoryRecheck
  Call FactoryRefreshPrereqs
FunctionEnd


!endif ; !BUILD_UNINSTALLER

; ---------------------------------------------------------------------------
; Installer: finish page with run-now and opt-in "Start with Windows"
; ---------------------------------------------------------------------------
!macro customFinishPage
  Function FactoryStartApp
    ${if} ${isUpdated}
      StrCpy $1 "--updated"
    ${else}
      StrCpy $1 ""
    ${endif}
    ${StdUtils.ExecShellAsUser} $0 "$launchLink" "open" "$1"
  FunctionEnd

  Function FactoryEnableAutostart
    WriteRegStr HKCU "${FACTORY_RUN_KEY}" "${FACTORY_AUTOSTART_NAME}" '"$INSTDIR\${APP_EXECUTABLE_FILENAME}" --hidden'
  FunctionEnd

  !define MUI_FINISHPAGE_RUN
  !define MUI_FINISHPAGE_RUN_TEXT "Launch theFactory Mission Control now"
  !define MUI_FINISHPAGE_RUN_FUNCTION "FactoryStartApp"
  ; MUI's second finish-page checkbox, repurposed; off unless the user opts in.
  !define MUI_FINISHPAGE_SHOWREADME ""
  !define MUI_FINISHPAGE_SHOWREADME_TEXT "Start theFactory when Windows starts (runs in the tray)"
  !define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
  !define MUI_FINISHPAGE_SHOWREADME_FUNCTION "FactoryEnableAutostart"
  !insertmacro MUI_PAGE_FINISH
!macroend

; ---------------------------------------------------------------------------
; Uninstaller: keep-or-remove-data page (before anything is removed)
; ---------------------------------------------------------------------------
!macro customUnWelcomePage
Function un.FactoryDataPage
  !insertmacro MUI_HEADER_TEXT "Your factory data" "Choose what happens to your missions, settings and audit evidence."
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 30u "theFactory's services and data live in Docker Desktop. The app itself is always removed; its data does not have to be."
  Pop $0

  ${NSD_CreateRadioButton} 0 36u 100% 12u "Keep my data (recommended)"
  Pop $FactoryKeepRadio
  ${NSD_CreateLabel} 12u 50u 96% 24u "Stops and removes the factory's containers. Missions, settings, the local vault and audit evidence are kept, and a reinstall picks them up again."
  Pop $0

  ${NSD_CreateRadioButton} 0 80u 100% 12u "Remove everything"
  Pop $FactoryRemoveRadio
  ${NSD_CreateLabel} 12u 94u 96% 32u "Also deletes all factory data volumes and images: every mission, the vault, and audit evidence -- including reports under legal hold and retention. This cannot be undone."
  Pop $0

  ${NSD_Check} $FactoryKeepRadio
  nsDialogs::Show
FunctionEnd

Function un.FactoryDataLeave
  StrCpy $FactoryRemoveData "0"
  ${NSD_GetState} $FactoryRemoveRadio $0
  ${If} $0 == ${BST_CHECKED}
    MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 \
      "Permanently delete ALL theFactory data?$\r$\n$\r$\nThis removes every mission, your local vault, and all audit evidence -- including failed-audit reports kept under legal hold for compliance.$\r$\n$\r$\nIf you might need them for an audit, choose No and keep your data." \
      IDYES factory_confirmed
    Abort ; back to the page, nothing removed
    factory_confirmed:
    StrCpy $FactoryRemoveData "1"
  ${EndIf}
FunctionEnd

  !insertmacro MUI_UNPAGE_WELCOME
  UninstPage custom un.FactoryDataPage un.FactoryDataLeave
!macroend


; ---------------------------------------------------------------------------
; Uninstaller: stop/remove the stack, then clean up app-level state
; ---------------------------------------------------------------------------
!macro customUnInstall
  ${ifNot} ${isUpdated}
    ; Silent uninstalls (/S) never show the page: they keep data.
    ${If} $FactoryRemoveData == "1"
      StrCpy $R9 "purge"
    ${Else}
      StrCpy $R9 "down"
    ${EndIf}

    SetShellVarContext current
    ; Electron's userData folder is named after the product name.
    StrCpy $R8 "$APPDATA\${PRODUCT_NAME}"

    DetailPrint "Stopping theFactory services ($R9)..."
    System::Call 'Kernel32::SetEnvironmentVariable(t "ELECTRON_RUN_AS_NODE", t "1")'
    nsExec::ExecToLog '"$INSTDIR\${APP_EXECUTABLE_FILENAME}" "$INSTDIR\resources\maintenance\maintenance.js" $R9 --deploy-dir "$INSTDIR\resources\deploy" --env "$R8\backend.env" --version ${VERSION}'
    Pop $0
    System::Call 'Kernel32::SetEnvironmentVariable(t "ELECTRON_RUN_AS_NODE", i 0)'
    ${If} $0 != 0
      DetailPrint "Some factory services could not be stopped cleanly (code $0). See the log above."
    ${EndIf}

    DeleteRegValue HKCU "${FACTORY_RUN_KEY}" "${FACTORY_AUTOSTART_NAME}"
    DeleteRegValue HKCU "${FACTORY_STARTUP_APPROVED_KEY}" "${FACTORY_AUTOSTART_NAME}"

    ${If} $R9 == "purge"
      DetailPrint "Removing application data in $R8"
      RMDir /r "$R8"
    ${Else}
      ; backend.env holds the secrets that unlock the kept volumes; a
      ; reinstall must find it or the old database can no longer be opened.
      DetailPrint "Kept application data in $R8 (configuration and secrets for your kept data)"
    ${EndIf}
  ${endIf}
!macroend
