# runner/loop.py — Der Agent-Loop.
#
# Der Agent ist bewusst einfach gehalten (didaktisch):
#   1. System-Prompt bauen (aus prompts/<version>/system_prompt.txt)
#   2. LLM fragen -> JSON-Plan mit "steps" und "done"
#   3. process_steps() führt die Steps aus (mit $results[i].key-Auflösung)
#   4. Wenn "done" == false: LLM erneut fragen, diesmal MIT den bisherigen
#      echten results im Kontext, bis "done" == true (oder max_iterations
#      erreicht ist).
#
# WICHTIGER PUNKT (didaktisch): Es gibt bewusst KEINEN zweiten Prompt für
# "Iteration 2". Derselbe system_prompt wird wiederverwendet — nur der
# user_prompt wächst um die bisherigen Ergebnisse. Das Modell entscheidet
# über "done" selbst, wie viele Runden es braucht (typischerweise 2:
# Daten sammeln -> entscheiden, aber nicht als Regel im Code erzwungen).
#
# Der Agent kennt ein "as_of"-Datum. Alle Tools richten sich über clock.today()
# nach diesem Datum. Perfekt für Simulation.

import os
import json
from typing import Any, Dict, List, Optional

import clock
from model import call_llm
from tools import TOOLS

from .refs import resolve_args


_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROMPTS_ROOT = os.path.join(_HERE, "prompts")

# Sicherheitsnetz: verhindert Endlos-Loops, falls das Modell "done" nie
# auf true setzt (z. B. wegen eines Prompt-Bugs oder eines schwachen Modells).
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
      get_prices      -> "NVDA: 210.96 (2026-07-31)"
      calculator      -> "result: 15.0"
      portfolio       -> "cash=7506.60 holdings={NVDA: 11.0, ...}"
      error           -> "error: <meldung>"
    """
    if not isinstance(result, dict):
        return str(result)

    if "error" in result:
        return f"error: {result['error']}"

    # get_prices -> {symbol, prices, latest}
    if "symbol" in result and "latest" in result:
        latest = result["latest"] or {}
        return f"{result['symbol']}: {latest.get('close', 0):.2f} ({latest.get('date', '?')})"

    # calculator
    if "result" in result:
        return f"result: {result['result']}"

    # portfolio
    if "cash" in result and "holdings" in result:
        holdings = {k: v for k, v in result["holdings"].items() if v}
        return f"cash={result['cash']:.2f} holdings={holdings}"

    return json.dumps(result, ensure_ascii=False, default=str)


# ---------------------------------------------------------
# Bisherige results als Text für den nächsten user_prompt rendern
# ---------------------------------------------------------
def _render_results_block(results: List[Any]) -> str:
    """Rendert die bisher (in diesem Tages-Lauf, über alle Iterationen
    hinweg) ausgeführten Tool-Ergebnisse als Text — mit EXAKT der
    Indizierung, die $results[i] im Prompt referenziert (Step 0 = erstes
    Ergebnis des Tages, Step 1 = zweites, ... unabhängig davon, in
    welcher Iteration der Step lief).

    Das ist der Kernmechanismus für "zweiter LLM-Call sieht echte Zahlen":
    Iteration 2 bekommt hier die tatsächlichen Tool-Outputs aus
    Iteration 1 zu sehen, statt sie zu erraten.
    """
    if not results:
        return ""
    lines = ["Bisherige Ergebnisse (results) für HEUTE — bereits ausgeführt, "
             "NICHT wiederholen, per $results[i] referenzieren:"]
    for i, r in enumerate(results):
        lines.append(f"$results[{i}] = {json.dumps(r, ensure_ascii=False, default=str)}")
    return "\n".join(lines)


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
    """Führt alle Steps EINES Plans (einer Iteration) der Reihe nach aus.

    existing_results: bereits vorhandene Ergebnisse früherer Iterationen
    desselben Tages. Neue Steps werden dagegen aufgelöst UND an diese
    Liste angehängt — die Indizierung bleibt so über mehrere Iterationen
    hinweg stabil (wichtig für $results[i]-Referenzen aus späteren
    Iterationen auf Ergebnisse früherer Iterationen).

    Gibt die VOLLSTÄNDIGE (alte + neue) results-Liste zurück.
    """
    results: List[Any] = list(existing_results or [])
    for step in steps:
        idx = len(results)
        op = step.get("args", {}).get("operation", "")
        desc = step.get("description")
        print(f"  Step {idx}: {step.get('tool')} {op}"
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
# Agent-Log schreiben (didaktisch: alle Pläne + finale Ergebnisse pro Tag)
# ---------------------------------------------------------
def _write_agent_log(day: str, plans: List[Dict[str, Any]], results: List[Any]) -> None:
    """Schreibt pro Agent-Lauf (Tag) eine JSONL-Zeile nach data/agent_log.jsonl.

    "plans" ist jetzt eine Liste (eine pro Iteration dieses Tages), damit
    man beim Nachvollziehen sieht, was das Modell in JEDER Runde geplant
    hat — nicht nur die letzte.
    """
    data_dir = os.getenv("DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "agent_log.jsonl")
    row = {"day": day, "plans": plans, "results": results}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------
# Haupt-Loop
# ---------------------------------------------------------
def run_agent(user_goal: str, as_of: Optional[str] = None,
              max_iterations: int = DEFAULT_MAX_ITERATIONS) -> Dict[str, Any]:
    """Führt den Agenten für einen (simulierten) Tag aus — über MEHRERE
    Iterationen hinweg, bis das Modell "done": true zurückgibt.

    Jede Iteration:
      1. call_llm()  -> liefert einen JSON-Plan mit "steps" und "done"
      2. process_steps() -> führt NUR die neuen Steps dieser Iteration aus
         und hängt die Ergebnisse an die Tages-results an.
      3. Falls "done" != true UND max_iterations noch nicht erreicht:
         nächste Iteration — der user_prompt enthält jetzt die ECHTEN
         bisherigen Ergebnisse (nicht geraten).

    Args:
        user_goal: Ziel-Text an den LLM.
        as_of: Optional "YYYY-MM-DD" — wenn gesetzt, gilt dieses Datum als
               "heute" für alle Tools. Sonst wird das echte Systemdatum
               verwendet.
        max_iterations: Sicherheitsnetz gegen Endlos-Loops, falls "done"
               nie true wird.
    """
    if as_of is not None:
        clock.set_today(as_of)

    day = clock.today_str()
    system_prompt = build_system_prompt()

    all_results: List[Any] = []
    all_plans: List[Dict[str, Any]] = []
    done = False
    iteration = 0

    while not done and iteration < max_iterations:
        iteration += 1

        user_prompt = f"Heutiges Datum: {day}\n\n{user_goal}"
        results_block = _render_results_block(all_results)
        if results_block:
            user_prompt += f"\n\n{results_block}"

        raw_plan = call_llm(system_prompt, user_prompt)
        if not isinstance(raw_plan, dict):
            print(f"WARN: Modell lieferte keinen JSON-Plan als Objekt: {type(raw_plan).__name__}")
            plan: Dict[str, Any] = {"error": "invalid_plan_type", "raw": raw_plan}
        else:
            plan = raw_plan

        # ensure_ascii=True: verhindert UnicodeEncodeError auf cp1252-Konsolen (Windows).
        print(f"Plan (Iteration {iteration}):",
              json.dumps(plan, ensure_ascii=True, indent=2, default=str))
        all_plans.append(plan)

        if "error" in plan:
            print(f"WARN: Modellfehler im Plan: {plan.get('error')}")
            break

        steps = plan.get("steps") or []
        if not steps:
            print("WARN: Modell lieferte keine ausführbaren Steps in dieser Iteration.")

        # WICHTIG: gegen die BISHERIGEN results auflösen/anhängen, nicht bei
        # 0 neu anfangen -> $results[i]-Indizes bleiben über Iterationen
        # hinweg stabil und zeigen auf die richtigen früheren Ergebnisse.
        all_results = process_steps(steps, existing_results=all_results)

        done = bool(plan.get("done"))

    if iteration >= max_iterations and not done:
        print(f"WARN: max_iterations ({max_iterations}) erreicht, "
              f"ohne dass 'done' gesetzt wurde.")

    _write_agent_log(day, all_plans, all_results)

    # Rückwärtskompatibel: "plan" zeigt weiterhin auf den letzten Plan
    # (falls agent.py/simulate.py/report.py darauf zugreifen), zusätzlich
    # "plans" mit der vollständigen Historie aller Iterationen dieses Tages.
    return {
        "day": day,
        "plan": all_plans[-1] if all_plans else None,
        "plans": all_plans,
        "results": all_results,
    }