
import os
import re
import tempfile
import asyncio
import edge_tts

import streamlit as st
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

from wegweiser.router import Assistant


# Languages the assistant supports, with a natural-sounding voice for each
VOICES = {
    "de": "de-DE-KatjaNeural",
    "en": "en-US-AriaNeural",
    "uk": "uk-UA-PolinaNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "tr": "tr-TR-EmelNeural",
    "ar": "ar-SA-ZariyahNeural",
}
LANGUAGE_NAMES = {
    "auto": "Automatisch erkennen / Detect automatically",
    "de": "Deutsch", "en": "English", "uk": "Українська", "ru": "Русский", "tr": "Türkçe", "ar": "العربية",
}


def detect_language(model, audio):
    """Whisper's guess, limited to the languages we support and biased towards German.

    Short or accented German is sometimes detected as English, and Whisper then writes an English
    translation instead of a German transcript. German wins unless another language is clearly ahead.
    """
    _, _, probabilities = model.detect_language(audio)
    scores = {code: p for code, p in probabilities if code in VOICES}
    best = max(scores, key=scores.get)
    if best != "de" and scores.get("de", 0) > 0.15 and scores[best] - scores["de"] < 0.4:
        return "de"
    return best


async def generate_speech(text, language):
    voice = VOICES.get(language, VOICES["en"])

    with tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=False,
    ) as audio_file:
        audio_path = audio_file.name

    try:
        communicator = edge_tts.Communicate(text, voice)
        await communicator.save(audio_path)

        with open(audio_path, "rb") as file:
            return file.read()
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def speakable(reply):
    """What to read aloud: the answer without e-mails and web addresses, which sound terrible in TTS."""
    if reply.kind != "recommend":
        return reply.text
    lines = [line for line in reply.text.split("\n") if not line.startswith(("•", "  "))]
    for office in reply.offices[:1]:
        lines.append(f"{office['organisation']}, {office['city']}. Tel. {office['phone']}.")
    return re.sub(r"https?://\S+", "", "\n".join(lines))


st.set_page_config(
    page_title="Caritas Voice Assistant",
    page_icon="🎙️",
)

st.title("🎙️ Caritas AI Voice Assistant")
st.write("Sprechen Sie einfach – auf Deutsch, Englisch, Ukrainisch, Russisch, Türkisch oder Arabisch. Speak in your language to find the right Caritas service.")


@st.cache_resource
def load_whisper():
    return WhisperModel(
        "small",
        device="cpu",
        compute_type="int8",
    )


try:
    with st.spinner("Loading AI models..."):
        whisper_model = load_whisper()
except Exception as error:
    st.error(f"Could not load the AI models: {error}")
    st.stop()

# One routing engine per browser session, so follow-up questions ("Where do you live?") keep their context
if "assistant" not in st.session_state:
    st.session_state.assistant = Assistant()
    st.session_state.history = []

for role, text, offices in st.session_state.history:
    with st.chat_message(role):
        st.write(text)
        for office in offices:
            st.markdown(
                f"**{office['organisation']}**  \n"
                f"{office['street']}, {office['plz']} {office['city']}  \n"
                f"Tel. {office['phone']} · {office['email']}  \n"
                f"[Website]({office['website'].split(';')[0].strip()})"
            )

st.subheader("Ask your question")

language_choice = st.selectbox(
    "Sprache / Language",
    list(LANGUAGE_NAMES),
    format_func=LANGUAGE_NAMES.get,
)

audio = st.audio_input(
    "Click the microphone and speak",
    sample_rate=16000,
)

if audio is not None:
    if st.button("Get Caritas answer", type="primary"):
        temporary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                delete=False,
            ) as temporary_file:
                temporary_file.write(audio.getvalue())
                temporary_path = temporary_file.name

            with st.spinner("Understanding your speech..."):
                samples = decode_audio(temporary_path)
                language = (
                    detect_language(whisper_model, samples)
                    if language_choice == "auto"
                    else language_choice
                )
                # Passing the language stops Whisper from translating German speech into English
                segments, info = whisper_model.transcribe(
                    samples,
                    language=language,
                    beam_size=5,
                )
                transcript = " ".join(
                    segment.text.strip() for segment in segments
                ).strip()

            if not transcript:
                st.warning("I couldn't recognize your speech. Please try again.")
                st.stop()

            with st.spinner("Finding the right Caritas service..."):
                reply = st.session_state.assistant.handle(transcript, lang=language)

            st.session_state.history.append(("user", transcript, []))
            text = reply.text
            if reply.kind == "recommend":       # offices are shown as cards below the text
                text = "\n".join(l for l in reply.text.split("\n") if not l.startswith(("•", "  ")))
            st.session_state.history.append(("assistant", text, reply.offices))

            with st.spinner("Speaking the answer..."):
                st.session_state.audio_reply = asyncio.run(
                    generate_speech(speakable(reply), language)
                )
            st.rerun()

        except Exception as error:
            st.error(f"Something went wrong: {error}")

        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

if "audio_reply" in st.session_state:
    st.audio(
        st.session_state.pop("audio_reply"),
        format="audio/mp3",
        autoplay=True,
    )

if st.button("New conversation"):
    for key in ("assistant", "history"):
        st.session_state.pop(key, None)
    st.rerun()

st.divider()
st.caption("Prototype, not an official Caritas service. In an emergency call 112 · TelefonSeelsorge 0800 111 0 111")
