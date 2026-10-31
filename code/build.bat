@echo off
setlocal
cd /d "%~dp0"

rem Find Visual Studio and select the x86 tools, even from a regular terminal.
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" goto noTools
set "LAB2_VS="
for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "LAB2_VS=%%I"
if not defined LAB2_VS goto noTools
call "%LAB2_VS%\VC\Auxiliary\Build\vcvars32.bat"
if errorlevel 1 exit /b 1

echo ml /nologo /c /coff /Zi main.asm
ml /nologo /c /coff /Zi main.asm
if errorlevel 1 exit /b 1
echo link /nologo /subsystem:console /machine:x86 /debug /out:lab2.exe main.obj kernel32.lib
link /nologo /subsystem:console /machine:x86 /debug /out:lab2.exe main.obj kernel32.lib
if errorlevel 1 exit /b 1
echo Built lab2.exe
exit /b 0

:noTools
echo Install Visual Studio or Build Tools with Desktop development with C++.
exit /b 1
