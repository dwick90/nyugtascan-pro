# 🧾 NyugtaScan Pro — Automatisztált Helyi Nyugta- és Költéskezelő

A **NyugtaScan Pro** egy teljesen ön-hosztolt, adatvédelmi szempontból zárt és VRAM-hatékony rendszer, amely papíralapú és digitális nyugtákból automatikusan kinyeri a vásárlási adatokat (üzlet, dátum, tételek, egységárak, kategóriák, végösszeg), majd egy mobilbarát webes dashboardon jeleníti meg azokat.

A rendszer Telegram bot segítségével távolról vezérelhető, Cloudflare Tunnelen keresztül biztonságos HTTPS hozzáférést biztosít, és a GPU-memória (VRAM) maximális kímélése érdekében sorosított AI pipeline-t használ.

---

## 🌟 Főbb Jellemzők

* **Zárt, Helyi AI Pipeline**:
  * **GLM-OCR**: Nagy pontosságú, helyi Vision-LLM modell a nyugtákon lévő nyers szöveg felismerésére.
  * **Gemma LLM**: Helyi LLM (llama-server / OpenAI-kompatibilis API) a nyers OCR szöveg strukturálására és kategóriákba sorolására.

* **VRAM-Tudatos Életciklus-Kezelés**:
  * Készenléti állapotban kizárólag a Telegram bot fut (0 MB VRAM / minimális RAM).
  * Ha nincs új kép a bemeneti mappában, az AI modellek el sem indulnak.
  * A modellek egymás után lefutva azonnal törlődnek a GPU memóriájából (`taskkill` / PyTorch CUDA cache ürítés).

* **Távoli Vezérlés & Értesítések**:
  * **Telegram Bot**: Egyetlen `/run` parancsra elindítja a teljes feldolgozást és elküldi a kattintható weboldal linkjét.
  * **E-mail Jelentés**: SMTP-n keresztül elküldi a generált alagút linket és az OCR feldolgozási naplót a megadott e-mail címekre.
  * **Cloudflare Tunnel**: Nyilvános portnyitás nélkül biztosít ideiglenes, titkosított HTTPS elérést.

* **Mobilbarát Web Dashboard**:
  * **Élő Kimutatások**: Chart.js alapú kategória- és idősoros költségarchitektúra.
  * **Termál Nyugta Nézet**: Digitalizált, nyomtatható és kereshető nyugtamásolatok SHA256 ellenőrzőösszeggel.
  * **Egy-Kattintásos Távoli Leállítás**: A webszerverről közvetlenül leállítható a Python szerver és a Cloudflare alagút (`/api/shutdown`), visszaállítva a rendszert alacsony fogyasztású készenlétbe.

---

## 📁 Projekt Mappaszerkezet

```text
D:\OCR\
├── config.py             # Gitignored - Érzékeny adatok, tokenek, helyi útvonalak
├── config.example.py     # Mintafájl a GitHub repóhoz
├── .gitignore            # Git által figyelmen kívül hagyott fájlok
├── receipt_pipeline.py   # GLM-OCR és LLM feldolgozó motor + SQLite adatbázis kezelő
├── telegram_bot.py       # A háttérben futó vezérlő bot és munkafolyamat-menedzser
├── server.py             # Python HTTP webszerver REST API végpontokkal (/api/data, /api/shutdown)
├── run_tunnel.py         # Standalone Cloudflare alagút indító és e-mail küldő
├── index.html            # Tailwind CSS + Chart.js alapú mobilbarát Web Dashboard
├── requirements.txt      # Python csomagfüggőségek listája
├── start_bot.bat         # Windows indítószkript (Auto-start)
├── start_llama.bat       # Llama server indító és auto-installer szkript
├── cloudflared.exe       # Cloudflare alagút futtatható állomány
└── nyugta.db             # Helyi SQLite adatbázis (automatikusan jön létre)
```

---

## 💻 Hardverigény

A helyi nyelvi modell (LLM) és az OCR feldolgozás futtatásához az alábbi minimális ajánlott hardver szükséges:

* **GPU:** **12 GB VRAM**-mal rendelkező videókártya (pl. NVIDIA GeForce RTX 3060 12GB / RTX 4070 12GB vagy erősebb)
* **RAM:** 16 GB (ajánlott: 32 GB)
* **Tárhely:** ~10 GB szabad hely a modellnek és a binárisoknak (NVMe SSD ajánlott)

---

## 🛠️ Telepítés és Beállítás

### 1. Előfeltételek

* **Operációs rendszer**: Windows 10 / 11 (64-bit)
* **Python**: Python 3.10+ telepítve
* **NVIDIA GPU**: CUDA támogatással (a GLM-OCR és a helyi LLM futtatásához)
* **Google Drive for Desktop** (vagy tetszőleges helyi/felhős bemeneti mappa)

---

### 2. Telegram Fiók, Bot és Chat ID Létrehozása

A rendszer biztonságos távoli vezérléséhez egy Telegram botra és a saját felhasználói azonosítódra (Chat ID) lesz szükség.

#### A. Telegram Fiók Létrehozása
1. Töltsd le a Telegram alkalmazást okostelefonodra (App Store / Google Play) vagy számítógépedre (Telegram Desktop).
2. Hozz létre egy fiókot a telefonszámod megadásával.

#### B. Telegram Bot Létrehozása (Bot Token megszerzése)
1. Nyisd meg a Telegramot, és a keresőmezőbe írd be: **`@BotFather`** (kék pipás, hivatalos Telegram bot).
2. Indítsd el a beszélgetést a **`Start`** gombbal vagy küldd el a `/start` parancsot.
3. Küldd el a **`/newbot`** parancsot.
4. A BotFather megkérdezi a bot nevét — adj meg egy tetszőleges nevet (pl. `NyugtaScan Bot`).
5. Ezután adj meg egy egyedi felhasználónevet (username), aminek **`bot`**-ra vagy **`_bot`**-ra kell végződnie (pl. `my_nyugtascan_bot`).
6. A BotFather elküldi a **HTTP API Token**-t (egy hosszabb karakterlánc, pl. `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`). **Ezt mentsd el**, mert ez lesz a `config.py` fájlban a `BOT_TOKEN`.

#### C. Saját Telegram Chat ID Lekérése
A rendszer kizárólag a te fiókodtól fogad el parancsokat, ehhez meg kell adnod a saját számszerű azonosítódat:
1. A Telegram keresőjébe írd be: **`@userinfobot`** vagy **`@raw_data_bot`**.
2. Indítsd el a botot a **`Start`** gombbal.
3. A bot azonnal válaszol a profiladataiddal, ahol megtalálod az **`Id`** mezőt (egy számsor, pl. `123456789`). **Ezt mentsd el**, ez lesz a `config.py`-ban az `ALLOWED_CHAT_ID`.
4. Keress rá a saját újonnan létrehozott botodra is a Telegramban, és kattints a **`Start`** gombra, hogy a bot tudjon neked üzenetet küldeni!

---

### 3. Projekt Klónozása és Virtuális Környezet

```bash
git clone https://github.com/dwick90/nyugtascan-pro.git
cd D:\OCR

:: Virtuális környezet létrehozása
python -m venv glm_env

:: Függőségek telepítése
glm_env\Scripts\python.exe -m pip install -r requirements.txt
```

*Megjegyzés: CUDA-kompatibilis PyTorch telepítéséhez használd az alábbi parancsot:*

```bash
glm_env\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu121
```

---

## ⚙️ Konfiguráció (`config.py`)

A biztonság érdekében a projekt a beállításokat külön `config.py` fájlban tárolja, amit a `.gitignore` nem enged feltölteni a verziókövetőbe.

1. Másold le a `config.example.py` fájlt `config.py` néven:
   ```bash
   copy config.example.py config.py
   ```

2. Nyisd meg a `config.py` fájlt és add meg a saját adataidat (beillesztve a fent megszerzett Telegram Bot Tokent és Chat ID-t):

```python
import os
from pathlib import Path

# ==========================================
# 1. HELYI ÉS FELHŐ ÚTVONALAK
# ==========================================
BASE_DIR = Path(r"D:\OCR")

INPUT_DIR = Path(r"G:\Saját meghajtó\nyugta\input")
OCR_DIR = Path(r"G:\Saját meghajtó\nyugta\ocr_json")
ANALYSIS_DIR = Path(r"G:\Saját meghajtó\nyugta\analysis")
DONE_DIR = Path(r"G:\Saját meghajtó\nyugta\feldolgozva")

DB_PATH = BASE_DIR / "nyugta.db"

PYTHON_EXE = BASE_DIR / "glm_env" / "Scripts" / "python.exe"
CLOUDFLARED_EXE = BASE_DIR / "cloudflared.exe"

# ==========================================
# 2. TELEGRAM BOT BEÁLLÍTÁSOK
# ==========================================
BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"  # A BotFather-től kapott HTTP API Token
ALLOWED_CHAT_ID = 123456789                         # A @userinfobot-tól kapott számszerű ID

# ==========================================
# 3. E-MAIL (SMTP) BEÁLLÍTÁSOK
# ==========================================
SENDER_EMAIL = "sajat.email@gmail.com"
APP_PASSWORD = "abcd efgh ijkl mnop"  # 16 karakteres Gmail alkalmazásjelszó
RECIPIENT_EMAILS = [
    "sajat.email@gmail.com",
    "masik.címzett@gmail.com"
]

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
LLM_MODEL = "gemma-4-12b-it-Q4_K_M.gguf"
LLM_TIMEOUT = 300

OCR_MODEL = "zai-org/GLM-OCR"
OCR_MAX_SIDE = 2200
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"}

CATEGORIES = [
    "Étel", "Ital", "Háztartás", "Drogéria/Higiénia", "Szépségápolás",
    "Baba/Gyerek", "Ruházat", "Szórakozás", "Egészség/Gyógyszer",
    "Közlekedés/Üzemanyag", "Otthon/Szerszám", "Egyéb",
]
```

---

## 🚀 Használati Útmutató

### A. Automatikus Indítás Beállítása (Windows Startup)

Ahhoz, hogy a Telegram bot a számítógép bekapcsolásakor automatikusan elinduljon a háttérben:

1. Nyomd meg a `Win + R` billentyűkombinációt, írd be: `shell:startup`, majd nyomj Entert.
2. Hozz létre ebben a mappában egy `start_bot.bat` fájlt az alábbi tartalommal:

```bat
@echo off
cd /d D:\OCR
D:\OCR\glm_env\Scripts\python.exe telegram_bot.py
```

### B. Működés a Gyakorlatban (Telegram Távvezérlés)

1. **Fotózz le egy nyugtát** a telefonoddal, és töltsd fel a szinkronizált Google Drive `input` mappába!
2. Nyisd meg a Telegramot, és küldd el a botodnak a **/run** parancsot!
3. **A folyamat automata lépései**:
   * A bot törli a várakozási sorban lévő régi üzeneteket.
   * Ellenőrzi az `input` mappát. Ha nincs kép, nem indít VRAM-igényes AI-t.
   * Ha van új kép, megnyit egy látható CMD ablakot és lefuttatja a **GLM-OCR** modellt.
   * Elindítja a **nyelvi LLM** modellt, elvégzi az adatok strukturálását az SQLite adatbázisba, majd **azonnal lelövi az LLM-et**, 0 MB-ra ürítve a GPU VRAM-ot.
   * Elindítja a `server.py` webszervert és a `cloudflared.exe` alagutat.
   * Visszaküldi az egyedi, kattintható **HTTPS alagút linket** Telegramon és E-mailben.

---

## 🖥️ Web Dashboard és Távoli Leállítás

A megnyitott HTTPS linken elérhető a **NyugtaScan Pro Dashboard**:

* **Összesített Analytics**: Dátum, üzlet és kategória szűrők, interaktív kör- és oszlopdiagramok (Chart.js).
* **Nyugta Kereső**: Keresés szavakra, tételekre, dátumra vagy fizetési módra.
* **Termál Paper Nézet**: Kattintásra felugró digitális blokk nyomtatási opcióval.
* **🔴 Szerver Leállítása Gomb**:
  * A fejlécben található piros **Leállítás** gombra kattintva a weboldal egy `POST /api/shutdown` kérést küld.
  * A webszerver automatikusan leállítja a `cloudflared.exe` alagutat és lezárja a saját folyamatát.
  * A rendszer visszatér a minimális fogyasztású készenléti állapotba (ahol újra csak a Telegram bot várja a következő `/run` parancsot).

---

## 🛡️ Biztonság és Adatvédelem

* **Zárt Adatkezelés**: A nyugták képei, a kinyert OCR szövegek és az SQLite adatbázis kizárólag a helyi gépeden maradnak. A Telegram és Cloudflare hálózatán csak a vezérlő parancs és a Dashboard ideiglenes webcíme halad át.
* **Hozzáférés-korlátozás**: A `telegram_bot.py` szigorúan ellenőrzi az `ALLOWED_CHAT_ID` értéket. Idegen Telegram fiókok nem tudnak parancsot végrehajtani a gépeden.

