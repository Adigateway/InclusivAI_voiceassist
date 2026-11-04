# CaritAssist

A voice assistant that helps people in Lower Franconia find the right **Caritas** service. You describe your situation in your own words, and it tells you which service fits, why, and which local office to contact.

Built at a hackathon for the **Caritas Würzburg** challenge:

> *"I need help. Which Caritas service can support me, and why is it the right place for my situation?"*

## What it does

> **You:** "Ich habe so viele Schulden und weiß nicht mehr weiter. Ich wohne in Schweinfurt."
>
> **CaritAssist:** recommends *Schuldner- und Insolvenzberatung* (debt counselling) at Kolping Bildungswerk Schweinfurt, with phone number and address, read out loud.

- **Understands everyday speech** in German and English.
- **Asks only when needed:** at most 2 short follow-up questions, then a recommendation.
- **Answers follow-ups** such as "Do they judge me there?" or "Is it free?".
- **Crisis first:** suicide or violence → emergency numbers (112, TelefonSeelsorge) before anything else.
- **Never invents contacts:** addresses and phone numbers always come from the database, not from the AI.
- **Covers all 9 districts**, including villages and other spellings.

## How it works

```
Speech (browser) → crisis check → AI picks 1 of 32 services, or asks a question
                 → code looks up the office in the user's district → answer + voice
```

| Part | Technology |
|---|---|
| AI | **gpt-oss-120b** on Groq (free tier). Backups: a second Groq key, then **Qwen 2.5 7B** locally via Ollama. No training or fine-tuning. |
| Speech to text | The browser's built-in speech recognition (best in Chrome) |
| Voice | Microsoft neural voices via `edge-tts` (Seraphina / Ava), with local **Piper** voices (Kerstin / Jenny) as an instant offline backup |
| Backend | Python standard library (`server.py`) |
| Frontend | React + Vite (`frontend/`) |

## The data

Caritas has no API, so we scraped all 49 "Hilfe & Beratung" pages of [caritas-wuerzburg.de](https://www.caritas-wuerzburg.de/hilfe-beratung/) and cleaned them:

- **33 services and 115 offices**, mapped to the 9 districts, each with address, phone, email and website.
- **16 pages removed** (overviews, internal staff pages). Missing values were filled only from real sources, and every filled value is listed in `filled_fields`.
- **32 plain-language service cards** and **follow-up questions** (based on the Caritas dataset) tell the AI how people actually describe their problems.

## Run it

You need Python 3.12, Node.js and a free [Groq API key](https://console.groq.com/keys).

**1. Setup (first time only):**

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m piper.download_voices --download-dir voices de_DE-kerstin-low en_GB-jenny_dioco-medium
cd frontend && npm install && cd ..
cp .env.example .env
```

Then open `.env` and paste your Groq key after `LLM_API_KEY=`.

**2. Start the backend** (terminal 1):

```bash
.venv/bin/python server.py
```

**3. Start the frontend** (terminal 2):

```bash
cd frontend && npm run dev
```

**4. Open http://localhost:5173 in Chrome.**

To check that the backend is up, open http://127.0.0.1:8000/api/health.

## Project structure

```
frontend/          Website (React): microphone, chat, service cards
server.py          API for the website: /api/search, /api/tts
wegweiser/         The assistant
  router.py          Questions, service choice, office lookup
  llm.py             AI connection with backup providers
  safety.py          Crisis detection
data/
  processed/         Clean offices and services (what the app uses)
  routing/           Service cards and follow-up questions for the AI
  raw/               Scraped pages and the Caritas dataset
scripts/           Scraper and data cleaning
tests/             20 test situations: python -m tests.eval_routing
docs/              Pitch deck, test questions, follow-up questions
```

## Results

| | |
|---|---|
| Correct service (20 test cases, best run) | **95%** |
| AI answer time | **~0.4 s** |
| Time until the voice starts | **< 1 s** |
| Invented phone numbers | **0** |

## Team

Five people: 2 on the frontend, 2 on the backend and AI, 1 on voice and the pitch. One shared GitHub repo with feature branches.

---

*Hackathon prototype, not an official Caritas service. In an emergency, call **112**. TelefonSeelsorge (free, 24/7): **0800 111 0 111**.*
