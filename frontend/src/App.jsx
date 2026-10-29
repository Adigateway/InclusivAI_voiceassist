
import { useEffect, useRef, useState } from "react";
import {
  HeartHandshake,
  Mic,
  MicOff,
  Globe,
  ShieldCheck,
  Volume2,
  VolumeX,
  RotateCcw,
  MapPin,
  Phone,
  Mail,
  ExternalLink,
  Info,
  X
} from "lucide-react";
import "./styles.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const API_ENDPOINT =
  import.meta.env.VITE_API_ENDPOINT || "/api/search";

// Demo mode answers without a backend; the real backend (python server.py) is used by default
const DEMO_MODE =
  (import.meta.env.VITE_DEMO_MODE ?? "false") === "true";

function newSessionId() {
  return crypto.randomUUID?.() ?? String(Date.now() + Math.random());
}

const words = {
  de: {
    tagline: "Ihre Unterstützung in Unterfranken",
    headline: "Wie können wir Ihnen helfen?",
    intro: "Sprechen Sie ganz natürlich. Wir helfen Ihnen, eine passende Anlaufstelle zu finden.",
    start: "Jetzt sprechen",
    stop: "Aufnahme beenden",
    ready: "Bereit, wenn Sie es sind",
    listening: "Ich höre Ihnen zu …",
    processing: "Einen Moment bitte …",
    welcome: "Hallo! Ich bin CaritAssist. Wobei benötigen Sie Unterstützung?",
    hint: "Tippen Sie auf das Mikrofon und erzählen Sie mir, was Sie beschäftigt.",
    privacy: "Datenschutz",
    about: "Über uns",
    read: "Antwort vorlesen",
    newRequest: "Neues Anliegen",
    noSpeech: "Dieser Browser unterstützt keine Spracheingabe. Bitte versuchen Sie Google Chrome.",
    denied: "Mikrofonzugriff verweigert. Bitte erlauben Sie den Zugriff in Ihren Browsereinstellungen.",
    empty: "Ich habe leider nichts verstanden. Bitte versuchen Sie es erneut.",
    demo: "Der Demo-Modus ist aktiv. Sobald Ihr Backend verbunden ist, kann ich passende Caritas-Angebote suchen. Ihre Anfrage wurde nicht an ein KI-Modell gesendet.",
    error: "Der Suchdienst ist gerade nicht erreichbar. Bitte prüfen Sie die Backend-Verbindung.",
    fallback: "Es wurde kein passender Vorschlag zurückgegeben. Sie können Ihr Anliegen anders beschreiben oder sich direkt an Caritas wenden.",
    details: "Details",
    official: "Offizielle Angebotsseite",
    noContact: "Keine Kontaktdaten verfügbar.",
    privacyTitle: "Datenschutz bei CaritAssist",
    privacy1: "CaritAssist sendet Ihre Anfrage an den konfigurierten Suchdienst, um passende Unterstützungsangebote zu finden.",
    privacy2: "Die Spracheingabe des Browsers kann Audio an einen Dienst des Browseranbieters übertragen. Bitte prüfen Sie die Datenschutzhinweise Ihres Browsers.",
    privacy3: "Bitte teilen Sie in diesem Prototyp keine unnötigen sensiblen persönlichen Daten. Die Vorschläge ersetzen keine professionelle Beratung.",
    close: "Schließen",
    assistant: "Sprachassistent",
    suggestion: "PASSENDES ANGEBOT",
    reason: "Warum dieser Vorschlag?",
    source: "Quelle: bereitgestellte Servicedaten"
  },
  en: {
    tagline: "Support and guidance in Lower Franconia",
    headline: "How can we help you?",
    intro: "Speak naturally. We’ll help you find the right support service.",
    start: "Start speaking",
    stop: "Stop recording",
    ready: "Ready when you are",
    listening: "I’m listening …",
    processing: "One moment, please …",
    welcome: "Hello! I’m CaritAssist. What would you like help with?",
    hint: "Tap the microphone and tell me what is on your mind.",
    privacy: "Privacy",
    about: "About us",
    read: "Read answers aloud",
    newRequest: "New request",
    noSpeech: "This browser does not support speech recognition. Please try Google Chrome.",
    denied: "Microphone access denied. Please allow it in your browser settings.",
    empty: "Sorry, I did not catch that. Please try again.",
    demo: "Demo mode is active. Once your backend is connected, I can search for relevant Caritas services. Your request has not been sent to an AI model.",
    error: "The search service is unavailable. Please check the backend connection.",
    fallback: "No suitable suggestion was returned. Try describing your situation differently or contact Caritas directly.",
    details: "Details",
    official: "Official service page",
    noContact: "No contact details available.",
    privacyTitle: "Privacy at CaritAssist",
    privacy1: "CaritAssist sends your request to the configured search service to find relevant support options.",
    privacy2: "Browser speech recognition may send audio to a service operated by your browser provider. Please check your browser’s privacy information.",
    privacy3: "Avoid sharing unnecessary sensitive personal information in this prototype. Suggestions do not replace professional advice.",
    close: "Close",
    assistant: "Voice assistant",
    suggestion: "SUGGESTED SERVICE",
    reason: "Why this suggestion?",
    source: "Source: provided service data"
  }
};

function clean(value) {
  if (value == null) return "";
  const result = String(value).trim();

  return ["null", "undefined", "nan", "none"].includes(
    result.toLowerCase()
  ) ? "" : result;
}

function ServiceCard({ service, language }) {
  const t = words[language];
  const [expanded, setExpanded] = useState(false);

  const offices = Array.isArray(service.offices)
    ? service.offices.filter(Boolean)
    : [];

  return (
    <article className="service-card">
      <div className="service-main">
        <div className="service-icon">
          <HeartHandshake size={24} />
        </div>

        <div className="service-description">
          <small>{t.suggestion}</small>
          <h3>{clean(service.title) || "Caritas service"}</h3>

          {clean(service.category) && (
            <span className="category">{service.category}</span>
          )}

          {clean(service.description) && (
            <p>{service.description}</p>
          )}

          {clean(service.match_reason) && (
            <p className="reason">
              <Info size={14} /> {t.reason} {service.match_reason}
            </p>
          )}
        </div>

        <button
          className="details-button"
          onClick={() => setExpanded(!expanded)}
        >
          {t.details}
        </button>
      </div>

      {expanded && (
        <div className="service-details">
          {offices.length === 0 && <p>{t.noContact}</p>}

          {offices.slice(0, 3).map((office, index) => (
            <div className="office" key={index}>
              <strong>
                <MapPin size={15} />{" "}
                {clean(office.organisation) || "Caritas"}
              </strong>

              <p>
                {[
                  office.street,
                  office.plz,
                  office.city
                ].map(clean).filter(Boolean).join(", ")}
              </p>

              {clean(office.phone) && (
                <a href={`tel:${office.phone}`}>
                  <Phone size={14} /> {office.phone}
                </a>
              )}

              {clean(office.email) && (
                <a href={`mailto:${office.email}`}>
                  <Mail size={14} /> {office.email}
                </a>
              )}
            </div>
          ))}

          {clean(service.url) && (
            <a
              className="official-link"
              href={service.url}
              target="_blank"
              rel="noreferrer"
            >
              {t.official} <ExternalLink size={14} />
            </a>
          )}

          <small className="source-note">{t.source}</small>
        </div>
      )}
    </article>
  );
}

export default function App() {
  const [language, setLanguage] = useState("de");
  const [messages, setMessages] = useState([]);
  const [services, setServices] = useState([]);
  const [listening, setListening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [error, setError] = useState("");
  const [showPrivacy, setShowPrivacy] = useState(false);

  const recognitionRef = useRef(null);
  const finalTextRef = useRef("");
  // The backend keeps the conversation per session, so follow-up questions ("Where do you live?") work
  const sessionRef = useRef(newSessionId());
  const audioRef = useRef(null);
  const speechTokenRef = useRef(0);
  const t = words[language];

  useEffect(() => {
    document.documentElement.lang = language;
    document.title = "CaritAssist";
  }, [language]);

  useEffect(() => {
    return () => {
      try {
        recognitionRef.current?.stop();
      } catch {}

      stopSpeaking();
    };
  }, []);

  // Stops whatever is being said right now, including an answer that is still loading
  function stopSpeaking() {
    speechTokenRef.current += 1;
    audioRef.current?.pause();
    audioRef.current = null;
    window.speechSynthesis?.cancel();
  }

  function browserSpeak(message) {
    if (!window.speechSynthesis) return;
    const utterance = new SpeechSynthesisUtterance(message);
    utterance.lang = language === "de" ? "de-DE" : "en-GB";
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  }

  // Natural neural voice from the backend (/api/tts); the browser voice is only a fallback
  async function speak(message) {
    if (!voiceEnabled || !message) return;

    stopSpeaking();
    const token = speechTokenRef.current;

    if (DEMO_MODE) {
      browserSpeak(message);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL.replace(/\/$/, "")}/api/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: message, language })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();

      // the user pressed the microphone or "new request" while the audio was loading
      if (token !== speechTokenRef.current) return;

      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      audioRef.current = audio;
      await audio.play();
    } catch (err) {
      console.warn("Neural voice unavailable, using browser voice:", err);
      if (token === speechTokenRef.current) browserSpeak(message);
    }
  }

  async function sendToBackend(message) {
    const question = clean(message);
    if (!question || busy) return;

    setError("");
    setBusy(true);
    setServices([]);

    setMessages(old => [
      ...old,
      { role: "user", text: question }
    ]);

    if (DEMO_MODE) {
      setMessages(old => [
        ...old,
        { role: "assistant", text: t.demo }
      ]);

      setBusy(false);
      speak(t.demo);
      return;
    }

    try {
      const endpoint =
        `${API_BASE_URL.replace(/\/$/, "")}/` +
        API_ENDPOINT.replace(/^\//, "");

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: question,
          location: "",
          language,
          session: sessionRef.current
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      const results = Array.isArray(data.results)
        ? data.results
        : [];

      const reply = clean(data.reply) || t.fallback;

      setServices(results);

      setMessages(old => [
        ...old,
        {
          role: "assistant",
          text: reply,
          followUp: clean(data.follow_up)
        }
      ]);

      speak(reply);
    } catch (err) {
      console.error("CaritAssist backend error:", err);
      setError(t.error);

      setMessages(old => [
        ...old,
        { role: "assistant", text: t.error }
      ]);
    } finally {
      setBusy(false);
    }
  }

  function toggleMicrophone() {
    const SpeechRecognition =
      window.SpeechRecognition ||
      window.webkitSpeechRecognition;

    setError("");

    if (!SpeechRecognition) {
      setError(t.noSpeech);
      return;
    }

    if (listening) {
      recognitionRef.current?.stop();
      return;
    }

    stopSpeaking();
    finalTextRef.current = "";

    const recognition = new SpeechRecognition();
    recognition.lang = language === "de" ? "de-DE" : "en-GB";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => setListening(true);

    recognition.onresult = event => {
      let finalText = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          finalText += event.results[i][0].transcript;
        }
      }

      if (finalText.trim()) {
        finalTextRef.current = finalText.trim();
      }
    };

    recognition.onerror = event => {
      setListening(false);

      if (event.error === "not-allowed") {
        setError(t.denied);
      } else if (
        event.error !== "no-speech" &&
        event.error !== "aborted"
      ) {
        setError(t.empty);
      }
    };

    recognition.onend = () => {
      setListening(false);

      const question = finalTextRef.current;
      finalTextRef.current = "";

      if (question) {
        sendToBackend(question);
      } else {
        setError(t.empty);
      }
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch {
      setError(t.noSpeech);
    }
  }

  function restart() {
    try {
      recognitionRef.current?.stop();
    } catch {}

    stopSpeaking();

    if (!DEMO_MODE) {
      const endpoint = `${API_BASE_URL.replace(/\/$/, "")}/api/reset`;
      fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session: sessionRef.current })
      }).catch(() => {});
    }
    sessionRef.current = newSessionId();
    setMessages([]);
    setServices([]);
    setError("");
    setListening(false);
    setBusy(false);
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        

<a className="brand" href="#home" aria-label="Caritas Wegweiser home">
  <div className="caritas-emblem">
    <svg viewBox="0 0 100 100" aria-hidden="true">
      <g fill="white">
        <path d="M42 8 H58 V42 H92 V58 H58 V92 H42 V58 H8 V42 H42 Z" />
      </g>
      <g
        fill="none"
        stroke="white"
        strokeWidth="5"
        strokeLinecap="square"
      >
        <path d="M15 24 L34 40 M22 16 L40 34" />
        <path d="M85 24 L66 40 M78 16 L60 34" />
        <path d="M15 76 L34 60 M22 84 L40 66" />
        <path d="M85 76 L66 60 M78 84 L60 66" />
      </g>
    </svg>
    <span className="caritas-label">caritas</span>
  </div>

  <div className="brand-copy">
    
<strong className="brand-name">
  <span className="brand-red">CaritAs</span><span className="brand-black">sist</span>
</strong>

    <span className="brand-tagline">{t.tagline}</span>
  </div>
</a>



        <nav className="top-actions">
          <Globe size={17} />

          <button
            className={language === "de" ? "selected" : ""}
            onClick={() => setLanguage("de")}
          >
            Deutsch
          </button>

          <span>|</span>

          <button
            className={language === "en" ? "selected" : ""}
            onClick={() => setLanguage("en")}
          >
            English
          </button>

          <button
            className="nav-link"
            onClick={() => setShowPrivacy(true)}
          >
            <ShieldCheck size={16} /> {t.privacy}
          </button>
        </nav>
      </header>

      <main id="home" className="layout">
        <section className="hero">
          <div>
            <p className="eyebrow">A GOOD FIRST STEP</p>
            <h1>{t.headline}</h1>
            <p className="intro">{t.intro}</p>
          </div>

          <div className={`mic-stage ${listening ? "active" : ""}`}>
            <div className="mic-halo" />

            <button
              className="mic-button"
              onClick={toggleMicrophone}
              disabled={busy}
              aria-label={listening ? t.stop : t.start}
            >
              {listening ? (
                <MicOff size={40} />
              ) : (
                <Mic size={44} />
              )}
            </button>

            <p className="mic-status">
              {busy
                ? t.processing
                : listening
                  ? t.listening
                  : t.ready}
            </p>

            <button
              className="start-button"
              onClick={toggleMicrophone}
              disabled={busy}
            >
              <Mic size={17} /> {listening ? t.stop : t.start}
            </button>
          </div>

          <p className="hero-note">
            <ShieldCheck size={15} /> Support, one step at a time
          </p>
        </section>

        <section className="chat-panel">
          <header className="chat-header">
            <div className="chat-avatar">
              <HeartHandshake size={21} />
            </div>

            <div>
              <strong>CaritAssist</strong>
              <small>{t.assistant}</small>
            </div>

            <span className="online-dot">
              ● {busy ? t.processing : t.ready}
            </span>
          </header>

          <div className="chat-content">
            {messages.length === 0 ? (
              <div className="welcome">
                <div className="welcome-avatar">
                  <HeartHandshake size={24} />
                </div>

                <div className="bubble">
                  <p>{t.welcome}</p>
                  <small>{t.hint}</small>
                </div>
              </div>
            ) : (
              <>
                {messages.map((message, index) => (
                  <div
                    className={`message ${message.role}`}
                    key={index}
                  >
                    <div className="bubble">
                      <p>{message.text}</p>

                      {message.followUp && (
                        <small>{message.followUp}</small>
                      )}

                      {message.role === "assistant" && (
                        <button
                          className="listen-answer"
                          onClick={() => speak(message.text)}
                        >
                          <Volume2 size={14} /> Listen
                        </button>
                      )}
                    </div>
                  </div>
                ))}

                {busy && (
                  <p className="loading">Searching for support …</p>
                )}

                {services.map((service, index) => (
                  <ServiceCard
                    key={index}
                    service={service}
                    language={language}
                  />
                ))}
              </>
            )}
          </div>

          {error && (
            <div className="error">
              <Info size={16} />
              <span>{error}</span>
              <button onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}

          <footer className="chat-footer">
            <button
              className="read-toggle"
              onClick={() => {
                if (voiceEnabled) {
                  stopSpeaking();
                }

                setVoiceEnabled(value => !value);
              }}
            >
              {voiceEnabled ? (
                <Volume2 size={17} />
              ) : (
                <VolumeX size={17} />
              )}

              {t.read}
            </button>

            <button className="restart-button" onClick={restart}>
              <RotateCcw size={16} /> {t.newRequest}
            </button>
          </footer>
        </section>
      </main>

      <footer className="page-footer">
        CaritAssist · A digital guide to Caritas support services

        <button onClick={() => setShowPrivacy(true)}>
          {t.about}
        </button>
      </footer>

      {showPrivacy && (
        <div
          className="modal-backdrop"
          onClick={() => setShowPrivacy(false)}
        >
          <section
            className="privacy-modal"
            role="dialog"
            aria-modal="true"
            onClick={event => event.stopPropagation()}
          >
            
          <button
          className="modal-close"
          onClick={() => setShowPrivacy(false)}
          aria-label="Close privacy window"
          >
          <X size={22} strokeWidth={2.5} />
          </button>


            <ShieldCheck size={30} />
            <h2>{t.privacyTitle}</h2>
            <p>{t.privacy1}</p>
            <p>{t.privacy2}</p>
            <p>{t.privacy3}</p>

            <button
              className="restart-button"
              onClick={() => setShowPrivacy(false)}
            >
              {t.close}
            </button>
          </section>
        </div>
      )}
    </div>
  );
}
