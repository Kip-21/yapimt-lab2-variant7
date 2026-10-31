@echo off
setlocal
cd /d "%~dp0"
if exist lab2.exe goto run
call build.bat
if errorlevel 1 goto done
:run
lab2.exe
:done
pause
