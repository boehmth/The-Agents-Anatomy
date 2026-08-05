# tools/aggregates.py — count, sum und average.
#
# Diese Tools arbeiten auf einer Liste von "Items" (typischerweise eine
# Produktliste aus getProducts oder einem Filter). sum und average wirken
# standardmäßig auf das Feld "price"; ein anderes numerisches Feld kann als
# optionaler zweiter Parameter angegeben werden.

from typing import Any, Dict, List

from .base import AgentTool


def _require_items(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return None
    return value


def _get_field(item: Any, field: str) -> Any:
    """Liest ein Feld aus einem Item — unterstützt verschachtelte Pfade
    (z. B. 'rating.rate' -> item['rating']['rate'])."""
    node = item
    for key in field.split("."):
        if isinstance(node, dict) and key in node:
            node = node[key]
        else:
            return None
    return node



class CountTool(AgentTool):
    name = "count"
    description = (
        "Zählt die Anzahl der Items in einer Liste (z. B. einer Produktliste)."
    )
    parameters = {
        "operation": "muss 'count' sein",
        "operand1": "Liste (z. B. $results[1].products)",
        "operand2": "leer ('')",
    }
    returns = '{"count": int}'

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        items = _require_items(args.get("operand1"))
        if items is None:
            return {
                "error": (
                    "operand1 muss eine Liste sein. "
                    "Nutze eine $results[i].products-Referenz."
                )
            }
        return {"count": len(items)}


class SumTool(AgentTool):
    name = "sum"
    description = (
        "Summiert ein numerisches Feld über alle Items einer Liste. "
        "Standardfeld ist 'price'; ein anderes Feld kann als operand2 "
        "angegeben werden (z. B. 'rating.count')."
    )
    parameters = {
        "operation": "muss 'sum' sein",
        "operand1": "Liste (z. B. $results[1].products)",
        "operand2": "Feldname (optional, Default 'price')",
    }
    returns = '{"sum": float, "field": str, "count": int}'

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        items = _require_items(args.get("operand1"))
        if items is None:
            return {
                "error": (
                    "operand1 muss eine Liste sein. "
                    "Nutze eine $results[i].products-Referenz."
                )
            }
        field = args.get("operand2") or "price"
        total = 0.0
        n = 0
        for it in items:
            val = _get_field(it, field)
            if val is not None:
                try:
                    total += float(val)
                    n += 1
                except (TypeError, ValueError):
                    pass
        return {"sum": total, "field": field, "count": n}



class AverageTool(AgentTool):
    name = "average"
    description = (
        "Berechnet den Durchschnitt eines numerischen Felds über alle Items "
        "einer Liste. Standardfeld ist 'price'; ein anderes Feld kann als "
        "operand2 angegeben werden (z. B. 'rating.rate')."
    )
    parameters = {
        "operation": "muss 'average' sein",
        "operand1": "Liste (z. B. $results[1].products)",
        "operand2": "Feldname (optional, Default 'price')",
    }
    returns = '{"average": float, "field": str, "count": int}'

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        items = _require_items(args.get("operand1"))
        if items is None:
            return {
                "error": (
                    "operand1 muss eine Liste sein. "
                    "Nutze eine $results[i].products-Referenz."
                )
            }
        field = args.get("operand2") or "price"
        values = []
        for it in items:
            val = _get_field(it, field)
            if val is not None:
                try:
                    values.append(float(val))
                except (TypeError, ValueError):
                    pass
        if not values:
            return {"error": f"kein numerisches Feld '{field}' in den Items gefunden"}

        return {
            "average": sum(values) / len(values),
            "field": field,
            "count": len(values),
        }
