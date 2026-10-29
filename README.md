# InclusivAI Voice Assist

A voice assistant prototype that helps people find the right **Caritas** support service in Lower Franconia (Unterfranken, Germany). It was built for the **Caritas Würzburg** hackathon challenge.

> *"I need help. Which Caritas service can support me, and why is it the right place for my situation?"*

## The problem

The Caritasverband für die Diözese Würzburg is an umbrella for many local Caritas associations, specialist associations and partner organisations. Each service is organised locally (the "subsidiarity" principle), so people seeking help often don't know which office is responsible for their situation and region.

## Our approach

Users describe their situation by **speaking in everyday language**. The assistant:

1. **Transcribes** the speech (multilingual speech-to-text).
2. **Builds a structured case** with an LLM: needs, region, target group and urgency.
3. **Asks follow-up questions** in plain language when information is missing, most often the region.
4. **Matches** the case against the service directory: hard filters on region and audience, then semantic ranking.
5. **Explains why** a service fits, using only the directory data, and gives contact details.
6. **Detects crises** at every step and gives emergency numbers immediately (TelefonSeelsorge 0800 111 0 111, 112, 116 016).

```
Speech → STT → LLM case builder ──missing info?──▶ follow-up question
                     │                                 
                     ▼                                 
              Service matcher (region × service type) → explanation → TTS + contact card
```

## Repository structure

```
.
├── data/
│   ├── raw/
│   │   └── services_raw.json          # Scraped "Hilfe & Beratung" pages (49 pages)
│   ├── processed/                     # Clean data used by the assistant
│   │   ├── services.json              # 33 routable services (what the LLM chooses from)
│   │   ├── offices.json / .csv        # 115 local offices (what the code looks up by region)
│   │   ├── referents.json             # Diocesan subject-matter contacts (fallback contact person)
│   │   └── services_structured.xlsx   # Sheets: Offices, Services, Coverage, Referents
│   └── exports/
│       ├── services_overview.xlsx     # Readable dump of raw pages + all contact links
│       └── services_pages.csv
├── scripts/
│   ├── scrape.py                      # caritas-wuerzburg.de → data/raw/
│   ├── structure.py                   # raw pages → cleaned services, offices, referents
│   └── export_overview.py             # raw pages → readable Excel/CSV
├── requirements.txt
└── README.md
```

## Data

The source is the public directory at <https://www.caritas-wuerzburg.de/hilfe-beratung/>.

| Dataset | Rows | Used by | Description |
|---|---|---|---|
| `services.json` | 33 | LLM | Service types a person can be routed to, with descriptions |
| `offices.json` | 115 | Code | Local offices per service and region. Has **no empty fields** |
| `referents.json` | 13 | Code | Diocesan specialists per subject area |

Fields in `offices.json`:

| Field | Meaning |
|---|---|
| `service_id`, `service`, `section` | Service type and life situation |
| `organisation` | The provider (a Caritas association or a partner such as SkF, Diakonie or the city) |
| `offer` | What this office offers |
| `contact_person` | Named contact. If the page names none, this is "Beratungsteam vor Ort" plus the responsible diocesan specialist |
| `street`, `plz`, `city`, `region` | Address. `region` is the district (Landkreis) in Lower Franconia |
| `phone`, `email`, `website` | Contact details |
| `is_caritas` | `false` for partner organisations |
| `source_url` | The page the record came from |
| `filled_fields` | Fields that were inferred rather than read from the office's own entry (see below) |

### Cleaning rules (`scripts/structure.py`)

- **Titles:** image credits ("© stock.adobe.com") are skipped and services get clean names.
- **Removed pages:** 16 pages that aren't services for people seeking help. These are the section overview pages, the internal child-protection prevention pages, Kita management advice, professional working groups (DiAG, AGkE) and contact lists.
- **Diocesan coordinators** (Referent/innen) are moved out of the offices into `referents.json`.
- **Offer:** person names and addresses are moved into `contact_person` and `street`. The offer is always the service name plus the specific offer.
- **Missing values** are filled from the most reliable real source, in this order:
  1. the same organisation's entry on another page;
  2. the website, taken from the email domain;
  3. the responsible diocesan specialist for that subject area, for `contact_person`;
  4. the central Caritas office (0931 386-66 700, info@caritas-wuerzburg.de), as a last resort.

  Every inferred value is listed in `filled_fields`, so nothing invented looks like original data.
- **Services with no addresses on the site** get one row per partner organisation they link to (for example the SkF offices for pregnancy counselling). If there are no such links, they get one row pointing to the central office.

**Known limitations:** parsing is heuristic, so check any record against its `source_url`. Partner-link rows have no street address ("siehe Website des Trägers").

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/scrape.py           # re-scrape the website (optional, data is committed)
python scripts/structure.py        # build data/processed/
python scripts/export_overview.py  # build data/exports/
```

## Roadmap

- [x] Scrape and structure the Caritas service directory
- [ ] LLM case builder (structured extraction from speech)
- [ ] Region and service matcher
- [ ] Voice UI (speech-to-text and text-to-speech, multilingual)
- [ ] Crisis detection and safety layer
- [ ] Demo personas

## Disclaimer

This is a hackathon prototype and not an official Caritas service. In an emergency, call **112**. For confidential support at any time, call TelefonSeelsorge on **0800 111 0 111**.
