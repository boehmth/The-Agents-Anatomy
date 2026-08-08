# runner/features.py — Versionen als explizite Feature-Sets (didaktisch).
#
# Jede Version ist ein benanntes Feature-Set. So sieht man auf einen Blick,
# was jede Version "aufbaut" (V1 -> V2 -> V3 -> ...). Die aktive Version wird
# über AGENT_VERSION gewählt (Fallback: PROMPT_VERSION, dann "v1") und steuert
# sowohl die Prompt-Auswahl als auch die Code-Fähigkeiten des Runners.
#
#   v1: done_field=False, validate=False, retry=False -> One-Shot, keine Verifikation
#   v2: done_field=True,  validate=False, retry=False -> Mehrschritt-Loop (done-gesteuert)
#   v3: done_field=True,  validate=True,  retry=False -> + strukturelle Verifikation
#   v4: done_field=True,  validate=True,  retry=True  -> + technischer Retry (Self-Healing)
#
# Bedeutung der Features:
#   done_field  -> ob der Prompt das "done"-Feld kennt (V2+). Das ist eine
#                  PROMPT-Eigenschaft: V2s system_prompt.txt lehrt das Modell,
#                  "done" zu setzen. Der Runner ist dafür bereits generisch
#                  (fehlt "done", gilt die Runde als abgeschlossen).
#   validate    -> ob der Runner Pläne VOR der Ausführung gegen ein Schema
#                  prüft (V3+). Das ist eine CODE-Eigenschaft (runner/validate.py).
#   retry       -> ob fehlgeschlagene Steps (V3-Validierungsfehler ODER echte
#                  Tool-Laufzeitfehler) als Text an das Modell zurückgegeben
#                  werden und es eine begrenzte Anzahl Korrektur-Versuche
#                  bekommt (V4+). Das ist eine CODE-Eigenschaft (runner/loop.py).
#
# So bleibt jede Version explizit aktivierbar, und zukünftige Versionen (V5+)
# fügen hier einfach ein weiteres Feature hinzu — ohne den Loop anzufassen.

import os

from typing import Dict

DEFAULT_VERSION = "v1"

FEATURES: Dict[str, Dict[str, bool]] = {
    "v1": {"done_field": False, "validate": False, "retry": False},
    "v2": {"done_field": True,  "validate": False, "retry": False},
    "v3": {"done_field": True,  "validate": True,  "retry": False},
    "v4": {"done_field": True,  "validate": True,  "retry": True},
}


def active_version() -> str:
    """Aktive Version: AGENT_VERSION, sonst PROMPT_VERSION, sonst 'v1'."""
    return (
        os.getenv("AGENT_VERSION")
        or os.getenv("PROMPT_VERSION")
        or DEFAULT_VERSION
    ).strip()


def features_for(version: str) -> Dict[str, bool]:
    """Feature-Set einer Version. Unbekannte Versionen fallen auf 'v1' zurück."""
    return FEATURES.get(version, FEATURES[DEFAULT_VERSION])



