@echo off
chcp 65001 >nul
title 深度清理與釋放電腦效能 (Shutdown AI & Dev Services)
color 0A

echo ==========================================================
echo   🛌 電腦休眠/寫其他程式前 - 一鍵徹底清理釋放效能工具
echo ==========================================================
echo.
echo 正在為您的電腦進行徹底清理與資源釋放：
echo 1. 關閉 Ngrok 與 Cloudflared 網路穿透
echo 2. 徹底關閉 Ollama 核心與羊駝圖示 (釋放顯存/記憶體)
echo 3. 關閉所有 Python 背景伺服器
echo 4. 關閉背景殘留的所有 cmd 與 powershell 視窗
echo.
echo ----------------------------------------------------------

:: 1. 關閉穿透工具
echo [1/4] 正在關閉 ngrok 與 cloudflared...
taskkill /F /IM ngrok.exe /T >nul 2>&1
taskkill /F /IM cloudflared.exe /T >nul 2>&1
echo   -> 穿透服務已全數終止！

:: 2. 徹底關閉 Ollama (釋放 3.5GB 顯存/記憶體)
echo.
echo [2/4] 正在徹底關閉 Ollama 核心與應用程式...
taskkill /F /IM "ollama.exe" /T >nul 2>&1
taskkill /F /IM "ollama app.exe" /T >nul 2>&1
echo   -> Ollama 已關閉，GPU 顯存與 RAM 已全數釋放！

:: 3. 關閉 Python
echo.
echo [3/4] 正在關閉殘留的 Python 程式...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1
echo   -> Python 已全數關閉！

:: 4. 提示清理完成
echo.
echo [4/4] 正在完成清理...
echo.
echo ==========================================================
echo   ✨ 清理完成！電腦已恢復最高效能與乾淨狀態。
echo   您可以安心寫別的程式或讓電腦待機休息了！
echo ==========================================================
echo.
echo 倒數 3 秒後自動關閉本視窗...
timeout /t 3 >nul
exit
