# 制造计划助手 - 一键启动
# 用法：
#   1) 双击 start-all.bat（推荐）
#   2) 或在 PowerShell 里执行  .\start-all.ps1
#   3) 带 -NoWait 参数：启动后不等待，立即返回，服务在后台继续运行
# 停止：在等待状态下按 Ctrl+C 或输入 q 回车（-NoWait 模式需自行在任务管理器结束）

param([switch]$NoWait)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

# ---------- 1. 定位 Python ----------
$pyExe = $null
$pyArgs = @()
foreach ($v in @("$root\venv\Scripts\python.exe",
                 "$root\.venv\Scripts\python.exe",
                 "$root\backend\.venv\Scripts\python.exe")) {
    if (Test-Path $v) { $pyExe = $v; break }
}
if (-not $pyExe) {
    $gc = Get-Command python -ErrorAction SilentlyContinue
    if ($gc) { $pyExe = $gc.Source }
}
if (-not $pyExe) {
    $gc = Get-Command py -ErrorAction SilentlyContinue
    if ($gc) { $pyExe = $gc.Source; $pyArgs = @("-3") }
}
if (-not $pyExe) {
    Write-Host "[错误] 找不到 Python。请安装 Python 3.10+ 并勾选加入 PATH。" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}
Write-Host "[Python] $pyExe $($pyArgs -join ' ')"

# ---------- 2. 缺失依赖时自动安装 ----------
& $pyExe $pyArgs -c "import fastapi,uvicorn,sqlalchemy,pulp,statsmodels" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[提示] 检测到依赖缺失，正在安装 requirements.txt ..." -ForegroundColor Yellow
    & $pyExe $pyArgs -m pip install -r "$root\requirements.txt"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 依赖安装失败，请手动执行：pip install -r requirements.txt" -ForegroundColor Red
        Read-Host "按回车退出"
        exit 1
    }
}

# ---------- 3. 数据库：不存在则初始化 ----------
if (-not (Test-Path "$root\scm.db")) {
    Write-Host "[1/3] 初始化数据库（seed）..."
    & $pyExe $pyArgs -m backend.app.seed
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 数据初始化失败" -ForegroundColor Red
        Read-Host "按回车退出"
        exit 1
    }
} else {
    Write-Host "[1/3] 已存在 scm.db，跳过 seed"
}

# ---------- 4. 启动后端 (uvicorn) ----------
$backendPort = 8000
$frontPort   = 8080
Write-Host "[2/3] 启动后端 uvicorn  :$backendPort ..."
$backend = Start-Process -FilePath $pyExe `
    -ArgumentList ($pyArgs + @("-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "$backendPort")) `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput "$root\backend.log" -RedirectStandardError "$root\backend.err.log"

# ---------- 5. 启动前端 (http.server) ----------
Write-Host "[3/3] 启动前端 http.server :$frontPort ..."
$front = Start-Process -FilePath $pyExe `
    -ArgumentList ($pyArgs + @("-m", "http.server", "$frontPort", "--bind", "127.0.0.1")) `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput "$root\frontend.log" -RedirectStandardError "$root\frontend.err.log"

# ---------- 6. 等待后端就绪 ----------
$backendUrl = "http://127.0.0.1:$backendPort"
Write-Host "等待后端就绪 ..."
$up = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri "$backendUrl/health" -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $up = $true; break }
    } catch {}
}
if (-not $up) {
    Write-Host "[错误] 后端未就绪，请查看 backend.err.log" -ForegroundColor Red
    Stop-Process -Id $backend.Id, $front.Id -Force -ErrorAction SilentlyContinue
    Read-Host "按回车退出"
    exit 1
}

# ---------- 7. 打开浏览器 ----------
$page = "http://127.0.0.1:$frontPort/frontend/index.html"
try { Start-Process $page } catch { Write-Host "[提示] 无法自动打开浏览器，请手动访问：$page" -ForegroundColor Yellow }
Write-Host "已就绪，浏览器将打开：$page" -ForegroundColor Green
Write-Host "账号：admin / admin123  （planner/plan123 · viewer/view123）"

if ($NoWait) {
    Write-Host "[-NoWait] 服务已后台运行（backend:8000 / front:8080）。日志：backend.log、frontend.log"
    exit 0
}

# ---------- 8. 前台等待，退出时清理 ----------
try {
    for (;;) {
        Write-Host "服务运行中。输入 q 回车 或 Ctrl+C 停止。"
        $k = Read-Host
        if ($k -match '^q$|^quit$|^exit$') { break }
    }
}
finally {
    Stop-Process -Id $backend.Id, $front.Id -Force -ErrorAction SilentlyContinue
    Write-Host "已停止后端与前端。"
}