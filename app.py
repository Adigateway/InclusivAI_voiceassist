
import os
import tempfile
import asyncio
import edge_tts

import streamlit as st
from faster_whisper import WhisperModel
from sentence_transformers import SentenceTransformer

from scripts.rag_assistant import (
    load_services,
    create_service_text,
    retrieve_services,
    generate_answer,
)
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
            
st.set_page_config(
    page_title="Caritas Voice Assistant",
    page_icon="🎙️",
)

st.title("🎙️ Caritas AI Voice Assistant")
st.write("Speak in German or English to find Caritas services.")

@st.cache_resource
def load_models_and_data():
    services = load_services()

    embedding_model = SentenceTransformer(
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    service_texts = [create_service_text(s) for s in services]

    embeddings = embedding_model.encode(
        service_texts,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    whisper_model = WhisperModel(
        "small",
        device="cpu",
        compute_type="int8",
    )

    return services, embedding_model, embeddings, whisper_model


try:
    with st.spinner("Loading AI models..."):
        services, embedding_model, embeddings, whisper_model = (
            load_models_and_data()
        )
except Exception as error:
    st.error(f"Could not load the AI models: {error}")
    st.stop()


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

            st.subheader("You said")
            st.write(transcript)
            st.caption(f"Detected language: {info.language}")

            with st.spinner("Searching Caritas services..."):
                results = retrieve_services(
                    transcript,
                    services,
                    embedding_model,
                    embeddings,
                )

            with st.spinner("Preparing your answer..."):
                answer = generate_answer(transcript, results)

            st.subheader("Caritas answer")
            st.write(answer)

            with st.spinner("Speaking the answer..."):
                audio_bytes = asyncio.run(
                    generate_speech(answer, info.language)
                )

            st.audio(
                audio_bytes,
                format="audio/mp3",
                autoplay=True,
            )

            if results:
                st.subheader("Sources")
                for score, service in results:
                    title = service.get("title_de", "Caritas service")
                    url = service.get("url")

                    if url:
                        st.markdown(f"- [{title}]({url})")
                    else:
                        st.write(f"- {title}")

        except Exception as error:
            st.error(f"Something went wrong: {error}")

        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

st.divider()
st.caption("Responses are based on the available Caritas service dataset.")
