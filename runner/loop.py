# runner/loop.py — Der One-Shot-Loop des Shop-Controllers.
#
# Der Agent ist bewusst einfach gehalten (didaktisch):
#   1. System-Prompt bauen (aus prompts/<version>/system_prompt.txt)
#   2. LLM fragen -> JSON-Plan mit "steps" und "answer"
#   3. process_steps() führt die Steps aus (mit $results[i].key-Auflösung)
#   4. Fertig. Es gibt KEINE zweite Iteration.
#
# Der Plan enthält:
#   - "steps":  Liste der Tool-Aufrufe (getProducts, filterByCategory, ...)
#   - "answer": die finale betriebswirtschaftliche Antwort auf die Frage
#               des Nutzers (reine Selbstauskunft des Modells, wird nicht
#               ausgeführt).
#
# Die Tools reichen Produktlisten per $results[i].products-Referenz aneinander
# weiter (siehe runner/refs.py). So kann der Agent z. B. "Wie viele
# Elektronikprodukte kosten mehr als 100 €?" in einer Kette aus
# getProducts -> filterByCategory -> filterByPrice -> count beantworten.

import os
import json
from typing import Any, Dict, List, Optional

from model import call_llm
from tools import TOOLS

from .refs import resolve_args


_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROMPTS_ROOT = os.path.join(_HERE, "prompts")


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
def process_steps(steps: List[Dict[str, Any]]) -> List[Any]:
    """Führt alle Steps EINES Plans der Reihe nach aus.

    Gibt die results-Liste zurück (ein Eintrag pro Step, 0-basiert).
    """
    results: List[Any] = []
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
# Agent-Log schreiben (didaktisch: Plan + Ergebnisse pro Lauf)
# ---------------------------------------------------------
def _write_agent_log(plan: Dict[str, Any], results: List[Any]) -> None:
    """Schreibt pro Agent-Lauf eine JSONL-Zeile nach data/agent_log.jsonl."""
    data_dir = os.getenv("DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "agent_log.jsonl")
    row = {"plan": plan, "results": results}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------
# Haupt-Loop (One-Shot)
# ---------------------------------------------------------
def run_agent(user_question: str) -> Dict[str, Any]:
    """Führt den Shop-Controller für EINE Frage aus — in einem einzigen
    Durchlauf (One-Shot):

      1. call_llm()  -> liefert einen JSON-Plan mit "steps" und "answer"
      2. process_steps() -> führt die Steps aus
      3. Fertig. Keine zweite Iteration.

    Args:
        user_question: Die betriebswirtschaftliche Frage an den Shop-Controller.

    Returns:
        Dict mit "plan", "results" und "answer".
    """
    system_prompt = build_system_prompt()
    user_prompt = f"Frage: {user_question}"

    raw_plan = call_llm(system_prompt, user_prompt)
    if not isinstance(raw_plan, dict):
        print(f"WARN: Modell lieferte keinen JSON-Plan als Objekt: {type(raw_plan).__name__}")
        plan: Dict[str, Any] = {"error": "invalid_plan_type", "raw": raw_plan}
    else:
        plan = raw_plan

    # ensure_ascii=True: verhindert UnicodeEncodeError auf cp1252-Konsolen (Windows).
    print("Plan:",
          json.dumps(plan, ensure_ascii=True, indent=2, default=str))

    results: List[Any] = []
    if "error" not in plan:
        steps = plan.get("steps") or []
        if not steps:
            print("WARN: Modell lieferte keine ausführbaren Steps.")
        results = process_steps(steps)

    _write_agent_log(plan, results)

    return {
        "plan": plan,
        "results": results,
        "answer": plan.get("answer", ""),
    }
