"""API server for the CaritAssist frontend (standard library only):  python server.py  ->  http://127.0.0.1:8000

POST /api/search  {"message": "...", "language": "de|en", "session": "<id>"}
  -> {"kind": "ask|recommend|crisis", "reply": "<text to show and read aloud>", "follow_up": "",
      "region": "...", "results": [{"title", "category", "description", "match_reason", "url", "offices": [...]}]}
POST /api/reset   {"session": "<id>"}
"""
import json, os, re
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from wegweiser.router import Assistant, CARD, find_offices
from wegweiser import llm

PORT = int(os.environ.get("PORT", 8000))
SERVICES = {s["service_id"]: s for s in json.load(open(Path(__file__).resolve().parent / "data/processed/services.json", encoding="utf8"))}
sessions = {}                      # session id -> Assistant (in memory; fine for a prototype)
OFFICE_FIELDS = ("organisation", "street", "plz", "city", "region", "phone", "email", "website")


def first_sentences(text, limit=300):
    """Whole sentences up to about `limit` characters, so a description never stops mid-word."""
    out = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        if out and len(out) + len(sentence) > limit:
            break
        out = f"{out} {sentence}".strip()
    return out


def service_result(service_id, reply):
    """One suggested service in the shape the frontend's ServiceCard expects."""
    card = CARD[service_id]
    page = SERVICES.get(card["office_ids"][0], {})
    offices = [o for o in reply.offices if o["service_id"] in card["office_ids"]] or find_offices(service_id, reply.region)[0]
    return {
        "id": service_id,
        "title": card["name"],
        "category": reply.region,
        # German page text for German users, the plain-language card for everyone else
        "description": first_sentences(page.get("description", "")) if reply.lang == "de" else card["helps_with"],
        "match_reason": reply.reason if service_id == reply.service_ids[0] else "",
        "url": page.get("url", ""),
        "offices": [{k: o[k] for k in OFFICE_FIELDS} for o in offices[:3]],
    }


def spoken_reply(reply):
    """The reply without the office list; the offices are shown as cards, so they aren't read out line by line."""
    if reply.kind != "recommend":
        return reply.text
    return "\n".join(l for l in reply.text.split("\n") if not l.startswith(("•", "  ")))


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _cors(self):
        # the Vite dev server runs on another port; local prototype, so any origin is fine
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            return self._send(200, {"ok": True, "model": llm.MODEL, "providers": [p["name"] for p in llm.PROVIDERS]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid JSON"})
        sid = str(req.get("session", ""))[:64] or "default"

        if self.path == "/api/reset":
            sessions.pop(sid, None)
            return self._send(200, {"ok": True})
        if self.path not in ("/api/search", "/api/chat"):
            return self._send(404, {"error": "not found"})

        message = str(req.get("message", "")).strip()[:2000]
        if not message:
            return self._send(400, {"error": "empty message"})
        language = req.get("language") if req.get("language") in ("de", "en") else None
        bot = sessions.setdefault(sid, Assistant())
        try:
            reply = bot.handle(message, lang=language)
        except Exception as e:                       # every LLM provider failed
            return self._send(502, {"error": f"LLM request failed: {e}"})
        self._send(200, {
            "kind": reply.kind,
            "reply": spoken_reply(reply),
            "follow_up": "",
            "region": reply.region,
            "results": [service_result(s, reply) for s in reply.service_ids] if reply.kind == "recommend" else [],
        })

    def log_message(self, fmt, *args):            # keep the console quiet except for errors
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    print(f"CaritAssist API on http://127.0.0.1:{PORT}  [providers: {', '.join(p['name'] for p in llm.PROVIDERS)}]")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
