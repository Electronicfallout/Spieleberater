#!/usr/bin/env python3
"""Lädt Schachtelbilder aus dem Hive-Games-Shop (Odoo) für alle Einträge in tools/images.json.
Ergebnis: img/<key>.jpg und img/index.json (Liste der vorhandenen Bilder)."""
import json, re, io, time, difflib, pathlib, urllib.parse, html
import requests
from PIL import Image

BASE = "https://shop.hivegames.at"
root = pathlib.Path(__file__).resolve().parent.parent
items = json.loads((root / "tools/images.json").read_text(encoding="utf-8"))
out = root / "img"; out.mkdir(exist_ok=True)
idx_path = out / "index.json"
index = json.loads(idx_path.read_text()) if idx_path.exists() else {}
S = requests.Session(); S.headers["User-Agent"] = "Mozilla/5.0 (Spieleberater image sync)"
TILE = re.compile(r'href="(/shop/(?!page/|category/|cart|checkout|change_pricelist)[^"?#]*?-(\d+))(?:\?[^"]*)?"[^>]*>\s*([^<]{2,200}?)\s*<', re.I)

def norm(t): return re.sub(r"\s+", " ", html.unescape(t)).strip().lower()

for key, q in items.items():
    if key in index and (out / f"{key}.jpg").exists():
        continue
    try:
        r = S.get(f"{BASE}/shop", params={"search": q}, timeout=30); r.raise_for_status()
        tiles = [(m.group(2), norm(m.group(3))) for m in TILE.finditer(r.text)]
        if not tiles:
            ids = re.findall(r'href="/shop/[^"?#]*?-(\d+)(?:\?[^"]*)?"', r.text)
            tiles = [(i, "") for i in ids]
        if not tiles:
            print("kein Treffer:", q); continue
        best = max(tiles, key=lambda t: difflib.SequenceMatcher(None, norm(q), t[1]).ratio())
        pid = best[0]
        im = S.get(f"{BASE}/web/image/product.template/{pid}/image_512", timeout=30); im.raise_for_status()
        img = Image.open(io.BytesIO(im.content)).convert("RGB")
        if img.width < 40 or img.height < 40: print("Bild zu klein:", q); continue
        img.thumbnail((480, 480))
        img.save(out / f"{key}.jpg", "JPEG", quality=82, optimize=True)
        index[key] = {"q": q, "product": pid, "match": best[1]}
        print("ok", key, pid, best[1])
    except Exception as e:
        print("Fehler", q, e)
    time.sleep(0.7)
idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(index), "Bilder")
