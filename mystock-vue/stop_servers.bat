@echo off
echo Stopping backend server (Port 18888)...
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 18888 -ErrorAction SilentlyContinue; if ($conns) { foreach ($conn in $conns) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue } }"

echo Stopping frontend server (Port 5173 / 5175)...
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue; if ($conns) { foreach ($conn in $conns) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue } }"
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 5175 -ErrorAction SilentlyContinue; if ($conns) { foreach ($conn in $conns) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue } }"

echo Servers stopped!
pause
