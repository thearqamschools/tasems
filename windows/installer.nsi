; TASEMS-Setup.exe — installs the offline test copy of TASEMS on one Windows computer (docs/WINDOWS_INSTALL.md).
; Built on Linux by windows/build_installer.sh with makensis. Installs for the current user (no admin rights).
Unicode true
!include "MUI2.nsh"

!define APPNAME "TASEMS"
!define FULLNAME "TASEMS - The Arqam Schools"
!ifndef VERSION
  !define VERSION "test"
!endif

Name "${FULLNAME}"
OutFile "${OUTDIR}\TASEMS-Setup.exe"
InstallDir "$LOCALAPPDATA\TASEMS"
RequestExecutionLevel user
SetCompressor /SOLID lzma
BrandingText "The Arqam Schools"

!define MUI_ICON "${BUILD}\app\windows\tasems.ico"
!define MUI_UNICON "${BUILD}\app\windows\tasems.ico"
!define MUI_WELCOMEPAGE_TITLE "TASEMS for The Arqam Schools"
!define MUI_WELCOMEPAGE_TEXT "This installs the offline test copy of TASEMS (version ${VERSION}) on this computer.$\r$\n$\r$\nNo internet is needed. Data stays on this computer.$\r$\n$\r$\nClick Next to continue."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Start TASEMS now"
!define MUI_FINISHPAGE_RUN_FUNCTION StartTasems

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

!define PY '"$INSTDIR\python\python.exe"'
!define LAUNCHER '-E -s "$INSTDIR\app\windows\launcher.py"'

Function StartTasems
  Exec '${PY} ${LAUNCHER}'
FunctionEnd

Section "TASEMS" Main
  SetOutPath "$INSTDIR"
  ; A running database would lock its files: stop it first (an older TASEMS may be installed).
  IfFileExists "$INSTDIR\app\windows\launcher.py" 0 +2
    ExecWait '${PY} ${LAUNCHER} --stop-quiet'
  ; A new version replaces the program; the data (in TASEMS-data) is kept.
  RMDir /r "$INSTDIR\app"
  File /r "${BUILD}\python"
  File /r "${BUILD}\pgsql"
  File /r "${BUILD}\gtk"
  File /r "${BUILD}\app"

  CreateShortcut "$DESKTOP\TASEMS.lnk" ${PY} '${LAUNCHER}' "$INSTDIR\app\windows\tasems.ico"
  CreateDirectory "$SMPROGRAMS\TASEMS"
  CreateShortcut "$SMPROGRAMS\TASEMS\TASEMS.lnk" ${PY} '${LAUNCHER}' "$INSTDIR\app\windows\tasems.ico"
  CreateShortcut "$SMPROGRAMS\TASEMS\Make master login.lnk" ${PY} '${LAUNCHER} --master' "$INSTDIR\app\windows\tasems.ico"
  CreateShortcut "$SMPROGRAMS\TASEMS\Backup data.lnk" ${PY} '${LAUNCHER} --backup' "$INSTDIR\app\windows\tasems.ico"
  CreateShortcut "$SMPROGRAMS\TASEMS\Stop database.lnk" ${PY} '${LAUNCHER} --stop' "$INSTDIR\app\windows\tasems.ico"
  CreateShortcut "$SMPROGRAMS\TASEMS\Uninstall TASEMS.lnk" "$INSTDIR\Uninstall.exe"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TASEMS" "DisplayName" "${FULLNAME}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TASEMS" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TASEMS" "Publisher" "The Arqam Schools"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TASEMS" "DisplayIcon" "$INSTDIR\app\windows\tasems.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TASEMS" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  ExecWait '${PY} ${LAUNCHER} --stop-quiet'
  Delete "$DESKTOP\TASEMS.lnk"
  RMDir /r "$SMPROGRAMS\TASEMS"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TASEMS"
  MessageBox MB_OK "TASEMS is removed. Its data is kept in $LOCALAPPDATA\TASEMS-data (delete that folder to remove the data too)."
SectionEnd
