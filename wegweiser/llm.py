"""Minimal client for any OpenAI-compatible chat API (Ollama, Groq, OpenRouter, Gemini, ...).

Configure with environment variables:
  LLM_BASE_URL  default http://localhost:11434/v1   (Ollama)   e.g. https://api.groq.com/openai/v1
  LLM_MODEL     default qwen2.5:3b                             e.g. openai/gpt-oss-120b (Groq)
  LLM_API_KEY   not needed for Ollama
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


def chat(messages, json_mode=False, temperature=0.1, timeout=120):
    body = {"model": MODEL, "messages": messages, "temperature": temperature}
    if json_mode:                       # supported by Ollama, Groq, OpenRouter, Gemini; works with small models
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}",
                                          # Groq's firewall rejects Python's default user agent (error 1010)
                                          "User-Agent": "inclusivai-voiceassist/0.1"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["choices"][0]["message"]
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:        # free tiers rate-limit: wait and retry
                raise
            time.sleep(float(e.headers.get("retry-after") or 2 ** attempt))


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
