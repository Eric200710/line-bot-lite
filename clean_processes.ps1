<#
.SYNOPSIS
    智能進程清理工具 (Clean Environment Tools)
.DESCRIPTION
    清理作業中殘留的 ngrok, python (LINE bot), ollama (可重啟), 多餘的 cmd/powershell 背景視窗
#>

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  🧹 LINE Bot 作業環境 - 智能進程清理與釋放工具" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$currentPid = $PID

# 1. 關閉殘留的 Ngrok 與 Cloudflared 穿透服務
Write-Host "[1/4] 清理殘留的網路穿透服務 (ngrok / cloudflared)..." -ForegroundColor Yellow
$tunnels = Get-Process -Name "ngrok", "cloudflared" -ErrorAction SilentlyContinue
if ($tunnels) {
    $tunnels | ForEach-Object {
        Write-Host "  -> 關閉 $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✅ 網路穿透程序已全數關閉，釋放 Port 4040 與 5000！" -ForegroundColor Green
} else {
    Write-Host "  -> 無殘留的穿透服務。" -ForegroundColor Gray
}

# 2. 清理背景卡住的 Python 服務 (例如卡住的 line_bot_lite / app_ollama)
Write-Host ""
Write-Host "[2/4] 清理背景卡住的 Python 伺服器..." -ForegroundColor Yellow
$pythons = Get-Process -Name "python" -ErrorAction SilentlyContinue
if ($pythons) {
    $pythons | ForEach-Object {
        Write-Host "  -> 關閉 Python (PID: $($_.Id))" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✅ 殘留的 Python 伺服器已清理完畢，Port 5000/8000 已釋放！" -ForegroundColor Green
} else {
    Write-Host "  -> 無殘留的 Python 服務。" -ForegroundColor Gray
}

# 3. 處理 Ollama 背景程序 (解決模型卡住或被佔用問題)
Write-Host ""
Write-Host "[3/4] 檢查 Ollama 模型伺服器..." -ForegroundColor Yellow
$ollamaProcs = Get-Process -Name "ollama*" -ErrorAction SilentlyContinue
if ($ollamaProcs) {
    Write-Host "  檢測到 $($ollamaProcs.Count) 個 Ollama 程序運行中。" -ForegroundColor Cyan
    $restartOllama = Read-Host "  是否重啟 Ollama (解決模型卡住/記憶體佔用)? (y/N)"
    if ($restartOllama -eq "y" -or $restartOllama -eq "Y") {
        $ollamaProcs | Stop-Process -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
        Write-Host "  ✅ Ollama 已重新啟動在乾淨狀態！" -ForegroundColor Green
    } else {
        Write-Host "  -> 保留 Ollama 背景服務繼續運作。" -ForegroundColor Gray
    }
} else {
    Write-Host "  -> Ollama 目前未運行。" -ForegroundColor Gray
}

# 4. 清理無標題/殘留的背景 cmd 與 powershell 視窗
Write-Host ""
Write-Host "[4/4] 掃描多餘的背景終端機 (cmd / powershell)..." -ForegroundColor Yellow
$terminals = Get-Process -Name "cmd", "powershell" -ErrorAction SilentlyContinue | Where-Object { 
    $_.Id -ne $currentPid -and [string]::IsNullOrWhiteSpace($_.MainWindowTitle)
}

if ($terminals) {
    Write-Host "  發現 $($terminals.Count) 個無標題/背景幽靈終端機。" -ForegroundColor Magenta
    $terminals | ForEach-Object {
        Write-Host "  -> 關閉 $($_.ProcessName) (PID: $($_.Id))" -ForegroundColor Gray
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✅ 多餘背景終端機已清理！" -ForegroundColor Green
} else {
    Write-Host "  -> 無殘留的無標題終端機。" -ForegroundColor Gray
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  ✨ 系統環境清理完成！記憶體與連接埠已全數釋放。" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
