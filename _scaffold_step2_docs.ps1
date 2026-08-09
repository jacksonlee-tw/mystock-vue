$src = 'C:\git_repos\tcci-fastapi-vue-template\docs'
$dst = 'C:\github_repos\#ai-agent\mystock-analysis\docs'

# 建立標準文件目錄骨架
$docFolders = @(
    '00_Project_Overview',
    '01_Requirements\use-cases',
    '02_Design\api',
    '02_Design\db',
    '03_Development',
    '04_Tests',
    '11_Standards_and_Templates\Standards',
    '11_Standards_and_Templates\templates\document-templates',
    '11_Standards_and_Templates\templates\prompt-templates',
    '99_Study'
)
foreach ($d in $docFolders) {
    New-Item -ItemType Directory -Path (Join-Path $dst $d) -Force | Out-Null
}
Write-Host "OK: 文件目錄結構已建立"

# 複製 Standards
$stdSrc = Join-Path $src '11_Standards_and_Templates\Standards'
$stdDst = Join-Path $dst '11_Standards_and_Templates\Standards'
if (Test-Path $stdSrc) {
    Copy-Item "$stdSrc\*" $stdDst -Recurse -Force
    Write-Host "Synced: 11_Standards_and_Templates\Standards"
}

# 複製 document-templates
$tmplSrc = Join-Path $src '11_Standards_and_Templates\templates\document-templates'
$tmplDst = Join-Path $dst '11_Standards_and_Templates\templates\document-templates'
if (Test-Path $tmplSrc) {
    Copy-Item "$tmplSrc\*" $tmplDst -Recurse -Force
    Write-Host "Synced: document-templates"
}

# 複製 prompt-templates
$ptSrc = Join-Path $src '11_Standards_and_Templates\templates\prompt-templates'
$ptDst = Join-Path $dst '11_Standards_and_Templates\templates\prompt-templates'
if (Test-Path $ptSrc) {
    Copy-Item "$ptSrc\*" $ptDst -Recurse -Force
    Write-Host "Synced: prompt-templates"
}

# 複製 02_Design 通用文件（排除 A.arrivePlant、python-dll、ai-agent 目錄；排除評估報告 md）
$designSrc = Join-Path $src '02_Design'
$designDst = Join-Path $dst '02_Design'
$designExcludeDirs = @('A.arrivePlant','python-dll','ai-agent')
Get-ChildItem $designSrc -File | Where-Object {
    $_.Name -notmatch '架構評估報告' -and $_.Name -ne '設備串接開發指引.md'
} | ForEach-Object {
    Copy-Item $_.FullName -Destination $designDst -Force
    Write-Host "Synced design file: $($_.Name)"
}
Get-ChildItem $designSrc -Directory | Where-Object {
    $designExcludeDirs -notcontains $_.Name
} | ForEach-Object {
    New-Item -ItemType Directory -Path (Join-Path $designDst $_.Name) -Force | Out-Null
    Copy-Item "$($_.FullName)\*" (Join-Path $designDst $_.Name) -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Synced design dir: $($_.Name)"
}

Write-Host "--- docs sync complete ---"
