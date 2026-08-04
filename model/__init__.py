# model/__init__.py — Dispatcher zwischen mehreren LLM-Providern.
#
# Wähle den Provider über die .env:
#   LLM_PROVIDER=gemini   (Default; nutzt model/gemini.py, braucht GOOGLE_API_KEY)
#   LLM_PROVIDER=openai   (nutzt model/openai.py, braucht OPENAI_API_KEY)
#   LLM_PROVIDER=sap      (nutzt model/sap.py, braucht SAP GenAI Hub Service Key)
#
# Das Modell kann per .env-Variable (GEMINI_MODEL / OPENAI_MODEL /
# SAP_GENAI_MODEL) gesetzt oder zur Laufzeit per set_model(...) überschrieben
# werden.

import os
from dotenv import load_dotenv

load_dotenv()

_PROVIDER = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()


def set_provider(name: str) -> None:
    """Provider zur Laufzeit wechseln (z. B. 'gemini' -> 'sap')."""
    global _PROVIDER
    _PROVIDER = name.strip().lower()


def get_provider() -> str:
    """Aktueller Provider ('gemini', 'openai' oder 'sap')."""
    return _PROVIDER


def set_model(model_name: str) -> None:
    """Modell zur Laufzeit setzen — für den aktuellen Provider.

    Der Provider wird über LLM_PROVIDER (oder set_provider) gewählt. Diese
    Funktion setzt nur die passende Modell-Env-Variable des aktiven Providers:
      - gemini -> GEMINI_MODEL
      - openai -> OPENAI_MODEL
      - sap    -> SAP_GENAI_MODEL

    Die Provider lesen das Modell zur Laufzeit aus der Env-Variable (bzw.
    cachen Deployment-IDs pro Modellname), daher ist keine Cache-Invalidierung
    nötig.
    """
    m = model_name.strip()
    if _PROVIDER == "gemini":
        # Gemini erwartet 'models/gemini-flash-latest' als Kanon; wir akzeptieren
        # aber auch nur 'gemini-flash-latest' und ergänzen den Prefix.
        os.environ["GEMINI_MODEL"] = m if m.startswith("models/") else f"models/{m}"
    elif _PROVIDER == "openai":
        os.environ["OPENAI_MODEL"] = m
    else:  # sap
        os.environ["SAP_GENAI_MODEL"] = m


def call_llm(system_prompt: str, user_prompt: str) -> dict:
    if _PROVIDER == "sap":
        from .sap import call_llm as _call
    elif _PROVIDER == "gemini":
        from .gemini import call_llm as _call
    elif _PROVIDER == "openai":
        from .openai import call_llm as _call
    else:
        raise RuntimeError(
            f"Unbekannter LLM_PROVIDER '{_PROVIDER}'. "
            "Erlaubt: 'gemini', 'openai' oder 'sap'."
        )
    return _call(system_prompt, user_prompt)
