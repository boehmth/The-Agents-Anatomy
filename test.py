# test.py — Sanity-Checks für Tools, $results-Auflösung und LLM.
import os
from dotenv import load_dotenv

from tools import TOOLS, TICKERS
from runner import resolve_ref, resolve_args
from model import call_llm, get_provider

load_dotenv()


def show_registry():
    print("\n=== Tool Registry ===")
    for name, tool in TOOLS.items():
        print(f"\n{name}")
        print(f"  description: {tool.description}")
        print(f"  parameters:  {tool.parameters}")
        print(f"  returns:     {tool.returns}")


def test_calculator():
    print("\n=== calculator ===")
    calc = TOOLS["calculator"]
    for op, a, b in [("add", "10", "5"), ("subtract", "10", "5"),
                     ("multiply", "10", "5"), ("divide", "10", "5"),
                     ("divide", "1", "0")]:
        print(f"  {a} {op} {b} = {calc.run({'operation': op, 'operand1': a, 'operand2': b})}")


def test_portfolio():
    print("\n=== portfolio ===")
    p = TOOLS["portfolio"]
    # Startzustand simulieren (portfolio.csv wird sonst nicht existieren)
    import pandas as pd, os
    os.makedirs("data", exist_ok=True)
    pd.DataFrame([{"date": "2026-01-01", "cash": 10000.0,
                   "NVDA": 0.0, "MSFT": 0.0, "SAP": 0.0, "AMZN": 0.0}]).to_csv(
        "data/portfolio.csv", index=False)

    print("  load:    ", p.run({"operation": "load", "operand1": "", "operand2": ""}))
    print("  buy 1 NVDA @145.30:",
          p.run({"operation": "buy", "operand1": "NVDA", "operand2": "1@145.30"}))
    print("  sell 0.5 NVDA @150:",
          p.run({"operation": "sell", "operand1": "NVDA", "operand2": "0.5@150"}))
    print("  load:    ", p.run({"operation": "load", "operand1": "", "operand2": ""}))
    print("  buy too much:",
          p.run({"operation": "buy", "operand1": "NVDA", "operand2": "1000@1000"}))


def test_prices():
    print("\n=== get_prices ===")
    gp = TOOLS["get_prices"]
    for symbol in TICKERS:
        r = gp.run({"operation": "get", "operand1": symbol, "operand2": "5"})
        if "error" in r:
            print(f"  {symbol}: {r}")
        else:
            print(f"  {symbol}: latest={r['latest']}, points={len(r['prices'])}")


def test_ref_resolution():
    print("\n=== $results[i].key resolution ===")
    fake_results = [
        {"symbol": "NVDA", "latest": {"date": "2025-01-01", "close": 145.30}},
        {"result": 42.0},
        {"cash": 9500.0, "holdings": {"NVDA": 1.0, "MSFT": 0.0}},
    ]
    cases = [
        "$results[0].latest.close",
        "$results[1].result",
        "$results[2].holdings.NVDA",
        "$results[9].nope",
        "$results[0].nonexistent",
        "plain string",
    ]
    for c in cases:
        print(f"  {c!r:40s} -> {resolve_ref(c, fake_results)!r}")

    print("\n  resolve_args:",
          resolve_args(
              {"operation": "buy", "operand1": "NVDA", "operand2": "$results[0].latest.close"},
              fake_results,
          ))


def test_llm():
    print(f"\n=== LLM (provider={get_provider()}) ===")
    print("  ", call_llm("Antworte als reines JSON.",
                        "Gib ein JSON mit Feld 'ok' und Wert true zurück."))


if __name__ == "__main__":
    show_registry()
    test_calculator()
    test_portfolio()
    test_ref_resolution()
    test_prices()    # Netz-Call
    test_llm()       # Netz-Call