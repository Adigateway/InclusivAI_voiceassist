"""Minimal client for any OpenAI-compatible chat API (Ollama, Groq, OpenRouter, Gemini, ...).

Configure with environment variables or a .env file in the project root:
  LLM_BASE_URL  default http://localhost:11434/v1   (Ollama)   e.g. https://api.groq.com/openai/v1
  LLM_MODEL     default qwen2.5:3b                             e.g. openai/gpt-oss-120b (Groq)
  LLM_API_KEY   not needed for Ollama

Backups, tried in order when the one before fails (out of tokens, key invalid, service down):
  LLM_BACKUP_BASE_URL / LLM_BACKUP_MODEL / LLM_BACKUP_API_KEY   e.g. a second Groq key or another provider
  LLM_LOCAL_FALLBACK  local Ollama model used last, e.g. qwen2.5:7b (empty = off)
"""
import json, os, time, urllib.error, urllib.request
from pathlib import Path

# Optional .env file in the project root (gitignored) so API keys never go into the code
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "qwen2.5:3b")
API_KEY = os.environ.get("LLM_API_KEY", "ollama")

PROVIDERS = [{"name": "primary", "base_url": BASE_URL, "model": MODEL, "key": API_KEY}]
if os.environ.get("LLM_BACKUP_API_KEY") or os.environ.get("LLM_BACKUP_BASE_URL"):
    PROVIDERS.append({"name": "backup", "base_url": os.environ.get("LLM_BACKUP_BASE_URL", BASE_URL).rstrip("/"),
                      "model": os.environ.get("LLM_BACKUP_MODEL", MODEL), "key": os.environ.get("LLM_BACKUP_API_KEY", "")})
if os.environ.get("LLM_LOCAL_FALLBACK") and "localhost" not in BASE_URL:
    PROVIDERS.append({"name": "local", "base_url": "http://localhost:11434/v1",
                      "model": os.environ["LLM_LOCAL_FALLBACK"], "key": "ollama"})
last_provider = None            # which provider answered the last request (shown in the UI / logs)


def _call(provider, body, timeout):
    req = urllib.request.Request(f"{provider['base_url']}/chat/completions",
                                 data=json.dumps(dict(body, model=provider["model"])).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {provider['key']}",
                                          # Groq's firewall rejects Python's default user agent (error 1010)
                                          "User-Agent": "inclusivai-voiceassist/0.1"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            wait = float(e.headers.get("retry-after") or 2 ** attempt)
            # a short rate-limit pause is worth waiting for; a long one (daily quota used up) means: switch provider
            if e.code != 429 or attempt == 2 or wait > 20:
                raise
            time.sleep(wait)


def chat(messages, json_mode=False, temperature=0.1, timeout=60):
    global last_provider
    body = {"messages": messages, "temperature": temperature}
    if json_mode:                       # supported by Ollama, Groq, OpenRouter, Gemini; works with small models
        body["response_format"] = {"type": "json_object"}
    errors = []
    for provider in PROVIDERS:
        try:
            message = _call(provider, body, timeout)
            last_provider = f"{provider['name']} ({provider['model']})"
            return message
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as e:
            errors.append(f"{provider['name']}: {getattr(e, 'code', '')} {e}")
    raise RuntimeError("All LLM providers failed – " + "; ".join(errors))


def json_reply(message):
    """The JSON object in the reply (tolerates extra text around it)."""
    text = (message.get("content") or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            return data.get("arguments", data.get("parameters", data))
        except json.JSONDecodeError:
            pass
    return None
