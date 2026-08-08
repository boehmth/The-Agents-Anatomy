# runner/validate.py — Strukturelle Verifikation eines Plans VOR der Ausführung.
#
# Rein typ-/enum-basiert — kennt keine Geschäftslogik, nur: "ist dieser
# Tool-Aufruf überhaupt syntaktisch/strukturell sinnvoll?" Das ist bewusst
# simpel gehalten: kein Schema-Framework, nur Dicts und ein paar Checks.
#
# WICHTIG: Die Tools nutzen ein generisches operation/operand1/operand2/
# operand3-Interface (siehe tools/). Das Schema hier prüft genau diese
# Felder — nicht benannte Parameter.
#
# Abgrenzung zu V4: V3 erkennt und meldet nur. Es korrigiert NICHT
# automatisch und fragt das Modell NICHT erneut. Das ist bewusst V4
# vorbehalten (Retry-Mechanismus).

from typing import Any, Dict, List

KNOWN_CATEGORIES = {"electronics", "jewelery", "men's clothing", "women's clothing"}
ALLOWED_OPERATORS = {">", "<", ">=", "<=", "=="}

# Pro Tool: welche Felder sind Pflicht, welche haben einen bekannten
# Werte-Vorrat (enum), welche einen bestimmten Typ.
#
# Args, die auf $results verweisen (z. B. "operand1" als Produktliste),
# werden hier NICHT typgeprüft, weil ihr echter Wert erst nach der
# Auflösung bekannt ist — das prüft man separat, NACHDEM resolve_args()
# gelaufen ist (siehe validate_step unten).
TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "getProducts": {
        "required": ["operation"],
        "enum": {"operation": {"get"}},
    },
    "filterByCategory": {
        "required": ["operation", "operand1", "operand2"],
        "enum": {
            "operation": {"filterByCategory"},
            "operand2": KNOWN_CATEGORIES,
        },
    },
    "filterByPrice": {
        "required": ["operation", "operand1", "operand2", "operand3"],
        "enum": {
            "operation": {"filterByPrice"},
            "operand2": ALLOWED_OPERATORS,
        },
        # operand3 ist die Preis-Schwelle. Im Plan ist sie ein String
        # (z. B. "100"), das Tool konvertiert mit float(). Also: muss
        # numerisch sein ODER eine $results-Referenz.
        "numeric": ["operand3"],
    },
    "count": {
        "required": ["operation", "operand1"],
        "enum": {"operation": {"count"}},
    },
    "sum": {
        "required": ["operation", "operand1"],
        "enum": {"operation": {"sum"}},
    },
    "average": {
        "required": ["operation", "operand1"],
        "enum": {"operation": {"average"}},
    },
}


def _is_ref(value: Any) -> bool:
    """True, wenn der Wert eine (noch nicht aufgelöste) $results-Referenz ist."""
    return isinstance(value, str) and value.strip().startswith("$results[")


def validate_step(tool_name: str, args: Dict[str, Any]) -> List[str]:
    """Gibt eine Liste menschenlesbarer Fehler zurück (leer = gültig).

    Prüft NUR die statisch bekannten Felder (operation, operand2-Kategorie,
    operand2-Operator, operand3-Numerik), NICHT die $results-Referenzen
    selbst — die werden ja erst zur Laufzeit aufgelöst und sind nicht Teil
    dieser Prüfung.
    """
    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return [f"unbekanntes Tool '{tool_name}'"]

    errors: List[str] = []
    for field in schema.get("required", []):
        if field not in args or args[field] in (None, ""):
            errors.append(f"'{tool_name}': Pflichtfeld '{field}' fehlt")

    for field, allowed in schema.get("enum", {}).items():
        value = args.get(field)
        # $results[...]-Referenzen (noch nicht aufgelöst) hier nicht gegen
        # das enum prüfen -- das würde zur Planungszeit immer fehlschlagen,
        # weil der echte Wert noch nicht bekannt ist.
        if _is_ref(value):
            continue
        if value is not None and value not in allowed:
            errors.append(
                f"'{tool_name}': '{field}'='{value}' ist kein bekannter "
                f"Wert. Erlaubt: {sorted(allowed)}"
            )

    for field in schema.get("numeric", []):
        value = args.get(field)
        if _is_ref(value):
            continue
        if value is not None and value != "":
            try:
                float(value)
            except (TypeError, ValueError):
                errors.append(
                    f"'{tool_name}': '{field}'={value!r} muss eine Zahl sein "
                    f"(oder eine $results-Referenz)"
                )

    return errors


def validate_plan(steps: List[Dict[str, Any]]) -> Dict[int, List[str]]:
    """Prüft alle Steps eines Plans. Gibt {step_index: [fehler, ...]}
    zurück -- nur für Steps mit Fehlern, leeres Dict wenn alles gültig."""
    problems: Dict[int, List[str]] = {}
    for i, step in enumerate(steps):
        errs = validate_step(step.get("tool", ""), step.get("args", {}) or {})
        if errs:
            problems[i] = errs
    return problems
