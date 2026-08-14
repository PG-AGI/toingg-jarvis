Unicode True
; Non-solid compression keeps memory use predictable for the bundled browser.
SetCompressor lzma

!ifndef APP_VERSION
  !define APP_VERSION "0.0.0-dev"
!endif
!ifndef SOURCE_DIR
  !error "SOURCE_DIR must point to the PyInstaller onedir output"
!endif
!ifndef OUTPUT_DIR
  !define OUTPUT_DIR "."
!endif

!define PRODUCT_NAME "JARVIS"
!define PRODUCT_PUBLISHER "PG-AGI"
!define PRODUCT_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\JARVIS"

Name "${PRODUCT_NAME} ${APP_VERSION}"
OutFile "${OUTPUT_DIR}\JARVIS-${APP_VERSION}-windows-x64-setup.exe"
InstallDir "$LOCALAPPDATA\Programs\JARVIS"
InstallDirRegKey HKCU "${PRODUCT_KEY}" "InstallLocation"
RequestExecutionLevel user

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  ; Playwright's headed browser is used by JARVIS. The optional headless shell is
  ; deliberately omitted when building from an older local browser cache.
  File /r /x "chromium_headless_shell-*" "${SOURCE_DIR}\*"

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\JARVIS"
  CreateShortcut "$SMPROGRAMS\JARVIS\JARVIS.lnk" "$INSTDIR\JARVIS.exe"
  CreateShortcut "$SMPROGRAMS\JARVIS\Uninstall JARVIS.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\JARVIS.lnk" "$INSTDIR\JARVIS.exe"

  WriteRegStr HKCU "${PRODUCT_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKCU "${PRODUCT_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${PRODUCT_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKCU "${PRODUCT_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${PRODUCT_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${PRODUCT_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${PRODUCT_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\JARVIS.lnk"
  RMDir /r "$SMPROGRAMS\JARVIS"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKCU "${PRODUCT_KEY}"
SectionEnd
