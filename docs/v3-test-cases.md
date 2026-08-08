# V3-Testfälle — Strukturelle Verifikation

Diese Referenztabelle enthält die V3-Testfälle für die strukturelle
Verifikation eines Plans VOR der Ausführung. V3 erkennt und meldet
ungültige Steps — es korrigiert NICHT automatisch (das ist V4).

**Erwartung:** Ein ungültiger Step wird NICHT ausgeführt. Stattdessen
erscheint im Log ein klar sichtbarer Validierungsfehler, und das
Ergebnis an der Stelle `$results[i]` ist ein `{"error": ...}`-Objekt
mit dem konkreten Grund — keine stille Falschantwort.

> Hinweis: Die Validierung greift nur bei **ungültigen** Plänen. Für
> gültige Pläne (alle bisherigen V1/V2-Fragen) ändert sich sichtbar
> nichts.

## Testfälle

| # | Szenario | Ungültiger Step | Erwarteter Validierungsfehler |
|---|----------|-----------------|-------------------------------|
| 1 | Falsche Kategorie (Tippfehler) | `filterByCategory` mit `operand2="electronic"` (statt `"electronics"`) | `'filterByCategory': 'operand2'='electronic' ist kein bekannter Wert. Erlaubt: [...]` |
| 2 | Falsche Kategorie (britische Schreibweise) | `filterByCategory` mit `operand2="jewellery"` (statt `"jewelery"`) | `'filterByCategory': 'operand2'='jewellery' ist kein bekannter Wert. Erlaubt: [...]` |
| 3 | Ungültiger Operator | `filterByPrice` mit `operand2="="` (statt `"=="`) | `'filterByPrice': 'operand2'='=' ist kein bekannter Wert. Erlaubt: ['<', '<=', '==', '>', '>=']` |
| 4 | Ungültiger Operator | `filterByPrice` mit `operand2="gt"` | `'filterByPrice': 'operand2'='gt' ist kein bekannter Wert. Erlaubt: [...]` |
| 5 | Fehlendes Pflichtfeld | `filterByCategory` ohne `operand2` (Kategorie) | `'filterByCategory': Pflichtfeld 'operand2' fehlt` |
| 6 | Fehlendes Pflichtfeld | `filterByPrice` ohne `operand3` (Preis-Schwelle) | `'filterByPrice': Pflichtfeld 'operand3' fehlt` |
| 7 | Nicht-numerische Preis-Schwelle | `filterByPrice` mit `operand3="teuer"` | `'filterByPrice': 'operand3'='teuer' muss eine Zahl sein (oder eine $results-Referenz)` |
| 8 | Unbekanntes Tool | `tool="filterByCategry"` (Tippfehler) | `unbekanntes Tool 'filterByCategry'` |
| 9 | Falsche operation | `getProducts` mit `operation="load"` | `'getProducts': 'operation'='load' ist kein bekannter Wert. Erlaubt: ['get']` |

## Gültige Pläne (müssen weiterhin durchlaufen)

Diese Fälle dürfen von der Validierung NICHT als ungültig markiert
werden — insbesondere `$results[i]`-Referenzen:

| # | Szenario | Step | Erwartung |
|---|----------|------|-----------|
| 10 | `$results`-Referenz als Kategorie | `filterByCategory` mit `operand2="$results[0].category"` | Kein Fehler (Referenz wird zur Laufzeit aufgelöst) |
| 11 | `$results`-Referenz als Operator | `filterByPrice` mit `operand2="$results[1].operator"` | Kein Fehler |
| 12 | `$results`-Referenz als Preis-Schwelle | `filterByPrice` mit `operand3="$results[2].average"` | Kein Fehler |
| 13 | Gültige Kategorie | `filterByCategory` mit `operand2="electronics"` | Kein Fehler |
| 14 | Gültiger Operator | `filterByPrice` mit `operand2=">="` und `operand3="100"` | Kein Fehler |

## Testkommandos

```bash
# V1/V2-Regression: gültige Pläne müssen unverändert laufen
python agent.py --prompt-version v1 "Wie viele Elektronikprodukte kosten mehr als 100 €?"
python agent.py --prompt-version v2 "Zähle zuerst alle Elektronikprodukte über 300 €. Nur falls es mehr als 5 sind, berechne zusätzlich deren Durchschnittspreis."

# V3: Tippfehler-Fall provozieren (z. B. durch ein schwächeres Modell oder
# einen testweise manipulierten System-Prompt mit "electronic" statt
# "electronics" im Beispiel)
python agent.py --prompt-version v3 "Wie viele Elektronikprodukte kosten mehr als 100 €?"
```

## Abnahmekriterien für V3

- [ ] Alle bisherigen V1/V2-Referenzfragen liefern unverändert korrekte
      Ergebnisse (Validierung ist für gültige Pläne unsichtbar).
- [ ] Ein Plan mit falscher Kategorie (`"electronic"`) führt NICHT zu
      einer stillen Falschantwort, sondern zu einem klar sichtbaren
      Validierungsfehler im Log, referenzierbar über den korrekten
      `$results[i]`-Index.
- [ ] Ein Plan mit ungültigem Operator (z. B. `"="` statt `"=="`)
      verhält sich identisch.
- [ ] `$results[i]`-Referenzen (Strings, die mit `$results[` beginnen)
      werden von der Enum-/Typ-Prüfung NICHT fälschlich als ungültig
      markiert.
- [ ] `tools/` und `model/` sind unverändert (Diff prüfen).
