@echo off
chcp 65001 >nul
echo 正在停止後端服務 (Port 8000)...
powershell -Command "Get-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force"

echo 正在停止前端服務 (Port 5173)...
powershell -Command "Get-Process -Id (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force"

echo 前後端服務已停止！
pause
