<#
.SYNOPSIS
    徹底關閉所有開發服務、終端機與 AI 模型，完全釋放電腦資源
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🛌 一鍵徹底關閉開發服務與終端機 (釋放 CPU / GPU / RAM)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$currentPid = $PID

# 1. 關閉穿透
Write-Host "[1/4] 關閉 ngrok 與 cloudflared 穿透..." -ForegroundColor Yellow
Stop-Process -Name "ngrok", "cloudflared" -Force -ErrorAction SilentlyContinue
Write-Host "  -> 穿透服務已全數關閉！" -ForegroundColor Green

# 2. 徹底關閉 Ollama (釋放 3.5GB 顯卡 VRAM 與記憶體)
Write-Host ""
Write-Host "[2/4] 徹底關閉 Ollama 核心與常駐應用程式..." -ForegroundColor Yellow
Stop-Process -Name "ollama*", "ollama app*" -Force -ErrorAction SilentlyContinue
Write-Host "  -> Ollama 與模型已從記憶體中完全卸載！" -ForegroundColor Green

# 3. 關閉 Python 服務
Write-Host ""
Write-Host "[3/4] 關閉所有 Python 伺服器..." -ForegroundColor Yellow
Stop-Process -Name "python*", "pythonw*" -Force -ErrorAction SilentlyContinue
Write-Host "  -> Python 伺服器已全數關閉！" -ForegroundColor Green

# 4. 關閉其他所有多餘的 cmd 與 powershell 視窗
Write-Host ""
Write-Host "[4/4] 關閉其餘背景殘留的終端機視窗..." -ForegroundColor Yellow
Get-Process -Name "cmd", "powershell" -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $currentPid } | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "  -> 其他終端機視窗已全數關閉！" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  ✨ 電腦已恢復乾淨休息狀態！" -ForegroundColor Green
Write-Host "  您可以安心休息或進行其他高負載工作。" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
Start-Sleep -Seconds 2
