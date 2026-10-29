"""Crisis detection. Runs on every user message before the LLM, so it works even if the model fails."""
import re

CRISIS = re.compile("|".join([
    # suicide / self-harm (de, en, uk, ru, tr, ar)
    r"umbringen", r"suizid", r"selbstmord", r"nicht mehr leben", r"will sterben", r"mir (et)?was antun", r"ritzen",
    r"kill myself", r"suicid", r"end my life", r"don'?t want to live", r"want to die", r"hurt myself",
    r"покінчити", r"не хочу жити", r"убить себя", r"не хочу жить", r"kendimi öldür", r"intihar", r"انتحار", r"أقتل نفسي",
    # acute violence / danger
    r"schlägt mich", r"bedroht mich", r"hits me", r"beats me", r"going to kill me", r"bringt mich um",
]), re.I)

EMERGENCY = {
    "de": ("Das klingt nach einer sehr schweren Situation, und ich möchte, dass Sie sofort Unterstützung bekommen.\n"
           "• Akute Gefahr: Notruf 112\n"
           "• TelefonSeelsorge, rund um die Uhr, kostenlos und anonym: 0800 111 0 111 oder 0800 111 0 222\n"
           "• Hilfetelefon Gewalt gegen Frauen: 116 016\n"
           "Sie sind nicht allein. Wenn Sie möchten, suche ich danach auch eine Beratungsstelle in Ihrer Nähe."),
    "en": ("That sounds really serious, and I want you to get support right now.\n"
           "• Immediate danger: call 112\n"
           "• TelefonSeelsorge (24/7, free, anonymous): 0800 111 0 111 or 0800 111 0 222\n"
           "• Violence against women helpline (many languages): 116 016\n"
           "You are not alone. If you like, I can also find a counselling service near you."),
}


def is_crisis(text):
    return bool(CRISIS.search(text))
