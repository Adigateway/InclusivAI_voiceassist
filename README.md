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
├── data/routing/
│   └── service_cards.json             # Plain-language service cards the LLM routes with (32 cards)
├── app/
│   ├── llm.py                         # Client for any OpenAI-compatible API (Ollama, Groq, ...)
│   ├── router.py                      # Routing engine: LLM picks service, code picks office
│   └── safety.py                      # Crisis detection, runs before the LLM
├── tests/
│   ├── routing_cases.json             # 20 example situations with the expected service
│   └── eval_routing.py                # Measures routing accuracy
├── web/
│   └── index.html                     # Chat page (plain HTML/JS, no build step)
├── server.py                          # Web server + /api/chat (standard library only)
├── cli.py                             # Text chat in the terminal
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

## How routing works

1. **Crisis check** (`app/safety.py`): keyword rules in several languages run on every message *before* the LLM. On a match, the assistant gives the emergency numbers straight away.
2. **The LLM picks the service type.** Every request includes all service cards from `data/routing/service_cards.json` in the prompt. The model answers in JSON with `action` (`ask`/`recommend`), `service_ids`, `question`, `reason` and `language`. Nothing is trained or fine-tuned.
3. **Code validates the answer.** Any service id that isn't in the catalogue is dropped. If nothing valid remains, the assistant falls back to general social counselling (Allgemeine Sozialberatung).
4. **Code finds the region** from the town the user names (for example "Lohr" → Main-Spessart). If no town is known, it asks once.
5. **Code looks up the offices** in `offices.json`, in this order: an office in the user's region → a related service in the region → the central office serving all of Lower Franconia → local general social counselling. The LLM never produces contact details.

### LLM (free)

By default the engine uses **Ollama** running locally with `qwen2.5:3b`. It's free, works offline and no data leaves the machine. Any OpenAI-compatible API can be used instead:

```bash
export LLM_BASE_URL=https://api.groq.com/openai/v1 LLM_MODEL=openai/gpt-oss-120b LLM_API_KEY=<your key>
```

Put these settings in a `.env` file (copy `.env.example`). It's gitignored, so keys never get committed.

**Accuracy** (`python -m tests.eval_routing`, 20 cases, M1 with 8 GB RAM):

| Model | Where | Correct | Time per answer |
|---|---|---|---|
| `qwen2.5:3b` | Ollama, local | 15/20 (75%) | ~4 s |
| `qwen2.5:7b` | Ollama, local | 18/20 (90%) | ~12 s |
| `qwen/qwen3.8-27b` | Groq, free tier | 19/20 (95%) | ~0.4 s |
| **`openai/gpt-oss-120b`** | **Groq, free tier (recommended)** | **19/20 (95%)** | **~0.4 s** |

Every answer was a valid service id. The misses were neighbouring services, for example general social counselling instead of homelessness help.

Groq's free tier limits tokens per minute. The client waits and retries on HTTP 429, so a full test run takes a few minutes, but a single answer comes back in under a second.

## Getting started

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/scrape.py           # re-scrape the website (optional, data is committed)
python scripts/structure.py        # build data/processed/
python scripts/export_overview.py  # build data/exports/
ollama pull qwen2.5:3b             # free local LLM (~1.9 GB)
python server.py                   # web chat at http://localhost:8000
python cli.py                      # or: chat in the terminal
python -m tests.eval_routing       # routing accuracy
```

## Web API

The page talks to one endpoint, so a voice front end can reuse it:

```http
POST /api/chat   {"session": "<any id>", "message": "Ich habe Schulden, ich wohne in Lohr"}
→ {"kind": "ask" | "recommend" | "crisis", "text": "...", "region": "Main-Spessart",
   "services": [{"id": "schuldnerberatung", "name": "..."}], "offices": [{"organisation": "...", "phone": "...", ...}]}

POST /api/reset  {"session": "<id>"}
```

`text` is the complete answer, ready to be read aloud by text-to-speech.

## Roadmap

- [x] Scrape and structure the Caritas service directory
- [x] LLM routing (service cards + JSON output + validation)
- [x] Region and service matcher
- [x] Web chat UI
- [ ] Voice (speech-to-text and text-to-speech, multilingual)
- [x] Crisis detection and safety layer
- [ ] Demo personas

## Disclaimer

This is a hackathon prototype and not an official Caritas service. In an emergency, call **112**. For confidential support at any time, call TelefonSeelsorge on **0800 111 0 111**.
