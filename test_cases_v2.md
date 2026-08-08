# V2 — Referenz-/Testfragen (Mehrschritt-Loop)

Diese Fragen sind bewusst so gewählt, dass sie **strukturell nicht in einer
einzigen Runde planbar sind** — nicht weil sie mehr Steps brauchen (das kann
V1 auch), sondern weil die *Existenz* oder *Auswahl* eines Steps von einem
echten Zwischenergebnis abhängt, das erst nach Ausführung vorliegt.

Zur Abgrenzung: Alle 15 V1-Referenzfragen müssen mit `--prompt-version v2`
weiterhin korrekt funktionieren (typischerweise in einer einzigen Runde,
`done: true` sofort) — V2 ist eine Erweiterung, keine Ablösung von V1.

| Nr | User-Prompt | Warum V1 (One-Shot) hier strukturell scheitert | Erwartete Werkzeugkette (V2, über zwei Runden) |
|----|---|---|---|
| 1 | Zähle zuerst alle Elektronikprodukte über 300 €. Nur falls es mehr als 5 sind, berechne zusätzlich deren Durchschnittspreis. | Ob der `average`-Step überhaupt geplant wird, hängt vom echten `count`-Ergebnis ab. | R1: `getProducts → filterByCategory → filterByPrice → count` (done:false). R2: je nach echtem `count` entweder zusätzlich `average`, oder fertig. |
| 2 | Ermittle die Anzahl der Schmuckprodukte. Falls es weniger als 3 sind, ermittle stattdessen die Anzahl der Elektronikprodukte. | Welche Kategorie am Ende überhaupt gezählt wird, steht erst nach dem ersten `count` fest. | R1: `getProducts → filterByCategory(jewelery) → count` (done:false). R2: je nach echtem `count` entweder fertig, oder `filterByCategory(electronics) → count`. |
| 3 | Prüfe, ob es mehr Herrenbekleidungs- oder Damenbekleidungsartikel gibt. Gib für die größere der beiden Gruppen den Gesamtwert aus. | Welche der beiden Gruppen weiterverarbeitet wird, ist ein Vergleich zweier noch unbekannter Zahlen. | R1: `getProducts → filterByCategory(men's clothing) → count`, `filterByCategory(women's clothing) → count` (done:false). R2: `sum` nur für die Kategorie mit dem größeren echten `count`. |
| 4 | Berechne die Anzahl aller Produkte unter 50 €. Wenn diese Zahl größer ist als die Anzahl aller Produkte über 200 €, gib den Durchschnittspreis der günstigen Produkte zurück, sonst den der teuren. | Zwei Zählungen müssen verglichen werden, bevor feststeht, welcher `average`-Step überhaupt drankommt. | R1: zwei `filterByPrice → count`-Ketten (done:false). R2: `average` nur für die Gruppe mit der größeren echten Anzahl. |
| 5 | Zähle die Elektronikprodukte. Falls mehr als 10 vorhanden sind, filtere zusätzlich auf Preise über 400 € und zähle erneut. | Der zweite Filter-Step existiert nur bedingt, abhängig vom ersten echten `count`. | R1: `getProducts → filterByCategory → count` (done:false). R2: je nach echtem `count` optional `filterByPrice → count`. |
| 6 | Ermittle den Durchschnittspreis aller Produkte. Falls dieser über 100 € liegt, zähle, wie viele Produkte teurer als das Doppelte dieses Durchschnitts sind — sonst, wie viele billiger als die Hälfte. | Sowohl die Bedingung als auch der Schwellenwert für `filterByPrice` hängen vom echten `average`-Ergebnis ab. | R1: `getProducts → average` (done:false). R2: `filterByPrice` mit Operator/Wert, die vom echten Durchschnitt abhängen, dann `count`. |
| 7 | Prüfe die Anzahl der Schmuckprodukte unter 50 €. Ist sie 0, sag das einfach so. Ist sie größer als 0, berechne zusätzlich deren Gesamtwert. | Der `sum`-Step existiert nur, wenn der echte `count` > 0 ist. | R1: `getProducts → filterByCategory → filterByPrice → count` (done:false). R2: je nach echtem `count` optional `sum`. |
| 8 | Finde heraus, ob es mehr als 20 Produkte insgesamt gibt. Falls ja, arbeite nur mit den Elektronikprodukten weiter (Durchschnittspreis). Falls nein, nimm alle Produkte für den Durchschnittspreis. | Der Umfang der Datenbasis für `average` (gefiltert oder ungefiltert) hängt vom echten Gesamt-`count` ab. | R1: `getProducts → count` (done:false). R2: je nach echtem `count` entweder `filterByCategory → average` oder direkt `average` auf allen Produkten. |

**Hinweis zur Nutzung:** Diese Tabelle ist die Abnahmegrundlage für V2 —
jede Zeile sollte über `python agent.py --prompt-version v2 "<Prompt>"`
reproduzierbar zum richtigen Ergebnis führen, inklusive korrektem
`done:false` in Runde 1 und `done:true` erst in Runde 2.