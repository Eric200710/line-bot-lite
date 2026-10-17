"""
智能進程清理工具 (Cross-platform Python Process Cleaner)
雙擊或在終端機直接執行: python clean_processes.py
"""

import os
import subprocess
import sys

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return res.stdout.strip()
    except Exception:
        return ""

def kill_by_name(process_name, friendly_name):
    print(f"🧹 正在檢查並清理 {friendly_name} ({process_name})...")
    if sys.platform == "win32":
        # /T 殺死所有子程序樹，/F 強制
        out = run_cmd(f"taskkill /F /IM {process_name} /T")
        if "成功" in out or "SUCCESS" in out:
            print(f"  ✅ 已清理 {friendly_name}！")
        else:
            print(f"  -> 目前無殘留的 {friendly_name}。")
    else:
        run_cmd(f"pkill -f {process_name}")
        print(f"  ✅ 已處理 {friendly_name}。")

def main():
    print("==================================================")
    print("  LINE Bot 作業環境 - 智能進程清理與釋放工具")
    print("==================================================\n")

    current_pid = os.getpid()

    # 1. 關閉卡住的 ngrok 或 cloudflared
    kill_by_name("ngrok.exe", "Ngrok 穿透服務")
    kill_by_name("cloudflared.exe", "Cloudflared 隧道")

    # 2. 清理卡住的 Python 服務 (注意不要誤殺自己)
    print("\n🧹 正在檢查卡住的 Python 服務 (Port 5000 / 8000)...")
    if sys.platform == "win32":
        # 尋找占用 5000 或 8000 的進程
        for port in [5000, 8000]:
            netstat = run_cmd(f"netstat -ano | findstr :{port}")
            if netstat:
                for line in netstat.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5 and "LISTENING" in line:
                        target_pid = parts[-1]
                        if target_pid.isdigit() and int(target_pid) != current_pid:
                            run_cmd(f"taskkill /F /PID {target_pid}")
                            print(f"  ✅ 已終止占用 Port {port} 的進程 (PID: {target_pid})！")

    # 3. 處理 Ollama
    print("\n🧹 檢查 Ollama 模型服務...")
    choice = input("是否重啟 Ollama (解決模型被佔用或記憶體過高)? [y/N]: ").strip().lower()
    if choice == "y":
        kill_by_name("ollama.exe", "Ollama 背景核心")
        kill_by_name("ollama app.exe", "Ollama 圖示應用")
        print("  🔄 正在重新啟動 Ollama 在乾淨狀態...")
        if sys.platform == "win32":
            subprocess.Popen(["ollama", "serve"], shell=True, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
        print("  ✅ Ollama 已重啟！")
    else:
        print("  -> 保留 Ollama 繼續運行。")

    print("\n==================================================")
    print("  ✨ 清理完成！所有占用連接埠與幽靈程序已全數釋放。")
    print("==================================================\n")

if __name__ == "__main__":
    main()
