import http.server
import json
import os
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse

import config

DB_PATH = str(config.DB_PATH)
OCR_DIR = config.OCR_DIR
ANALYSIS_DIR = config.ANALYSIS_DIR


class ReceiptRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/data":
            self.handle_api_data()
        else:
            super().do_GET()

    def do_POST(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == "/api/shutdown":
            self.handle_shutdown()
        elif parsed_path.path == "/api/delete_receipt":
            self.handle_delete_receipt()
        elif parsed_path.path == "/api/update_receipt":
            self.handle_update_receipt()
        else:
            self.send_error(404, "Végpont nem található")

    def handle_api_data(self):
        if not os.path.exists(DB_PATH):
            self.send_response(404)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            error_msg = json.dumps({"error": f"Adatbázis nem található: {DB_PATH}"}, ensure_ascii=False)
            self.wfile.write(error_msg.encode("utf-8"))
            return

        try:
            conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM receipts ORDER BY receipt_date DESC")
            receipts = [dict(row) for row in cursor.fetchall()]

            cursor.execute("SELECT * FROM items")
            items = [dict(row) for row in cursor.fetchall()]

            conn.close()

            payload = {"receipts": receipts, "items": items}
            data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Content-Length", str(len(data_bytes)))
            self.end_headers()
            self.wfile.write(data_bytes)

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.wfile.write(err.encode("utf-8"))

    def handle_delete_receipt(self):
        """Nyugta, a hozzá tartozó tételek ÉS a Drive JSON fájlok törlése"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            receipt_id = data.get("id")

            if not receipt_id:
                self.send_response(400)
                self.end_headers()
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # 1. Lekérjük a sha256 hash-t a JSON fájlok beazonosításához
            cursor.execute("SELECT sha256 FROM receipts WHERE id = ?", (receipt_id,))
            row = cursor.fetchone()

            if row and row[0]:
                sha256_hash = row[0]
                hash_prefix = sha256_hash[:12]

                # 2. Törlés az OCR JSON mappából (ocr_json)
                for f in OCR_DIR.glob(f"*_{hash_prefix}.json"):
                    try:
                        f.unlink()
                        print(f"[+] OCR JSON törölve: {f.name}")
                    except Exception as e:
                        print(f"[-] Hiba az OCR JSON törlésekor: {e}")

                # 3. Törlés az Analysis JSON mappából (analysis)
                for f in ANALYSIS_DIR.glob(f"*_{hash_prefix}.json"):
                    try:
                        f.unlink()
                        print(f"[+] Analysis JSON törölve: {f.name}")
                    except Exception as e:
                        print(f"[-] Hiba az Analysis JSON törlésekor: {e}")

            # 4. Rekordok törlése az adatbázisból
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("DELETE FROM items WHERE receipt_id = ?", (receipt_id,))
            cursor.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
            conn.commit()
            conn.close()

            print(f"[+] Nyugta (ID: {receipt_id}) és a kapcsolódó fájlok sikeresen törölve.")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            res = json.dumps({"success": True, "message": "Nyugta és fájljai törölve"}, ensure_ascii=False)
            self.wfile.write(res.encode("utf-8"))

        except Exception as e:
            print(f"[-] Hiba a törlésnél: {e}")
            self.send_response(500)
            self.end_headers()

    def handle_update_receipt(self):
        """Nyugta tételeinek frissítése és ellenőrzötté állítása (needs_review = 0)"""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))

            receipt_id = data.get("id")
            items = data.get("items", [])

            if not receipt_id:
                self.send_response(400)
                self.end_headers()
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")

            # 1. Tételek kategóriáinak és adatainak frissítése
            for item in items:
                item_id = item.get("id")
                category = item.get("category")
                subcategory = item.get("subcategory")
                name_clean = item.get("name_clean")
                line_total = item.get("line_total")

                if item_id:
                    cursor.execute(
                        """UPDATE items 
                           SET category = ?, subcategory = ?, name_clean = ?, line_total = ?
                           WHERE id = ? AND receipt_id = ?""",
                        (category, subcategory, name_clean, line_total, item_id, receipt_id)
                    )

            # 2. Új tételek összegének kiszámítása és frissítése
            cursor.execute("SELECT SUM(line_total) FROM items WHERE receipt_id = ?", (receipt_id,))
            new_items_sum = cursor.fetchone()[0] or 0

            # 3. Nyugta átállítása ellenőrzöttre (needs_review = 0)
            cursor.execute(
                "UPDATE receipts SET items_sum = ?, needs_review = 0 WHERE id = ?",
                (new_items_sum, receipt_id)
            )

            conn.commit()
            conn.close()

            print(f"[+] Nyugta (ID: {receipt_id}) sikeresen frissítve és ellenőrizve.")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            res = json.dumps({"success": True, "message": "Nyugta sikeresen ellenőrizve"}, ensure_ascii=False)
            self.wfile.write(res.encode("utf-8"))

        except Exception as e:
            print(f"[-] Hiba a frissítésnél: {e}")
            self.send_response(500)
            self.end_headers()

    def handle_shutdown(self):
        """Webszerver és Cloudflare alagút teljes leállítása"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        res = json.dumps({"message": "Szerver és Cloudflare leállítása..."}, ensure_ascii=False)
        self.wfile.write(res.encode("utf-8"))

        def delayed_shutdown():
            time.sleep(1)
            print("\n[!] Leállítási parancs érkezett a weblapról...")
            try:
                subprocess.run(["taskkill", "/F", "/IM", "cloudflared.exe"], capture_output=True)
                print("[+] Cloudflare Tunnel sikeresen leállítva.")
            except Exception as e:
                print(f"[-] Cloudflare leállítási hiba: {e}")

            print("[+] Python webszerver leáll.")
            os._exit(0)

        threading.Thread(target=delayed_shutdown).start()

    def log_message(self, format, *args):
        sys.stdout.write(f"[{self.log_date_time_string()}] {args[0]}\n")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    PORT = config.SERVER_PORT
    local_ip = get_local_ip()

    print("=" * 65)
    print("      NYUGTA & KÖLTÉSEK DASHBOARD SZERVER ELINDULT")
    print("=" * 65)
    print(f" Adatbázis fájl: {DB_PATH}")
    print(f" Helyi elérés: http://localhost:{PORT}")
    print(f" Mobil elérés: http://{local_ip}:{PORT}")
    print("=" * 65)

    server_address = ("", PORT)
    httpd = http.server.HTTPServer(server_address, ReceiptRequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nA szerver leállt.")
        sys.exit(0)
