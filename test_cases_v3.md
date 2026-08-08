# V3 — Referenz-/Testfälle (Strukturelle Verifikation)

Diese Fälle sind bewusst so gewählt, dass sie **still falsche Ergebnisse**
provozieren würden, ohne dass ein Tool jemals einen technischen Fehler
wirft. V1 und V2 sehen das nicht — sie führen den fehlerhaften Step einfach
aus und liefern eine plausibel aussehende, aber bedeutungslose Zahl.

Da echte Modelle solche Tippfehler nicht auf Kommando reproduzieren, sind
die "User-Prompts" hier absichtlich so formuliert, dass sie zu einer
knappen Formulierung verleiten, bei der ein Modell (v. a. ein kleineres)
öfter danebenliegt. Zusätzlich: die letzten zwei Zeilen sind direkte
Plan-Manipulationstests (kein Prompt, sondern ein von Hand injizierter
fehlerhafter Step) — nützlich, um V3 auch OHNE auf einen zufälligen
Modellfehler warten zu müssen.

| Nr | Test | Fehlerhafter Step (typisch) | Erwartetes Verhalten V1/V2 (fehlerhaft) | Erwartetes Verhalten V3 |
|----|---|---|---|---|
| 1 | "Wie hoch ist der Durchschnittspreis der Schmuckprodukte?" | `filterByCategory(category="jewellery")` (br. Schreibweise statt `jewelery`) | Leere Liste → `average` liefert `0`/Fehler, aber ohne erkennbare Ursache | Validierungsfehler: "'category'='jewellery' ist kein bekannter Wert. Erlaubt: [...]" — Step wird nicht ausgeführt |
| 2 | "Wie viele Damenbekleidungsartikel kosten mehr als 50 €?" | `filterByCategory(category="women clothing")` (Apostroph vergessen) | Leere Liste → `count` liefert `0`, sieht aus wie ein valides Ergebnis | Validierungsfehler, Step wird nicht ausgeführt |
| 3 | "Wie viele Produkte kosten genau 29.99 €?" | `filterByPrice(operator="=")` statt `"=="` | Je nach Tool-Implementierung: Crash ODER stiller Fallback | Validierungsfehler: "'operator'='=' ist kein bekannter Wert. Erlaubt: ['<','<=','==','>','>=']" |
| 4 | "Wie teuer sind alle Produkte über 'hundert' Euro zusammen?" | `filterByPrice(value="100")` (String statt Zahl) | Je nach Tool-Implementierung: TypeError beim Vergleich, oder String-Vergleich liefert falsches Ergebnis | Validierungsfehler: "'value'='100' hat falschen Typ (erwartet (int, float))" |
| 5 | *(Plan-Manipulation, kein echter Prompt)* — Step ohne `category`-Feld: `filterByCategory(products="$results[0].products")` | fehlendes Pflichtfeld | `KeyError` oder stiller Fallback auf `None`/alle Produkte | Validierungsfehler: "Pflichtfeld 'category' fehlt" |
| 6 | *(Plan-Manipulation)* — `$results[3].result` als `category`-Wert (Zahl statt String, falscher Verweis) | falscher Referenz-Typ | Leere Liste oder Crash, je nach Tool | Wird NICHT fälschlich als "$results-Referenz, also ok" durchgewunken — prüfen, dass die Validierung hier trotzdem greift, da der Wert zur Planungszeit kein gültiger `$results[i]`-String-Präfix-Fall mehr ist, falls er anders formatiert ankommt (Edge Case, im Code-Review gegenchecken) |

**Hinweis zur Nutzung:** Zeilen 1–4 sind "natürliche" Testfälle (echter
Prompt an ein Modell) — ihr Ausgang hängt vom verwendeten Modell ab und ist
nicht 100% reproduzierbar. Zeilen 5–6 sind deterministische
Regressionstests: einen Plan von Hand (z. B. in `test.py`) mit dem
fehlerhaften Step bauen und direkt `validate_plan()` bzw. den kompletten
Loop darauf loslassen — das ist der zuverlässigere Teil der Abnahme.