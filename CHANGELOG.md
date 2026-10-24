# Changelog / Javítások és Frissítések

A projektben történt fontosabb módosítások, hibajavítások és új funkciók időrendi története.
## [1.2.0] - 2026-10-24

### ✨ Új Funkciók (Added)
- **Interaktív Kategória- & Tételszerkesztő**: A felugró blokk (modal) felületén a tételek nevéhez, árához és kategóriájához szerkeszthető mezők és lenyíló listák kerültek.
- **Manuális Ellenőrzés Mentés Gomb**: Új `✅ Ellenőrizve (Mentés)` gomb, ami átállítja a nyugta státuszát `needs_review = 0`-ra.
- **Új Backend Végpont (`/api/update_receipt`)**: Frissíti az `items` táblában a tételeket, újraszámolja a `items_sum` összeget, és elmenti az ellenőrzött státuszt.
- **Dinamikus Státuszjelvények**: Sárga `⚠️ Ellenőrizendő` státusz automatikus átváltása halványzöld `✅ Ellenőrizve` kijelzésre a mentés után.
  
## [1.1.0] - 2026-10-24

### 🐛 Hibajavítások (Bug Fixes)
- **iPhone HEIC Képkezelés**: Integrálva a `pillow-heif` könyvtár és a `register_heif_opener()`, így a rendszer a `.heic` / `.HEIC` fotókat is hiba nélkül feldolgozza.
- **Telegram Bot Mappa-szűrés**: A `has_pending_receipts()` függvény átállítva a `config.IMAGE_EXTS` dinamikus beolvasására, így a bot felismeri a HEIC fájlokat is.
- **LLM Szerver Indítási Várakozás**: A fix 5 másodperces várakozás lecserélve aktív port-ellenőrző ciklusra (max 60 mp), megelőzve a nagyobb (pl. 20B-s) modellek betöltési timeout hibáját.
- **Törölt Nyugták Újraforgatásának Megszüntetése**: A `server.py` törlés funkciója mostantól az SQLite rekord elengedése mellett a Google Drive-on található `ocr_json` és `analysis` `.json` fájlokat is eltávolítja.


---

## [1.0.0] - 2026-10-23
- Első éles kiadás (NyugtaScan Pro v1.0).
- Local GLM-OCR + Gemma LLM pipeline.
- Telegram Bot távvezérlés, Cloudflare Tunnel és mobilbarát Web Dashboard.
