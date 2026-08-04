# tools/calculator.py — exakte Arithmetik.

from typing import Any, Dict

from .base import AgentTool


class CalculatorTool(AgentTool):
    name = "calculator"
    description = "Führt eine exakte arithmetische Operation auf zwei Zahlen aus."
    parameters = {
        "operation": "add | subtract | multiply | divide",
        "operand1": "number as string",
        "operand2": "number as string",
    }
    returns = '{"result": float}'

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        op = args.get("operation")
        a_raw = args.get("operand1")
        b_raw = args.get("operand2")
        try:
            a = float(a_raw)
            b = float(b_raw)
        except Exception:
            bad = [x for x in (a_raw, b_raw)
                   if not isinstance(x, str) or "__ref_error__" in x]
            if bad:
                return {
                    "error": (
                        "operand ist keine gültige $results-Referenz "
                        f"({bad[0]}). Prüfe den Index: get_prices-Ergebnisse "
                        "sind die Indizes 1 und 2 im Beispiel-Plan."
                    )
                }
            return {"error": "operands must be numeric strings"}

        if op == "add":
            return {"result": a + b}
        if op == "subtract":
            return {"result": a - b}
        if op == "multiply":
            return {"result": a * b}
        if op == "divide":
            if b == 0:
                return {"error": "division by zero"}
            return {"result": a / b}
        return {"error": f"unsupported operation '{op}'"}