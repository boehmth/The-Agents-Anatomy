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

Aktuell gibt es **zwei** Versionen, die beide auf demselben (iterationsfähigen)
Runner laufen:

| Version | Fokus |
|---------|-------|
| v1 | One-Shot Plan-and-Execute: ein Plan, `$results`-Referenzen, Tool-Ketten (getProducts → filter → count/sum/average), Beispiel-Pläne |
| v2 | Mehrschritt-Loop: Entscheidungen erst nach echten Zwischenergebnissen (`done`-gesteuert) |

---

## Sicherheit



- Service-Keys **niemals** ins Repo commiten.
- `.gitignore` blockiert alle üblichen Secret-Dateien.
- **Privates Repo** wird empfohlen für Produktions-Setup.

---

## V1: Grenzen und die Motivation für V2

V1 ist bewusst als **One-Shot Plan-and-Execute** gebaut: Das Modell bekommt
die Frage, schreibt in einem einzigen Rutsch den kompletten Werkzeug-Plan
(`steps`), und der Runner führt ihn aus. Die 15 Referenzfragen weiter oben
sind bewusst so gewählt, dass sie mit genau dieser Architektur zuverlässig
lösbar sind — das ist die Test-/Referenztabelle für V1.

Das funktioniert, **solange die Struktur des Plans** (welche Tools, in
welcher Reihenfolge, mit welchen Kategorien/Operatoren) **vorab feststeht** —
unabhängig davon, welche konkreten Zahlen am Ende herauskommen.
`$results[i]`-Referenzen erlauben es zwar schon in V1, tatsächliche *Werte*
erst zur Ausführungszeit einzusetzen (z. B. einen berechneten
Durchschnittspreis als Schwellenwert in einem späteren Filter-Step), aber
sie können nicht die *Form* des Plans selbst verändern.

**Die Grenze wird sichtbar, sobald eine Frage einen Kontrollfluss enthält**
— also eine Entscheidung, die erst mit einer echten Zwischenzahl getroffen
werden kann:

> "Zähle zuerst alle Elektronikprodukte über 300 €. Nur falls es mehr als 5
> sind, berechne zusätzlich deren Durchschnittspreis."

V1 muss sich hier **vor** jeder Ausführung committen, ob der `average`-Step
überhaupt Teil des Plans ist — kennt zu diesem Zeitpunkt die Anzahl aber
noch nicht. Es kann raten (und liegt mal richtig, mal falsch), aber es kann
strukturell nicht korrekt "abwarten, bis es die Zahl kennt".

**Das ist die Motivation für V2:** ein echter Mehrschritt-Loop
(ReAct-artig) — Plan schreiben, ausführen, die *echten* Ergebnisse sehen,
dann erst über den nächsten Schritt entscheiden. Kein neuer Prompt-Grundtyp,
keine neuen Tools, kein neuer Code-Pfad für V1 — nur die Fähigkeit, ehrlich
"ich bin noch nicht fertig" zu sagen (`done: false`) und danach mit echtem
Wissen statt Vermutungen weiterzumachen.

### Die drei Szenarien im Vergleich

Der Unterschied lässt sich am besten anhand von drei konkreten Läufen
nachvollziehen. Alle drei nutzen dieselbe Frage — einmal eine, die V1
problemlos kann, und einmal eine Kontrollfluss-Frage, die V1 strukturell
nicht lösen kann:

**Szenario 1 — Erfolgreiche V1-Ausführung** (One-Shot-Frage, in einer Runde
planbar):

```bash
python agent.py --prompt-version v1 "Wie viele Elektronikprodukte kosten mehr als 100 €?"
```

V1 plant `getProducts → filterByCategory → filterByPrice → count` in **einer**
Runde und liefert korrekt: *"5 Elektronikprodukte kosten mehr als 100 €."*
Hier ist die Tool-Kette vorab bekannt — V1 ist dafür ideal.

**Szenario 2 — V2-Kontrollfluss-Frage im V1-Loop-Modus (scheitert):**

```bash
python agent.py --prompt-version v1 "Zähle zuerst alle Elektronikprodukte über 300 €. Nur falls es mehr als 5 sind, berechne zusätzlich deren Durchschnittspreis."
```

V1 muss sich **vor** jeder Ausführung committen, ob der `average`-Step Teil
des Plans ist — kennt die Anzahl zu diesem Zeitpunkt aber noch nicht. Es
plant den `average` blind mit (oder lässt ihn weg) und kann die Bedingung
nicht abwarten. Da es nur 2 Elektronikprodukte über 300 € gibt (nicht > 5),
ist der vorab geplante `average` falsch bzw. überflüssig — die Antwort ist
strukturell nicht zuverlässig.

**Szenario 3 — Erfolgreiche V2-Ausführung** (gleiche Frage, jetzt
`done`-gesteuert):

```bash
python agent.py --prompt-version v2 "Zähle zuerst alle Elektronikprodukte über 300 €. Nur falls es mehr als 5 sind, berechne zusätzlich deren Durchschnittspreis."
```

Runde 1 plant nur `getProducts → filterByCategory → filterByPrice → count`
mit `done: false`. Runde 2 sieht das echte `count` (2) und setzt `done: true`
mit der Antwort: *"Es gibt 2 Elektronikprodukte über 300 €. Da das nicht mehr
als 5 sind, wurde kein Durchschnitt berechnet."* — die Entscheidung fällt
erst mit echtem Wissen statt einer Vermutung.

Die Referenzfragen für V2 stehen in [`docs/v2-test-cases.md`](docs/v2-test-cases.md).

---

## Lizenz

Didaktisches Projekt, freie Verwendung.


