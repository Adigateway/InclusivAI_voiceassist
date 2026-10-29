"""Text chat with the routing engine (voice comes later):  python cli.py"""
from wegweiser.router import Assistant
from wegweiser import llm

print(f"Caritas Wegweiser  [model: {llm.MODEL} @ {llm.BASE_URL}]  (Ctrl+C to quit)\n")
bot = Assistant()
while True:
    try:
        text = input("Sie: ").strip()
    except (KeyboardInterrupt, EOFError):
        break
    if text:
        reply = bot.handle(text)
        print(f"\nWegweiser [{reply.kind}{' → ' + ', '.join(reply.service_ids) if reply.service_ids else ''}]:\n{reply.text}\n")
