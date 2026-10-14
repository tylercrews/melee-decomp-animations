@echo off
setlocal
cd /d "%~dp0"
if errorlevel 1 exit /b 1
set "python_check=import struct,sys; sys.exit(not ((3,10) <= sys.version_info[:2] <= (3,13) and struct.calcsize('P') == 8))"
if exist ".venv" goto check_local
:find_python
py -3.13 -c "%python_check%" >nul 2>&1
if not errorlevel 1 goto python_launcher
python -c "%python_check%" >nul 2>&1
if not errorlevel 1 goto path_python
"%LocalAppData%\Programs\Python\Python313\python.exe" -c "%python_check%" >nul 2>&1
if not errorlevel 1 goto installed_python
if defined python_install_attempted goto missing_python
where winget >nul 2>&1
if errorlevel 1 goto missing_python
echo Installing Python 3.13 for this user using Windows Package Manager...
set "python_install_attempted=1"
winget install --id Python.Python.3.13 --exact --source winget --scope user
if errorlevel 1 goto missing_python
goto find_python
:check_local
".venv\Scripts\python.exe" -c "%python_check%" >nul 2>&1
if not errorlevel 1 goto local_python
echo The existing .venv is incompatible or incomplete. Rename it and run setup again.
set "launcher_status=1"
goto finish
:missing_python
echo Compatible Python was not found or could not be installed.
echo Install 64-bit Python 3.13 from https://www.python.org/downloads/windows/
echo Enable Add Python to PATH, then run this setup again. See README.md.
set "launcher_status=1"
goto finish
:local_python
".venv\Scripts\python.exe" -m tools.melee_anim.launcher import %*
set "launcher_status=%errorlevel%"
goto finish
:python_launcher
py -3.13 -m tools.melee_anim.launcher import %*
set "launcher_status=%errorlevel%"
goto finish
:path_python
python -m tools.melee_anim.launcher import %*
set "launcher_status=%errorlevel%"
goto finish
:installed_python
"%LocalAppData%\Programs\Python\Python313\python.exe" -m tools.melee_anim.launcher import %*
set "launcher_status=%errorlevel%"
:finish
echo.
pause
exit /b %launcher_status%
