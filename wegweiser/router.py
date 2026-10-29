"""The routing engine: user text -> follow-up question or recommended Caritas offices.

1. Crisis check (rules, always first)
2. LLM picks the service type from service_cards.json and answers in JSON; code drops any id not in the catalogue
3. Code finds the region and looks up the offices in offices.json (no LLM, no invented contacts)
"""
import json, re
from dataclasses import dataclass, field
from pathlib import Path

from . import llm
from .safety import is_crisis, EMERGENCY

ROOT = Path(__file__).resolve().parent.parent
CARDS = json.load(open(ROOT / "data/routing/service_cards.json", encoding="utf8"))
OFFICES = json.load(open(ROOT / "data/processed/offices.json", encoding="utf8"))
CARD = {c["id"]: c for c in CARDS}
QUESTIONS = json.load(open(ROOT / "data/routing/clarifying_questions.json", encoding="utf8"))
MAX_QUESTIONS = 2                 # clarifying questions per conversation (the town question is extra)
FALLBACK = "allgemeine-sozialberatung"

REGIONS = sorted({o["region"] for o in OFFICES})
# Towns people may name -> region (office towns plus the district towns)
TOWNS = {o["city"].split("/")[0].split(" (")[0].strip(): o["region"] for o in OFFICES}
TOWNS.update({"Lohr": "Main-Spessart", "Karlstadt": "Main-Spessart", "Gemünden": "Main-Spessart",
              "Marktheidenfeld": "Main-Spessart", "Hammelburg": "Bad Kissingen", "Bad Brückenau": "Bad Kissingen",
              "Mellrichstadt": "Rhön-Grabfeld", "Bad Königshofen": "Rhön-Grabfeld", "Bad Neustadt": "Rhön-Grabfeld",
              "Ebern": "Haßberge", "Hassfurt": "Haßberge", "Haßfurt": "Haßberge", "Volkach": "Kitzingen",
              "Dettelbach": "Kitzingen", "Ochsenfurt": "Würzburg (Stadt/Land)", "Veitshöchheim": "Würzburg (Stadt/Land)",
              "Wurzburg": "Würzburg (Stadt/Land)", "Wuerzburg": "Würzburg (Stadt/Land)", "Gerolzhofen": "Schweinfurt (Stadt/Land)",
              "Alzenau": "Aschaffenburg (Stadt/Land)", "Obernburg": "Miltenberg", "Erlenbach": "Miltenberg",
              "Amorbach": "Miltenberg", "Elsenfeld": "Miltenberg"})
TOWNS.update({r.split(" (")[0]: r for r in REGIONS})

SYSTEM = """You are the Caritas Wegweiser, a friendly guide for people in Lower Franconia (Unterfranken, Germany) who need help.
Your only job: understand the person's situation and pick the right Caritas service from the list below.

SERVICES:
{services}

RULES:
- Answer with ONLY a JSON object, no other text:
  {{"action": "ask" or "recommend", "service_ids": ["<service id from the list>"], "question": "...", "reason": "...", "language": "<ISO code>"}}
- If the situation is clear, use action "recommend" with 1 service (2 only if there are clearly two separate problems).
- Only ask a question when you really cannot choose: the problem is unclear, or two services fit equally well.
  Ask ONE short, kind question. Never ask about something the person already told you.
  Prefer these questions (translate them into the person's language):
{questions}
- Never ask for the town or postcode; the system does that itself. Never ask for names or other personal details.
- If the person earlier said something that sounded like a crisis, take that into account (e.g. krisenhilfe-telefonseelsorge
  or sozialpsychiatrische-dienste) and answer their follow-up question kindly.
- Write `question` and `reason` in the same language the person uses. Keep them short and simple.
- `reason` explains in one sentence why this service fits what the person said.
- Pick the service that matches the CORE problem, not side details (drinking -> addiction, not money).
- For children and teenagers under 18 with drugs or alcohol, use "jugend-suchtberatung".
- Always prefer a SPECIFIC service when one matches (prison release -> straffaelligenhilfe, rejected asylum and
  thinking of going home -> rueckkehrberatung, nowhere to sleep -> wohnsitzlosigkeit).
  Use "allgemeine-sozialberatung" only when no specific service matches."""


def _questions_prompt():
    return "\n".join(f'  * {q["id"]} – when: {q["when"]} → "{q["en"]}"' for q in QUESTIONS if q["id"] != "Q001")


def _services_prompt():
    return "\n".join(f'- {c["id"]} ({c["name"]}): {c["helps_with"]} People say: ' + "; ".join(f'"{x}"' for x in c["says"][:2])
                     for c in CARDS)


@dataclass
class Reply:
    kind: str                     # "crisis" | "ask" | "recommend"
    text: str
    service_ids: list = field(default_factory=list)
    offices: list = field(default_factory=list)
    region: str = ""


EN_WORDS = re.compile(r"\b(i|my|me|the|and|is|need|help|can't|don't|have|live|what|please)\b", re.I)
DE_WORDS = re.compile(r"\b(ich|mein|meine|und|nicht|ist|habe|wohne|bitte|kann|keine|der|die|das)\b", re.I)


def guess_language(text, llm_guess):
    """Small models often misreport the language; trust word counts for de/en, the model for anything else."""
    en, de = len(EN_WORDS.findall(text)), len(DE_WORDS.findall(text))
    if en or de:
        return "en" if en > de else "de"
    return (llm_guess or "de")[:2].lower()


def find_region(text):
    for town, region in sorted(TOWNS.items(), key=lambda t: -len(t[0])):
        if re.search(rf"\b{re.escape(town)}\b", text, re.I):
            return region
    return ""


def region_from_llm(text):
    """For towns the list doesn't know: villages, other spellings, other alphabets ("Швайнфурт")."""
    try:
        out = llm.json_reply(llm.chat([{"role": "user", "content":
            f"Which of these districts in Lower Franconia is the place mentioned in the text in? Districts: {REGIONS}. "
            f'Text: "{text}". Reply with JSON {{"region": "<exact district from the list or unknown>"}}'}], json_mode=True))
        return out.get("region") if out and out.get("region") in REGIONS else ""
    except Exception:
        return ""


def lookup(service_id, region):
    ids = CARD[service_id]["office_ids"]
    local = [o for o in OFFICES if o["service_id"] in ids and o["region"] == region]
    # Prefer offices with a real address over "see provider website" rows
    return sorted(local, key=lambda o: o["street"].startswith("siehe"))


# A related service that can step in locally when the specific one has no office in the region
RELATED = {"jugend-suchtberatung": "suchtberatung", "essstoerungen": "suchtberatung",
           "jugendwohnen": "jugendsozialarbeit", "junge-eltern-und-beruf": "jugendsozialarbeit",
           "jugendhilfe": "erziehungshilfe", "familienpflege": "erziehungshilfe"}


def find_offices(service_id, region):
    """-> (offices, how): local, related service locally, diocese-wide office, or general social counselling."""
    if offices := lookup(service_id, region):
        return offices, "local"
    if (rel := RELATED.get(service_id)) and (offices := lookup(rel, region)):
        return offices, "related"
    everywhere = [o for o in OFFICES if o["service_id"] in CARD[service_id]["office_ids"]]
    if len({o["region"] for o in everywhere}) == 1:          # one central office serving all of Unterfranken
        return everywhere, "central"
    return lookup(FALLBACK, region), "fallback"


TEXT = {
    "de": {"region_q": "Damit ich Ihnen die richtige Stelle in Ihrer Nähe nennen kann: In welcher Stadt oder welchem Landkreis wohnen Sie?",
           "intro": "Ich empfehle Ihnen: {name}.", "why": "Warum: {reason}",
           "related": "In {region} übernimmt das diese Stelle:",
           "central": "Diese Stelle ist für ganz Unterfranken zuständig:",
           "fallback": "In {region} gibt es dafür keine eigene Stelle. Die Allgemeine Sozialberatung vor Ort hilft Ihnen weiter und vermittelt Sie:",
           "free": "Die Beratung ist kostenlos und vertraulich."},
    "en": {"region_q": "So I can find the right office near you: which town or district do you live in?",
           "intro": "I recommend: {name}.", "why": "Why: {reason}",
           "related": "In {region} this office covers it:",
           "central": "This office serves all of Lower Franconia:",
           "fallback": "There is no dedicated office for this in {region}. The local general social counselling service can help and refer you:",
           "free": "Counselling is free and confidential."},
}


def texts(lang):
    """Fixed reply phrases in the user's language. German and English are written by hand; other languages are
    translated once by the LLM and cached (contact details are never translated, only these phrases)."""
    if lang not in TEXT:
        try:
            src = dict(TEXT["en"], emergency=EMERGENCY["en"])
            out = llm.json_reply(llm.chat([{"role": "user", "content":
                f"Translate the values of this JSON into the language with ISO code '{lang}'. Keep the keys and the "
                f"{{placeholders}} and phone numbers unchanged. Reply with JSON only.\n{json.dumps(src)}"}], json_mode=True))
            TEXT[lang] = {k: out.get(k, v) for k, v in src.items()} if out else TEXT["en"]
        except Exception:
            return TEXT["en"]
    return TEXT[lang]


def needs_region(service_ids):
    """False when every chosen service has only one central office for all of Unterfranken."""
    return any(len({o["region"] for o in OFFICES if o["service_id"] in CARD[s]["office_ids"]}) > 1 for s in service_ids)


def format_office(o):
    addr = f"{o['street']}, {o['plz']} {o['city']}" if not o["street"].startswith("siehe") else o["city"]
    return f"• {o['organisation']}\n  {addr}\n  Tel. {o['phone']} · {o['email']}\n  {o['website']}"


class Assistant:
    def __init__(self):
        self.messages = [{"role": "system", "content": SYSTEM.format(services=_services_prompt(), questions=_questions_prompt())}]
        self.region = ""
        self.pending = None           # decision waiting for the region
        self.lang = "de"
        self.questions_asked = 0

    def handle(self, user_text, lang=None):
        """lang: language detected from speech (e.g. Whisper); more reliable than guessing from the text."""
        self.region = find_region(user_text) or self.region
        if is_crisis(user_text):
            self.lang = lang or guess_language(user_text, self.lang)
            text = EMERGENCY.get(self.lang) or texts(self.lang).get("emergency") or EMERGENCY["en"]
            # keep the crisis in the conversation, so a follow-up like "what help do I need?" is understood
            self.messages += [{"role": "user", "content": user_text}, {"role": "assistant", "content": text}]
            return Reply("crisis", text)

        if self.pending and not self.region:       # we asked for the town; the list didn't recognise the answer
            self.region = region_from_llm(user_text)
        if self.pending and self.region:          # user just told us where they live
            decision, self.pending = self.pending, None
            return self._recommend(decision)

        self.messages.append({"role": "user", "content": user_text})
        enough = self.questions_asked >= MAX_QUESTIONS
        extra = [{"role": "system", "content": "You have asked enough questions. Recommend the best fitting service now."}] if enough else []
        decision = llm.json_reply(llm.chat(self.messages + extra, json_mode=True)) or {}
        self.lang = lang or guess_language(user_text, decision.get("language"))
        t = texts(self.lang)

        ids = [i for i in decision.get("service_ids") or [] if i in CARD][:2]   # never trust the model blindly
        wants_to_ask = decision.get("action") == "ask" and decision.get("question") and not enough
        if wants_to_ask:
            self.questions_asked += 1
            self.messages.append({"role": "assistant", "content": decision["question"]})
            return Reply("ask", decision["question"])
        if not ids:
            ids = [FALLBACK]

        decision["service_ids"] = ids
        if not self.region and needs_region(ids):
            self.pending = decision
            self.messages.append({"role": "assistant", "content": t["region_q"]})
            return Reply("ask", t["region_q"], service_ids=ids)
        return self._recommend(decision)

    def _recommend(self, decision):
        t = texts(self.lang)
        parts, all_offices = [], []
        for sid in decision["service_ids"]:
            offices, how = find_offices(sid, self.region)
            parts.append(t["intro"].format(name=CARD[sid]["name"]))
            if decision.get("reason") and sid == decision["service_ids"][0]:
                parts.append(t["why"].format(reason=decision["reason"]))
            if how != "local":
                parts.append(t[how].format(region=self.region))
            parts += [format_office(o) for o in offices[:2]]
            all_offices += offices[:2]
        parts.append(t["free"])
        text = "\n".join(parts)
        self.messages.append({"role": "assistant", "content": text})
        return Reply("recommend", text, decision["service_ids"], all_offices, self.region)
