# model/sap.py — SAP GenAI Hub (BTP AI Core) Provider
#
# Nutzt einen BTP Service Key (JSON), holt sich ein OAuth2-Access-Token
# (Client Credentials, mit Cache), löst zur Laufzeit die deployment_id
# eines Modells auf und ruft dann die passende Inference-URL.

import json
import os
import re
import time
from typing import Any, Dict, Optional

import requests


# ---------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------
def _load_service_key() -> Dict[str, Any]:
    path = os.getenv("SAP_GENAI_SERVICE_KEY_FILE", "./.sap_service_key.json")
    if not os.path.exists(path):
        raise RuntimeError(
            f"SAP GenAI Hub: Service-Key-Datei nicht gefunden: {path}. "
            "Bitte SAP_GENAI_SERVICE_KEY_FILE in .env korrekt setzen."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_SERVICE_KEY: Optional[Dict[str, Any]] = None


def _sk() -> Dict[str, Any]:
    global _SERVICE_KEY
    if _SERVICE_KEY is None:
        _SERVICE_KEY = _load_service_key()
    return _SERVICE_KEY


def _ai_api_url() -> str:
    return _sk()["serviceurls"]["AI_API_URL"].rstrip("/")


def _resource_group() -> str:
    return os.getenv("SAP_GENAI_RESOURCE_GROUP", "default")


def _model_name() -> str:
    return os.getenv("SAP_GENAI_MODEL", "gemini-1.5-flash")


# ---------------------------------------------------------
# OAuth2 Token (Client Credentials) mit einfachem Cache
# ---------------------------------------------------------
_TOKEN_CACHE: Dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def _get_token() -> str:
    now = time.time()
    if _TOKEN_CACHE["access_token"] and _TOKEN_CACHE["expires_at"] - 60 > now:
        return _TOKEN_CACHE["access_token"]

    sk = _sk()
    token_url = sk["url"].rstrip("/") + "/oauth/token"
    resp = requests.post(
        token_url,
        data={"grant_type": "client_credentials"},
        auth=(sk["clientid"], sk["clientsecret"]),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    _TOKEN_CACHE["access_token"] = data["access_token"]
    _TOKEN_CACHE["expires_at"] = now + float(data.get("expires_in", 3600))
    return _TOKEN_CACHE["access_token"]


def _auth_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "AI-Resource-Group": _resource_group(),
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------
# Deployment-Auflösung (Modell -> deployment_id) mit Cache
# ---------------------------------------------------------
_DEPLOYMENT_CACHE: Dict[str, str] = {}


def _resolve_deployment_id(model: str) -> str:
    if model in _DEPLOYMENT_CACHE:
        return _DEPLOYMENT_CACHE[model]

    url = f"{_ai_api_url()}/v2/lm/deployments"
    params = {"scenarioId": "foundation-models", "status": "RUNNING"}
    resp = requests.get(url, headers=_auth_headers(), params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    resources = payload.get("resources", []) or []
    candidates = []
    for d in resources:
        details = d.get("details") or {}
        resources_field = details.get("resources") or {}
        backend = resources_field.get("backend_details") or {}
        model_info = backend.get("model") or {}
        m_name = model_info.get("name") or details.get("modelName") or ""
        if m_name == model:
            candidates.append(d)

    if not candidates:
        available = sorted({
            ((d.get("details") or {}).get("resources") or {})
            .get("backend_details", {}).get("model", {}).get("name", "?")
            for d in resources
        })
        raise RuntimeError(
            f"Kein laufendes Deployment für Modell '{model}' gefunden.\n"
            f"Verfügbare Modelle in dieser Resource Group ({_resource_group()}): {available}"
        )

    dep_id = candidates[0]["id"]
    _DEPLOYMENT_CACHE[model] = dep_id
    print(f"[model.sap] Deployment {model} -> {dep_id}")
    return dep_id


# ---------------------------------------------------------
# JSON-Extraktion
# ---------------------------------------------------------
def _extract_json(text: str) -> Dict[str, Any]:
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


# ---------------------------------------------------------
# Chat-Call
# ---------------------------------------------------------
# GenAI Hub braucht je nach Modelltyp einen anderen Inference-Pfad:
#   - OpenAI-Modelle:   /chat/completions?api-version=2023-05-15
#   - Anthropic Claude: /invoke
#   - Gemini:           /models/{model}:generateContent
# Wir probieren die Kandidaten in Reihenfolge; der erste, der nicht 404 ist,
# wird prozessweit gecached.
_INFERENCE_PATH_CACHE: Dict[str, str] = {}

OPENAI_API_VERSION = os.getenv("SAP_GENAI_OPENAI_API_VERSION", "2023-05-15")


def _candidate_paths(model: str) -> list:
    if model.startswith("gpt-") or model.startswith("sap-rpt"):
        return [f"/chat/completions?api-version={OPENAI_API_VERSION}"]
    if model.startswith("anthropic--"):
        return ["/invoke", f"/chat/completions?api-version={OPENAI_API_VERSION}"]
    if model.startswith("gemini"):
        return [
            f"/models/{model}:generateContent",
            f"/chat/completions?api-version={OPENAI_API_VERSION}",
        ]
    return [f"/chat/completions?api-version={OPENAI_API_VERSION}", "/invoke"]


# max_tokens großzügig, damit umfangreiche Pläne (viele Steps) nicht abgeschnitten werden.
MAX_TOKENS = int(os.getenv("SAP_GENAI_MAX_TOKENS", "4096"))


def _build_openai_body(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt +
                "\n\nFORMAT: Antworte ausschließlich als reines JSON-Objekt. "
                "Kein Markdown, kein Fließtext."},
        ],
        "temperature": 0.2,
        "max_tokens": MAX_TOKENS,
    }


def _build_anthropic_body(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    # temperature ist bei neueren Claude-Modellen (>= 4.5) im GenAI Hub deprecated.
    # Wir schicken sie nur, wenn SAP_GENAI_ANTHROPIC_TEMPERATURE gesetzt ist.
    body: Dict[str, Any] = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_prompt +
                "\n\nFORMAT: Antworte ausschließlich als reines JSON-Objekt."},
        ],
    }
    t = os.getenv("SAP_GENAI_ANTHROPIC_TEMPERATURE")
    if t:
        try:
            body["temperature"] = float(t)
        except Exception:
            pass
    return body


def _extract_text_from_payload(payload: Dict[str, Any]) -> Optional[str]:
    if isinstance(payload, dict) and "choices" in payload:
        try:
            return payload["choices"][0]["message"]["content"]
        except Exception:
            pass
    if isinstance(payload, dict) and "content" in payload:
        blocks = payload["content"]
        if isinstance(blocks, list) and blocks:
            parts = [b.get("text", "") for b in blocks if isinstance(b, dict)]
            return "".join(parts) or None
    if isinstance(payload, dict) and "candidates" in payload:
        try:
            parts = payload["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts) or None
        except Exception:
            pass
    return None


def call_llm(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    model = _model_name()
    dep_id = _resolve_deployment_id(model)
    base = f"{_ai_api_url()}/v2/inference/deployments/{dep_id}"

    if model.startswith("anthropic--"):
        body = _build_anthropic_body(system_prompt, user_prompt)
    else:
        body = _build_openai_body(system_prompt, user_prompt)

    paths = ([_INFERENCE_PATH_CACHE[model]]
             if model in _INFERENCE_PATH_CACHE
             else _candidate_paths(model))

    last_error: Dict[str, Any] = {}
    for path in paths:
        url = base + path
        resp = requests.post(url, headers=_auth_headers(), json=body, timeout=90)
        if resp.status_code == 404:
            last_error = {"error": "http_404", "url": url, "body": resp.text[:500]}
            continue
        if resp.status_code >= 400:
            return {"error": "http_error", "status": resp.status_code,
                    "url": url, "body": resp.text[:2000]}

        _INFERENCE_PATH_CACHE[model] = path
        payload = resp.json()
        text = _extract_text_from_payload(payload)
        if text is None:
            return {"error": "unexpected_response_schema", "raw": payload}
        return _extract_json(text)

    return {"error": "no_working_inference_path", "last": last_error,
            "tried": paths, "model": model, "deployment_id": dep_id}


if __name__ == "__main__":
    print(call_llm(
        "Antworte als reines JSON.",
        "Gib ein JSON-Objekt mit dem Feld 'gruss' und Wert 'hallo' zurück."
    ))