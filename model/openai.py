# model/openai.py — OpenAI Provider (via openai SDK)

import os
import json
import re
from openai import OpenAI


_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY fehlt in .env")
        _client = OpenAI(api_key=api_key)
    return _client


MAX_OUTPUT_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "4096"))
# Manche Modelle (z. B. gpt-5.x) unterstützen nur den Default-Wert 1.
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "1"))


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
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    response = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt +
                "\n\nFORMAT: Antworte ausschließlich als reines JSON-Objekt. "
                "Kein Markdown, kein Fließtext."},
        ],
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_OUTPUT_TOKENS,
    )
    return _extract_json(response.choices[0].message.content)


if __name__ == "__main__":
    print(call_llm("Antworte als JSON.", "Sag 'Hallo' im Feld gruss."))
