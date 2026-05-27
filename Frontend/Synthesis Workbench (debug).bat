@echo off
cd /d "%~dp0"

REM ============================================================
REM  Synthesis Workbench launcher  --  DEBUG BUILD
REM
REM  Use this one when something goes wrong. It keeps a console
REM  window open, logs everything desktop.py prints to
REM  launcher_log.txt, and pauses at the end so nothing flashes
REM  past before you can read it.
REM
REM  For everyday use, double-click "Synthesis Workbench.bat"
REM  instead -- that one opens the app with no console window.
REM ============================================================

set "PY=%USERPROFILE%\miniconda3\python.exe"
if not exist "%PY%" set "PY=python"

set "LOG=%~dp0launcher_log.txt"

echo Launching Synthesis Workbench (debug)...
echo   Python : %PY%
echo   Log    : %LOG%
echo.

"%PY%" desktop.py > "%LOG%" 2>&1

echo.
echo ============================================================
echo  desktop.py exited with code %errorlevel%
echo  The full output was saved to:
echo    %LOG%
echo ============================================================
pause
