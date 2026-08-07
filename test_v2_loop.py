# test_v2_loop.py — Verifikation des V2-Mehrschritt-Loops (ohne LLM).
#
# Mockt runner.loop.call_llm, um das Zwei-Runden-Verhalten zu simulieren:
#   Runde 1: done:false, Steps: getProducts -> filterByCategory ->
#            filterByPrice -> count
#   Runde 2: done:true,  Steps: leer (Bedingung nicht erfüllt)
#
# Prüft: (a) genau 2 Runden, (b) stabile $results[i]-Indizierung über Runden,
# (c) done-Verhalten, (d) V1-Kompatibilität (kein done-Feld -> 1 Runde),
# (e) max_iterations-Sicherheitsnetz.

import runner.loop as loop

_round = {"n": 0}


def fake_call_llm(system_prompt, user_prompt):
    _round["n"] += 1
    if _round["n"] == 1:
        return {
            "steps": [
                {"tool": "getProducts",
                 "args": {"operation": "get", "operand1": "", "operand2": "", "operand3": ""},
                 "description": "Alle Produkte laden"},
                {"tool": "filterByCategory",
                 "args": {"operation": "filterByCategory",
                          "operand1": "$results[0].products",
                          "operand2": "electronics",
                          "operand3": ""},
                 "description": "Nur Elektronik"},
                {"tool": "filterByPrice",
                 "args": {"operation": "filterByPrice",
                          "operand1": "$results[1].products",
                          "operand2": ">",
                          "operand3": "300"},
                 "description": "Nur über 300 EUR"},
                {"tool": "count",
                 "args": {"operation": "count",
                          "operand1": "$results[2].products",
                          "operand2": "",
                          "operand3": ""},
                 "description": "Anzahl zaehlen"},
            ],
            "done": False,
        }
    else:
        # Runde 2: sieht die echten Ergebnisse im user_prompt (results_block)
        assert "$results[3]" in user_prompt, "results_block fehlt in Runde 2!"
        # count ist hier 2 (nicht > 5) -> Bedingung nicht erfüllt -> leere Steps.
        return {
            "steps": [],
            "done": True,
            "answer": "Es gibt 2 Elektronikprodukte über 300 €. Da das nicht mehr als 5 sind, wurde kein Durchschnitt berechnet.",
        }


# --- Test 1: Zwei-Runden-Loop ---
print("=== Test 1: Zwei-Runden-Loop ===")
loop.call_llm = fake_call_llm
_round["n"] = 0
res = loop.run_agent("Zähle zuerst alle Elektronikprodukte über 300 €. Nur falls es mehr als 5 sind, berechne zusätzlich deren Durchschnittspreis.")
assert _round["n"] == 2, f"erwartet 2 Runden, war {_round['n']}"
assert len(res["plans"]) == 2, "plans muss 2 Einträge haben"
assert len(res["results"]) == 4, f"results muss 4 Einträge haben (4+0), war {len(res['results'])}"
assert res["results"][3]["count"] == 2, f"count in Runde 1 falsch: {res['results'][3]}"
assert res["plan"]["done"] is True, "letzter Plan muss done:true haben"
assert res["answer"] == "Es gibt 2 Elektronikprodukte über 300 €. Da das nicht mehr als 5 sind, wurde kein Durchschnitt berechnet."
print(f"OK: 2 Runden, {len(res['results'])} results, count={res['results'][3]['count']}")
print(f"OK: answer = {res['answer']}")


# --- Test 2: V1-Kompatibilität (kein done-Feld -> eine Runde) ---
print("\n=== Test 2: V1-Kompatibilität (kein done-Feld) ===")
def fake_call_llm_v1(system_prompt, user_prompt):
    return {
        "steps": [
            {"tool": "getProducts",
             "args": {"operation": "get", "operand1": "", "operand2": "", "operand3": ""}},
            {"tool": "count",
             "args": {"operation": "count", "operand1": "$results[0].products", "operand2": "", "operand3": ""}},
        ],
        "answer": "Es gibt 20 Produkte.",
    }
loop.call_llm = fake_call_llm_v1
_round["n"] = 0
res = loop.run_agent("Wie viele Produkte gibt es?")
assert len(res["plans"]) == 1, f"V1 muss 1 Runde laufen, war {len(res['plans'])}"

assert res["results"][1]["count"] == 20, f"count falsch: {res['results'][1]}"
assert res["answer"] == "Es gibt 20 Produkte."
print(f"OK: V1 läuft exakt 1 Runde, count={res['results'][1]['count']}, answer={res['answer']}")

# --- Test 3: max_iterations-Sicherheitsnetz ---
print("\n=== Test 3: max_iterations-Sicherheitsnetz ===")
def fake_call_llm_loop(system_prompt, user_prompt):
    # Modell setzt nie done -> muss nach max_iterations abbrechen
    return {"steps": [], "done": False}
loop.call_llm = fake_call_llm_loop
_round["n"] = 0
res = loop.run_agent("Verwirrende Frage", max_iterations=3)
assert len(res["plans"]) == 3, f"muss nach 3 Runden abbrechen, war {len(res['plans'])}"
print(f"OK: nach {len(res['plans'])} Runden abgebrochen (max_iterations=3)")


print("\nAlle V2-Loop-Tests bestanden.")
