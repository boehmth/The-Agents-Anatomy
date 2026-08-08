# Die technischen Evolutionsstufen des Agents

Dieses Dokument beschreibt die **schrittweise technische Evolution** des
Agents. Jede Stufe wird erklärt und beispielhaft implementiert — die Stufen
bauen logisch aufeinander auf: Erst wenn die Grundmechanik steht, lohnt sich
der nächste Schritt.

| Version | Technik | Warum an dieser Stelle |
|---------|---------|------------------------|
| **v1** ✅ vorhanden | Single-Shot Plan-and-Execute, `$results`-Referenzen | Grundmechanik: Plan → Tool-Zuordnung → Ausführung |
| **v2** ✅ vorhanden | Echter Mehrschritt-Loop (ReAct-Prinzip): planen → ausführen → echte Ergebnisse sehen → weiterplanen, bis `done` | Ohne das ist alles danach witzlos — Reasoning über erfundene Zahlen ist kein Reasoning. Hier als dokumentierte Stufe mit Vorher/Nachher-Vergleich |
| **v3** ✅ vorhanden | Strukturelle Verifikation: Plan-JSON gegen Schema prüfen (fehlende Felder, falscher Typ, bekannte Kategorien/Operatoren) | Fundament für Retry — man muss zuerst erkennen, dass etwas falsch ist, bevor man es korrigieren kann |
| **v4** ✅ vorhanden | Technischer Retry-Mechanismus: Bei Tool-Fehler oder Schema-Verstoß wird der Fehler als Text an das Modell zurückgegeben ("dein letzter Step ist fehlgeschlagen: ungültige Kategorie 'electronic' — korrigiere") statt nur geloggt. Begrenzt auf z. B. 2–3 Versuche | Klassisches "self-healing agent"-Pattern — genau der Fehlertyp, den wir im Log mehrfach gesehen haben (falsche Kategorie, falscher Operator), wurde bisher nie korrigiert, nur dokumentiert |
| **v5** | Reasoning/Thinking vor dem Plan: explizites Scratchpad-Feld oder natives Thinking (z. B. Claude Extended Thinking, o-Serie mit `reasoning_effort`) vor der JSON-Antwort, statt nur ein `analysis`-Feld als Pflicht-Attrappe | Baut auf v2–v4 auf: erst wenn der Loop technisch stabil ist, lohnt sich der Vergleich "freies Reasoning vs. harte Regel" — sonst vermischt man wieder zwei Fehlerquellen |
| **v6** | Modell-Routing/Eskalation: gpt-4.1-mini versucht zuerst; meldet das Modell selbst Unsicherheit (z. B. ein `confidence: "low"`-Feld oder ein Parsing-/Retry-Fehlschlag nach v4), wird mit einem stärkeren Reasoning-Modell erneut versucht | Braucht v3/v4 als Unsicherheits-/Fehler-Erkennung — sonst hat man kein Kriterium, WANN eskaliert wird |


## Weitere Stufen (Ausblick, nicht sofort)

| Version | Technik | Warum an dieser Stelle |
|---------|---------|------------------------|
| **v7** | Reflexion/Gedächtnis über Tage hinweg: der Agent schreibt sich kurze Notizen ("letzte Woche wurde die Kategorie 'electronic' fälschlich als gültig angenommen"), die in künftige Prompts einfließen (Reflexion-Pattern) | Lernen aus eigener Historie über einzelne Läufe hinaus |
| **v8** | Kritiker/Gegenkontrolle: ein zweiter LLM-Aufruf prüft den Plan des ersten, bevor er ausgeführt wird (Separation of Concerns, "Vier-Augen-Prinzip" für Agenten) | Qualitätssicherung durch unabhängige Prüfung |
| **v9** | Natives Function-Calling statt Text-JSON: Vergleich des handgebauten `$results`-Mechanismus mit der nativen Tool-Use-API der Provider | Guter Lerneffekt, warum wir es zu Lehrzwecken selbst gebaut haben |
| **v10** | Eval-Harness statt nur manueller Tests: feste Referenzfragen mit erwartetem qualitativem Verhalten (nicht nur "läuft durch", sondern korrekte Antwort) | Ähnlich Unit-Tests fürs Agentenverhalten selbst |


## Stand

- **v1** ist implementiert und getestet (`test.py`).
- **v2** ist implementiert (Mehrschritt-Loop, `done`-gesteuert) und verifiziert
  (`test_v2_loop.py`, Referenzfragen in `docs/v2-test-cases.md`).
- **v3** ist implementiert (strukturelle Verifikation, `runner/validate.py`,
  Testfälle in `docs/v3-test-cases.md`).
- **v4** ist implementiert (technischer Retry, `runner/loop.py`,
  Testfälle in `docs/v4-test-cases.md`).
- **v5–v6** sind als nächste dokumentierte Stufen vorgesehen.
- **v7–v10** sind bewusst nur als Ausblick gelistet.


