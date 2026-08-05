# runner/refs.py — Auflösung von "$results[i].key.subkey".
#
# Wenn der LLM in einem Step-Argument eine Referenz auf ein früheres Ergebnis
# einfügt (Format: "$results[<index>].<key>[.<subkey>...]"), löst diese Datei
# den Wert vor dem Tool-Call auf.
#
# Zwei Fälle:
#   1. Das Argument ist GENAU eine einzige Referenz (z. B. "$results[0].products"):
#      -> der tatsächliche Wert wird übergeben (auch Listen/Dicts). So kann ein
#         Tool eine Produktliste an das nächste Tool weiterreichen.
#   2. Die Referenz ist in anderen Text eingebettet (z. B. "1@$results[1].latest.close"):
#      -> nur skalare Werte (Zahlen/Strings) werden inline eingesetzt.

import re
from typing import Any, Dict, List

# Findet $results[i].path in einem String (auch eingebettet, z. B. "12@$results[1].latest.close").
_REF_RE = re.compile(r"\$results\[(\d+)\]\.([A-Za-z0-9_\.\-]+)")
# Erkennt, ob der GESAMTE String eine einzige Referenz ist.
_FULL_REF_RE = re.compile(r"^\$results\[(\d+)\]\.([A-Za-z0-9_\.\-]+)$")


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
    """Ersetzt jede $results[i].key-Referenz durch ihren Wert.

    - Nicht-Strings bleiben unverändert.
    - Ist der String GENAU eine Referenz, wird der tatsächliche Wert
      zurückgegeben (auch Listen/Dicts) — für Tool-zu-Tool-Weitergabe.
    - Ist die Referenz eingebettet, werden nur Skalare (Zahlen/Strings)
      als Text eingesetzt.
    """
    if not isinstance(value, str):
        return value

    # Fall 1: gesamter String ist eine einzige Referenz -> Objekt übergeben.
    m = _FULL_REF_RE.match(value.strip())
    if m:
        return _lookup(int(m.group(1)), m.group(2), results)

    # Fall 2: eingebettete Referenzen -> nur Skalare inline.
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
