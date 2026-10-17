# LINE Bot 輕量整合版：Python + Ngrok + LINE Bot + Ollama (gemma4:e2b)
#
# 特色：
# 1. 純 Python 3 內建標準庫，無需額外 pip 安裝（具備 requests/flask 容錯）
# 2. 支援 --simulate 終端機模擬模式（免開 LINE 免開通道即可測試模型）
# 3. 支援自動啟動本機 ngrok 穿透，並自動切換 LINE Developers Webhook 端點
# 4. 內建 LINE HMAC-SHA256 簽章安全驗證防偽造
# 5. 整合生活實用指令（天氣、地震、油價、Steam限免、運勢、/help）
# 6. 本地小模型預設 gemma4:e2b（可透過環境變數 MODEL 切換）

import base64
import getpass
import hashlib
import hmac
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ==========================================
# 1. 核心組態與提示詞 (Prompt Settings)
# ==========================================
MODEL = os.environ.get("MODEL", "gemma4:e2b")
FALLBACK_MODEL = "gemma:2b"
PORT = int(os.environ.get("PORT", "5000"))
OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

SEARCH = "--search" in sys.argv
SIMULATE = "--simulate" in sys.argv
_turn = threading.Lock()
_procs = []

# 回答提示詞 (對齊規格：台灣繁體中文、純文字、120字以內先講結論)
SYSTEM_PROMPT = (
    "你是 LINE 上的智慧助理，今天是 {today}。"
    "回答請一律使用台灣繁體中文、純文字格式（不要使用 Markdown 星號 ** 或井字號 #），"
    "控制在 120 字以內，開門見山先講結論。"
    + ("遇到最新時事、未確認事實時請參考檢附之網路搜尋結果回答；" if SEARCH else "不確定的事請直說不確定，切勿捏造事實。")
)

GREETING_REGEX = re.compile(r"^(hi|hello|你好|嗨|哈囉|測試|test)$", re.I)

LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "").strip()  # 選填：留空時跳過簽章驗證，如同原版 GAS


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


# ==========================================
# 2. HTTP 與外部 API 請求工具 (標準庫封裝)
# ==========================================
def http_request(method, url, body=None, headers=None, timeout=60):
    data = None
    h = headers.copy() if headers else {}
    if body is not None:
        if isinstance(body, (dict, list)):
            data = json.dumps(body).encode("utf-8")
            h["Content-Type"] = "application/json"
        elif isinstance(body, str):
            data = body.encode("utf-8")
        elif isinstance(body, bytes):
            data = body

    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", "replace")
            try:
                return resp.status, json.loads(text)
            except Exception:
                return resp.status, text
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", "replace")[:300]
        return e.code, {"error": err_body}
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}
    except Exception as e:
        return 0, {"error": str(e)}


def call_ollama(prompt, model_name=None):
    target_model = model_name or MODEL
    payload = {
        "model": target_model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 4096}
    }
    code, res = http_request("POST", f"{OLLAMA_URL}/api/generate", payload, timeout=120)
    if code == 0:
        raise RuntimeError("無法連線至本地 Ollama，請確認 Ollama 服務已在背景啟動 (http://127.0.0.1:11434)")
    if code != 200:
        # 若 gemma4:e2b 不存在，自動嘗試備援模型 gemma:2b
        if target_model != FALLBACK_MODEL:
            log(f"⚠️ 模型 {target_model} 呼叫失敗，嘗試備援模型 {FALLBACK_MODEL}...")
            return call_ollama(prompt, model_name=FALLBACK_MODEL)
        raise RuntimeError(f"Ollama 回應狀態碼 {code}: {res}")
    return res.get("response", "").strip()


def search_web_multi(query, max_results=3):
    """
    強韌多引擎聯網搜尋：
    1. 優先使用 DuckDuckGo HTML 版抓取真實即時網頁摘要
    2. 備援使用 Bing 搜尋
    3. 若遇冷門名詞自動結合中文維基百科 API
    回傳：(搜尋摘要文字, 來源網址清單)
    """
    snippets = []
    sources = []

    # 1. DuckDuckGo HTML 版
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read().decode("utf-8", "replace")
            # 擷取摘要
            raw_snippets = re.findall(r'class="result__snippet[^>]*>([\s\S]*?)</a>', html)
            # 擷取對應網址
            raw_urls = re.findall(r'class="result__url"[^>]*>([\s\S]*?)</span>', html)
            
            for i, s in enumerate(raw_snippets[:max_results]):
                clean_text = re.sub(r'<[^>]+>', '', s).strip()
                if clean_text:
                    snippets.append(f"• {clean_text}")
                    if i < len(raw_urls):
                        clean_url = "https://" + re.sub(r'<[^>]+>', '', raw_urls[i]).strip()
                        sources.append(clean_url)
    except Exception as e:
        log(f"DDG 搜尋異常: {e}")

    # 2. 備援 Bing
    if not snippets:
        try:
            bing_url = "https://www.bing.com/search?q=" + urllib.parse.quote(query)
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            req = urllib.request.Request(bing_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                html = resp.read().decode("utf-8", "replace")
                raw_snippets = re.findall(r'<p class="b_lineclamp[^>]*>([\s\S]*?)</p>', html)
                for s in raw_snippets[:max_results]:
                    clean_text = re.sub(r'<[^>]+>', '', s).replace('&nbsp;', ' ').replace('&#0183;', '·').strip()
                    if clean_text:
                        snippets.append(f"• {clean_text}")
                sources.append("https://www.bing.com")
        except Exception as e:
            log(f"Bing 搜尋異常: {e}")

    # 3. 備援中文維基百科
    if not snippets:
        try:
            wiki_url = f"https://zh.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&utf8=1"
            req = urllib.request.Request(wiki_url, headers={"User-Agent": "LINEBot-Python/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                results = data.get("query", {}).get("search", [])
                for r in results[:max_results]:
                    title = r.get("title", "")
                    clean_text = re.sub(r'<[^>]+>', '', r.get("snippet", "")).strip()
                    if clean_text:
                        snippets.append(f"• [{title}] {clean_text}")
                        sources.append(f"https://zh.wikipedia.org/wiki/{urllib.parse.quote(title)}")
        except Exception:
            pass

    return "\n".join(snippets), sources


# ==========================================
# 3. 生活實用指令庫 (天氣 / 地震 / 油價 / 遊戲 / 運勢)
# ==========================================
def handle_utility_commands(user_prompt):
    cmd = user_prompt.strip()
    lower = cmd.lower()

    if lower in ["/help", "說明", "指令", "幫助"]:
        return (
            "🤖 【實用指令小幫手】\n"
            "-------------------------\n"
            "⛅ 輸入「天氣」：查詢花蓮當地即時氣象\n"
            "🌋 輸入「地震」：查詢台灣最近一次地震報告\n"
            "⛽ 輸入「油價」：查詢今日中油牌價與下週預測\n"
            "🎮 輸入「免費遊戲」：查詢 Steam 限免好康\n"
            "🔮 輸入「運勢」：抽取今日運勢靈籤\n"
            "-------------------------\n"
            f"💬 其它任何文字皆由本地小模型 {MODEL} 為你解答！"
        )

    if cmd in ["天氣", "花蓮天氣"]:
        code, res = http_request("GET", "https://api.open-meteo.com/v1/forecast?latitude=23.987&longitude=121.601&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m&timezone=Asia%2FTaipei")
        if code == 200 and isinstance(res, dict):
            d = res.get("current", {})
            code_map = {0: "晴朗 ☀️", 1: "大致晴朗 🌤️", 2: "局部多雲 ⛅", 3: "多雲陰天 ☁️", 61: "小雨 🌧️", 63: "中雨 🌧️", 65: "大雨 ⛈️"}
            cond = code_map.get(d.get("weather_code"), "多雲 🌥️")
            return (
                "⛅ 【花蓮即時氣象資訊】\n-------------------------\n"
                f"🌡️ 即時氣溫：{d.get('temperature_2m')} °C\n"
                f"👕 體感溫度：{d.get('apparent_temperature')} °C\n"
                f"🌤️ 天氣狀況：{cond}\n"
                f"💧 相對濕度：{d.get('relative_humidity_2m')} %\n"
                f"🌧️ 目前降雨量：{d.get('precipitation')} mm"
            )

    if cmd in ["地震", "地震報告"]:
        code, res = http_request("GET", "https://exp.api.cwb.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization=rdec-key-123-45678-011121314&format=JSON")
        if code == 200 and isinstance(res, dict):
            try:
                eq = res["records"]["Earthquake"][0]
                info = eq["EarthquakeInfo"]
                return (
                    "🌋 【台灣最新地震速報】\n-------------------------\n"
                    f"📅 時間：{info['OriginTime']}\n"
                    f"📍 震央位置：{info['Epicenter']['Location']}\n"
                    f"💥 地震規模：M(L) {info['EarthquakeMagnitude']['MagnitudeValue']}\n"
                    f"📏 震源深度：{info['FocalDepth']} 公里\n"
                    f"🔗 報告網址：{eq.get('Web', '')}"
                )
            except Exception:
                pass

    if cmd in ["油價", "今日油價"]:
        code, res = http_request("GET", "https://gas.goodlife.tw/gas.json", headers={"User-Agent": "Mozilla/5.0"})
        if code == 200 and isinstance(res, dict):
            return (
                "⛽ 【中油最新即時油價】\n-------------------------\n"
                f"🚗 92 無鉛汽油：{res.get('gas_92', '--')} 元/公升\n"
                f"🚗 95 無鉛汽油：{res.get('gas_95', '--')} 元/公升\n"
                f"🚗 98 無鉛汽油：{res.get('gas_98', '--')} 元/公升\n"
                f"🚛 超級柴油：{res.get('diesel', '--')} 元/公升\n"
                "-------------------------\n"
                f"📢 公告資訊：{res.get('share_text', '預測持平')}"
            )

    if cmd in ["免費遊戲", "限免"] or lower == "free game":
        code, res = http_request("GET", "https://www.gamerpower.com/api/giveaways?platform=steam")
        if code == 200 and isinstance(res, list) and res:
            lines = ["🎮 【Steam 限免好康】", "-------------------------"]
            for g in res[:3]:
                url = g.get("open_giveaway_url") or g.get("gamerpower_url")
                lines.append(f"📌 {g.get('title')}\n🔗 領取網址：{url}\n")
            return "\n".join(lines).strip()

    if cmd in ["運勢", "今日運勢"]:
        import random
        fortunes = [
            ("大吉 🌟", "今天好運連連，不管是工作還是生活都能順風順水，出門會有小驚喜！"),
            ("中吉 ☀️", "今天充滿正面能量，適合開啟新計畫，合作順利。"),
            ("吉 😊", "平淡中自帶小確幸，適合喝杯好咖啡犒賞自己。"),
            ("小吉 🍀", "凡事循序漸進，不急躁便能穩妥達成目標。多走動、多喝水！")
        ]
        colors = ["米白色", "天藍色", "森林綠", "琥珀黃", "櫻花粉"]
        f_title, f_desc = random.choice(fortunes)
        return (
            "🔮 【今日運勢靈籤】\n-------------------------\n"
            f"✨ 運勢：{f_title}\n"
            f"💬 解曰：{f_desc}\n"
            f"🎨 幸運色：{random.choice(colors)}"
        )

    return None


# ==========================================
# 4. 訊息處理與 Ollama 回答產生
# ==========================================
def ask_ai(question):
    today = datetime.now().strftime("%Y-%m-%d (%A)")
    sys_instruction = SYSTEM_PROMPT.format(today=today)

    search_summary = ""
    sources = []
    if SEARCH:
        log(f"  🔍 正在連網搜尋關於「{question[:20]}」的即時資訊...")
        search_summary, sources = search_web_multi(question)
        if search_summary:
            log(f"  ✅ 成功取得即時網路摘要資料，注入小模型中...")
        else:
            log(f"  ⚠️ 未能取得搜尋結果，將依靠模型本身知識回答。")

    if search_summary:
        full_prompt = (
            f"{sys_instruction}\n\n"
            f"【最新網路搜尋摘要資料】\n{search_summary}\n\n"
            f"【使用者提問】\n{question}\n\n"
            f"請根據上述資料回答："
        )
    else:
        full_prompt = f"{sys_instruction}\n\n【使用者提問】\n{question}\n\n請回答："

    raw_answer = call_ollama(full_prompt)
    clean_answer = raw_answer.replace("**", "").replace("##", "").strip()
    return clean_answer, sources


def handle_event(event):
    with _turn:
        if event.get("type") != "message":
            return
        msg = event.get("message", {})
        reply_token = event.get("replyToken")
        if not reply_token or msg.get("type") != "text":
            return

        text = msg.get("text", "").strip()

        # 1. 招呼語快速回應
        if GREETING_REGEX.match(text):
            reply_line(reply_token, f"你好！我是跑在電腦上的小模型 ({MODEL}) 🤖\n有什麼我可以幫忙的嗎？輸入「/help」可查看實用生活指令！")
            return

        # 2. 實用生活指令比對
        util_res = handle_utility_commands(text)
        if util_res:
            reply_line(reply_token, util_res)
            return

        # 3. 啟動 LINE「輸入中動畫」
        user_info = event.get("source", {})
        if not SIMULATE and user_info.get("type") == "user":
            start_loading_animation(user_info.get("userId"))

        log(f"📩 收到提問:「{text[:30]}...」，交給 {MODEL}...")
        t0 = time.time()
        try:
            ans, sources = ask_ai(text)
            cost = time.time() - t0
            
            # 若有連網搜尋，附上參考來源
            tail = ""
            if sources:
                unique_src = list(dict.fromkeys(sources))[:3]
                tail = "\n\n🔗 網路參考來源：\n" + "\n".join(f"• {u}" for u in unique_src)
            elif SEARCH:
                tail = "\n\nℹ️ 本題未能檢索到外部網路來源，純憑模型記憶回答。"

            reply_line(reply_token, f"{ans}{tail}\n\n（本地模型 {MODEL}，耗時 {cost:.1f} 秒）")
            log(f"✅ 回覆成功（耗時 {cost:.1f} 秒）")
        except Exception as e:
            log(f"❌ 錯誤: {e}")
            reply_line(reply_token, f"⚠️ 抱歉，回答時發生錯誤：{str(e)[:250]}")


def start_loading_animation(user_id):
    if not LINE_TOKEN or not user_id:
        return
    url = "https://api.line.me/v2/bot/chat/loading/start"
    http_request("POST", url, {"chatId": user_id, "loadingSeconds": 60}, {"Authorization": f"Bearer {LINE_TOKEN}"})


def reply_line(reply_token, text):
    if SIMULATE:
        print(f"\n🤖 [Bot 回覆]\n{text}\n", flush=True)
        return

    url = "https://api.line.me/v2/bot/message/reply"
    payload = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text[:4900]}]
    }
    code, res = http_request("POST", url, payload, {"Authorization": f"Bearer {LINE_TOKEN}"})
    if code != 200:
        log(f"⚠️ LINE 回覆失敗 ({code}): {res}")


# ==========================================
# 5. Webhook HTTP Server
# ==========================================
class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)

        # 安全簽章比對 (若設定了 LINE_SECRET)
        if LINE_SECRET:
            sig = base64.b64encode(hmac.new(LINE_SECRET.encode("utf-8"), body, hashlib.sha256).digest()).decode("utf-8")
            if not hmac.compare_digest(sig, self.headers.get("x-line-signature", "")):
                log("⛔ 簽章不符，拒絕請求")
                self.send_response(401)
                self.end_headers()
                return

        # 立即回傳 200 避免 LINE 逾時
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

        try:
            data = json.loads(body.decode("utf-8", "replace"))
            for ev in data.get("events", []):
                threading.Thread(target=handle_event, args=(ev,), daemon=True).start()
        except Exception as e:
            log(f"解析 JSON 失敗: {e}")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"LBHKTEST1 Ollama ({MODEL}) LINE Bot 運行中".encode("utf-8"))

    def log_message(self, *args):
        pass


# ==========================================
# 6. Ngrok 自動穿透管理
# ==========================================
def find_ngrok_bin():
    # 優先找本專案目錄下的 ngrok.exe，其次尋找 PATH
    local_ngrok = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ngrok.exe")
    if os.path.exists(local_ngrok):
        return local_ngrok
    return shutil.which("ngrok")


def start_ngrok():
    ngrok_bin = find_ngrok_bin()
    if not ngrok_bin:
        log("⚠️ 找不到 ngrok.exe。請手動下載 ngrok 或放入此資料夾中。")
        return None

    # 啟動 ngrok http PORT
    p = subprocess.Popen([ngrok_bin, "http", str(PORT)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    _procs.append(p)

    # 等待 ngrok 建立通道並由 127.0.0.1:4040 取得公開網址
    log("正在連線 Ngrok 取得公開網址...")
    for _ in range(25):
        time.sleep(1)
        code, data = http_request("GET", "http://127.0.0.1:4040/api/tunnels")
        if code == 200 and isinstance(data, dict):
            tunnels = data.get("tunnels", [])
            for t in tunnels:
                if t.get("proto") == "https":
                    return t.get("public_url")
    return None


def update_line_webhook(new_url):
    if not LINE_TOKEN:
        return None
    # 讀取現有 Webhook
    code, cur = http_request("GET", "https://api.line.me/v2/bot/channel/webhook/endpoint", headers={"Authorization": f"Bearer {LINE_TOKEN}"})
    old_endpoint = cur.get("endpoint") if (code == 200 and isinstance(cur, dict)) else None

    # 更新為新端點
    webhook_url = new_url.rstrip("/") + "/webhook"
    code, res = http_request("PUT", "https://api.line.me/v2/bot/channel/webhook/endpoint", {"endpoint": webhook_url}, {"Authorization": f"Bearer {LINE_TOKEN}"})
    if code == 200:
        log(f"✅ LINE Webhook 端點已自動設定為: {webhook_url}")
    else:
        log(f"⚠️ 自動更新 Webhook 失敗 ({code})，請手動複製此網址貼至 LINE Developers:\n👉 {webhook_url}")

    return old_endpoint


def restore_line_webhook(old_url):
    if old_url and LINE_TOKEN:
        http_request("PUT", "https://api.line.me/v2/bot/channel/webhook/endpoint", {"endpoint": old_url}, {"Authorization": f"Bearer {LINE_TOKEN}"})
        log(f"↩️ LINE Webhook 已自動還原回原本設定: {old_url}")


# ==========================================
# 7. 模擬模式 (終端機快速測試)
# ==========================================
def run_simulation():
    log(f"=== 啟動模擬測試模式 (模型: {MODEL}) ===")
    log("正在測試 Ollama 預載模型...")
    t0 = time.time()
    try:
        call_ollama("測試")
        log(f"✅ 模型準備就緒 (耗時 {time.time() - t0:.1f} 秒)")
    except Exception as e:
        log(f"⚠️ {e}")

    log("可在下方直接打字測試，輸入「quit」或「exit」結束。")
    idx = 0
    while True:
        try:
            user_in = input("📱 你說: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_in:
            continue
        if user_in.lower() in ["quit", "exit", "q"]:
            break
        idx += 1
        fake_ev = {
            "type": "message",
            "replyToken": f"sim-token-{idx}",
            "source": {"type": "user", "userId": "U_SIMULATED"},
            "message": {"type": "text", "id": str(idx), "text": user_in}
        }
        handle_event(fake_ev)
    log("模擬結束。")


# ==========================================
# 8. 主程式進入點
# ==========================================
def main():
    global LINE_TOKEN, LINE_SECRET

    if SIMULATE:
        run_simulation()
        return

    # 詢問或讀取 LINE 憑證（只需 Access Token 即可運作！）
    if not LINE_TOKEN:
        LINE_TOKEN = getpass.getpass("貼上 LINE Channel Access Token (畫面不顯示，按 Enter 確認): ").strip()
    
    # Secret 設為選填：若沒填就直接跳過，維持跟 Google Apps Script 一樣的極簡設定
    if not LINE_SECRET and "LINE_CHANNEL_SECRET" in os.environ:
        LINE_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "").strip()

    # 驗證 Token
    code, info = http_request("GET", "https://api.line.me/v2/bot/info", headers={"Authorization": f"Bearer {LINE_TOKEN}"})
    if code != 200:
        sys.exit(f"❌ LINE Token 驗證失敗 ({code})，請確認 Token 是否正確。")
    log(f"✅ LINE Bot 連線成功: 【{info.get('displayName', 'LINE Bot')}】")

    # 預熱本地模型
    log(f"正在預熱本地模型 {MODEL}...")
    try:
        call_ollama("hi")
        log("✅ 模型預熱完成！")
    except Exception as e:
        log(f"⚠️ {e}")

    # 啟動本機 Webhook Server
    server = ThreadingHTTPServer(("0.0.0.0", PORT), WebhookHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    log(f"✅ 本地伺服器已在 Port {PORT} 啟動！")

    # 啟動 Ngrok 並更新 LINE Webhook
    old_webhook = None
    public_url = start_ngrok()
    if public_url:
        log(f"🌐 Ngrok 公開通道已建立: {public_url}")
        old_webhook = update_line_webhook(public_url)
    else:
        log(f"⚠️ 未能自動啟動 ngrok，若已手動開啟 ngrok，請手動將網址填至 LINE 後台。")

    print("\n----------------------------------------------------------")
    print("  🚀 機器人現已上線！請用手機 LINE 傳送訊息測試。")
    print("  隨時按下 Ctrl + C 即可關閉伺服器並自動清理通道。")
    print("----------------------------------------------------------\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("\n正在安全關閉伺服器...")
    finally:
        if old_webhook:
            restore_line_webhook(old_webhook)
        for proc in _procs:
            proc.terminate()
        server.shutdown()
        log("服務已安全結束。")


if __name__ == "__main__":
    main()
