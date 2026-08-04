# The Agents Anatomy

Ein didaktischer, LLM-basierter Trading-Agent, der einmal pro Tag Kurse
analysiert und über den Kauf/Verkauf von Aktien entscheidet.

**Ziel dieses Projekts**: Zeigen, wie **dynamisches Tool-Calling** funktioniert
— und wie sich die Qualität eines Agents allein durch Textänderungen
(**Prompt Engineering**) verbessern lässt, ohne den Code anzufassen.

---

## Architektur

```
The-Agents-Anatomy/
├── agent.py                # CLI: ein einzelner Agent-Lauf
├── simulate.py             # CLI + Library: N-Tage-Simulation
├── benchmark.py            # Fährt mehrere Modelle gegeneinander
├── report.py               # Baut aus data/leaderboard.csv eine HTML-Seite
├── plot.py                 # Equity-Kurve + Trade-Marker
│
├── prompts/                # ← reine Texte (Prompt-Versionen)
│   ├── v1/
│   ├── CHANGELOG.md
│
├── runner/                 # Orchestrator (Iterations-Loop, $results-Resolver)
├── model/                  # LLM-Provider (Gemini, OpenAI, DeepSeek, SAP GenAI Hub)
├── tools/                  # get_prices, calculator, portfolio
├── clock.py                # simuliertes "heute"
├── price_cache.py          # yfinance-Vorab-Cache
│
└── .github/workflows/      # GitHub Actions: täglicher Benchmark
```

Die Ebenen des Agents sind **sauber getrennt**:
- **Texte** (`prompts/`) → beschreiben *was* der Agent tun soll.
- **Runner** (`runner/`) → führt die vom Modell gelieferten Steps aus.
- **Model** (`model/`) → tauschbar (Gemini / OpenAI / SAP GenAI Hub / …).
- **Tools** (`tools/`) → was der Agent in der Welt tun kann.

---

## Wie der Agent arbeitet (Blockdiagramm)

Der Agent ist bewusst einfach gehalten: Er besteht aus **genau zwei Teilen** —
`call_llm()` (Plan holen) und `process_steps()` (Steps ausführen).

```
                    ┌─────────────────────────────────────────────┐
                    │              SYSTEM-PROMPT                  │
                    │  (prompts/<version>/system_prompt.txt)      │
                    │  + Tool-Beschreibungen (tool_descriptions)  │
                    └───────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────▼─────────────────────────┐
                    │  1. call_llm() → JSON-Plan                 │
                    │     { "steps": [...], "done": true|false }  │
                    └───────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────▼─────────────────────────┐
                    │  2. process_steps() → Steps ausführen      │
                    │     get_prices / calculator / portfolio     │
                    └───────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────▼─────────────────────────┐
                    │  Ergebnisse in `results` merken             │
                    │  ($results[i].key-Referenzen)               │
                    └─────────────────────────────────────────────┘
```

**Die zwei Teile im Detail:**

1. **call_llm()** — Das Modell erhält das Tagesziel (mit Datum) und liefert
   einen JSON-Plan mit `steps` (Tool-Aufrufe) und `done` (fertig ja/nein).
2. **process_steps()** — Der Runner führt jeden Step der Reihe nach aus.
   Jedes Ergebnis landet in `results`. Ein späterer Step kann per
   `$results[i].key` auf ein früheres Ergebnis zugreifen, statt den Step zu
   wiederholen. Die Tools greifen auf `clock.today()` zu, damit alles am
   simulierten "heute" stattfindet.

### Beispiel: Ein konkreter Plan

So könnte der Agent an einem Tag antworten — ein einziger Plan mit allen
Schritten (Bestandsaufnahme → Analyse → Micro-Trade). In v1 handelt der Agent
bewusst klein: **maximal 1 Aktie pro Tag**.

```json
{
  "steps": [
    { "tool": "portfolio", "args": { "operation": "load", "operand1": "", "operand2": "" },
      "description": "Aktuellen Cash- und Holdings-Stand laden" },
    { "tool": "get_prices", "args": { "operation": "get", "operand1": "NVDA", "operand2": "20" },
      "description": "NVDA-Historie für die 5-Tage-Rendite" },
    { "tool": "get_prices", "args": { "operation": "get", "operand1": "MSFT", "operand2": "20" },
      "description": "MSFT-Historie für die 5-Tage-Rendite" },
    { "tool": "calculator",
      "args": { "operation": "subtract",
                "operand1": "$results[1].latest.close",
                "operand2": "$results[1].prices.15.close" },
      "description": "NVDA 5-Tage-Differenz" },
    { "tool": "calculator",
      "args": { "operation": "subtract",
                "operand1": "$results[2].latest.close",
                "operand2": "$results[2].prices.15.close" },
      "description": "MSFT 5-Tage-Differenz" },
    { "tool": "portfolio",
      "args": { "operation": "buy", "operand1": "NVDA",
                "operand2": "1@$results[1].latest.close" },
      "description": "Portfolio ist leer; NVDA ist stärker; 1 NVDA kaufen" }
  ],
  "done": true
}
```

Die Steps werden der Reihe nach ausgeführt. `$results[1]` verweist auf das
Ergebnis von Step 1 (get_prices NVDA), `$results[2]` auf Step 2 (get_prices
MSFT) — so nutzt der Agent die frisch geladenen Kurse, ohne sie als Zahlen
zu kodieren.

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
LLM_PROVIDER=sap              # oder "gemini" / "openai" / "deepseek"
PROMPT_VERSION=v1
TICKERS=NVDA,MSFT

# Für SAP GenAI Hub:
SAP_GENAI_SERVICE_KEY_FILE=./.sap_service_key.json
SAP_GENAI_MODEL=anthropic--claude-4.7-opus
SAP_GENAI_RESOURCE_GROUP=default

# Für Gemini:
GOOGLE_API_KEY=...

# Für OpenAI:
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini

# Für DeepSeek (OpenAI-kompatible API):
DEEPSEEK_API_KEY=...
DEEPSEEK_MODEL=deepseek-chat
```

### 3. Service-Key hinterlegen
Für den SAP GenAI Hub die JSON-Datei mit dem Service-Key als
`.sap_service_key.json` im Projekt-Root ablegen. Sie ist in `.gitignore`.

---

## Ein einzelner Agent-Lauf

```bash
python agent.py
python agent.py --model gpt-4o --prompt-version v1
python agent.py --as-of 2025-11-14
```

## Eine 5-Tage-Simulation

```bash
python simulate.py --days 5
python simulate.py --days 15 --model gpt-5.6 --prompt-version v1
```

Output in `data/`:
- `portfolio.csv` — Cash- und Holdings-Verlauf.
- `trades.csv` — Trade-Log (Kauf/Verkauf mit Preis).
- `agent_log.jsonl` — pro Tag: Modell-Plan und Tool-Ergebnisse
  (didaktisch hilfreich zum Nachvollziehen des Loops).
- `simulation_equity.csv` — täglicher Kontostand.
- `simulation.png` — Equity-Kurve mit Buy/Sell-Markern.
- `summary.json` — kompakte Zusammenfassung (P&L, Trades, Audit).

## Modelle vergleichen (Benchmark)

```bash
python benchmark.py --days 5
# oder mit expliziter Modellliste:
python benchmark.py --days 5 \
    --models gpt-4o-mini,gpt-4o,anthropic--claude-4.7-opus \
    --prompt-version v1
```

Output pro Lauf:
```
data/runs/<YYYY-MM-DD>/<model>/
    portfolio.csv
    trades.csv
    simulation_equity.csv
    simulation.png
    summary.json
```

Zusätzlich wird `data/leaderboard.csv` ergänzt — eine Zeile pro Modell pro
Datum, ideal für den Zeitreihen-Vergleich.

## HTML-Report

```bash
python report.py
```

Baut aus `data/leaderboard.csv` eine `docs/index.html`. Zeigt:
- Letzten Lauf (Rangliste heute)
- Aggregat (Ø P&L, Best/Worst, Trades pro Modell)
- **Trade-Historie** (was wurde wann gekauft/verkauft, aus `data/runs/`)
- Zeitreihe des P&L pro Modell

## Täglicher GitHub-Benchmark

Der Workflow `.github/workflows/daily-benchmark.yml` läuft werktags um 20:00 UTC
und tut:

1. Schreibt aus dem GitHub-Secret `SAP_GENAI_SERVICE_KEY_JSON` die Datei
   `.sap_service_key.json`.
2. Führt `python benchmark.py --days 5` aus.
3. Baut den HTML-Report.
4. Löscht die Service-Key-Datei.
5. Commited `data/` und `docs/` zurück ins Repo.
6. Deployed `docs/` auf GitHub Pages.

**Benötigte Secrets** (Settings → Secrets and variables → Actions):
- `SAP_GENAI_SERVICE_KEY_JSON` — der komplette JSON-Inhalt des Service-Keys.

**Manuell auslösen**: `Actions → Daily Benchmark → Run workflow`.

---

## Prompt-Versionen

Der Agent liest aus `prompts/<PROMPT_VERSION>/`. Wechseln über `.env` oder
CLI-Argument `--prompt-version`.

Aktuell gibt es **eine** Version (`v1`), die zum Single-Shot-Runner passt:

| Version | Fokus |
|---------|-------|
| v1 | Minimal autonomer Micro-Trading-Agent: Single-Shot-Tagesplan, `$results`-Referenzen, Relative Stärke (NVDA vs. MSFT), maximal 1 Aktie pro Tag, Einstiegspflicht bei leerem Portfolio, Beispiel-Plan |

Die Iterations-Historie (v1–v6) ist in `prompts/CHANGELOG.md` dokumentiert.
Die Versionen v2–v6 wurden entfernt, weil sie dem didaktischen Anspruch
nicht genügten; die Erkenntnisse daraus sind in den neu strukturierten
v1-Prompt eingeflossen.

---

## Sicherheit

- Service-Keys **niemals** ins Repo commiten. Der Workflow zieht sie zur
  Laufzeit aus GitHub Secrets.
- `.gitignore` blockiert alle üblichen Secret-Dateien.
- **Privates Repo** wird empfohlen für Produktions-Setup.

---

## Lizenz

Didaktisches Projekt, freie Verwendung.