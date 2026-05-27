@echo off
REM ============================================================
REM  Synthesis Workbench  --  launcher
REM
REM  Opens the app in its own window, with no console window.
REM  Uses pythonw.exe (the windowless Python) from the conda
REM  base environment, where pywebview is installed. 'start'
REM  launches it detached, so this script closes itself at once.
REM
REM  If the app does NOT appear, run "Synthesis Workbench
REM  (debug).bat" instead -- that one keeps a console open and
REM  writes launcher_log.txt so the problem can be seen.
REM ============================================================
cd /d "%~dp0"
set "PYW=%USERPROFILE%\miniconda3\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
start "" "%PYW%" desktop.py
