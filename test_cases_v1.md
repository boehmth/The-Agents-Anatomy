# V1 — Referenz-/Testfragen (One-Shot Plan-and-Execute)

Diese 15 Fragen sind die ursprüngliche Referenztabelle für V1. Sie sind
bewusst so gewählt, dass die Struktur des Plans (welche Tools, in welcher
Reihenfolge, mit welchen Kategorien/Operatoren) **vorab feststeht** —
unabhängig davon, welche konkreten Zahlen am Ende herauskommen. Genau
deshalb sind sie in einer einzigen Runde (`done: true` sofort) lösbar,
ohne dass der Agent echte Zwischenergebnisse abwarten müsste (siehe
[`README: V1 — Grenzen und die Motivation für V2`](README.md#v1-grenzen-und-die-motivation-für-v2)).

| Nr | User-Prompt | Erwartete Werkzeugkette |
|----|---|---|
| 1 | Wie viele Produkte gibt es insgesamt? | `getProducts → count` |
| 2 | Wie hoch ist der Durchschnittspreis aller Produkte? | `getProducts → average` |
| 3 | Wie teuer sind alle Produkte zusammen? | `getProducts → sum` |
| 4 | Wie viele Elektronikprodukte gibt es? | `getProducts → filterByCategory → count` |
| 5 | Wie hoch ist der Durchschnittspreis der Schmuckprodukte? | `getProducts → filterByCategory → average` |
| 6 | Wie teuer sind alle Damenbekleidungsartikel zusammen? | `getProducts → filterByCategory → sum` |
| 7 | Wie viele Produkte kosten mehr als 100 €? | `getProducts → filterByPrice → count` |
| 8 | Wie hoch ist der Durchschnittspreis aller Produkte unter 50 €? | `getProducts → filterByPrice → average` |
| 9 | Wie teuer sind alle Produkte unter 20 € zusammen? | `getProducts → filterByPrice → sum` |
| 10 | Wie viele Elektronikprodukte kosten mehr als 200 €? | `getProducts → filterByCategory → filterByPrice → count` |
| 11 | Wie hoch ist der Durchschnittspreis aller Schmuckprodukte unter 100 €? | `getProducts → filterByCategory → filterByPrice → average` |
| 12 | Wie teuer wären alle Herrenbekleidungsprodukte über 50 € zusammen? | `getProducts → filterByCategory → filterByPrice → sum` |
| 13 | Wie viele Produkte kosten zwischen 20 € und 80 €? | `getProducts → filterByPrice (>20) → filterByPrice (<80) → count` |
| 14 | Wie hoch ist der Durchschnittspreis aller Elektronikprodukte über 300 €? | `getProducts → filterByCategory → filterByPrice → average` |
| 15 | Wie teuer wären alle Schmuckartikel unter 150 € zusammen? | `getProducts → filterByCategory → filterByPrice → sum` |

**Hinweis zur Nutzung:** Diese Tabelle ist die Abnahmegrundlage für V1 —
und gleichzeitig die Regressionsgrundlage für alle Folgeversionen (V2, V3,
…): jede Zeile muss mit `python agent.py --prompt-version <vN> "<Prompt>"`
weiterhin korrekt und in der Regel weiterhin in einer einzigen Runde zum
richtigen Ergebnis führen, egal welche Version aktiv ist.