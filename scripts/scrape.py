"""Scrape Caritas Würzburg 'Hilfe & Beratung' pages into data/raw/services_raw.json."""
import re, html, json, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASE = "https://www.caritas-wuerzburg.de"
UA = {"User-Agent": "Mozilla/5.0 (hackathon prototype)"}

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20).read().decode("utf8", "ignore")

def body_text(page):
    t = re.sub(r"<(script|style).*?</\1>", "", page, flags=re.S)
    links = re.findall(r'<a [^>]*href="((?:mailto:|tel:|https?://)[^"]+)"[^>]*>(.*?)</a>', t, flags=re.S)
    t = re.sub(r"<[^>]+>", "\n", t)
    t = re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", html.unescape(t)))
    start = t.rfind("Weiterführende Materialien\nKontakt\n")
    start = start + len("Weiterführende Materialien\nKontakt\n") if start > 0 else 0
    end = t.find("\nDrucken", start)
    content = t[start:end if end > 0 else None].strip()
    ext = [{"url": u, "text": re.sub(r"<[^>]+>|\s+", " ", html.unescape(x)).strip()}
           for u, x in links
           if "caritas-wuerzburg.de" not in u and not any(s in u for s in ("viadesk", "bistum-wuerzburg", "sicher-melden", "plento"))]
    return content, ext

home = get(BASE + "/hilfe-beratung/")
paths = sorted(set(re.findall(r'href="(?:https://www\.caritas-wuerzburg\.de)?(/hilfe-beratung/[^"]+/)"', home)))
out = []
for p in paths:
    try:
        content, ext = body_text(get(BASE + p))
    except Exception as e:
        print("ERR", p, e); continue
    parts = p.strip("/").split("/")
    out.append({"url": BASE + p, "section": parts[1] if len(parts) > 1 else "", "slug": parts[-1],
                "title": content.split("\n")[0] if content else parts[-1],
                "text": content, "external_links": ext})
    print(f"{len(content):6d} chars {len(ext):3d} links  {p}")
    time.sleep(0.3)
json.dump(out, open(ROOT / "data/raw/services_raw.json", "w", encoding="utf8"), ensure_ascii=False, indent=2)
print(len(out), "pages")
