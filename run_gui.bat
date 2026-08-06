@echo off
setlocal EnableExtensions
cd /d "%~dp0"

py -3 -m pip install -q -e "%~dp0." 2>nul
if errorlevel 1 (
  echo pip install failed. Use Python 3.10+ with the py launcher.
  exit /b 1
)

py -3 -m eq_augs.web_gui
endlocal
