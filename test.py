# test.py — Selbsttest der Shop-Controller-Tools (ohne LLM).
#
# Verifiziert, dass die Tools getProducts, filterByCategory, filterByPrice,
# count, sum und average korrekt funktionieren — inklusive der
# $results[i].products-Referenzauflösung (Tool-zu-Tool-Weitergabe).

import json
import sys

from tools import TOOLS
from runner.refs import resolve_args


def _run(tool_name: str, args: dict, results: list) -> dict:
    """Führt ein Tool mit aufgelösten Argumenten aus und hängt das Ergebnis an."""
    resolved = resolve_args(args, results)
    r = TOOLS[tool_name].run(resolved)
    results.append(r)
    return r


def main() -> None:
    results = []

    # Step 0: getProducts
    r0 = _run("getProducts", {"operation": "get", "operand1": "", "operand2": "", "operand3": ""}, results)
    assert "products" in r0 and r0["count"] == 20, f"getProducts: {r0}"
    print(f"OK getProducts: {r0['count']} Produkte")

    # Step 1: filterByCategory -> electronics
    r1 = _run("filterByCategory",
              {"operation": "filterByCategory",
               "operand1": "$results[0].products",
               "operand2": "electronics",
               "operand3": ""}, results)
    assert r1["count"] == 6, f"filterByCategory electronics: {r1}"
    print(f"OK filterByCategory electronics: {r1['count']}")

    # Step 2: filterByPrice > 100
    r2 = _run("filterByPrice",
              {"operation": "filterByPrice",
               "operand1": "$results[1].products",
               "operand2": ">",
               "operand3": "100"}, results)
    assert r2["count"] == 5, f"filterByPrice >100: {r2}"
    print(f"OK filterByPrice >100: {r2['count']}")

    # Step 3: count
    r3 = _run("count",
              {"operation": "count",
               "operand1": "$results[2].products",
               "operand2": "",
               "operand3": ""}, results)
    assert r3["count"] == 5, f"count: {r3}"
    print(f"OK count: {r3['count']}")


    # Step 4: sum (default price) über alle Produkte
    r4 = _run("sum",
              {"operation": "sum",
               "operand1": "$results[0].products",
               "operand2": "",
               "operand3": ""}, results)
    assert r4["sum"] > 0 and r4["count"] == 20, f"sum: {r4}"
    print(f"OK sum(price): {r4['sum']:.2f} ({r4['count']} Items)")

    # Step 5: average (default price) über alle Produkte
    r5 = _run("average",
              {"operation": "average",
               "operand1": "$results[0].products",
               "operand2": "",
               "operand3": ""}, results)
    assert r5["average"] > 0 and r5["count"] == 20, f"average: {r5}"
    print(f"OK average(price): {r5['average']:.2f} ({r5['count']} Items)")

    # Step 6: average über rating.rate (anderes Feld)
    r6 = _run("average",
              {"operation": "average",
               "operand1": "$results[0].products",
               "operand2": "rating.rate",
               "operand3": ""}, results)
    assert r6["average"] > 0, f"average rating.rate: {r6}"
    print(f"OK average(rating.rate): {r6['average']:.2f}")

    # Fehlerfall: filterByCategory ohne Liste
    r7 = _run("filterByCategory",
              {"operation": "filterByCategory",
               "operand1": "keine-liste",
               "operand2": "electronics",
               "operand3": ""}, results)
    assert "error" in r7, f"erwartete Fehler: {r7}"
    print(f"OK Fehlerbehandlung filterByCategory: {r7['error'][:40]}...")

    print("\nAlle Tests bestanden.")

    # Beispiel-Antwort für die Beispiel-Frage
    print("\nBeispiel-Frage: 'Wie viele Elektronikprodukte kosten mehr als 100 €?'")
    print(f"Antwort: {r3['count']} Elektronikprodukte kosten mehr als 100 €.")


if __name__ == "__main__":
    main()
