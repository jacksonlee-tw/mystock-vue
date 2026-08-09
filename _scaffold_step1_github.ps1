$src = 'C:\git_repos\tcci-fastapi-vue-template\.github'
$dst = 'C:\github_repos\#ai-agent\mystock-analysis\.github'

# 建立目標 .github 目錄
New-Item -ItemType Directory -Path $dst -Force | Out-Null

# 複製 agents、hooks、prompts（整個目錄）
foreach ($f in @('agents','hooks','prompts')) {
    $s = Join-Path $src $f
    if (Test-Path $s) {
        Copy-Item -Path $s -Destination $dst -Recurse -Force
        Write-Host "Synced: $f"
    }
}

# 複製 instructions — 排除 delphi-source.instructions.md
$instrSrc = Join-Path $src 'instructions'
$instrDst = Join-Path $dst 'instructions'
New-Item -ItemType Directory -Path $instrDst -Force | Out-Null
Get-ChildItem $instrSrc -File | Where-Object { $_.Name -ne 'delphi-source.instructions.md' } | ForEach-Object {
    Copy-Item $_.FullName -Destination $instrDst -Force
    Write-Host "Synced instruction: $($_.Name)"
}

# 複製 skills — 排除 Delphi 相關 skill 目錄
$skillSrc = Join-Path $src 'skills'
$skillDst = Join-Path $dst 'skills'
$excludeSkills = @('delphi-to-usecase','delphi-to-vue','delphi-to-python-driver','fr3-to-reportlab')
New-Item -ItemType Directory -Path $skillDst -Force | Out-Null
Get-ChildItem $skillSrc -Directory | Where-Object { $excludeSkills -notcontains $_.Name } | ForEach-Object {
    Copy-Item $_.FullName -Destination $skillDst -Recurse -Force
    Write-Host "Synced skill: $($_.Name)"
}

# 複製 copilot-instructions.md
Copy-Item (Join-Path $src 'copilot-instructions.md') -Destination $dst -Force
Write-Host "Synced: copilot-instructions.md"

Write-Host "--- .github sync complete ---"
