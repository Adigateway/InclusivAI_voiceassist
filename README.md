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
│   ├── processed/
│   │   ├── offices.json               # One record per local office (used by the app)
│   │   ├── offices.csv
│   │   └── services_structured.xlsx   # Sheets: Offices, Services, Coverage (service × region)
│   └── exports/
│       ├── services_overview.xlsx     # Readable dump of raw pages + all contact links
│       └── services_pages.csv
├── scripts/
│   ├── scrape.py                      # caritas-wuerzburg.de → data/raw/
│   ├── structure.py                   # raw pages → structured office records
│   └── export_overview.py             # raw pages → readable Excel/CSV
├── requirements.txt
└── README.md
```

## Data

The source is the public directory at <https://www.caritas-wuerzburg.de/hilfe-beratung/>.

| Dataset | Rows | Description |
|---|---|---|
| Services | 49 | Service types (debt, addiction, pregnancy, migration, care, …) with descriptions |
| Offices | 105 | Local offices with organisation, address, region, phone, email and website |

Fields in `offices.json`:

| Field | Meaning |
|---|---|
| `section`, `service`, `service_slug` | Life situation and service type |
| `organisation`, `offer`, `contact_person` | Who runs the office and what it offers |
| `street`, `plz`, `city`, `region` | Address. `region` is the district (Landkreis) in Lower Franconia |
| `phone`, `fax_or_phone2`, `email`, `website` | Contact details |
| `is_caritas` | `false` for partner organisations, such as Diakonie or city services |
| `audience` | `public`, or `professionals/coordination` for internal staff contacts. Only route users to `public` |
| `source_url` | The page the record came from |

**Known limitations:**
- Some services, such as pregnancy counselling, only link to partner websites and have no addresses here.
- 4 records have no organisation name.
- Parsing is heuristic, so check any record against its `source_url`.

## Getting started

```bash
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
