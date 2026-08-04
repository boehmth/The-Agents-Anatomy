# runner/loop.py — Der Agent-Loop.
#
# Der Agent ist bewusst einfach gehalten (didaktisch):
#   1. System-Prompt bauen (aus prompts/<version>/system_prompt.txt)
#   2. LLM fragen -> JSON-Plan mit "steps"
#   3. process_steps() führt die Steps aus (mit $results[i].key-Auflösung)
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
    """Führt alle Steps eines Plans der Reihe nach aus.

    Jedes Ergebnis wird in `results` gesammelt. Spätere Steps können über
    $results[i].key auf frühere Ergebnisse zugreifen (siehe runner.refs).
    """
    results: List[Any] = []
    for step in steps:
        op = step.get("args", {}).get("operation", "")
        print(f"  Step {len(results)}: {step.get('tool')} {op}")
        r = execute_step(step, results)
        print(f"    -> {_summarize(r)}")
        results.append(r)
    return results


# ---------------------------------------------------------
# Agent-Log schreiben (didaktisch: Plan + Ergebnisse pro Tag)
# ---------------------------------------------------------
def _write_agent_log(day: str, plan: Dict[str, Any], results: List[Any]) -> None:
    """Schreibt pro Agent-Lauf eine JSONL-Zeile nach data/agent_log.jsonl.

    Das ist bewusst nur Beobachtung, keine zusätzliche Agent-Logik:
    Der Loop bleibt call_llm() -> process_steps(), aber man kann später
    nachvollziehen, was das Modell geplant hat und was die Tools lieferten.
    """
    data_dir = os.getenv("DATA_DIR", "data")
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "agent_log.jsonl")
    row = {"day": day, "plan": plan, "results": results}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


# ---------------------------------------------------------
# Haupt-Loop
# ---------------------------------------------------------
def run_agent(user_goal: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    """Führt den Agenten für einen (simulierten) Tag aus.

    Der Agent besteht aus genau zwei Teilen:
      1. call_llm()  -> liefert einen JSON-Plan mit "steps"
      2. process_steps() -> führt die Steps aus

    Args:
        user_goal: Ziel-Text an den LLM.
        as_of: Optional "YYYY-MM-DD" — wenn gesetzt, gilt dieses Datum als "heute"
               für alle Tools. Sonst wird das echte Systemdatum verwendet.
    """
    if as_of is not None:
        clock.set_today(as_of)

    day = clock.today_str()
    system_prompt = build_system_prompt()
    user_prompt = f"Heutiges Datum: {day}\n\n{user_goal}"

    raw_plan = call_llm(system_prompt, user_prompt)
    if not isinstance(raw_plan, dict):
        print(f"WARN: Modell lieferte keinen JSON-Plan als Objekt: {type(raw_plan).__name__}")
        plan: Dict[str, Any] = {"error": "invalid_plan_type", "raw": raw_plan}
    else:
        plan = raw_plan

    # ensure_ascii=True: verhindert UnicodeEncodeError auf cp1252-Konsolen (Windows).
    print("Plan:", json.dumps(plan, ensure_ascii=True, indent=2, default=str))

    if "error" in plan:
        print(f"WARN: Modellfehler im Plan: {plan.get('error')}")

    steps = plan.get("steps") or []
    if not steps:
        print("WARN: Modell lieferte keine ausführbaren Steps.")

    results = process_steps(steps)
    _write_agent_log(day, plan, results)

    return {"day": day, "plan": plan, "results": results}
