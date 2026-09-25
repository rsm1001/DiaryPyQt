# Codex PostToolUse 适配层：复用 Claude 与 Codex 共用的风格守卫实现。
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$guard = Join-Path $projectRoot '.claude\hooks\style_guard.py'

if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "style_guard 启动失败：未找到项目 Python 环境 $python"
    exit 1
}

if (-not (Test-Path -LiteralPath $guard)) {
    Write-Error "style_guard 启动失败：未找到共用守卫脚本 $guard"
    exit 1
}

$env:STYLE_GUARD_PROJECT_DIR = $projectRoot
& $python $guard
exit $LASTEXITCODE