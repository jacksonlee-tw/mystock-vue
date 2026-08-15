@echo off
echo Stopping all Python processes...
taskkill /IM python.exe /F 2>nul
taskkill /IM pythonw.exe /F 2>nul
echo All Python processes have been stopped.
pause
