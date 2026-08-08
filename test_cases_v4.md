# V4 — Referenz-/Testfälle (Technischer Retry)

Diese Fälle bauen direkt auf `docs/v3-test-cases.md` auf. Der Unterschied:
Bei V3 endet der Test mit einem sichtbaren, aber unkorrigierten
Validierungsfehler. Bei V4 muss derselbe Fehler zu einer **erzwungenen
Zusatzrunde mit Fehler-Feedback** führen, in der das Modell den Step
korrigiert -- der Nutzer bekommt am Ende die richtige Antwort.

Wie in `v3-test-cases.md`: Zeilen mit echtem Prompt hängen vom verwendeten
Modell ab (reproduzierbar, aber nicht 100% deterministisch); die
Plan-Manipulationstests (direkt injizierter fehlerhafter Step) sind der
zuverlässigere Teil der Abnahme.

| Nr | Test | Fehlerhafter Step | Verhalten V3 (nur sichtbar) | Verhalten V4 (mit Retry) |
|----|---|---|---|---|
| 1 | "Wie hoch ist der Durchschnittspreis der Schmuckprodukte?" | `filterByCategory(category="jewellery")` (br. Schreibweise) | Validierungsfehler im Log, keine Antwort | Retry 1: Fehler-Feedback ("category='jewellery' ist kein bekannter Wert...") → Modell korrigiert zu `"jewelery"` → korrekter Durchschnittspreis |
| 2 | "Wie viele Damenbekleidungsartikel kosten mehr als 50 €?" | `filterByCategory(category="women clothing")` (Apostroph fehlt) | Validierungsfehler, keine Antwort | Retry 1: Modell korrigiert zu `"women's clothing"` → korrekte Anzahl |
| 3 | "Wie viele Produkte kosten genau 29.99 €?" | `filterByPrice(operator="=")` | Validierungsfehler, keine Antwort | Retry 1: Modell korrigiert zu `"=="` → korrekte Anzahl |
| 4 | *(Plan-Manipulation)* — Step ohne `category`-Feld | fehlendes Pflichtfeld | Validierungsfehler "Pflichtfeld 'category' fehlt" | Retry 1: Modell ergänzt das fehlende Feld korrekt |
| 5 | "Wie hoch ist der Durchschnittspreis der Kategorie 'Bücher'?" | Es gibt im Shop keine Kategorie "Bücher" -- egal wie das Modell den String schreibt, er wird nie in `KNOWN_CATEGORIES` stehen | Validierungsfehler, keine Antwort | **Bewusst NICHT korrigierbar:** Retry 1 und Retry 2 schlagen ebenfalls fehl (das Modell kann keine Kategorie erfinden, die es nicht gibt) → nach `max_retries` kontrollierter Abbruch mit klarer Fehlermeldung, KEINE Endlosschleife |
| 6 | *(Plan-Manipulation)* — zwei fehlerhafte Steps gleichzeitig im selben Plan (falsche Kategorie UND falscher Operator) | zwei unabhängige Fehler in einer Runde | Beide Validierungsfehler stehen im Log | Ein einziges Retry-Feedback listet BEIDE Fehler auf (`_render_error_feedback` mit mehreren Einträgen) → Modell korrigiert beide in einem Rutsch, kein zweifacher Retry-Verbrauch nötig |

**Hinweis zur Nutzung:** Fall 5 ist der wichtigste Test für die
Sicherheitsnetz-Eigenschaft von V4 — er beweist, dass der Retry-Mechanismus
kontrolliert aufgibt, statt bei einem strukturell unlösbaren Problem in
eine Endlosschleife zu laufen. Ohne diesen Test bleibt "Retries sind
begrenzt" eine unbewiesene Behauptung im Code.