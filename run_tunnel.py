import re
import smtplib
import subprocess
from email.mime.text import MIMEText

import config

def send_email(tunnel_url):
    subject = "Nyugta Dashboard - Uj Cloudflare Tunnel Link"
    body = (
        f"Szia!\n\n"
        f"Elindult a Nyugta Dashboard szerver!\n\n"
        f"Az uj eleresi link:\n{tunnel_url}\n\n"
        f"Udv,\nNyugta Bot"
    )
    
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SENDER_EMAIL
    msg["To"] = ", ".join(config.RECIPIENT_EMAILS)
    
    try:
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SENDER_EMAIL, config.APP_PASSWORD)
            server.sendmail(config.SENDER_EMAIL, config.RECIPIENT_EMAILS, msg.as_string())
        print(f"\n[+] Email sikeresen elkuldve a megadott címzetteknek!\n")
    except Exception as e:
        print(f"\n[-] Hiba az email kuldesekor: {e}\n")

def run_tunnel():
    print("[*] Cloudflare Tunnel inditasa es link figyelese...")
    cmd = [str(config.CLOUDFLARED_EXE), "tunnel", "--url", f"http://localhost:{config.SERVER_PORT}"]
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )
    
    url_found = False
    regex = r"https://[a-zA-Z0-9-]+\.trycloudflare\.com"
    
    for line in process.stdout:
        print(line, end="")
        if not url_found:
            match = re.search(regex, line)
            if match:
                tunnel_url = match.group(0)
                print(f"\n[!] Megtalalt Cloudflare URL: {tunnel_url}")
                send_email(tunnel_url)
                url_found = True
                
    process.wait()

if __name__ == "__main__":
    run_tunnel()