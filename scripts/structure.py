"""Turn data/raw/services_raw.json into clean, routable tables -> data/processed/.

Outputs
  services.json      one row per service a person can be routed to
  offices.json/.csv  one row per local office (no empty fields; inferred values are listed in `filled_fields`)
  referents.json     diocesan subject-matter contacts (used as fallback contact person)
  services_structured.xlsx  Offices, Services, Coverage, Referents
"""
import json, re, csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Main office of the diocesan association (from the Impressum page) - last-resort contact
CENTRAL = {"organisation": "Caritasverband für die Diözese Würzburg e. V.", "phone": "0931 386-66 700",
           "email": "info@caritas-wuerzburg.de", "website": "https://www.caritas-wuerzburg.de"}

# Pages that are not a service someone can be routed to: section overviews, internal/professional
# pages (child-protection policy, Kita management, working groups) and contact lists.
NOT_ROUTABLE = {
    "familie", "jugend", "kinder", "menschen-in-krisensituationen", "menschen-mit-behinderung",
    "migrationasyl", "senioren",                                   # section overview pages
    "praevention", "institutionelles-schutzkonzept", "paragrafen-fuer-die-selbstauskunftserklaerung",
    "kontakt", "weiterfuehrende-materialien",                      # prevention policy for staff
    "kita-fachberatung", "kindertageseinrichtungen",               # advice for Kita operators
    "diag-altenhilfe", "agke",                                     # professional working groups
}

# Clean, plain service names (page titles are often image credits or long headings)
SERVICE_NAMES = {
    "besuchsdienste": "Besuchsdienste", "familienpflege": "Familienpflege", "jugendhilfe": "Jugendhilfe",
    "kuren-und-erholung": "Kuren für Mütter, Väter und pflegende Angehörige",
    "nachbarschaftshilfe": "Nachbarschaftshilfe", "schwangerschaftsberatung": "Schwangerschaftsberatung",
    "erziehungshilfe": "Erziehungsberatung", "essstoerungen": "Beratung bei Essstörungen",
    "jugendsozialarbeit": "Jugendsozialarbeit", "jugendwohnen": "Jugendwohnen",
    "junge-eltern-und-beruf": "Junge Eltern und Berufsausbildung", "jugend-suchtberatung": "Suchtberatung für Jugendliche",
    "fruehfoerderung": "Frühförderung", "kur-und-erholung": "Kinderkuren und Erholung",
    "allgemeine-sozialberatung": "Allgemeine Sozialberatung",
    "fachambulanz-fuer-sexualstraftaeter": "Fachambulanz für Sexual- und Gewaltstraftäter",
    "hilfen-fuer-frauen-1": "Hilfen für Frauen in Not- und Gewaltsituationen", "hivaids": "HIV/Aids-Beratung",
    "krisenhilfe-telefonseelsorge-und-suizidpraevention": "Krisenhilfe, Telefonseelsorge und Suizidprävention",
    "schuldnerberatung": "Schuldner- und Insolvenzberatung", "sozialpsychiatrische-dienste": "Sozialpsychiatrische Dienste",
    "straffaelligenhilfe": "Straffälligenhilfe", "suchtberatung": "Suchtberatung",
    "wohnsitzlosigkeit": "Wohnungslosenhilfe", "foerderschulen": "Förderschulen",
    "adressen-migrationsdienste": "Flüchtlings- und Integrationsberatung",
    "beratung-in-wuerzburg": "Flüchtlings- und Integrationsberatung Würzburg",
    "rueckkehrberatung": "Rückkehrberatung für Geflüchtete", "ambulante-pflege": "Ambulante Pflege",
    "ambulante-wohngemeinschaften": "Ambulant betreute Wohngemeinschaften",
    "palliativ-ethik-und-hospizarbeit": "Hospiz- und Palliativbegleitung",
    "teilstationaere-altenhilfe": "Tagespflege", "vollstationaere-pflege": "Pflegeheim (vollstationäre Pflege)",
}

REGION = {
    "Würzburg": "Würzburg (Stadt/Land)", "Ochsenfurt": "Würzburg (Stadt/Land)", "Höchberg": "Würzburg (Stadt/Land)",
    "Schweinfurt": "Schweinfurt (Stadt/Land)", "Gerolzhofen": "Schweinfurt (Stadt/Land)",
    "Kolitzheim": "Schweinfurt (Stadt/Land)", "Werneck": "Schweinfurt (Stadt/Land)",
    "Aschaffenburg": "Aschaffenburg (Stadt/Land)", "Alzenau": "Aschaffenburg (Stadt/Land)",
    "Schöllkrippen": "Aschaffenburg (Stadt/Land)",
    "Miltenberg": "Miltenberg", "Bürgstadt": "Miltenberg", "Obernburg": "Miltenberg", "Erlenbach": "Miltenberg",
    "Kitzingen": "Kitzingen", "Dettelbach": "Kitzingen",
    "Haßfurt": "Haßberge", "Ebern": "Haßberge", "Hofheim": "Haßberge",
    "Bad Kissingen": "Bad Kissingen", "Bas Kissingen": "Bad Kissingen", "Hammelburg": "Bad Kissingen",
    "Bad Brückenau": "Bad Kissingen",
    "Bad Neustadt": "Rhön-Grabfeld", "Mellrichstadt": "Rhön-Grabfeld", "Bad Königshofen": "Rhön-Grabfeld",
    "Lohr": "Main-Spessart", "Karlstadt": "Main-Spessart", "Marktheidenfeld": "Main-Spessart", "Gemünden": "Main-Spessart",
}

ADDR = re.compile(r"^(?:Adresse:\s*)?(?P<street>.+?),?\s+(?P<plz>\d{5})\s+(?P<city>[A-ZÄÖÜ][^\d]*)$")
PHONE = re.compile(r"^(?:(?:Telefon|Tel\.?|Fax):?\s*)?[\d\s/()+\-]{6,}$")
EMAIL = re.compile(r"^(?:E-Mail:\s*)?\S+@\S+\.\w+$")
URL = re.compile(r"^(https?://|www\.)\S+$")
ORG = re.compile(r"verband|e\. ?V|gGmbH|GmbH|mbH|Gesellschaft|^Stadt |Diakonie|SkF|Sozialdienst|Kreuzbund|"
                 r"Stiftung|Landratsamt|Sozialwerk|IN VIA|Zentrum|Haus |Schule|Blaues Kreuz|Kolping|Don Bosco|der Stadt|"
                 r"Diözese|ROVEN|Frühförderstelle|Beratungsstelle|Dienst ", re.I)
# Roles of diocesan staff who coordinate a field (not client-facing)
COORD_ROLE = re.compile(r"Referent|Fachberatung|Stabs|Hilfskraft|Abteilungsleitung", re.I)
PERSON = re.compile(r"(?:(?:Frau|Herr) )?[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)? [A-ZÄÖÜ][a-zäöüß]+(?:-[A-Za-zäöüß]+)?")
ROLE = re.compile(r"Referent|Leitung|Leiter|Verwaltung|Fachberat|Sachbearbeit|Hilfskraft|Koordinat|Ansprechpartner", re.I)
OFFER = re.compile(r"[Bb]eratung|[Dd]ienst|[Ss]telle|[Hh]ilfe|[Pp]flege|[Ww]ohnen|[Bb]ildung|[Ff]örder|[Ss]precht|Ambulanz|"
                   r"Behandlung|Sozialarbeit|Begleitung|Erholung|Kur", re.I)
GENERIC_MAIL = ("t-online.de", "gmail.com", "web.de", "gmx.de")


def region_of(city):
    return next((v for k, v in REGION.items() if city.startswith(k)), "")


def is_contact(l):
    return bool(PHONE.match(l) or EMAIL.match(l) or URL.match(l)) or l in ("E-Mail:", "Telefon:", "Fax:")


def is_prose(l):
    return len(l) > 140 or l.endswith(":") or (l.endswith(".") and not re.search(r"(e\. ?V|mbH|e\.V)\.?$", l)) \
        or l.startswith(("©", "Hier finden", "Alle Kontakt", "Wenden Sie", "Im ", "Ihr", "mehr erfahren"))


def clean_title(page):
    for l in page["text"].split("\n"):
        l = l.strip()
        if l and not l.startswith("©"):
            return l
    return page["slug"]


def split_header(lines):
    """Classify the short lines above an address into organisation / person / role / offer / branches."""
    out = {"organisation": "", "person": [], "role": [], "offer": [], "branches": []}
    i = 0
    while i < len(lines):
        l = lines[i].strip(" :-")
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if l.startswith("Außensprechstunde"):
            out["branches"].append(l.replace("Außensprechstunde", "").strip(" -"))
        elif l.startswith("Stellvertretung"):
            out["person"].append("Vertretung: " + l.split(":", 1)[1].split(", E-Mail")[0].strip())
        elif re.fullmatch(r"(Frau|Herr) [A-ZÄÖÜ][\w\-]+", l):
            out["person"].append(l)
        elif PERSON.fullmatch(l) and not (ORG.search(l) or ROLE.search(l) or OFFER.search(l)) \
                and not any(l.endswith(c) for c in REGION):
            out["person"].append(l)
        elif re.fullmatch(r"[A-ZÄÖÜ][\w\-]+", l) and re.fullmatch(r"[A-ZÄÖÜ][\w\-]+", nxt):
            out["person"].append(f"{l} {nxt}"); i += 1                     # "Firstname\nLastname"
        elif ROLE.search(l) and not ORG.search(l):
            out["role"].append(l)
        elif ORG.search(l) and not out["organisation"]:
            out["organisation"] = l
        elif OFFER.search(l) or len(l.split()) > 3:
            out["offer"].append(l)
        elif not out["organisation"]:
            out["organisation"] = l
        else:
            out["offer"].append(l)
        i += 1
    return out


def parse(page, service_id):
    text = re.sub(r"\s*\r\n\s*", " ", page["text"])          # addresses broken over "\r\n" lines
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    offices, last_end = [], 0
    for i, l in enumerate(lines):
        m = ADDR.match(l)
        if not m or i < last_end:
            continue
        # header: short lines directly above the address, back to the previous office or a prose line
        j = i - 1
        while j >= last_end and i - j <= 6 and not is_prose(lines[j]) and not is_contact(lines[j]) and not ADDR.match(lines[j]):
            j -= 1
        h = split_header(lines[j + 1:i])
        # contact block below (and, for "Adresse:" style pages, also above)
        phones, emails, urls = [], [], []
        k = i + 1
        staff = []
        while k < len(lines) and (is_contact(lines[k]) or lines[k].startswith("Telefon:") or
                                  (PERSON.fullmatch(lines[k]) and k + 1 < len(lines) and lines[k + 1].startswith("("))):
            if PERSON.fullmatch(lines[k]):                       # "Name\n(Mo-Fr)" staff lists
                staff.append(f"{lines[k]} {lines[k + 1]}"); k += 2; continue
            c = re.sub(r"^(E-Mail|Telefon|Tel\.?|Fax):?\s*", "", lines[k])
            if c:
                (emails if "@" in c else urls if URL.match(c) else phones).append(c)
            k += 1
        last_end = k
        h["person"] += staff
        offices.append({"page": page, "service_id": service_id, "h": h, "m": m,
                        "phones": phones, "emails": emails, "urls": urls})
    return offices


pages = json.load(open(ROOT / "data/raw/services_raw.json", encoding="utf8"))
raw_offices, referents, services = [], [], []
for p in pages:
    sid = "jugend-suchtberatung" if (p["section"], p["slug"]) == ("jugend", "suchtberatung") else p["slug"]
    parsed = parse(p, sid)
    for o in parsed:
        h = o["h"]
        diocesan = any(e.endswith("@caritas-wuerzburg.de") for e in o["emails"]) and "Franziskanergasse" in o["m"]["street"]
        if diocesan and any(COORD_ROLE.search(x) for x in h["role"]):
            referents.append({"service_id": sid, "section": p["section"],
                              "name": ", ".join(x for x in h["person"] if not x.startswith("Vertretung")) or "",
                              "role": "; ".join(h["role"]), "phone": o["phones"][0] if o["phones"] else "",
                              "email": "; ".join(o["emails"])})
        elif sid not in NOT_ROUTABLE:
            raw_offices.append(o)
    if sid not in NOT_ROUTABLE:
        paras = [l for l in p["text"].split("\n") if len(l) > 120]
        services.append({"service_id": sid, "section": p["section"], "service": SERVICE_NAMES.get(sid, clean_title(p)),
                         "description": paras[0] if paras else "", "url": p["url"]})

referents = [r for r in referents if r["name"]]
ref_by_service = {r["service_id"]: r for r in referents}
# Fallback referent per life situation, by the subject area in their job title
SECTION_REFERENT = {"familie": "Sabrina Göpfert", "jugend": "Sabrina Göpfert", "kinder": "Sabrina Göpfert",
                    "migrationasyl": "Patrick Sammetinger", "senioren": "Silke Birklein",
                    "menschen-in-krisensituationen": "Kilian Bundschuh", "menschen-mit-behinderung": "Silke Birklein"}
by_name = {r["name"]: r for r in referents}
ref_by_section = {sec: by_name[n] for sec, n in SECTION_REFERENT.items() if n in by_name}

# Services with no addresses on the site: add one row per partner link that names a town, else one central row
page_by_id = {("jugend-suchtberatung" if (p["section"], p["slug"]) == ("jugend", "suchtberatung") else p["slug"]): p for p in pages}
for s in services:
    if any(o["service_id"] == s["service_id"] for o in raw_offices):
        continue
    page = page_by_id[s["service_id"]]
    seen = set()
    for link in page["external_links"]:
        city = next((c for c in REGION if c in link["text"]), "")
        domain = re.sub(r"^https?://(www\.)?", "", link["url"]).split("/")[0]
        if not city or not link["url"].startswith("http") or (city, domain) in seen or "Leichte Sprache" in link["text"]:
            continue
        seen.add((city, domain))
        name = re.sub(r"^Hier geht es zur Homepage (des|von|in) |\.$", "", link["text"]).replace("Skf", "SkF")
        if name in REGION:                                   # link text is just a town name
            name = f"{s['service']} {name} ({domain})"
        raw_offices.append({"page": page, "service_id": s["service_id"], "link_only": True,
                            "h": {"organisation": name, "person": [], "role": [], "offer": [], "branches": []},
                            "m": {"street": "", "plz": "", "city": city}, "phones": [], "emails": [], "urls": [link["url"]]})
    if not seen:
        raw_offices.append({"page": page, "service_id": s["service_id"], "link_only": True,
                            "h": {"organisation": CENTRAL["organisation"], "person": [], "role": [], "offer": [], "branches": []},
                            "m": {"street": "Franziskanergasse 3", "plz": "97070", "city": "Würzburg"},
                            "phones": [], "emails": [], "urls": [page["url"]]})

# First pass: build rows from what the page says
offices = []
for o in raw_offices:
    h, m, sid = o["h"], o["m"], o["service_id"]
    service = SERVICE_NAMES.get(sid, sid)
    offer_bits = [x for x in h["offer"] if not ADDR.match(x)]
    # "Außensprechstunde X Außensprechstunde Y Street 5" -> outreach locations + street
    parts = re.split(r"\s*Außensprechstunde\s*", m["street"].rstrip(","))
    street, branches_in_street = parts[-1], []
    if len(parts) > 1:
        last = re.match(r"(.*?)\s+([A-ZÄÖÜ][\w.\-]*(?:str\.|straße|gasse|platz|weg)\s*\d.*)$", parts[-1])
        street = last[2] if last else parts[-1]
        branches_in_street = [x for x in parts[1:-1] + ([last[1]] if last else []) if x]
    offices.append({
        "service_id": sid, "service": service, "section": o["page"]["section"],
        "organisation": h["organisation"], "offer": " – ".join([service] + [x for x in offer_bits if x.lower() != service.lower()]),
        "contact_person": "; ".join(h["person"] + (["(" + ", ".join(h["role"]) + ")"] if h["role"] else [])),
        "street": street, "plz": m["plz"], "city": m["city"].strip(), "region": region_of(m["city"].strip()),
        "outreach_locations": ", ".join(h["branches"] + branches_in_street),
        "phone": o["phones"][0] if o["phones"] else "", "email": "; ".join(o["emails"]), "website": "; ".join(o["urls"]),
        "source_url": o["page"]["url"], "filled_fields": [],
    })

# Second pass: fill gaps from the best available real source, and record what was inferred
def same_org(row, field):
    for other in offices:
        if other is not row and other[field] and other["organisation"] == row["organisation"] and other["city"] == row["city"]:
            return other[field]
    return ""

for r in offices:
    for k in ("organisation", "offer", "city"):
        r[k] = r[k].replace("Bas Kissingen", "Bad Kissingen")       # typo on the source page
    if not r["street"]:
        r["street"] = "siehe Website des Trägers"; r["plz"] = "-"; r["filled_fields"].append("street")
    if not r["organisation"] and "caritas-wuerzburg.de" in r["email"] + r["website"] + r["source_url"] \
            and r["street"].startswith(("Franziskanergasse", "Dominikanerplatz", "Gemeinschaftsunterkunft")):
        r["organisation"] = CENTRAL["organisation"]; r["filled_fields"].append("organisation")
    if r["service_id"] == "beratung-in-wuerzburg" and r["organisation"] != CENTRAL["organisation"]:
        r["organisation"] = CENTRAL["organisation"]         # whole page is run by the diocesan association
    if not r["organisation"]:
        r["organisation"] = r["offer"].split(" – ")[-1] if " – " in r["offer"] else f"{r['service']} {r['city']}"
        r["filled_fields"].append("organisation")
    for f in ("phone", "email", "website"):
        if not r[f] and (v := same_org(r, f)):
            r[f] = v; r["filled_fields"].append(f)
    if not r["website"] and r["email"]:
        dom = r["email"].split(";")[0].split("@")[-1].strip()
        if dom not in GENERIC_MAIL:
            r["website"] = "https://www." + dom; r["filled_fields"].append("website")
    if not r["website"]:
        r["website"] = r["source_url"]; r["filled_fields"].append("website")
    if not r["contact_person"]:
        ref = ref_by_service.get(r["service_id"]) or ref_by_section.get(r["section"])
        if ref and ref["service_id"] in NOT_ROUTABLE and ref["name"] not in SECTION_REFERENT.values():
            ref = None
        r["contact_person"] = f"Beratungsteam vor Ort; Fachreferent/in Diözese: {ref['name']} ({ref['phone']})" if ref \
            else "Beratungsteam vor Ort"
        r["filled_fields"].append("contact_person")
    if not r["phone"]:
        r["phone"] = CENTRAL["phone"] + " (Zentrale Caritas Diözese)"; r["filled_fields"].append("phone")
    if not r["email"]:
        r["email"] = CENTRAL["email"]; r["filled_fields"].append("email")
    if not r["outreach_locations"]:
        r["outreach_locations"] = "keine"
    r["is_caritas"] = bool(re.search(r"caritas", r["organisation"] + r["email"] + r["website"], re.I))
    r["filled_fields"] = ", ".join(r["filled_fields"]) or "none"

# Services: counts and coverage
regions = sorted({o["region"] for o in offices if o["region"]})
for s in services:
    mine = [o for o in offices if o["service_id"] == s["service_id"]]
    s["office_count"] = len(mine)
    s["regions_covered"] = ", ".join(sorted({o["region"] for o in mine if o["region"]})) or \
        "keine Adressen auf der Website (Verweis auf Partner/Online-Beratung)"
    if not s["description"]:
        s["description"] = s["service"]
offices = [o for o in offices if o["region"]]      # drop offices outside Unterfranken (e.g. München)

out = ROOT / "data/processed"
for old in ("offices.json", "offices.csv"):
    (out / old).unlink(missing_ok=True)
json.dump(services, open(out / "services.json", "w", encoding="utf8"), ensure_ascii=False, indent=2)
json.dump(offices, open(out / "offices.json", "w", encoding="utf8"), ensure_ascii=False, indent=2)
json.dump(referents, open(out / "referents.json", "w", encoding="utf8"), ensure_ascii=False, indent=2)
with open(out / "offices.csv", "w", newline="", encoding="utf-8-sig") as f:
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


sheet("Offices", offices, {"service": 34, "organisation": 45, "offer": 50, "contact_person": 50, "street": 28, "plz": 7,
                           "region": 24, "outreach_locations": 40, "phone": 30, "email": 34, "website": 45,
                           "source_url": 50, "filled_fields": 30})
ws = sheet("Services", services, {"service_id": 30, "service": 40, "description": 90, "regions_covered": 60, "url": 50})
for c in ws["D"][1:]: c.alignment = Alignment(wrap_text=True, vertical="top")
sheet("Coverage", [{"service": s["service"], **{rg: sum(o["service_id"] == s["service_id"] and o["region"] == rg for o in offices)
                                               for rg in regions}} for s in services],
      {"service": 46, **{rg: 14 for rg in regions}})
sheet("Referents", referents, {"name": 30, "role": 60, "email": 40})
wb.save(out / "services_structured.xlsx")

print(f"{len(services)} services, {len(offices)} offices, {len(referents)} referents")
empty = {k: sum(1 for o in offices if o[k] in ("", None)) for k in offices[0]}
print("empty fields:", {k: v for k, v in empty.items() if v} or "none")
