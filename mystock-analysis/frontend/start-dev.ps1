# 建立 Junction（不含 # 的路徑），繞過 Vite 的 URL fragment bug
$junctionPath = "C:\vite-mystock-frontend"
$targetPath   = $PSScriptRoot   # 此腳本所在目錄（frontend/）

if (-not (Test-Path $junctionPath)) {
    Write-Host "建立 Junction: $junctionPath -> $targetPath"
    New-Item -ItemType Junction -Path $junctionPath -Target $targetPath | Out-Null
} else {
    Write-Host "Junction 已存在: $junctionPath"
}

Write-Host "從 Junction 路徑啟動 Vite..."
Set-Location $junctionPath
npm run dev
