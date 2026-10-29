"""Turn data/raw/services_raw.json into one row per local office -> data/processed/."""
import json, re, csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ADDR = re.compile(r"^(?P<street>.+?),?\s+(?P<plz>\d{5})\s+(?P<city>[A-ZÄÖÜ][^\d]*)$")
PHONE = re.compile(r"^[\d\s/()+\-]{6,}$")
EMAIL = re.compile(r"^\S+@\S+\.\w+$")
URL = re.compile(r"^(https?://|www\.)\S+$")

# City -> Landkreis/kreisfreie Stadt in Unterfranken
REGION = {
    "Würzburg": "Würzburg (Stadt/Land)", "Ochsenfurt": "Würzburg (Stadt/Land)", "Höchberg": "Würzburg (Stadt/Land)",
    "Schweinfurt": "Schweinfurt (Stadt/Land)", "Gerolzhofen": "Schweinfurt (Stadt/Land)", "Kolitzheim": "Schweinfurt (Stadt/Land)", "Werneck": "Schweinfurt (Stadt/Land)",
    "Aschaffenburg": "Aschaffenburg (Stadt/Land)", "Schöllkrippen": "Aschaffenburg (Stadt/Land)", "Alzenau": "Aschaffenburg (Stadt/Land)",
    "Miltenberg": "Miltenberg", "Bürgstadt": "Miltenberg", "Obernburg": "Miltenberg", "Erlenbach": "Miltenberg", "Amorbach": "Miltenberg",
    "Kitzingen": "Kitzingen", "Dettelbach": "Kitzingen",
    "Haßfurt": "Haßberge", "Ebern": "Haßberge", "Hofheim": "Haßberge",
    "Bad Kissingen": "Bad Kissingen", "Bas Kissingen": "Bad Kissingen", "Hammelburg": "Bad Kissingen", "Bad Brückenau": "Bad Kissingen",
    "Bad Neustadt": "Rhön-Grabfeld", "Mellrichstadt": "Rhön-Grabfeld", "Bad Königshofen": "Rhön-Grabfeld",
    "Lohr": "Main-Spessart", "Karlstadt": "Main-Spessart", "Marktheidenfeld": "Main-Spessart", "Gemünden": "Main-Spessart",
}

def region_of(city):
    for k, v in REGION.items():
        if city.startswith(k):
            return v
    return ""

def is_contact(l):
    return bool(PHONE.match(l) or EMAIL.match(l) or URL.match(l))

def is_name_line(l):
    sentence = l.endswith(".") and not re.search(r"(e\. ?V|mbH|e\.V)\.?$", l)
    return 0 < len(l) < 140 and not l.endswith(":") and not sentence and not is_contact(l) and not ADDR.match(l) \
        and not l.startswith(("©", "Hier finden", "Alle Kontakt"))

def parse(page):
    lines = [l.strip() for l in page["text"].split("\n") if l.strip()]
    offices = []
    for i, l in enumerate(lines):
        m = ADDR.match(l)
        if not m:
            continue
        # name: up to 2 short lines before the address, stopping at a previous office's contact lines
        name = []
        j = i - 1
        while j >= 0 and len(name) < 3 and is_name_line(lines[j]):
            name.insert(0, lines[j]); j -= 1
        # contacts after the address
        phones, emails, urls = [], [], []
        k = i + 1
        while k < len(lines) and is_contact(lines[k]):
            c = lines[k]
            (emails if EMAIL.match(c) else urls if URL.match(c) else phones).append(c)
            k += 1
        ORG = re.compile(r"verband|e\. ?V|GmbH|Gesellschaft|Stadt |Diakonie|SkF|Sozialdienst|Kreuzbund|Bistum|Stiftung|Landratsamt", re.I)
        org_i = next((n for n in range(len(name) - 1, -1, -1) if ORG.search(name[n])), 0 if name else None)
        org = name[org_i] if name else ""
        rest = [n for n in range(len(name)) if n != org_i]
        # 3 lines before org = "Firstname Lastname / role / org"
        person = name[0] if len(name) == 3 and org_i == 2 else ""
        offer = " - ".join(name[n] for n in rest if name[n] != person)
        # pages list a person (first/last name) + role before diocesan coordination contacts
        coordination = any("@caritas-wuerzburg.de" in e for e in emails) and \
            (bool(person) or any(w in " ".join(lines[max(0, i - 5):i]) for w in ("Referent", "Fachberatung", "Ansprechpartner")))
        offices.append({
            "section": page["section"], "service": page["title"], "service_slug": page["slug"],
            "organisation": org, "offer": offer, "contact_person": person,
            "street": m["street"].rstrip(","), "plz": m["plz"], "city": m["city"].strip(),
            "region": region_of(m["city"].strip()),
            "phone": phones[0] if phones else "", "fax_or_phone2": phones[1] if len(phones) > 1 else "",
            "email": "; ".join(emails), "website": "; ".join(urls),
            "is_caritas": "caritas" in (org + offer + " ".join(emails + urls)).lower(),
            "audience": "professionals/coordination" if coordination else "public",
            "source_url": page["url"],
        })
    return offices

def service_summary(page):
    # first real paragraph = description
    paras = [l for l in page["text"].split("\n") if len(l) > 120]
    return paras[0] if paras else ""

pages = json.load(open(ROOT / "data/raw/services_raw.json", encoding="utf8"))
offices = [o for p in pages for o in parse(p)]
services = [{"section": p["section"], "service_slug": p["slug"], "service": p["title"],
             "description": service_summary(p), "office_count": sum(o["service_slug"] == p["slug"] for o in offices),
             "regions_covered": ", ".join(sorted({o["region"] for o in offices if o["service_slug"] == p["slug"] and o["region"]})),
             "url": p["url"]} for p in pages]

json.dump(offices, open(ROOT / "data/processed/offices.json", "w", encoding="utf8"), ensure_ascii=False, indent=2)
with open(ROOT / "data/processed/offices.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=offices[0].keys()); w.writeheader(); w.writerows(offices)

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
wb = Workbook(); wb.remove(wb.active)
def sheet(name, rows, widths):
    ws = wb.create_sheet(name); keys = list(rows[0].keys()); ws.append(keys)
    for r in rows: ws.append([r[k] for k in keys])
    for c in ws[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="C8102E")
    ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
    for i, k in enumerate(keys): ws.column_dimensions[ws.cell(1, i + 1).column_letter].width = widths.get(k, 18)
    return ws
sheet("Offices", offices, {"service": 30, "organisation": 45, "offer": 40, "street": 28, "plz": 7, "city": 18,
                           "region": 24, "phone": 16, "email": 34, "website": 45, "source_url": 50})
ws = sheet("Services", services, {"service": 32, "description": 90, "regions_covered": 60, "url": 50})
for c in ws["D"][1:]: c.alignment = Alignment(wrap_text=True, vertical="top")
# coverage matrix: service x region
regions = sorted({o["region"] for o in offices if o["region"]})
pub = [o for o in offices if o["audience"] == "public"]
matrix = [{"service": s["service"], **{r: sum(o["service_slug"] == s["service_slug"] and o["region"] == r for o in pub) or "" for r in regions}}
          for s in services if s["office_count"]]
sheet("Coverage", matrix, {"service": 34, **{r: 14 for r in regions}})
wb.save(ROOT / "data/processed/services_structured.xlsx")

print(len(offices), "offices;", sum(o["region"] == "" for o in offices), "without region;",
      sum(o["organisation"] == "" for o in offices), "without name")
print("unmapped cities:", sorted({o["city"] for o in offices if not o["region"]}))
