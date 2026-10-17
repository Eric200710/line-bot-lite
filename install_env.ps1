<#
.SYNOPSIS
    LINE bot 輕量版 - 一鍵全自動環境安裝與引導腳本
.DESCRIPTION
    1. 檢查並安裝 Python 3 (若尚未安裝)
    2. 下載並安裝 Ollama，暫停等待使用者手動安裝完成，並引導登入/拉取 gemma4:e2b 模型
    3. 下載並安裝 Ngrok，暫停等待配置完成，並引導使用者填入 authtoken 登入
    4. 自動加入環境變數 PATH，設定完成即可直接啟動機器人
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  LINE bot 輕量版 - 一鍵環境安裝與設定精靈 (W6 作業)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------------------
# 步驟 1：檢查 Python 3
# -----------------------------------------------------------
Write-Host "[1/4] 檢查 Python 3..." -ForegroundColor Yellow
$pythonCmd = Get-Command "python" -ErrorAction SilentlyContinue

if (-not $pythonCmd) {
    Write-Host "  -> 未檢測到 Python 3，嘗試使用 winget 自動安裝..." -ForegroundColor Magenta
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
} else {
    $pyVer = python --version 2>&1
    Write-Host "  -> Python 已安裝：$pyVer" -ForegroundColor Green
}
Write-Host ""

# -----------------------------------------------------------
# 步驟 2：下載與安裝 Ollama (含暫停等待安裝與登入)
# -----------------------------------------------------------
Write-Host "[2/4] 檢查 Ollama 狀態..." -ForegroundColor Yellow
$ollamaCmd = Get-Command "ollama" -ErrorAction SilentlyContinue
$ollamaDefaultPath = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"

if (-not $ollamaCmd -and -not (Test-Path $ollamaDefaultPath)) {
    Write-Host "  -> 尚未安裝 Ollama，開始下載官方安裝檔..." -ForegroundColor Magenta
    $ollamaInstaller = "$env:TEMP\OllamaSetup.exe"
    Invoke-WebRequest -Uri "https://ollama.com/download/OllamaSetup.exe" -OutFile $ollamaInstaller
    
    Write-Host "  -> 正在啟動 Ollama 安裝精靈視窗..." -ForegroundColor Cyan
    Start-Process -FilePath $ollamaInstaller
    
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Red
    Write-Host " [暫停等待] 請在彈出的視窗中點擊「Install」完成 Ollama 安裝！" -ForegroundColor Yellow
    Write-Host " 安裝完成後，請回到此視窗按下 [Enter] 鍵繼續..." -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Red
    Read-Host

    # 重新整理 PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
} else {
    Write-Host "  -> 檢測到 Ollama 已安裝！" -ForegroundColor Green
}

# 確保 Ollama 加入 PATH
if (Test-Path "$env:LOCALAPPDATA\Programs\Ollama") {
    $env:Path += ";$env:LOCALAPPDATA\Programs\Ollama"
}

# 啟動 Ollama 服務背景
Get-Process -Name "ollama*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 提示 Ollama 登入
Write-Host ""
Write-Host ">>> 提示：若您想使用 Ollama 官方線上服務，可執行登入：" -ForegroundColor Cyan
$doOllamaLogin = Read-Host "是否現在進行 Ollama 登入 (ollama signin)? (y/N)"
if ($doOllamaLogin -eq "y" -or $doOllamaLogin -eq "Y") {
    ollama signin
}

# 下載 gemma4:e2b 模型
Write-Host ""
Write-Host "  -> 正在檢查並拉取模型 gemma4:e2b (檔案約 3.5GB，請稍候)..." -ForegroundColor Yellow
ollama pull gemma4:e2b
if ($LASTEXITCODE -ne 0) {
    Write-Host "  -> 拉取 gemma4:e2b 遇到狀況，嘗試拉取備援模型 gemma:2b..." -ForegroundColor Magenta
    ollama pull gemma:2b
}
Write-Host "  -> Ollama 與模型準備就緒！" -ForegroundColor Green
Write-Host ""

# -----------------------------------------------------------
# 步驟 3：下載與配置 Ngrok (含暫停等待安裝與 Token 登入)
# -----------------------------------------------------------
Write-Host "[3/4] 檢查 Ngrok 工具..." -ForegroundColor Yellow
$ngrokCmd = Get-Command "ngrok" -ErrorAction SilentlyContinue
$localNgrok = Join-Path $PSScriptRoot "ngrok.exe"

if (-not $ngrokCmd -and -not (Test-Path $localNgrok)) {
    Write-Host "  -> 尚未檢測到 ngrok，正在自動下載免安裝穩定版..." -ForegroundColor Magenta
    $ngrokZip = "$env:TEMP\ngrok.zip"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip" -OutFile $ngrokZip
    Expand-Archive -Path $ngrokZip -DestinationPath $PSScriptRoot -Force
    Remove-Item $ngrokZip -Force -ErrorAction SilentlyContinue
    Write-Host "  -> ngrok.exe 已成功放置於當前目錄！" -ForegroundColor Green
} else {
    Write-Host "  -> 檢測到 ngrok 已就緒！" -ForegroundColor Green
}

$ngrokExe = if (Test-Path $localNgrok) { $localNgrok } else { "ngrok" }

# 檢查 ngrok authtoken 登入狀態，若未登入則暫停引導
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Red
Write-Host " [暫停等待] 請檢查並進行 Ngrok 登入授權：" -ForegroundColor Yellow
Write-Host " 1. 請前往 https://dashboard.ngrok.com 免費註冊/登入" -ForegroundColor White
Write-Host " 2. 在左側點選「Your Authtoken」複製您的專屬 Token" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Red
$userToken = Read-Host "請貼上您的 Ngrok Authtoken (若先前已設定過可直接按 Enter 跳過)"

if ($userToken.Trim() -ne "") {
    & $ngrokExe config add-authtoken $userToken.Trim()
    Write-Host "  -> Ngrok Authtoken 設定完成！" -ForegroundColor Green
} else {
    Write-Host "  -> 跳過 Token 設定，使用現有設定檔。" -ForegroundColor Gray
}
Write-Host ""

# -----------------------------------------------------------
# 步驟 4：安裝完成提示與啟動選單
# -----------------------------------------------------------
Write-Host "[4/4] 恭喜！所有環境已配置完成！" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 您現在可以選擇如何執行：" -ForegroundColor White
Write-Host " 1. 模擬模式 (終端機打字測試，不需接 LINE):" -ForegroundColor Cyan
Write-Host "    python line_bot_lite.py --simulate --search" -ForegroundColor Yellow
Write-Host ""
Write-Host " 2. 真的接 LINE (自動透過 ngrok 穿透上線):" -ForegroundColor Cyan
Write-Host "    python line_bot_lite.py --search" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$startNow = Read-Host "是否立即啟動模擬模式測試? (Y/n)"
if ($startNow -ne "n" -and $startNow -ne "N") {
    python line_bot_lite.py --simulate --search
}
