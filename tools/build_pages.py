#!/usr/bin/env python3
"""Baut die GitHub-Pages-Version des Spieleberaters.

Aufruf: python3 build.py <quelle.html> <db-ordner-mit-bgglinks-json|-> <ausgabe-ordner>

- Quelle ist die Claude-Artifact-Datei (ohne <head>-Gerüst).
- Profile aus der Artifact-Datenbank (bgglinks/*.json) werden fest eingebaut,
  weil die Datenbank außerhalb von Claude nicht erreichbar ist.
- Ergänzt Handy-Meta-Tags, Web-App-Manifest, Icons und einen Offline-Cache.
"""
import json, sys, pathlib, re, hashlib
from PIL import Image, ImageDraw, ImageFont

src, dbdir, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
html = pathlib.Path(src).read_text(encoding="utf-8")

# 1) Gespeicherte BGG-Links/Profile einbauen
links = {}
if dbdir != "-":
    for f in sorted(pathlib.Path(dbdir).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(d.get("url"), str):
            p = d.get("profile") if isinstance(d.get("profile"), dict) else None
            links[f.stem] = {"url": d["url"], "profile": p}
marker = "const LINKS = {}; let DB = null;"
assert marker in html, "LINKS-Marker nicht gefunden"
baked = json.dumps(links, ensure_ascii=False).replace("</", "<\\/")
html = html.replace(marker, f"const LINKS = {baked}; let DB = null;", 1)

# 2) Hinweistext außerhalb von Claude
old_note = "Speichern ist in dieser Ansicht nicht möglich (nicht angemeldet oder ohne Zugriff). Die Liste ist trotzdem nutzbar."
if old_note in html:
    html = html.replace(old_note, "In der Handy-Version können keine BGG-Links gespeichert werden. Neue Links bitte im Claude-Tool eintragen, sie erscheinen nach dem nächsten Update auch hier.")

# 3) Seitengerüst mit Handy-Tags
html = re.sub(r'<meta name="claude:viewport-fit-sides"[^>]*>\n?', "", html)
head = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="#d99a1e">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Spieleberater">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png" type="image/png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
"""
body_start = html.find("<script>")
# Kopfteil (title, fonts, style) bis zum ersten Markup-Element nach </style>
style_end = html.find("</style>") + len("</style>")
html = head + html[:style_end] + "\n</head>\n<body>\n" + html[style_end:].lstrip("\n")
sw = """<script>
if ("serviceWorker" in navigator && location.protocol === "https:") {
  addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}
</script>
"""
html = html.rstrip() + "\n" + sw + "</body>\n</html>\n"
(out / "index.html").write_text(html, encoding="utf-8")

# 4) Manifest
(out / "manifest.webmanifest").write_text(json.dumps({
    "name": "Hive Games Spieleberater",
    "short_name": "Spieleberater",
    "lang": "de",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#f6f4ee",
    "theme_color": "#d99a1e",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"},
        {"src": "icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}, ensure_ascii=False, indent=2), encoding="utf-8")

# 5) Icons: Honig-Sechseck mit Würfel-Augen
def icon(size, maskable=False, bg=True):
    S = size * 4
    im = Image.new("RGBA", (S, S), (246, 244, 238, 255) if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = S * (0.36 if maskable else 0.46)
    cx = cy = S / 2
    import math
    pts = [(cx + r * math.cos(math.radians(90 + 60 * i)), cy + r * math.sin(math.radians(90 + 60 * i))) for i in range(6)]
    d.polygon(pts, fill=(217, 154, 30, 255))
    pr = r * 0.13
    for dx, dy in [(-0.38, -0.38), (0.38, -0.38), (0, 0), (-0.38, 0.38), (0.38, 0.38)]:
        x, y = cx + dx * r, cy + dy * r
        d.ellipse([x - pr, y - pr, x + pr, y + pr], fill=(30, 28, 24, 255))
    return im.resize((size, size), Image.LANCZOS)

icon(192).save(out / "icon-192.png")
icon(512).save(out / "icon-512.png")
icon(512, maskable=True).save(out / "icon-maskable-512.png")
icon(180).convert("RGB").save(out / "apple-touch-icon.png")

# 6) Service Worker: erst Netz, bei Funkloch aus dem Cache
ver = hashlib.sha1(html.encode()).hexdigest()[:10]
(out / "sw.js").write_text(f"""const CACHE = "spieleberater-{ver}";
const CORE = ["./", "index.html", "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png"];
self.addEventListener("install", e => {{ e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE))); self.skipWaiting(); }});
self.addEventListener("activate", e => {{
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
}});
self.addEventListener("fetch", e => {{
  if (e.request.method !== "GET") return;
  e.respondWith(fetch(e.request).then(r => {{
    if (r.ok && (new URL(e.request.url).origin === location.origin || e.request.url.includes("fonts.g"))) {{
      const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy));
    }}
    return r;
  }}).catch(() => caches.match(e.request).then(m => m || caches.match("index.html"))));
}});
""", encoding="utf-8")

(out / ".nojekyll").write_text("")
print("ok", len(links), "verknüpfte Links,", sum(1 for v in links.values() if v["profile"]), "Profile")
