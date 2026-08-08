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

from .features import active_version, features_for
from .refs import resolve_args
from .validate import validate_plan

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_PROMPTS_ROOT = os.path.join(_HERE, "prompts")

DEFAULT_MAX_ITERATIONS = 4

# V4: Retries sind strikt begrenzt und UNABHÄNGIG von max_iterations.
# Eine Iteration (V2) ist eine geplante Zwischenrunde (done: false).
# Ein Retry (V4) ist eine ERZWUNGENE Zusatzrunde, weil etwas schiefging.
DEFAULT_MAX_RETRIES = 2


def _prompt_dir() -> str:
    """Aktives Prompt-Verzeichnis (versioniert).

    Wählt prompts/<active_version()>/ (Default: 'v1'). Die aktive Version
    kommt aus runner/features.py (AGENT_VERSION, sonst PROMPT_VERSION).

    Fällt zurück auf prompts/ selbst, wenn es dort .txt-Dateien gibt
    (Rückwärtskompatibilität).
    """
    version = active_version()
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
        # Unbekanntes Tool (z. B. "__validation_error__" aus runner/validate.py):
        # die description enthält dann den konkreten Validierungsgrund und
        # muss sichtbar bleiben statt eines generischen "unknown tool".
        desc = step.get("description")
        if desc:
            return {"error": f"unknown tool '{step.get('tool')}': {desc}"}
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
# V3: Strukturelle Verifikation (schaltbar über features["validate"])
# ---------------------------------------------------------
def _validate_steps(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Prüft die Steps eines Plans VOR der Ausführung (runner/validate.py).

    Ungültige Steps werden NICHT ausgeführt, sondern durch ein
    "__validation_error__"-Ergebnis ersetzt, damit $results[i] konsistent
    indiziert bleibt und der Fehler SICHTBAR im Log steht statt einer
    stillen Falschantwort.

    Ist die Verifikation deaktiviert (features["validate"] == False, z. B.
    V1/V2), wird die Liste unverändert zurückgegeben.
    """
    if not features_for(active_version())["validate"]:
        return steps

    problems = validate_plan(steps)
    if not problems:
        return steps

    print("WARN: Plan enthält ungültige Steps (werden NICHT ausgeführt):")
    for idx, errs in problems.items():
        for e in errs:
            print(f"  Step {idx}: {e}")

    fixed_steps = []
    for i, step in enumerate(steps):
        if i in problems:
            fixed_steps.append({
                "tool": "__validation_error__",
                "args": {},
                "description": "; ".join(problems[i]),
            })
        else:
            fixed_steps.append(step)
    return fixed_steps


# ---------------------------------------------------------
# V4: Fehler erkennen und als Retry-Feedback zurückspielen
# ---------------------------------------------------------
def _find_step_errors(results: List[Any], start_index: int) -> List[tuple]:
    """Gibt (index, fehlermeldung) für alle results ab start_index zurück,
    die einen 'error'-Schlüssel enthalten — also sowohl echte
    Tool-Laufzeitfehler als auch V3-Validierungsfehler (die technisch
    genauso als {"error": ...} im Ergebnis landen)."""
    errors: List[tuple] = []
    for i in range(start_index, len(results)):
        r = results[i]
        if isinstance(r, dict) and "error" in r:
            errors.append((i, r["error"]))
    return errors


def _render_error_feedback(errors: List[tuple]) -> str:
    """Baut den Text, der dem Modell in der Retry-Runde als Kontext
    mitgegeben wird: welche Steps fehlgeschlagen sind und wie es sie
    korrigieren soll."""
    lines = ["ACHTUNG: Die folgenden Steps aus deinem letzten Plan sind "
             "fehlgeschlagen:"]
    for idx, msg in errors:
        lines.append(f"  Step {idx}: {msg}")
    lines.append(
        "Korrigiere NUR die betroffenen Steps in deinem nächsten Plan "
        "(z. B. richtige Kategorie, richtiger Operator, richtiger Typ). "
        "Wiederhole NICHT die bereits erfolgreichen Steps -- referenziere "
        "sie stattdessen per $results[i]."
    )
    return "\n".join(lines)


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
              max_iterations: int = DEFAULT_MAX_ITERATIONS,
              max_retries: int = DEFAULT_MAX_RETRIES) -> Dict[str, Any]:
    """Führt den Shop-Controller für EINE Frage aus.

    Der Loop fährt mehrere Runden, bis der Plan "done": true setzt (oder das
    Feld "done" fehlt — dann gilt die Runde als abgeschlossen) oder das
    Sicherheitsnetz max_iterations greift.

    V1 (Prompt ohne "done"-Feld) läuft dadurch mechanisch exakt einmal durch.
    V2 (Prompt mit "done"-Feld) kann über mehrere Runden echte
    Zwischenergebnisse abwarten, bevor es eine bedingte Entscheidung trifft.

    V4 (Retry): Schlägt ein Step fehl (V3-Validierungsfehler ODER echter
    Tool-Laufzeitfehler), wird der Fehler als Text an das Modell
    zurückgegeben und es bekommt max_retries Versuche, den Step zu
    korrigieren. Retries sind strikt begrenzt und UNABHÄNGIG von
    max_iterations.

    Args:
        user_question: Die betriebswirtschaftliche Frage an den Shop-Controller.
        max_iterations: Sicherheitsnetz gegen Endlosschleifen (Default 4).
        max_retries: Max. erzwungene Korrektur-Runden bei fehlgeschlagenen
            Steps (Default 2).

    Returns:
        Dict mit "plan" (letzter Plan), "plans" (alle Pläne), "results",
        "answer" (aus dem letzten Plan, falls vorhanden) und "retries_used".
    """
    system_prompt = build_system_prompt()

    all_results: List[Any] = []
    all_plans: List[Dict[str, Any]] = []
    done = False
    iteration = 0
    retries_used = 0
    pending_error_feedback: Optional[str] = None

    while not done and iteration < max_iterations:
        iteration += 1

        user_prompt = f"Frage: {user_question}"
        results_block = _render_results_block(all_results)
        if results_block:
            user_prompt += f"\n\n{results_block}"
        if pending_error_feedback:
            print(f"\n=== Runde {iteration} (Retry {retries_used}/{max_retries}) ===")
            user_prompt += f"\n\n{pending_error_feedback}"
            pending_error_feedback = None  # nur einmal einspeisen
        else:
            print(f"\n=== Runde {iteration} ===")

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

        before_count = len(all_results)

        if "error" not in plan:
            steps = plan.get("steps") or []
            if not steps:
                print("WARN: Modell lieferte keine ausführbaren Steps.")

            # V3: Strukturelle Verifikation VOR der Ausführung. Ob sie greift,
            # hängt von features["validate"] der aktiven Version ab (V1/V2:
            # aus, V3: an). Ungültige Steps werden NICHT ausgeführt, sondern
            # durch ein "__validation_error__"-Ergebnis ersetzt, damit
            # $results[i] konsistent indiziert bleibt und der Fehler SICHTBAR
            # im Log steht statt einer stillen Falschantwort.
            steps = _validate_steps(steps)

            all_results = process_steps(steps, existing_results=all_results)

        # done: Fehlt das Feld, gilt die Runde als abgeschlossen (V1-Kompatibilität).
        done = bool(plan.get("done", True))

        # V4: Fehlgeschlagene Steps (V3-Validierungsfehler ODER echte
        # Tool-Laufzeitfehler) erzwingen eine Korrektur-Runde — unabhängig
        # davon, was das Modell selbst in "done" geschrieben hat. Retries
        # sind strikt begrenzt (max_retries), damit keine Endlosschleife
        # entsteht, wenn das Modell denselben Fehler wiederholt macht.
        step_errors = _find_step_errors(all_results, before_count)
        if step_errors and retries_used < max_retries:
            retries_used += 1
            print(f"WARN: {len(step_errors)} Step(s) fehlgeschlagen -- "
                  f"erzwinge Retry {retries_used}/{max_retries}.")
            done = False  # überschreibt, was das Modell selbst gesagt hat
            pending_error_feedback = _render_error_feedback(step_errors)
        elif step_errors:
            print(f"WARN: Fehlgeschlagene Steps, aber max_retries "
                  f"({max_retries}) erreicht -- gebe auf, keine weitere "
                  f"Korrektur.")
            # done bleibt, wie vom Modell gesetzt (i. d. R. True) --
            # der Loop endet HIER bewusst, statt endlos weiterzuversuchen.

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
        "retries_used": retries_used,
    }




