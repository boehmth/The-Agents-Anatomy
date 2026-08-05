# tools/products.py — getProducts: lädt die Produktliste vom Fake Store API.

import os
from typing import Any, Dict, List

import requests

from .base import AgentTool


# Fake Store API Endpunkt. Kann per Env-Variable überschrieben werden.
FAKE_STORE_URL = os.getenv("FAKE_STORE_URL", "https://fakestoreapi.com/products")


class ProductsTool(AgentTool):
    name = "getProducts"
    description = (
        "Lädt die komplette Produktliste des Online-Shops von der Fake Store API. "
        "Jedes Produkt hat: id, title, price, description, category, image, "
        "rating (mit rate und count). Liefert die Liste als Array."
    )
    parameters = {
        "operation": "muss 'get' sein",
        "operand1": "leer ('')",
        "operand2": "leer ('')",
    }
    returns = (
        '[{"id": int, "title": str, "price": float, "category": str, '
        '"rating": {"rate": float, "count": int}, ...}, ...]'
    )

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if args.get("operation") != "get":
            return {"error": f"unsupported operation '{args.get('operation')}'"}

        try:
            r = requests.get(FAKE_STORE_URL, timeout=15)
            r.raise_for_status()
            products = r.json()
        except Exception as e:
            return {"error": f"Fake Store API Fehler: {e}"}

        if not isinstance(products, list):
            return {"error": "unerwartetes Antwortformat von der Fake Store API"}

        return {"products": products, "count": len(products)}
