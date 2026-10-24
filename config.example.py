import os
from pathlib import Path

# ==========================================
# 1. HELYI ÉS FELHŐ ÚTVONALAK
# ==========================================
BASE_DIR = Path(r"C:\path\to\your\project")

INPUT_DIR = Path(r"C:\path\to\input")
OCR_DIR = Path(r"C:\path\to\ocr_json")
ANALYSIS_DIR = Path(r"C:\path\to\analysis")
DONE_DIR = Path(r"C:\path\to\done")

DB_PATH = BASE_DIR / "nyugta.db"

PYTHON_EXE = BASE_DIR / "glm_env" / "Scripts" / "python.exe"
CLOUDFLARED_EXE = BASE_DIR / "cloudflared.exe"
GEMMA_BAT = Path(r"C:\path\to\gemma.bat")

# ==========================================
# 2. TELEGRAM BOT BEÁLLÍTÁSOK
# ==========================================
BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
ALLOWED_CHAT_ID = 000000000

# ==========================================
# 3. E-MAIL (SMTP) BEÁLLÍTÁSOK
# ==========================================
SENDER_EMAIL = "your.email@gmail.com"
APP_PASSWORD = "your_app_password"
RECIPIENT_EMAILS = ["recipient1@gmail.com", "recipient2@gmail.com"]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ==========================================
# 4. WEB SZERVER BEÁLLÍTÁSOK
# ==========================================
SERVER_PORT = 8000

# ==========================================
# 5. AI / OCR ÉS LLM PIPELINE BEÁLLÍTÁSOK
# ==========================================
LLM_URL = "http://localhost:8080/v1/chat/completions"
LLM_MODEL = "your-model-name"
LLM_TIMEOUT = 300

OCR_MODEL = "zai-org/GLM-OCR"
OCR_MAX_SIDE = 2200
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".heic", ".HEIC"}

CATEGORIES = [
    "Étel", "Ital", "Háztartás", "Drogéria/Higiénia", "Szépségápolás",
    "Baba/Gyerek", "Ruházat", "Szórakozás", "Egészség/Gyógyszer",
    "Közlekedés/Üzemanyag", "Otthon/Szerszám", "Egyéb",
]
