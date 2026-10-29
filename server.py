"""API server for the CaritAssist frontend (standard library only):  python server.py  ->  http://127.0.0.1:8000

POST /api/search  {"message": "...", "language": "de|en", "session": "<id>"}
  -> {"kind": "ask|recommend|crisis", "reply": "<text to show and read aloud>", "follow_up": "",
      "region": "...", "results": [{"title", "category", "description", "match_reason", "url", "offices": [...]}]}
POST /api/reset   {"session": "<id>"}
      plus "tts_url": the spoken answer, already being generated while the text is sent (GET it to stream)
GET  /api/tts/<id>  -> audio/mpeg, streamed: playback can start before the whole answer is synthesized
POST /api/tts     {"text": "...", "language": "de|en"}  -> audio/mpeg (for the "Listen" button on older messages)
"""
import asyncio, io, json, os, re, threading, time, uuid, wave
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import edge_tts

from wegweiser.router import Assistant, CARD, find_offices
from wegweiser import llm

PORT = int(os.environ.get("PORT", 8000))
SERVICES = {s["service_id"]: s for s in json.load(open(Path(__file__).resolve().parent / "data/processed/services.json", encoding="utf8"))}
sessions = {}                      # session id -> Assistant (in memory; fine for a prototype)
# Natural-sounding neural voices; change in .env (TTS_VOICE_DE / TTS_VOICE_EN), list: edge-tts --list-voices
VOICES = {"de": os.environ.get("TTS_VOICE_DE", "de-DE-SeraphinaMultilingualNeural"),
          "en": os.environ.get("TTS_VOICE_EN", "en-US-AvaMultilingualNeural")}
TTS_RATE = os.environ.get("TTS_RATE", "-5%")          # a touch slower than default sounds calmer
TTS_DEADLINE = float(os.environ.get("TTS_DEADLINE", 1.5))   # seconds to wait for the online voice before going local
ONLINE_PAUSE = 60                  # after the online voice was too slow, use the local one directly for this long
_skip_online_until = 0.0
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
    label = {"de": "Anlaufstelle:", "en": "Where to go:"}.get(reply.lang, "→")
    lines, offices, named = [], iter(reply.offices), False
    for line in reply.text.split("\n"):
        if line.startswith("•"):                    # office bullet: name the first office per service, briefly
            office = next(offices, None)
            if office and not named:
                where = f"{office['organisation']}, {office['city']}."
                if lines and lines[-1].endswith(":"):
                    lines[-1] += " " + where
                else:
                    lines.append(f"{label} {where}")
                named = True
        elif not line.startswith("  "):
            named = named and not line.startswith(("Ich empfehle", "I recommend"))
            lines.append(line)
    return "\n".join(lines)


def speech_text(text):
    """Text as it should be spoken: no web or e-mail addresses, no bullet symbols."""
    text = re.sub(r"https?://\S+|www\.\S+|\S+@\S+", "", text)
    text = text.replace("•", "").replace("·", "").replace("–", ",").replace("—", ",").replace("Tel.", "Telefon")
    return re.sub(r"[ \t]+", " ", text).strip()


class TtsJob:
    """Speaks one answer. Tries the natural online voice (Seraphina/Ava); if it hasn't produced audio within
    TTS_DEADLINE seconds or fails, the local Piper voice (Kerstin/Jenny) is used instead, which takes ~0.3 s.
    Synthesis runs in a background thread and readers get the audio chunks as soon as they arrive."""

    def __init__(self, text, language):
        self.chunks, self.done, self.error, self.engine = [], False, None, None
        self.mime = "audio/mpeg"
        self.created = time.time()
        self.cond = threading.Condition()
        threading.Thread(target=self._run, args=(text, language), daemon=True).start()

    def _add(self, data):
        with self.cond:
            self.chunks.append(data)
            self.cond.notify_all()

    async def _online(self, text, voice):
        stream = edge_tts.Communicate(text, voice, rate=TTS_RATE).stream().__aiter__()
        deadline = time.time() + TTS_DEADLINE
        while True:                                  # until the first audio chunk, but no longer than the deadline
            chunk = await asyncio.wait_for(stream.__anext__(), max(0.05, deadline - time.time()))
            if chunk["type"] == "audio":
                self.engine = "online"
                self._add(chunk["data"])
                break
        async for chunk in stream:
            if chunk["type"] == "audio":
                self._add(chunk["data"])

    def _run(self, text, language):
        global _skip_online_until
        voice = VOICES.get(language, VOICES["de"])
        try:
            if time.time() < _skip_online_until and language_has_local_voice(language):
                raise TimeoutError("online voice was slow a moment ago")
            asyncio.run(self._online(text, voice))
        except Exception as e:                       # too slow (TimeoutError), service error, no internet
            self.error = e
            if not self.chunks and language_has_local_voice(language):
                if "a moment ago" not in str(e):     # it just failed: don't wait for it again for a while
                    _skip_online_until = time.time() + ONLINE_PAUSE
                self.engine, self.mime = "local", "audio/wav"
                self._add(local_wav(text, language))
        finally:
            with self.cond:
                self.done = True
                self.cond.notify_all()

    def wait_for_start(self, timeout=20):
        with self.cond:
            self.cond.wait_for(lambda: self.chunks or self.done, timeout)
            return bool(self.chunks)

    def stream(self):
        i = 0
        while True:
            with self.cond:
                self.cond.wait_for(lambda: i < len(self.chunks) or self.done, timeout=30)
                if i >= len(self.chunks):
                    return
                chunk = self.chunks[i]
            i += 1
            yield chunk


# Local Piper voices: instant and offline. Models in voices/ (see README for the download command)
VOICE_DIR = Path(__file__).resolve().parent / "voices"
LOCAL_VOICES = {"de": os.environ.get("LOCAL_VOICE_DE", "de_DE-kerstin-low"),
                "en": os.environ.get("LOCAL_VOICE_EN", "en_GB-jenny_dioco-medium")}
_local_voices, _local_lock = {}, threading.Lock()


def language_has_local_voice(language):
    return (VOICE_DIR / f"{LOCAL_VOICES.get(language, LOCAL_VOICES['de'])}.onnx").exists()


def local_wav(text, language):
    from piper import PiperVoice                     # imported lazily: optional dependency
    name = LOCAL_VOICES.get(language, LOCAL_VOICES["de"])
    with _local_lock:                                # one synthesis at a time; each takes well under a second
        if name not in _local_voices:
            _local_voices[name] = PiperVoice.load(str(VOICE_DIR / f"{name}.onnx"))
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            for i, chunk in enumerate(_local_voices[name].synthesize(text)):
                if i == 0:
                    wav.setframerate(chunk.sample_rate)
                    wav.setsampwidth(chunk.sample_width)
                    wav.setnchannels(chunk.sample_channels)
                wav.writeframes(chunk.audio_int16_bytes)
    return buffer.getvalue()


tts_jobs = {}                      # id -> TtsJob, kept a few minutes
_last_warm_up = 0.0


def start_tts(text, language):
    for job_id in [k for k, job in tts_jobs.items() if time.time() - job.created > 600]:
        tts_jobs.pop(job_id, None)
    job_id = uuid.uuid4().hex
    tts_jobs[job_id] = TtsJob(speech_text(text)[:1500], language if language in VOICES else "de")
    return job_id


def warm_up_tts():
    """The first request after a pause can take seconds to reach the voice service. Opening a connection
    while the LLM is still thinking means the real answer starts speaking without that delay."""
    global _last_warm_up
    if time.time() - _last_warm_up > 30:
        _last_warm_up = time.time()
        TtsJob("Hallo.", "de")


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
        if self.path.startswith("/api/tts/"):
            job = tts_jobs.get(self.path.rsplit("/", 1)[-1])
            if not job:
                return self._send(404, {"error": "unknown audio id"})
            if not job.wait_for_start():
                return self._send(502, {"error": f"TTS failed: {job.error}"})
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", job.mime)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()                       # no length: the browser plays while chunks keep coming
            self.close_connection = True
            try:
                for chunk in job.stream():
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass                                 # user pressed the mic; the browser stopped listening
            return
        if self.path == "/api/health":
            return self._send(200, {"ok": True, "model": llm.MODEL, "providers": [p["name"] for p in llm.PROVIDERS]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid JSON"})
        sid = str(req.get("session", ""))[:64] or "default"

        if self.path == "/api/tts":                  # "Listen" button on an older message
            text = speech_text(str(req.get("text", "")))[:1500]
            if not text:
                return self._send(400, {"error": "empty text"})
            job = TtsJob(text, req.get("language") if req.get("language") in VOICES else "de")
            if not job.wait_for_start():
                return self._send(502, {"error": f"TTS failed: {job.error}"})
            audio = b"".join(job.stream())
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", job.mime)
            self.send_header("Content-Length", str(len(audio)))
            self.end_headers()
            self.wfile.write(audio)
            return

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
        warm_up_tts()
        try:
            reply = bot.handle(message, lang=language)
        except Exception as e:                       # every LLM provider failed
            return self._send(502, {"error": f"LLM request failed: {e}"})
        text = spoken_reply(reply)
        self._send(200, {
            "kind": reply.kind,
            "reply": text,
            "tts_url": f"/api/tts/{start_tts(text, reply.lang if reply.lang in VOICES else language or 'de')}",
            "follow_up": "",
            "region": reply.region,
            "results": [service_result(s, reply) for s in reply.service_ids] if reply.kind == "recommend" else [],
        })

    def log_message(self, fmt, *args):            # keep the console quiet except for errors
        if args and str(args[1]).startswith(("4", "5")):
            super().log_message(fmt, *args)


if __name__ == "__main__":
    print(f"CaritAssist API on http://127.0.0.1:{PORT}  [providers: {', '.join(p['name'] for p in llm.PROVIDERS)}]")
    warm_up_tts()
    if language_has_local_voice("de"):              # load the local voices now, so the first fallback is instant
        threading.Thread(target=lambda: [local_wav("Hallo.", lang) for lang in ("de", "en")], daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
