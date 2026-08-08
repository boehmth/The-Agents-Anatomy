# agent.py — CLI-Einstieg für einen einzelnen Shop-Controller-Lauf (One-Shot).

import argparse
import os

from dotenv import load_dotenv
load_dotenv()

from runner import run_agent
from model import set_model


DEFAULT_QUESTION = (
    "Wie viele Elektronikprodukte kosten mehr als 100 €?"
)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--question", type=str, default=DEFAULT_QUESTION,
                   help="Betriebswirtschaftliche Frage an den Shop-Controller.")
    p.add_argument("--model", type=str, default=None,
                   help="LLM-Modell (überschreibt die Provider-Env-Variable).")
    p.add_argument("--prompt-version", type=str, default=None,
                   help="prompts/<version>/ (überschreibt PROMPT_VERSION).")
    p.add_argument("--agent-version", type=str, default=None,
                   help="Aktive Agent-Version (v1|v2|v3, siehe runner/features.py). "
                        "Überschreibt AGENT_VERSION und PROMPT_VERSION.")
    args = p.parse_args()

    if args.model:
        set_model(args.model)
    if args.agent_version:
        os.environ["AGENT_VERSION"] = args.agent_version
    elif args.prompt_version:
        os.environ["PROMPT_VERSION"] = args.prompt_version

    result = run_agent(args.question)
    print("\n--- Antwort ---")
    print(result["answer"])


if __name__ == "__main__":
    main()


