"""Exam for the router: how often does the LLM pick the expected service?   python -m tests.eval_routing"""
import json, time
from pathlib import Path
from app import llm
from app.router import Assistant

cases = json.load(open(Path(__file__).parent / "routing_cases.json", encoding="utf8"))
hits, start = 0, time.time()
for c in cases:
    reply = Assistant().handle(c["text"] + " Ich wohne in Würzburg.")
    ok = bool(set(reply.service_ids) & set(c["expect"]))
    hits += ok
    print(f"{'✓' if ok else '✗'} {reply.kind:9} {','.join(reply.service_ids) or '-':40} expected {c['expect'][0]:28} | {c['text'][:55]}")
print(f"\n{hits}/{len(cases)} correct ({hits / len(cases):.0%})  model={llm.MODEL}  {time.time() - start:.0f}s")
