"""
Nyugta pipeline
  1) input mappa képei -> GLM-OCR -> nyers szöveg JSON (ocr_json mappa)
  2) OCR JSON -> LLM (helyi, OpenAI-kompatibilis végpont) -> strukturált tételek + kategóriák
  3) minden SQLite adatbázisba kerül -> riportok

Használat:
    python receipt_pipeline.py            # = all (OCR + elemzés)
    python receipt_pipeline.py ocr        # csak OCR
    python receipt_pipeline.py analyze    # csak LLM elemzés + adatbázis
    python receipt_pipeline.py redo       # needs_review=1 nyugták törlése + újraelemzés
    python receipt_pipeline.py report     # havi kimutatás kategóriánként
"""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import requests

import config

INPUT_DIR = config.INPUT_DIR
OCR_DIR = config.OCR_DIR
ANALYSIS_DIR = config.ANALYSIS_DIR
DONE_DIR = config.DONE_DIR
DB_PATH = config.DB_PATH

LLM_URL = config.LLM_URL
LLM_MODEL = config.LLM_MODEL
LLM_TIMEOUT = config.LLM_TIMEOUT

OCR_MODEL = config.OCR_MODEL
OCR_MAX_SIDE = config.OCR_MAX_SIDE
IMAGE_EXTS = config.IMAGE_EXTS
CATEGORIES = config.CATEGORIES
# ===========================================================


# ---------------------- segédfüggvények ----------------------
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def to_int(value):
    """'4 199', '4199 Ft', 4199.0 -> 4199; hibánál None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(round(value))
    s = re.sub(r"[^\d\-]", "", str(value))
    return int(s) if s not in ("", "-") else None


def to_float(value, default=1.0):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return default


def photo_date(image, path: Path) -> str:
    """EXIF készítési dátum, ennek hiányában a fájl módosítási ideje."""
    try:
        exif = image.getexif()
        raw = exif.get_ifd(0x8769).get(36867) or exif.get(306)
        if raw:
            return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S").strftime("%Y-%m-%d")
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")


def unique_target(folder: Path, name: str) -> Path:
    target = folder / name
    i = 1
    while target.exists():
        target = folder / f"{Path(name).stem}_{i}{Path(name).suffix}"
        i += 1
    return target


# ---------------------- 1. lépés: OCR ----------------------
def stage_ocr():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OCR_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)

    images = sorted(p for p in INPUT_DIR.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        print("[OCR] Nincs új kép az input mappában.")
        return

    # Modell csak akkor töltődik be, ha van mit feldolgozni
    import torch
    from PIL import Image, ImageOps
    from transformers import AutoProcessor, AutoModelForImageTextToText

    print(f"[OCR] {len(images)} kép feldolgozása, modell betöltése...")
    processor = AutoProcessor.from_pretrained(OCR_MODEL)
    model = AutoModelForImageTextToText.from_pretrained(
        OCR_MODEL, dtype=torch.bfloat16, device_map="cuda"
    )

    for img_path in images:
        digest = sha256_of(img_path)
        if list(OCR_DIR.glob(f"*_{digest[:12]}.json")):
            print(f"[OCR] Már feldolgozva, kihagyom: {img_path.name}")
            shutil.move(str(img_path), str(unique_target(DONE_DIR, img_path.name)))
            continue

        print(f"[OCR] {img_path.name}")
        image = Image.open(img_path)
        shot_date = photo_date(image, img_path)
        image = ImageOps.exif_transpose(image).convert("RGB")  # telefonos fotók forgatása
        if OCR_MAX_SIDE:
            image.thumbnail((OCR_MAX_SIDE, OCR_MAX_SIDE))

        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": "Text Recognition:"},
            ],
        }]
        inputs = processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt",
        ).to(model.device)

        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=2048)
        text = processor.decode(
            out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True
        ).strip()

        record = {
            "source_file": img_path.name,
            "sha256": digest,
            "photo_date": shot_date,
            "ocr_at": datetime.now().isoformat(timespec="seconds"),
            "ocr_text": text,
        }
        out_path = OCR_DIR / f"{img_path.stem}_{digest[:12]}.json"
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.move(str(img_path), str(unique_target(DONE_DIR, img_path.name)))

    # GPU memória felszabadítása, ha az LLM ugyanazon a kártyán fut
    del model, processor
    torch.cuda.empty_cache()
    print("[OCR] Kész.")


# ---------------------- 2. lépés: LLM elemzés ----------------------
SYSTEM_PROMPT = f"""Magyar bolti nyugták OCR szövegét kapod. Elemezd, és CSAK egy érvényes JSON objektumot adj vissza, magyarázat és markdown nélkül.

Séma:
{{
  "store": "üzlet neve",
  "store_address": "az üzlet címe vagy null",
  "date": "YYYY-MM-DD vagy null, ha nem olvasható a szövegből",
  "total": egész szám forintban,
  "payment_method": "bankkártya | készpénz | egyéb | null",
  "items": [
    {{"name_raw": "a sor eredeti neve", "name_clean": "olvasható magyar terméknév",
      "quantity": szám, "unit_price": egész, "line_total": egész,
      "category": "az alábbi listából", "subcategory": "rövid, szabad szöveg"}}
  ]
}}

Kategóriák (pontosan ezek egyike): {", ".join(CATEGORIES)}

Szabályok:
- Az összegek forintban, egész számként értendők, a "4 199" jelentése 4199.
- A JSON számaiban SOHA ne legyen szóköz: 1199, nem 1 199.
- A nyugtán az ezres tagolás szóközzel történik: az "1 299" egyetlen ár (1299 Ft), nem 1 db × 299 Ft. Mennyiség csak akkor van, ha "db" vagy "KG *" jelölés mutatja.
- Mérlegelt tételnél az "x,xx KG * y Ft/KG z" sor a közvetlenül előtte lévő terméksorhoz tartozik, ne legyen külön tétel. A termék ára az a szám, ami a súly × egységár szorzatához közel áll.
- A tételek line_total értékeinek összege egyezzen a total-lal. Ha egy szám a terméknév és az ár között nem illik a képbe, az valószínűleg OCR-zaj, ne tekintsd mennyiségnek.
- Kupon/kedvezmény sor legyen külön tétel negatív line_total-lal. Ha nincs rajta összeg, a line_total 0.
- A pontegyenleg, kártyaszám, adószám és hasonló sorok nem tételek, ezeket hagyd ki.
- A név alapján válassz kategóriát (pl. hajlakk, balzsam -> Szépségápolás; fogkrém -> Drogéria/Higiénia; bébi snack -> Étel, subcategory: baba).
- Kávé, tea, üdítő, alkohol -> Ital (a tej és a tejtermékek -> Étel). Vitamin, kollagén, étrend-kiegészítő -> Egészség/Gyógyszer.
"""


class LLMFormatError(Exception):
    def __init__(self, msg, raw=""):
        super().__init__(msg)
        self.raw = raw


def repair_json(s: str) -> str:
    """Gyakori LLM-hibák javítása: '1 199' számérték és záró vessző."""
    s = re.sub(
        r'(:\s*)(-?\d{1,3}(?:[ \u00a0]\d{3})+)(\s*[,}\]])',
        lambda m: m.group(1) + re.sub(r"[ \u00a0]", "", m.group(2)) + m.group(3),
        s,
    )
    return re.sub(r",(\s*[}\]])", r"\1", s)


def call_llm(messages) -> dict:
    resp = requests.post(
        LLM_URL,
        json={"model": LLM_MODEL, "messages": messages, "temperature": 0},
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S)  # gondolkodó modellek
    content = content.replace("```json", "").replace("```", "").strip()
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end == -1:
        raise LLMFormatError("Az LLM nem adott vissza JSON-t", content)
    raw_json = content[start:end + 1]
    err = None
    for candidate in (raw_json, repair_json(raw_json)):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as e:
            err = e
    raise LLMFormatError(f"Érvénytelen JSON: {err}", content)


def normalize(data: dict) -> dict:
    items = []
    for it in data.get("items") or []:
        cat = it.get("category")
        items.append({
            "name_raw": str(it.get("name_raw") or "").strip(),
            "name_clean": str(it.get("name_clean") or it.get("name_raw") or "").strip(),
            "quantity": to_float(it.get("quantity")),
            "unit_price": to_int(it.get("unit_price")),
            "line_total": to_int(it.get("line_total")) or 0,
            "category": cat if cat in CATEGORIES else "Egyéb",
            "subcategory": str(it.get("subcategory") or "").strip() or None,
        })
    data["items"] = items
    data["total"] = to_int(data.get("total"))
    return data


def reconcile(data: dict) -> dict:
    """Ha az LLM kuponhoz/kedvezményhez összeget talált ki (a nyugtán nincs), és a
    nullázásától stimmel a végösszeg, akkor nullázza."""
    total = data.get("total")
    items = data["items"]
    if total is None:
        return data
    s = sum(i["line_total"] for i in items)
    if abs(s - total) <= 1:
        return data
    neg = [i for i in items if i["line_total"] < 0]
    if neg and abs(s - sum(i["line_total"] for i in neg) - total) <= 1:
        for i in neg:
            i["line_total"] = 0
    return data


def analyze_text(ocr_text: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Nyugta OCR szövege:\n\n{ocr_text}"},
    ]
    try:
        data = normalize(call_llm(messages))
    except LLMFormatError as e:
        print(f"   (hibás formátum, újrapróbálom: {e})")
        retry = messages[:-1] + [{
            "role": "user",
            "content": messages[-1]["content"]
            + "\n\nFONTOS: csak érvényes JSON, a számokban nincs szóköz (1199, nem 1 199).",
        }]
        data = normalize(call_llm(retry))

    # Összegellenőrzés: ha nem stimmel, egyszer visszaküldjük javításra
    items_sum = sum(i["line_total"] for i in data["items"])
    if data["total"] is not None and abs(items_sum - data["total"]) > 1:
        messages += [
            {"role": "assistant", "content": json.dumps(data, ensure_ascii=False)},
            {"role": "user", "content": (
                f"A tételek összege ({items_sum}) nem egyezik a végösszeggel ({data['total']}). "
                "Javítsd az árakat/mennyiségeket az OCR szöveg alapján, és add vissza a teljes JSON-t."
            )},
        ]
        try:
            data = normalize(call_llm(messages))
        except Exception as e:
            print(f"   (javítási kör nem sikerült: {e})")
    return reconcile(data)


# ---------------------- 3. lépés: adatbázis ----------------------
def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sha256 TEXT UNIQUE NOT NULL,
        source_file TEXT,
        store TEXT,
        store_address TEXT,
        receipt_date TEXT,
        total INTEGER,
        items_sum INTEGER,
        payment_method TEXT,
        needs_review INTEGER DEFAULT 0,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_id INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
        name_raw TEXT,
        name_clean TEXT,
        quantity REAL,
        unit_price INTEGER,
        line_total INTEGER,
        category TEXT,
        subcategory TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_items_cat ON items(category);
    CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(receipt_date);
    CREATE VIEW IF NOT EXISTS v_items AS
        SELECT r.receipt_date, r.store, i.name_clean, i.quantity, i.line_total,
               i.category, i.subcategory, r.needs_review
        FROM items i JOIN receipts r ON r.id = i.receipt_id;
    """)
    return con


def stage_analyze():
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    con = init_db()
    con.execute("PRAGMA foreign_keys = ON")

    files = sorted(OCR_DIR.glob("*.json"))
    new = 0
    for f in files:
        rec = json.loads(f.read_text(encoding="utf-8"))
        if con.execute("SELECT 1 FROM receipts WHERE sha256=?", (rec["sha256"],)).fetchone():
            continue
        if not rec.get("ocr_text"):
            print(f"[AI] Üres OCR szöveg, kihagyom: {f.name}")
            continue

        print(f"[AI] Elemzés: {f.name}")
        try:
            data = analyze_text(rec["ocr_text"])
        except Exception as e:
            print(f"   HIBA: {e}")
            raw = getattr(e, "raw", "")
            (ANALYSIS_DIR / f"{f.stem}.error.txt").write_text(
                f"{e}\n\n--- LLM nyers kimenet ---\n{raw}", encoding="utf-8"
            )
            continue

        items_sum = sum(i["line_total"] for i in data["items"])
        date = data.get("date") or rec.get("photo_date")  # ha a nyugtán nincs dátum -> fotó dátuma
        date_from_receipt = bool(data.get("date"))
        needs_review = int(
            not data["items"]
            or data["total"] is None
            or abs(items_sum - (data["total"] or 0)) > 1
            or not date_from_receipt
        )

        (ANALYSIS_DIR / f.name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        cur = con.execute(
            """INSERT INTO receipts (sha256, source_file, store, store_address, receipt_date,
               total, items_sum, payment_method, needs_review, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (rec["sha256"], rec["source_file"], data.get("store"), data.get("store_address"),
             date, data["total"], items_sum, data.get("payment_method"), needs_review,
             datetime.now().isoformat(timespec="seconds")),
        )
        rid = cur.lastrowid
        con.executemany(
            """INSERT INTO items (receipt_id, name_raw, name_clean, quantity, unit_price,
               line_total, category, subcategory) VALUES (?,?,?,?,?,?,?,?)""",
            [(rid, i["name_raw"], i["name_clean"], i["quantity"], i["unit_price"],
              i["line_total"], i["category"], i["subcategory"]) for i in data["items"]],
        )
        con.commit()
        new += 1
        flag = "  (ELLENŐRIZENDŐ)" if needs_review else ""
        print(f"   {data.get('store')} | {date} | {data['total']} Ft | {len(data['items'])} tétel{flag}")

    print(f"[AI] Kész, {new} új nyugta az adatbázisban.")
    con.close()


def stage_redo():
    """Az ellenőrzendő nyugtákat törli az adatbázisból és újraelemzi."""
    con = init_db()
    con.execute("PRAGMA foreign_keys = ON")
    n = con.execute("DELETE FROM receipts WHERE needs_review=1").rowcount
    con.commit()
    con.close()
    print(f"[REDO] {n} ellenőrzendő nyugta törölve, újraelemzés...")
    stage_analyze()


# ---------------------- riport ----------------------
def stage_report():
    con = init_db()
    print("\nHavi kiadás kategóriánként (Ft)")
    print("-" * 50)
    rows = con.execute("""
        SELECT substr(receipt_date,1,7) AS honap, category, SUM(line_total)
        FROM v_items GROUP BY honap, category ORDER BY honap DESC, SUM(line_total) DESC
    """).fetchall()
    for honap, cat, s in rows:
        print(f"{honap}  {cat:<24}{s:>10,}".replace(",", " "))

    n = con.execute("SELECT COUNT(*) FROM receipts WHERE needs_review=1").fetchone()[0]
    if n:
        print(f"\n{n} nyugta ellenőrzésre vár (needs_review=1).")
    con.close()


# ---------------------- main ----------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", default="all",
                    choices=["all", "ocr", "analyze", "redo", "report"])
    stage = ap.parse_args().stage

    if stage in ("all", "ocr"):
        stage_ocr()
    if stage in ("all", "analyze"):
        stage_analyze()
    if stage == "redo":
        stage_redo()
    if stage == "report":
        stage_report()


if __name__ == "__main__":
    sys.exit(main())
