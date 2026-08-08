# V4-Testfälle — Technischer Retry (Self-Healing)

Diese Referenztabelle enthält die V4-Testfälle für den **technischen Retry**.
V4 baut auf V3 auf: Fehlgeschlagene Steps (V3-Validierungsfehler ODER echte
Tool-Laufzeitfehler) werden als Text an das Modell zurückgegeben, und das
Modell bekommt eine begrenzte Anzahl Korrektur-Versuche (`max_retries`,
Default 2).

**Erwartung:** Ein fehlgeschlagener Step wird NICHT einfach geloggt und
verworfen. Stattdessen erzwingt der Loop eine Korrektur-Runde, in der das
Modell den fehlerhaften Step reparieren kann (z. B. richtige Kategorie,
richtiger Operator, richtiger Typ). Am Ende steht eine korrekte Antwort —
nicht nur ein sauber dokumentierter Fehler.

> **Wichtig:** V4 korrigiert nur **technische** Fehler (Struktur, Laufzeit).
> Es ist kein Reasoning-Loop — die inhaltliche Qualität der Antwort bleibt
> Aufgabe des Prompts.

## Testfälle

| # | Szenario | Fehlerhafter Step | Erwarteter Retry-Verlauf |
|---|----------|-------------------|--------------------------|
| 1 | Falsche Kategorie (Tippfehler) | `filterByCategory` mit `operand2="electronic"` (statt `"electronics"`) | Runde 1: V3-Validierungsfehler. Runde 2 (Retry): Modell korrigiert zu `"electronics"`, Plan läuft durch, korrekte Antwort. |
| 2 | Ungültiger Operator | `filterByPrice` mit `operand2="="` (statt `"=="`) | Runde 1: V3-Validierungsfehler. Runde 2 (Retry): Modell korrigiert zu `">"`, Plan läuft durch. |
| 3 | Nicht-numerische Preis-Schwelle | `filterByPrice` mit `operand3="teuer"` | Runde 1: V3-Validierungsfehler. Runde 2 (Retry): Modell setzt eine Zahl ein. |
| 4 | Unbekanntes Tool | `tool="filterByCategry"` | Runde 1: V3-Validierungsfehler. Runde 2 (Retry): Modell nutzt `filterByCategory`. |
| 5 | Echter Tool-Laufzeitfehler | `$results[i]`-Verweis auf nicht existierenden Index | Runde 1: Tool-Laufzeitfehler. Runde 2 (Retry): Modell referenziert einen gültigen Index. |
| 6 | Wiederholter Fehler (Modell korrigiert nicht) | Modell macht denselben Fehler erneut | Nach `max_retries` (2) Versuchen gibt der Loop auf und endet mit dem Fehler — keine Endlosschleife. |

## Testkommandos

```bash
# V4 — Retry (Self-Healing)
python agent.py --agent-version v4 "Wie viele Elektronikprodukte kosten mehr als 100 €?"

# V4 — Tippfehler-Fall provozieren (z. B. durch ein schwächeres Modell oder
# einen testweise manipulierten System-Prompt mit "electronic" statt
# "electronics" im Beispiel)
python agent.py --agent-version v4 "Wie viele Elektronikprodukte kosten mehr als 100 €?"
```

## Abnahmekriterien für V4

- [ ] Ein fehlgeschlagener Step (V3-Validierungsfehler ODER echter
      Tool-Laufzeitfehler) erzwingt eine Korrektur-Runde.
- [ ] Das Modell bekommt den Fehler als Text zurückgegeben und kann den
      fehlerhaften Step reparieren.
- [ ] Retries sind strikt begrenzt (`max_retries`, Default 2) und UNABHÄNGIG
      von `max_iterations` — es entsteht keine Endlosschleife.
- [ ] Bereits erfolgreiche Steps werden NICHT wiederholt, sondern per
      `$results[i]` referenziert.
- [ ] Am Ende steht eine korrekte Antwort, nicht nur ein dokumentierter
      Fehler.
- [ ] Alle bisherigen V1/V2/V3-Referenzfragen laufen unverändert korrekt
      (Retry ist für gültige Pläne unsichtbar).
