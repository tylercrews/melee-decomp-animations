@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto local_python
py -3.13 -c "import sys" >nul 2>&1
if not errorlevel 1 goto python_launcher
python -c "import sys" >nul 2>&1
if not errorlevel 1 goto path_python
echo Python was not found. Install 64-bit Python 3.13; see README.md.
pause
exit /b 1
:local_python
".venv\Scripts\python.exe" -m tools.melee_anim.launcher open %*
set "launcher_status=%errorlevel%"
goto finish
:python_launcher
py -3.13 -m tools.melee_anim.launcher open %*
set "launcher_status=%errorlevel%"
goto finish
:path_python
python -m tools.melee_anim.launcher open %*
set "launcher_status=%errorlevel%"
:finish
if not "%launcher_status%"=="0" pause
exit /b %launcher_status%
