"""Tiny web server for the chat UI (standard library only):  python server.py  ->  http://localhost:8000

POST /api/chat  {"session": "<id>", "message": "<text>"}
  -> {"kind": "ask|recommend|crisis", "text": "...", "services": [...], "offices": [...], "region": "..."}
POST /api/reset {"session": "<id>"}
"""
import json, os
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from wegweiser.router import Assistant, CARD
from wegweiser import llm

WEB = Path(__file__).resolve().parent / "web"
PORT = int(os.environ.get("PORT", 8000))
sessions = {}                      # session id -> Assistant (in memory; fine for a prototype)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        name = "index.html" if self.path in ("/", "/index.html") else None
        if not name:
            return self._send(404, {"error": "not found"})
        self._send(200, (WEB / name).read_bytes(), "text/html")

    def do_POST(self):
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid JSON"})
        sid = str(req.get("session", ""))[:64] or "default"

        if self.path == "/api/reset":
            sessions.pop(sid, None)
            return self._send(200, {"ok": True})
        if self.path != "/api/chat":
            return self._send(404, {"error": "not found"})

        message = str(req.get("message", "")).strip()[:2000]
        if not message:
            return self._send(400, {"error": "empty message"})
        bot = sessions.setdefault(sid, Assistant())
        try:
            reply = bot.handle(message)
        except Exception as e:                       # LLM down, rate limit exhausted, ...
            return self._send(502, {"error": f"LLM request failed: {e}"})
        self._send(200, {
            "kind": reply.kind, "text": reply.text, "region": reply.region,
            "services": [{"id": s, "name": CARD[s]["name"]} for s in reply.service_ids],
            "offices": [{k: o[k] for k in ("service", "organisation", "street", "plz", "city", "phone", "email", "website")}
                        for o in reply.offices],
        })

    def log_message(self, fmt, *args):            # keep the console quiet except for errors
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    print(f"Caritas Wegweiser on http://localhost:{PORT}  [model: {llm.MODEL}]")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
