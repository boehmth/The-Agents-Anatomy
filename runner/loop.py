# runner/loop.py — Der (iterationsfähige) Loop des Shop-Controllers.
#
# Der Agent ist bewusst einfach gehalten (didaktisch):
#   1. System-Prompt bauen (aus prompts/<version>/system_prompt.txt)
#   2. LLM fragen -> JSON-Plan mit "steps" und optional "done"
#   3. process_steps() führt die Steps aus (mit $results[i].key-Auflösung)
#   4. done? -> fertig. sonst: nächste Runde mit den echten Ergebnissen.
#
# Der Plan enthält:
#   - "steps":  Liste der Tool-Aufrufe (getProducts, filterByCategory, ...)
#   - "done":   optional. true/false. Fehlt das Feld, gilt die Runde als
#               abgeschlossen (done = true). So läuft V1 (dessen Prompt kein
#               "done"-Feld kennt) mechanisch exakt einmal durch.
#   - "answer": optional. die finale betriebswirtschaftliche Antwort auf die
#               Frage des Nutzers (reine Selbstauskunft des Modells, wird
#               nicht ausgeführt).
#
# Die Tools reichen Produktlisten per $results[i].products-Referenz aneinander
# weiter (siehe runner/refs.py). Die Indizierung von $results[i] bleibt über
# alle Runden hinweg stabil: Jeder ausgeführte Step bekommt einen festen Index,
# unabhängig davon, in welcher Runde er lief.

import os
import json
from typing import Any, Dict, List, Optional

from model import call_llm
from tools import TOOLS

from .refs import resolve_args


_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROMPTS_ROOT = os.path.join(_HERE, "prompts")

DEFAULT_MAX_ITERATIONS = 4


def _prompt_dir() -> str:
    """Aktives Prompt-Verzeichnis (versioniert).

    Wählt prompts/<PROMPT_VERSION>/ (Default: 'v1').
    Fällt zurück auf prompts/ selbst, wenn es dort .txt-Dateien gibt
    (Rückwärtskompatibilität).
    """
    version = (os.getenv("PROMPT_VERSION") or "v1").strip()
    versioned = os.path.join(_PROMPTS_ROOT, version)
    if os.path.isdir(versioned):
        return versioned
    return _PROMPTS_ROOT


# ---------------------------------------------------------
# Prompt zusammenbauen
# ---------------------------------------------------------
def build_system_prompt() -> str:
    pdir = _prompt_dir()
    with open(os.path.join(pdir, "system_prompt.txt"), encoding="utf-8") as f:
        base = f.read()
    with open(os.path.join(pdir, "tool_descriptions.txt"), encoding="utf-8") as f:
        tools_desc = f.read()
    return base.replace("{{tools_description}}", tools_desc)


# ---------------------------------------------------------
# Kompakte Darstellung eines Tool-Ergebnisses
# ---------------------------------------------------------
def _summarize(result: Any) -> str:
    """Macht ein Tool-Ergebnis lesbar — statt des vollen JSON nur das Wesentliche.

    Beispiele:
      getProducts       -> "20 Produkte geladen"
      filterByCategory  -> "6 Produkte in Kategorie 'electronics'"
      filterByPrice     -> "4 Produkte mit price > 100.0"
      count             -> "count: 4"
      sum               -> "sum(price): 1234.56 (4 Items)"
      average           -> "average(price): 308.64 (4 Items)"
      error             -> "error: <meldung>"
    """
    if not isinstance(result, dict):
        return str(result)

    if "error" in result:
        return f"error: {result['error']}"

    # filterByPrice (vor getProducts prüfen, da beide "products"+"count" liefern)
    if "operator" in result and "value" in result:
        return f"{result['count']} Produkte mit price {result['operator']} {result['value']}"

    # filterByCategory
    if "category" in result and "products" in result:
        return f"{result['count']} Produkte in Kategorie '{result['category']}'"

    # getProducts
    if "products" in result and "count" in result:
        return f"{result['count']} Produkte geladen"

    # count
    if "count" in result and len(result) == 1:
        return f"count: {result['count']}"

    # sum
    if "sum" in result:
        return f"sum({result['field']}): {result['sum']:.2f} ({result['count']} Items)"

    # average
    if "average" in result:
        return f"average({result['field']}): {result['average']:.2f} ({result['count']} Items)"

    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------
# Einen Step ausführen
# ---------------------------------------------------------
def execute_step(step: Dict[str, Any], results: List[Any]) -> Any:
    tool = TOOLS.get(step.get("tool"))
    if not tool:
        return {"error": f"unknown tool '{step.get('tool')}'"}

    args = resolve_args(step.get("args", {}) or {}, results)
    try:
        return tool.run(args)
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------
# Steps ausführen
# ---------------------------------------------------------
def process_steps(steps: List[Dict[str, Any]],
                  existing_results: Optional[List[Any]] = None) -> List[Any]:
    """Führt alle Steps EINES Plans der Reihe nach aus.

    existing_results: bereits vorhandene Ergebnisse früherer Runden.
    Neue Steps werden GEGEN DIESE LISTE aufgelöst und ANGEHÄNGT — die
    Indizierung von $results[i] bleibt über Runden hinweg stabil.

    Gibt die (ggf. verlängerte) results-Liste zurück.
    """
    results: List[Any] = list(existing_results or [])
    for step in steps:
        idx = len(results)
        desc = step.get("description")
        print(f"  Step {idx}: {step.get('tool')}"
              + (f"  // {desc}" if desc else ""))
        args = resolve_args(step.get("args", {}) or {}, results)
        r = execute_step(step, results)
        summary = _summarize(r)
        if "error" in r:
            # Bei Fehlern die aufgelösten Argumente zeigen, damit klar ist,
            # was der Agent tatsächlich versucht hat (didaktisch wichtig).
            print(f"    -> {summary}")
            print(f"       versucht: {args}")
        else:
            print(f"    -> {summary}")
        results.append(r)
    return results


# ---------------------------------------------------------
# Bisherige Ergebnisse als Text für den nächsten LLM-Aufruf
# ---------------------------------------------------------
def _render_results_block(results: List[Any]) -> str:
    """Rendert bisherige Ergebnisse als Text, in EXAKT der Indizierung,
    die $results[i] im Prompt referenziert — unabhängig davon, in welcher
    Runde der jeweilige Step lief."""
    if not results:
        return ""
    lines = [
        "Bisherige Ergebnisse (results) — bereits ausgeführt, "
        "NICHT wiederholen, per $results[i] referenzieren:"
    ]
    for i, r in enumerate(results):
        lines.append(f"$results[{i}] = {json.dumps(r, ensure_ascii=False, default=str)}")
    return "\n".join(lines)


# ---------------------------------------------------------
# Agent-Log schreiben (didaktisch: Pläne + Ergebnisse pro Lauf)
# ---------------------------------------------------------
def _write_agent_log(plans: List[Dict[str, Any]], results: List[Any]) -> None:
    """Schreibt pro Agent-Lauf eine JSONL-Zeile nach data/agent_log.jsonl."""
    data_dir = os.getenv("DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "agent_log.jsonl")
    row = {"plans": plans, "results": results}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------
# Haupt-Loop (iterationsfähig)
# ---------------------------------------------------------
def run_agent(user_question: str,
              max_iterations: int = DEFAULT_MAX_ITERATIONS) -> Dict[str, Any]:
    """Führt den Shop-Controller für EINE Frage aus.

    Der Loop fährt mehrere Runden, bis der Plan "done": true setzt (oder das
    Feld "done" fehlt — dann gilt die Runde als abgeschlossen) oder das
    Sicherheitsnetz max_iterations greift.

    V1 (Prompt ohne "done"-Feld) läuft dadurch mechanisch exakt einmal durch.
    V2 (Prompt mit "done"-Feld) kann über mehrere Runden echte
    Zwischenergebnisse abwarten, bevor es eine bedingte Entscheidung trifft.

    Args:
        user_question: Die betriebswirtschaftliche Frage an den Shop-Controller.
        max_iterations: Sicherheitsnetz gegen Endlosschleifen (Default 4).

    Returns:
        Dict mit "plan" (letzter Plan), "plans" (alle Pläne), "results" und
        "answer" (aus dem letzten Plan, falls vorhanden).
    """
    system_prompt = build_system_prompt()

    all_results: List[Any] = []
    all_plans: List[Dict[str, Any]] = []
    done = False
    iteration = 0

    while not done and iteration < max_iterations:
        iteration += 1
        print(f"\n=== Runde {iteration} ===")

        user_prompt = f"Frage: {user_question}"
        results_block = _render_results_block(all_results)
        if results_block:
            user_prompt += f"\n\n{results_block}"

        raw_plan = call_llm(system_prompt, user_prompt)
        if not isinstance(raw_plan, dict):
            print(f"WARN: Modell lieferte keinen JSON-Plan als Objekt: "
                  f"{type(raw_plan).__name__}")
            plan: Dict[str, Any] = {"error": "invalid_plan_type", "raw": raw_plan}
        else:
            plan = raw_plan
        all_plans.append(plan)

        # ensure_ascii=True: verhindert UnicodeEncodeError auf cp1252-Konsolen (Windows).
        print("Plan:",
              json.dumps(plan, ensure_ascii=True, indent=2, default=str))

        if "error" not in plan:
            steps = plan.get("steps") or []
            if not steps:
                print("WARN: Modell lieferte keine ausführbaren Steps.")
            all_results = process_steps(steps, existing_results=all_results)

        # done: Fehlt das Feld, gilt die Runde als abgeschlossen (V1-Kompatibilität).
        done = bool(plan.get("done", True))

    if iteration >= max_iterations and not done:
        print(f"WARN: max_iterations ({max_iterations}) erreicht, "
              f"ohne dass 'done' gesetzt wurde.")

    _write_agent_log(all_plans, all_results)

    last_plan = all_plans[-1] if all_plans else {}
    return {
        "plan": last_plan,
        "plans": all_plans,
        "results": all_results,
        "answer": last_plan.get("answer", ""),
    }
