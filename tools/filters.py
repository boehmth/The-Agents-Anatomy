# tools/filters.py — filterByCategory und filterByPrice.
#
# Beide Tools nehmen eine Produktliste (aus getProducts oder einem früheren
# Filter) als Eingabe und liefern eine gefilterte Teilmenge zurück. So kann
# der Agent Fragen wie "Wie viele Elektronikprodukte kosten mehr als 100 €?"
# Schritt für Schritt beantworten.

from typing import Any, Dict, List

from .base import AgentTool


def _require_products(value: Any) -> List[Dict[str, Any]]:
    """Stellt sicher, dass operand1 eine Produktliste ist."""
    if not isinstance(value, list):
        return None
    return value


class FilterByCategoryTool(AgentTool):
    name = "filterByCategory"
    description = (
        "Filtert eine Produktliste nach einer Kategorie. "
        "Kategorien: 'electronics', 'jewelery', \"men's clothing\", "
        "\"women's clothing\"."
    )
    parameters = {
        "operation": "muss 'filterByCategory' sein",
        "operand1": "Produktliste (z. B. $results[0].products)",
        "operand2": "Kategorie als String",
    }
    returns = '{"products": [...], "count": int, "category": str}'

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        products = _require_products(args.get("operand1"))
        if products is None:
            return {
                "error": (
                    "operand1 muss eine Produktliste sein. "
                    "Nutze eine $results[i].products-Referenz."
                )
            }
        category = args.get("operand2") or ""
        filtered = [p for p in products if p.get("category") == category]
        return {"products": filtered, "count": len(filtered), "category": category}


class FilterByPriceTool(AgentTool):
    name = "filterByPrice"
    description = (
        "Filtert eine Produktliste nach dem Preis. "
        "Erlaubte Operatoren: '>', '>=', '<', '<=', '==' (oder '=')."
    )
    parameters = {
        "operation": "muss 'filterByPrice' sein",
        "operand1": "Produktliste (z. B. $results[0].products)",
        "operand2": "Operator als String ('>', '>=', '<', '<=', '==')",
        "operand3": "Preis-Schwelle als Zahl (String)",
    }
    returns = '{"products": [...], "count": int, "operator": str, "value": float}'

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        products = _require_products(args.get("operand1"))
        if products is None:
            return {
                "error": (
                    "operand1 muss eine Produktliste sein. "
                    "Nutze eine $results[i].products-Referenz."
                )
            }
        operator = args.get("operand2") or ""
        try:
            threshold = float(args.get("operand3"))
        except Exception:
            return {"error": "operand3 muss eine Zahl sein (Preis-Schwelle)"}

        ops = {
            ">": lambda p: p > threshold,
            ">=": lambda p: p >= threshold,
            "<": lambda p: p < threshold,
            "<=": lambda p: p <= threshold,
            "==": lambda p: p == threshold,
            "=": lambda p: p == threshold,
        }
        if operator not in ops:
            return {"error": f"unsupported operator '{operator}'"}

        filtered = [p for p in products if ops[operator](p.get("price", 0))]
        return {
            "products": filtered,
            "count": len(filtered),
            "operator": operator,
            "value": threshold,
        }
