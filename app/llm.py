"""Minimal client for any OpenAI-compatible chat API (Ollama, Groq, OpenRouter, Gemini, ...).

Configure with environment variables:
  LLM_BASE_URL  default http://localhost:11434/v1   (Ollama)   e.g. https://api.groq.com/openai/v1
  LLM_MODEL     default qwen2.5:3b                             e.g. llama-3.3-70b-versatile
  LLM_API_KEY   not needed for Ollama
"""
import json, os, urllib.request

BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "qwen2.5:3b")
API_KEY = os.environ.get("LLM_API_KEY", "ollama")


def chat(messages, json_mode=False, temperature=0.1, timeout=120):
    body = {"model": MODEL, "messages": messages, "temperature": temperature}
    if json_mode:                       # supported by Ollama, Groq, OpenRouter, Gemini; works with small models
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)["choices"][0]["message"]


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
