@echo off
setlocal
set "TARGET=%~dp0Nimbus.exe"
if not exist "%TARGET%" (
  echo Nimbus.exe not found next to this script.
  pause
  exit /b 1
)
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Nimbus.lnk'); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%TARGET%,0'; $s.Save()"
echo Shortcut created on your desktop.
ping -n 4 127.0.0.1 >nul
