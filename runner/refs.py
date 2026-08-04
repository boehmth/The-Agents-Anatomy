# runner/refs.py — Auflösung von "$results[i].key.subkey".
#
# Wenn der LLM in einem Step-Argument eine Referenz auf ein früheres Ergebnis
# einfügt (Format: "$results[<index>].<key>[.<subkey>...]"), löst diese Datei
# den Wert vor dem Tool-Call auf. Beispiel: "12@$results[1].latest.close".

import re
from typing import Any, Dict, List

# Findet $results[i].path in einem String (auch eingebettet, z. B. "12@$results[1].latest.close").
_REF_RE = re.compile(r"\$results\[(\d+)\]\.([A-Za-z0-9_\.\-]+)")


def _lookup(idx: int, path: str, results: List[Any]) -> Any:
    if idx < 0 or idx >= len(results):
        return f"__ref_error__:index {idx} out of range"
    node: Any = results[idx]
    # Versuche zuerst den exakten Index. Schlägt der Pfad fehl (z. B. weil
    # das Modell einen 1-basierten Index statt 0-basiert verwendet hat),
    # suchen wir rückwärts nach dem nächstgelegenen Element, das den Pfad
    # auflösen kann. Das macht den Agenten robust gegen Indexierungsfehler.
    exact = _walk(node, path)
    if not isinstance(exact, str) or not exact.startswith("__ref_error__"):
        return exact
    for i in range(idx - 1, -1, -1):
        candidate = _walk(results[i], path)
        if not isinstance(candidate, str) or not candidate.startswith("__ref_error__"):
            return candidate
    return exact


def _walk(node: Any, path: str) -> Any:
    """Löst einen Punkt-Pfad auf einem einzelnen Element auf."""
    for key in path.split("."):
        if isinstance(node, dict) and key in node:
            node = node[key]
        elif isinstance(node, list) and key.lstrip("-").isdigit():
            i = int(key)
            if -len(node) <= i < len(node):
                node = node[i]
            else:
                return f"__ref_error__:index '{key}' out of range"
        else:
            return f"__ref_error__:key '{key}' not found"
    return node


def resolve_ref(value: Any, results: List[Any]) -> Any:
    """Ersetzt jede $results[i].key-Referenz durch ihren Wert (als Text).

    Nicht-Strings bleiben unverändert. Skalare (Zahlen) werden als String
    eingesetzt, damit sie in Tool-Argumenten wie "12@$results[1].latest.close"
    funktionieren.
    """
    if not isinstance(value, str):
        return value

    def _sub(m):
        ref = m.group(0)  # z. B. "$results[3].latest.close"
        val = _lookup(int(m.group(1)), m.group(2), results)
        if isinstance(val, (int, float)):
            return str(val)
        if isinstance(val, str):
            return val
        # dict/list in einem String zu inlinen ist nicht sinnvoll
        return f"__ref_error__:{ref}: cannot inline non-scalar"

    return _REF_RE.sub(_sub, value)


def resolve_args(args: Dict[str, Any], results: List[Any]) -> Dict[str, Any]:
    return {k: resolve_ref(v, results) for k, v in args.items()}
