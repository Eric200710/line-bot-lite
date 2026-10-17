# LINE bot 輕量版（和 AI 一起寫程式 W6 回家作業）

## 怎麼裝
- **一鍵自動安裝**：在 PowerShell 執行 `.\install_env.ps1`，會依序自動檢查/安裝 Python 3、Ollama、模型拉取與 ngrok，並在適當時機暫停引導登入。
- **手動安裝**：
  - Python 3（可由微軟市集或官網安裝）
  - Ollama（前往 [https://ollama.com](https://ollama.com) 下載安裝，裝完在終端機執行 `ollama pull gemma4:e2b`）
  - Ngrok（前往 [https://ngrok.com](https://ngrok.com) 下載免安裝檔，並執行 `ngrok config add-authtoken <你的Token>` 登入）

## 怎麼跑
- 模擬模式：`python line_bot_lite.py --simulate`
- 模擬模式（加連網搜尋）：`python line_bot_lite.py --simulate --search`
- 真的接 LINE：`python line_bot_lite.py`（支援 ngrok 與 cloudflared 穿透；只需 LINE 長效通行碼，Channel secret 設為選填）

## 我改了什麼、跑起來怎樣
- 模型：gemma4:e2b／電腦：NVIDIA GeForce RTX 5050 Laptop GPU / AMD Radeon 780M、記憶體 16GB／一題約 3～8 秒
- 改了：
  1. 連網搜尋升級：原版搜尋功能需登入 Ollama 官方授權，改寫為「多引擎即時搜尋 (DuckDuckGo HTML + Bing + 中文維基百科)」，不需註冊或付費即可即時連網並在回覆文末自動附上參考來源網址。
  2. 穿透工具擴充支援：除 cloudflared 外，自動適配本機 ngrok.exe，並能自動設定與還原 LINE Developers Webhook URL。
  3. 憑證彈性化：將 LINE Channel Secret 改為選填（留空跳過簽章比對），讓使用者只需輸入 LINE Channel Access Token 即可直接連線啟動。
  4. 實用生活指令整合：內建花蓮即時氣象、台灣最新地震報告、中油即時油價（含下週預測）、Steam 限免遊戲情報、每日運勢靈籤與 /help 指令選單。
  5. 新增一鍵全自動安裝腳本 (`install_env.ps1`)：自動檢測與下載 Python 3、Ollama (`gemma4:e2b`) 與 ngrok，並具備暫停等待安裝與登入引導流程。
- 卡在：
  1. 之前 DuckDuckGo Lite 介面防爬阻擋回傳空白，已改接 DuckDuckGo HTML 版與 Bing 備援解決。
  2. 最初 Windows PowerShell 限制腳本執行權限，改以 Python 原生直接執行解決。
