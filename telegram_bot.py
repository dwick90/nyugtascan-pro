import json
import os
import re
import smtplib
import subprocess
import time
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

import config

BOT_TOKEN = config.BOT_TOKEN
ALLOWED_CHAT_ID = config.ALLOWED_CHAT_ID

SENDER_EMAIL = config.SENDER_EMAIL
APP_PASSWORD = config.APP_PASSWORD
RECIPIENT_EMAILS = config.RECIPIENT_EMAILS
SMTP_SERVER = config.SMTP_SERVER
SMTP_PORT = config.SMTP_PORT

BASE_DIR = config.BASE_DIR
PYTHON_EXE = str(config.PYTHON_EXE)
CLOUDFLARED_EXE = str(config.CLOUDFLARED_EXE)
GEMMA_BAT = str(config.GEMMA_BAT)
INPUT_DIR = config.INPUT_DIR

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def send_telegram_msg(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            pass
    except Exception as e:
        print(f"[-] Hiba a Telegram üzenet küldésekor: {e}")


def send_email(subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = ", ".join(RECIPIENT_EMAILS)
    
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())
        print(f"[+] E-mail sikeresen elküldve!")
    except Exception as e:
        print(f"[-] Hiba az e-mail küldésekor: {e}")


def flush_old_updates():
    """Törli a korábbi, felhalmozódott Telegram üzeneteket az indítás előtt."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1"
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode("utf-8"))
        results = data.get("result", [])
        if results:
            last_id = results[-1]["update_id"]
            return last_id + 1
    except Exception as e:
        print(f"[-] Régi üzenetek ürítési hibája: {e}")
    return 0


def has_pending_receipts():
    """Megvizsgálja a receipt_pipeline.py INPUT_DIR mappáját képfájlokért."""
    target_dir = INPUT_DIR if INPUT_DIR.exists() else Path(os.path.join(BASE_DIR, "input"))
    if not target_dir.exists():
        return False, 0
    
    valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"}
    found_files = [f for f in target_dir.iterdir() if f.suffix.lower() in valid_exts]
    return len(found_files) > 0, len(found_files)


def kill_gemma(gemma_proc=None):
    """Lelövi a Gemma szerver / llama-server folyamatokat a VRAM azonnali felszabadításához."""
    if gemma_proc:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(gemma_proc.pid)], capture_output=True)
        except Exception:
            pass
    try:
        subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    except Exception:
        pass


def run_pipeline_and_get_url(chat_id):
    has_receipts, count = has_pending_receipts()

    if not has_receipts:
        send_telegram_msg(
            chat_id,
            "ℹ️ Nincs új feldolgozandó nyugta a Google Drive input mappában.\n"
            "🛑 Egyik AI modell sem indul el, a VRAM szabadon marad."
        )
        ocr_status_msg = "Nincs új feldolgozandó nyugta."
    else:
        # 0. Biztonsági VRAM ürítés
        kill_gemma()

        # 1. GLM-OCR indítása KÜLÖN LÁTHATÓ CMD ABLAKBAN
        send_telegram_msg(chat_id, f"📸 {count} db új nyugta. GLM-OCR indítása (1/2 szakasz)...")
        cmd_ocr = f'start /wait "1/2 - GLM-OCR Feldolgozas" "{PYTHON_EXE}" "{os.path.join(BASE_DIR, "receipt_pipeline.py")}" ocr'
        subprocess.run(cmd_ocr, shell=True, cwd=BASE_DIR)

        # 2. Gemma LLM indítása külön ablakban
        send_telegram_msg(chat_id, "🚀 GLM-OCR kész. Gemma LLM indítása az elemzéshez (2/2 szakasz)...")
        gemma_proc = subprocess.Popen(["cmd.exe", "/c", GEMMA_BAT], creationflags=subprocess.CREATE_NEW_CONSOLE)
        time.sleep(5)  # Idő a Gemma betöltésére

        # 3. LLM Elemzés indítása KÜLÖN LÁTHATÓ CMD ABLAKBAN
        send_telegram_msg(chat_id, "🧠 Nyugta adatok strukturálása és mentése az adatbázisba...")
        cmd_analyze = f'start /wait "2/2 - Gemma LLM Elemzes" "{PYTHON_EXE}" "{os.path.join(BASE_DIR, "receipt_pipeline.py")}" analyze'
        subprocess.run(cmd_analyze, shell=True, cwd=BASE_DIR)

        # 4. Gemma leállítása és VRAM teljes felszabadítása
        kill_gemma(gemma_proc)
        send_telegram_msg(chat_id, "🧹 Feldolgozás kész! Gemma LLM leállítva, VRAM felszabadítva.")
        ocr_status_msg = f"{count} db nyugta sikeresen feldolgozva."

    # 5. Web szerver indítása (Dashboard)
    send_telegram_msg(chat_id, "🌐 Web szerver indítása...")
    subprocess.Popen([PYTHON_EXE, os.path.join(BASE_DIR, "server.py")], creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=BASE_DIR)

    # 6. Cloudflare Tunnel indítása
    send_telegram_msg(chat_id, "🔗 Cloudflare alagút nyitása...")
    cmd = [CLOUDFLARED_EXE, "tunnel", "--url", "http://localhost:8000"]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        cwd=BASE_DIR
    )

    regex = r"https://[a-zA-Z0-9-]+\.trycloudflare\.com"
    url_found = False

    for line in process.stdout:
        print(line, end="")
        if not url_found:
            match = re.search(regex, line)
            if match:
                tunnel_url = match.group(0)
                url_found = True
                
                # Telegram értesítés
                msg = f"✅ Nyugta Dashboard elindult!\n\n🔗 Elérési link:\n{tunnel_url}"
                send_telegram_msg(chat_id, msg)

                # E-mail értesítés
                email_subject = "Nyugta Dashboard - Új link és státusz"
                email_body = (
                    f"Szia!\n\n"
                    f"A Nyugta Dashboard szerver elindult.\n\n"
                    f"🔗 Elérési link:\n{tunnel_url}\n\n"
                    f"----------------------------------------\n"
                    f"📄 OCR Állapot: {ocr_status_msg}\n"
                    f"----------------------------------------\n\n"
                    f"Üdv,\nNyugta Bot"
                )
                send_email(email_subject, email_body)

def main():
    print("==================================================")
    print(f"[*] Telegram Bot elindult!")
    
    offset = flush_old_updates()
    print(f"[*] Régi függőben lévő üzenetek törölve. Készenlétben...")
    print("==================================================")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={offset}&timeout=30"
            req = urllib.request.urlopen(url)
            data = json.loads(req.read().decode("utf-8"))

            for result in data.get("result", []):
                offset = result["update_id"] + 1
                message = result.get("message", {})
                chat = message.get("chat", {})
                from_id = chat.get("id")
                text = message.get("text", "").strip()

                if from_id and int(from_id) == int(ALLOWED_CHAT_ID):
                    if text.lower().startswith(("/run", "/start", "start", "run", "inditas")):
                        send_telegram_msg(from_id, "⏳ Folyamat indítása elfogadva. Türelmet...")
                        run_pipeline_and_get_url(from_id)

        except Exception as e:
            print(f"[-] Hiba a lekérdezés során: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()