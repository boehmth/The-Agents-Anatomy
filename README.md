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

## Prompt-Versionen & Agent-Versionen

Der Agent liest aus `prompts/<PROMPT_VERSION>/`. Wechseln über `.env` oder
CLI-Argument `--prompt-version`.

Aktuell gibt es **vier** Versionen, die alle auf demselben (iterationsfähigen)
Runner laufen:

| Version | Fokus |
|---------|-------|
| v1 | One-Shot Plan-and-Execute: ein Plan, `$results`-Referenzen, Tool-Ketten (getProducts → filter → count/sum/average), Beispiel-Pläne |
| v2 | Mehrschritt-Loop: Entscheidungen erst nach echten Zwischenergebnissen (`done`-gesteuert) |
| v3 | Strukturelle Verifikation: jeder Plan wird VOR der Ausführung gegen ein Schema geprüft (bekannte Kategorien, erlaubte Operatoren, Pflichtfelder); ungültige Steps werden NICHT ausgeführt, sondern als sichtbarer Validierungsfehler ins Log geschrieben |
| v4 | Technischer Retry (Self-Healing): fehlgeschlagene Steps (V3-Validierungsfehler ODER echte Tool-Laufzeitfehler) werden als Text an das Modell zurückgegeben; es bekommt eine begrenzte Anzahl Korrektur-Versuche (`max_retries`) |

### Der didaktische "Aufbau"-Schalter: `AGENT_VERSION`

Jede Version ist ein **explizites Feature-Set** (siehe `runner/features.py`).
So sieht man auf einen Blick, was jede Version "aufbaut" — und jede Version
ist einzeln aktivierbar:

| Version | `done_field` | `validate` | `retry` | Bedeutung |
|---------|:---:|:---:|:---:|-----------|
| v1 | ✗ | ✗ | ✗ | One-Shot, keine Verifikation |
| v2 | ✓ | ✗ | ✗ | Mehrschritt-Loop (`done`-gesteuert) |
| v3 | ✓ | ✓ | ✗ | + strukturelle Verifikation |
| v4 | ✓ | ✓ | ✓ | + technischer Retry (Self-Healing) |
- `done_field` ist eine **Prompt**-Eigenschaft (V2s `system_prompt.txt` lehrt
  das Modell, `done` zu setzen). Der Runner ist dafür bereits generisch.
- `validate` ist eine **Code**-Eigenschaft (`runner/validate.py`). Sie wird
  über `features["validate"]` der aktiven Version geschaltet — V1/V2 führen
  Pläne unverändert aus, V3 prüft sie vorher.
- `retry` ist eine **Code**-Eigenschaft (`runner/loop.py`). Sie wird über
  `features["retry"]` der aktiven Version geschaltet — V4 gibt
  fehlgeschlagene Steps als Text an das Modell zurück und erlaubt eine
  begrenzte Anzahl Korrektur-Versuche.

Die aktive Version wird über `AGENT_VERSION` gewählt (Fallback:
`PROMPT_VERSION`, dann `v1`). `AGENT_VERSION` steuert **beides**: die
Prompt-Auswahl **und** die Code-Fähigkeiten. So bleibt jede Version explizit
aktivierbar, und zukünftige Versionen (V5+) fügen in `runner/features.py`
einfach ein weiteres Feature hinzu — ohne den Loop anzufassen.

```bash
# V1 (One-Shot, keine Verifikation)
python agent.py --agent-version v1

# V2 (Mehrschritt-Loop, keine Verifikation)
python agent.py --agent-version v2

# V3 (Mehrschritt-Loop + strukturelle Verifikation)
python agent.py --agent-version v3

# V4 (Mehrschritt-Loop + Verifikation + technischer Retry)
python agent.py --agent-version v4
```

Die vollständige technische Evolutions-Roadmap des Agents (v1–v10, inkl.
Ausblick auf Verifikation, Retry, Reasoning, Modell-Routing u. a.) steht in
[`docs/evolution.md`](docs/evolution.md).

---

## Sicherheit

- Service-Keys **niemals** ins Repo commiten.
- `.gitignore` blockiert alle üblichen Secret-Dateien.
- **Privates Repo** wird empfohlen für Produktions-Setup.

---

## V1: Grenzen und die Motivation für V2

V1 ist bewusst als **One-Shot Plan-and-Execute** gebaut: Das Modell bekommt
die Frage, schreibt in einem einzigen Rutsch den kompletten Werkzeug-Plan
(`steps`), und der Runner führt ihn aus. Die 15 Referenzfragen in
[`test_cases_v1.md`](test_cases_v1.md) sind bewusst so gewählt, dass sie mit
genau dieser Architektur zuverlässig lösbar sind — das ist die
Test-/Referenztabelle für V1.

Das funktioniert, **solange die Struktur des Plans** (welche Tools, in
welcher Reihenfolge, mit welchen Kategorien/Operatoren) **vorab feststeht** —
unabhängig davon, welche konkreten Zahlen am Ende herauskommen.

`$results[i]`-Referenzen erlauben es zwar schon in V1, tatsächliche *Werte*
erst zur Ausführungszeit einzusetzen (z. B. einen berechneten
Durchschnittspreis als Schwellenwert in einem späteren Filter-Step), aber
sie können nicht die *Form* des Plans selbst verändern.

**Die Grenze wird sichtbar, sobald eine Frage einen Kontrollfluss enthält** —
also eine Entscheidung, die erst mit einer echten Zwischenzahl getroffen
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

## V2: Grenzen und die Motivation für V3

V2 löst das Kontrollfluss-Problem, indem es Entscheidungen erst nach echten
Zwischenergebnissen trifft (`done`-gesteuert). Aber es gibt eine neue,
**andere** Fehlerklasse: Das Modell kann einen Plan liefern, der **strukturell
ungültig** ist — und V2 führt ihn trotzdem aus.

**Beispiele für strukturell ungültige Pläne:**

- `filterByCategory` mit `operand2="electronic"` (Tippfehler) statt
  `"electronics"` → liefert still 0 Produkte, obwohl es Elektronik gibt.
- `filterByPrice` mit `operand2="="` statt `"=="` → der Operator ist kein
  bekannter Wert, das Tool gibt einen Fehler zurück.
- `filterByPrice` mit `operand3="teuer"` statt einer Zahl → nicht ausführbar.
- Ein unbekanntes Tool (`tool="filterByCategry"`) → "unknown tool".

Das Problem: **Der Fehler passiert erst zur Laufzeit** — und je nach Tool
entweder als stille Falschantwort (falsche Kategorie) oder als generischer
Fehler, der im Log untergeht. Der Agent "merkt" es nicht, weil es keine
zweite Iteration gibt (One-Shot).

**Das ist die Motivation für V3:** eine **strukturelle Verifikation VOR der
Ausführung**. Jeder Plan wird gegen ein Schema geprüft:

- bekannte Kategorien (`electronics`, `jewelery`, `men's clothing`,
  `women's clothing`),
- erlaubte Operatoren (`<`, `<=`, `==`, `>`, `>=`),
- Pflichtfelder (`operand1`/`operand2`/`operand3` je nach Tool),
- numerische Preis-Schwellen,
- bekannte Tool-Namen.

Ungültige Steps werden **NICHT ausgeführt**, sondern durch ein
`__validation_error__`-Ergebnis ersetzt, das den konkreten Grund enthält.
So bleibt die `$results[i]`-Indizierung stabil und der Fehler ist **sichtbar
im Log** — statt einer stillen Falschantwort.

> **Wichtig:** V3 korrigiert NICHT automatisch (das ist V4). Es erkennt und
> meldet nur. Die Verifikation ist für gültige Pläne unsichtbar — alle
> bisherigen V1/V2-Referenzfragen laufen unverändert.

Die Testfälle für V3 stehen in [`docs/v3-test-cases.md`](docs/v3-test-cases.md).

---

## V3: Grenzen und die Motivation für V4

V3 erkennt strukturell ungültige Pläne **vor** der Ausführung und ersetzt
ungültige Steps durch einen sichtbaren `__validation_error__`. Aber es gibt
eine neue, **andere** Fehlerklasse: **echte Tool-Laufzeitfehler**, die V3
nicht vorhersehen kann.

**Beispiele für Laufzeitfehler, die V3 nicht abfängt:**

- Die Fake Store API ist kurz nicht erreichbar (`getProducts` wirft einen
  Netzwerkfehler).
- Ein Produkt hat ein unerwartetes Feldformat (z. B. `price` als String
  statt Zahl), sodass `sum`/`average` fehlschlägt.
- Ein `$results[i]`-Verweis zeigt auf einen Index, der nicht existiert.

Das Problem: **V3 meldet den Fehler nur** — es gibt keine zweite Iteration,
in der das Modell den Plan korrigieren könnte. Der Lauf endet mit einem
Fehler, obwohl das Modell die Frage eigentlich beantworten könnte.

**Das ist die Motivation für V4:** ein **technischer Retry (Self-Healing)**.
Fehlgeschlagene Steps (V3-Validierungsfehler ODER echte Tool-Laufzeitfehler)
werden als Text an das Modell zurückgegeben. Das Modell bekommt eine
begrenzte Anzahl Korrektur-Versuche (`max_retries`) und kann den Plan
reparieren — z. B. den Operator korrigieren, die Kategorie richtig
schreiben oder einen fehlenden `$results`-Verweis auflösen.

> **Wichtig:** V4 korrigiert nur **technische** Fehler (Struktur, Laufzeit).
> Es ist kein Reasoning-Loop — die inhaltliche Qualität der Antwort bleibt
> Aufgabe des Prompts.

Die Testfälle für V4 stehen in [`docs/v4-test-cases.md`](docs/v4-test-cases.md).

---

## Lizenz

Didaktisches Projekt, freie Verwendung.






