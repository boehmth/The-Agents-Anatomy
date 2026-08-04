# model/gemini.py — Google Gemini Provider (via google-genai SDK)

import os
import json
import re
from google.genai import Client
from google.genai.types import GenerateContentConfig


_client = None


def _get_client() -> Client:
    global _client
    if _client is None:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY oder GEMINI_API_KEY fehlt in .env")
        _client = Client(api_key=api_key)
    return _client


MAX_OUTPUT_TOKENS = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "4096"))


def _extract_json(text: str) -> dict:
    if text is None:
        return {"error": "empty_response"}

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return {"error": "no_json_found", "raw": text}

    json_text = match.group(0)
    open_count = json_text.count("{")
    close_count = json_text.count("}")
    if open_count > close_count:
        json_text += "}" * (open_count - close_count)

    try:
        return json.loads(json_text)
    except Exception as e:
        return {"error": "invalid_json", "detail": str(e), "raw": json_text}


def call_llm(system_prompt: str, user_prompt: str) -> dict:
    model = os.getenv("GEMINI_MODEL", "models/gemini-flash-latest")
    prompt = f"""
SYSTEM:
{system_prompt}

USER:
{user_prompt}

FORMAT:
Antworte ausschließlich als reines JSON-Objekt. Kein Markdown, kein Fließtext.
"""

    response = _get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=MAX_OUTPUT_TOKENS,
        ),
    )
    return _extract_json(response.text)


if __name__ == "__main__":
    print(call_llm("Antworte als JSON.", "Sag 'Hallo' im Feld gruss."))