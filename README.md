# The Agents Anatomy

Ein didaktischer, LLM-basierter **Shop-Controller**, der einen kleinen
Online-Shop (Fake Store API) analysiert und betriebswirtschaftliche Fragen
beantwortet.

**Ziel dieses Projekts**: Zeigen, wie **dynamisches Tool-Calling** funktioniert
— und wie sich die Qualität eines Agents allein durch Textänderungen
(**Prompt Engineering**) verbessern lässt, ohne den Code anzufassen.

---

## Architektur

```
The-Agents-Anatomy/
├── agent.py                # CLI: ein einzelner Agent-Lauf (One-Shot)
├── test.py                 # Selbsttest der Tools (ohne LLM)
│
├── prompts/                # ← reine Texte (Prompt-Versionen)
│   └── v1/
│       ├── system_prompt.txt       # Shop-Controller-Rolle
│       └── tool_descriptions.txt   # Tool-Beschreibungen
│
├── runner/                 # Orchestrator (One-Shot-Loop, $results-Resolver)
├── model/                  # LLM-Provider (Gemini, OpenAI, DeepSeek, SAP GenAI Hub)
├── tools/                  # getProducts, filterByCategory, filterByPrice,
│                           # count, sum, average
│
└── requirements.txt
```

Die Ebenen des Agents sind **sauber getrennt**:
- **Texte** (`prompts/`) → beschreiben *was* der Agent tun soll.
- **Runner** (`runner/`) → führt die vom Modell gelieferten Steps aus.
- **Model** (`model/`) → tauschbar (Gemini / OpenAI / SAP GenAI Hub / …).
- **Tools** (`tools/`) → was der Agent in der Welt tun kann.

---

## Wie der Agent arbeitet (One-Shot-Loop)

Der Agent ist bewusst einfach gehalten: Er besteht aus **genau zwei Teilen** —
`call_llm()` (Plan holen) und `process_steps()` (Steps ausführen). Es gibt
**keine zweite Iteration**: Aus der Frage des Nutzers wird in einem einzigen
Durchlauf ein Plan erzeugt und ausgeführt.

```
                    ┌─────────────────────────────────────────────┐
                    │              SYSTEM-PROMPT                  │
                    │  (prompts/<version>/system_prompt.txt)      │
                    │  + Tool-Beschreibungen (tool_descriptions)  │
                    └───────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────▼─────────────────────────┐
                    │  1. call_llm() → JSON-Plan                 │
                    │     { "steps": [...], "answer": "..." }     │
                    └───────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────▼─────────────────────────┐
                    │  2. process_steps() → Steps ausführen      │
                    │     getProducts / filterByCategory / ...    │
                    └───────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────▼─────────────────────────┐
                    │  Ergebnisse in `results` merken             │
                    │  ($results[i].products-Referenzen)          │
                    └─────────────────────────────────────────────┘
```

**Die zwei Teile im Detail:**

1. **call_llm()** — Das Modell erhält die Frage des Nutzers und liefert einen
   JSON-Plan mit `steps` (Tool-Aufrufe) und `answer` (die finale Antwort).
2. **process_steps()** — Der Runner führt jeden Step der Reihe nach aus.
   Jedes Ergebnis landet in `results`. Ein späterer Step kann per
   `$results[i].key` auf ein früheres Ergebnis zugreifen — insbesondere kann
   eine Produktliste per `$results[i].products` an das nächste Tool
   weitergereicht werden.

### Beispiel: Ein konkreter Plan

Frage: *"Wie viele Elektronikprodukte kosten mehr als 100 €?"*

```json
{
  "steps": [
    { "tool": "getProducts",
      "args": { "operation": "get", "operand1": "", "operand2": "", "operand3": "" },
      "description": "Alle Produkte laden" },
    { "tool": "filterByCategory",
      "args": { "operation": "filterByCategory",
                "operand1": "$results[0].products",
                "operand2": "electronics",
                "operand3": "" },
      "description": "Nur Elektronik behalten" },
    { "tool": "filterByPrice",
      "args": { "operation": "filterByPrice",
                "operand1": "$results[1].products",
                "operand2": ">",
                "operand3": "100" },
      "description": "Nur Produkte über 100 € behalten" },
    { "tool": "count",
      "args": { "operation": "count",
                "operand1": "$results[2].products",
                "operand2": "",
                "operand3": "" },
      "description": "Anzahl zählen" }
  ],
  "answer": "Es gibt 5 Elektronikprodukte, die mehr als 100 € kosten."

}
```

Die Steps werden der Reihe nach ausgeführt. `$results[0].products` verweist auf
die Produktliste aus `getProducts`, `$results[1].products` auf die gefilterte
Elektronik-Liste usw. So nutzt der Agent die frisch geladenen Daten, ohne sie
als Zahlen zu kodieren.

> **Didaktischer Kern:** Der Agent "denkt" nicht in freiem Text, sondern in
> **strukturierten Tool-Aufrufen**. Die Qualität hängt fast nur davon ab, wie
> gut der Prompt diese Schritte beschreibt — nicht vom Code.

---

## Setup

### 1. Abhängigkeiten
```bash
pip install -r requirements.txt
```

### 2. `.env` anlegen
Kopiere `.env.example` und fülle die Werte aus. Wichtigste Variablen:

```
LLM_PROVIDER=gemini              # oder "openai" / "deepseek" / "sap"
PROMPT_VERSION=v1

# Für Gemini:
GOOGLE_API_KEY=...

# Für OpenAI:
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

# Für DeepSeek (OpenAI-kompatible API):
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat

# Für SAP GenAI Hub:
SAP_GENAI_SERVICE_KEY_FILE=./.sap_service_key.json
SAP_GENAI_MODEL=anthropic--claude-4.7-opus
SAP_GENAI_RESOURCE_GROUP=default
```

### 3. Service-Key hinterlegen
Für den SAP GenAI Hub die JSON-Datei mit dem Service-Key als
`.sap_service_key.json` im Projekt-Root ablegen. Sie ist in `.gitignore`.

---

## Ein einzelner Agent-Lauf

```bash
python agent.py
python agent.py --question "Welche Kategorie hat den höchsten Durchschnittspreis?"
python agent.py --model gpt-4o --prompt-version v1
```

Der Agent lädt die Produkte von der Fake Store API, führt den Plan aus und
gibt die finale Antwort aus. Der Plan und die Tool-Ergebnisse werden nach
`data/agent_log.jsonl` geschrieben (didaktisch hilfreich zum Nachvollziehen).

## Tools testen (ohne LLM)

```bash
python test.py
```

Führt einen Selbsttest der sechs Tools aus — inklusive der
`$results[i].products`-Referenzauflösung (Tool-zu-Tool-Weitergabe).

---

## Die Tools

| Tool | Zweck |
|------|-------|
| `getProducts()` | Lädt alle Produkte von der Fake Store API |
| `filterByCategory(products, category)` | Filtert nach Kategorie |
| `filterByPrice(products, operator, value)` | Filtert nach Preis (`>`, `>=`, `<`, `<=`, `==`) |
| `count(items)` | Zählt die Items einer Liste |
| `sum(items, field?)` | Summiert ein Feld (Default `price`) |
| `average(items, field?)` | Durchschnitt eines Felds (Default `price`) |

---

## Prompt-Versionen

Der Agent liest aus `prompts/<PROMPT_VERSION>/`. Wechseln über `.env` oder
CLI-Argument `--prompt-version`.

Aktuell gibt es **eine** Version (`v1`), die zum One-Shot-Runner passt:

| Version | Fokus |
|---------|-------|
| v1 | Minimal autonomer Shop-Controller: One-Shot-Plan, `$results`-Referenzen, Tool-Ketten (getProducts → filter → count/sum/average), Beispiel-Pläne |

---

## Sicherheit

- Service-Keys **niemals** ins Repo commiten.
- `.gitignore` blockiert alle üblichen Secret-Dateien.
- **Privates Repo** wird empfohlen für Produktions-Setup.

---

## Lizenz

Didaktisches Projekt, freie Verwendung.
