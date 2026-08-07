# V2-Testfälle — Kontrollfluss-Fragen (zwei Runden)

Diese Referenztabelle enthält die V2-Testfragen, die einen echten
Kontrollfluss erfordern. Sie werden mit `--prompt-version v2` getestet.

**Erwartung:** Runde 1 setzt `done: false` (nur die Steps, die ohne die
gesuchte Information ausführbar sind), Runde 2 setzt `done: true` (die
restlichen Steps, abhängig vom echten Zwischenergebnis).

> Hinweis: Die konkreten Zahlen hängen von den aktuellen Fake-Store-Daten
> ab (20 Produkte, 4 Kategorien). Die Spalte "Erwartung" beschreibt das
> *Muster* (Anzahl Runden, `done`-Verlauf, welche Tools), nicht die
> exakten Zahlen.

| # | Frage | Erwartung (Runden / done) | Erwartete Tools |
|---|-------|---------------------------|-----------------|
| 1 | Zähle zuerst alle Elektronikprodukte über 300 €. Nur falls es mehr als 5 sind, berechne zusätzlich deren Durchschnittspreis. | 2 Runden: R1 `done:false`, R2 `done:true` | R1: getProducts, filterByCategory, filterByPrice, count. R2: average (nur falls count > 5) |
| 2 | Wie viele Produkte kosten mehr als 100 €? Falls es mehr als 10 sind, nenne zusätzlich die Gesamtsumme dieser Produkte. | 2 Runden: R1 `done:false`, R2 `done:true` | R1: getProducts, filterByPrice, count. R2: sum (nur falls count > 10) |
| 3 | Welche Kategorie hat mehr Produkte: electronics oder jewelery? Nenne die größere Kategorie und ihre Produktanzahl. | 2 Runden: R1 `done:false`, R2 `done:true` | R1: getProducts, filterByCategory (electronics), count, filterByCategory (jewelery), count. R2: keine Steps (Vergleich in answer), `done:true` |
| 4 | Berechne den Durchschnittspreis aller Produkte. Falls der Durchschnitt über 150 € liegt, zähle zusätzlich die Produkte über 200 €. | 2 Runden: R1 `done:false`, R2 `done:true` | R1: getProducts, average. R2: filterByPrice, count (nur falls avg > 150) |
| 5 | Zähle alle Schmuckprodukte. Falls es weniger als 5 sind, berechne zusätzlich deren Gesamtsumme. | 2 Runden: R1 `done:false`, R2 `done:true` | R1: getProducts, filterByCategory (jewelery), count. R2: sum (nur falls count < 5) |
| 6 | Wie viele Elektronikprodukte kosten weniger als 500 €? Falls es mehr als 3 sind, nenne zusätzlich deren Durchschnittspreis. | 2 Runden: R1 `done:false`, R2 `done:true` | R1: getProducts, filterByCategory, filterByPrice, count. R2: average (nur falls count > 3) |
| 7 | Berechne die Gesamtsumme aller Produkte. Falls die Summe über 3000 € liegt, zähle zusätzlich die Produkte über 100 €. | 2 Runden: R1 `done:false`, R2 `done:true` | R1: getProducts, sum. R2: filterByPrice, count (nur falls sum > 3000) |
| 8 | Welche Kategorie hat den höchsten Durchschnittspreis? Falls die höchste Kategorie electronics ist, nenne zusätzlich deren Produktanzahl. | 2 Runden: R1 `done:false`, R2 `done:true` | R1: getProducts, filterByCategory + average für alle 4 Kategorien. R2: count (nur falls electronics am höchsten) |

## Testkommandos

```bash
# V2 — Kontrollfluss-Fragen (zwei Runden)
python agent.py --prompt-version v2 "Zähle zuerst alle Elektronikprodukte über 300 €. Nur falls es mehr als 5 sind, berechne zusätzlich deren Durchschnittspreis."
```

## Abnahmekriterien für V2

- [ ] Alle 8 Fragen liefern mit `--prompt-version v2` korrekte Ergebnisse
      über zwei Runden.
- [ ] Runde 1 setzt `done: false`, Runde 2 setzt `done: true`.
- [ ] Die Bedingung wird erst nach dem echten Zwischenergebnis entschieden
      (kein Raten vorher).
- [ ] Fragen ohne Bedingung (V1-Fragen) werden weiterhin in EINER Runde
      gelöst (`done: true` in Runde 1).
