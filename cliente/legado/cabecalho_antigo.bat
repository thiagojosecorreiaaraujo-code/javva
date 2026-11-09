<# : jarvis.bat - cliente do Jarvis (o Claude roda no servidor; os comandos rodam aqui)
@echo off
setlocal
set "JARVIS_BAT=%~f0"
set "JARVIS_ARGS=%*"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-Expression ([IO.File]::ReadAllText($env:JARVIS_BAT))"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" if not defined JARVIS_ARGS pause
exit /b %RC%
#>
