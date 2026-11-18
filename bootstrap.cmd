@echo off
rem Start here on a fresh Windows PC: double-click, or run from a prompt with
rem install.py's options, e.g.   bootstrap.cmd --mpc-host 192.168.0.1 --from-mpc
rem
rem Runs bootstrap.ps1 for this one process past the execution policy that
rem blocks scripts downloaded from the internet. See README.md.
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" %*
set "RC=%ERRORLEVEL%"
rem Started by double-click (no arguments): keep the window open.
if "%~1"=="" pause
exit /b %RC%
