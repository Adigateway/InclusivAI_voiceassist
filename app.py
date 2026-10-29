
import os
import re
import tempfile
import asyncio
import edge_tts

import streamlit as st
from faster_whisper import WhisperModel

from wegweiser.router import Assistant


async def generate_speech(text, language):
    if language == "de":
        voice = "de-DE-KatjaNeural"
    else:
        voice = "en-US-AriaNeural"

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
        lines.append(f"{office['organisation']}, {office['city']}. Telefon {office['phone']}.")
    return re.sub(r"https?://\S+", "", "\n".join(lines))


st.set_page_config(
    page_title="Caritas Voice Assistant",
    page_icon="🎙️",
)

st.title("🎙️ Caritas AI Voice Assistant")
st.write("Speak in German or English to find Caritas services.")


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
                segments, info = whisper_model.transcribe(
                    temporary_path,
                    beam_size=5,
                )
                transcript = " ".join(
                    segment.text.strip() for segment in segments
                ).strip()

            if not transcript:
                st.warning("I couldn't recognize your speech. Please try again.")
                st.stop()

            with st.spinner("Finding the right Caritas service..."):
                reply = st.session_state.assistant.handle(transcript)

            st.session_state.history.append(("user", transcript, []))
            text = reply.text
            if reply.kind == "recommend":       # offices are shown as cards below the text
                text = "\n".join(l for l in reply.text.split("\n") if not l.startswith(("•", "  ")))
            st.session_state.history.append(("assistant", text, reply.offices))

            with st.spinner("Speaking the answer..."):
                st.session_state.audio_reply = asyncio.run(
                    generate_speech(speakable(reply), info.language)
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
