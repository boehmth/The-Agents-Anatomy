# tools/prices.py — Historische Preise als Tabelle.

import os
from typing import Any, Dict, List

import yfinance as yf

import clock
import price_cache

from .base import AgentTool


# Bekannte Ticker (kanonische Liste).
# Kann per .env-Variable TICKERS überschrieben werden:
#     TICKERS=NVDA,MSFT
_DEFAULT_TICKERS = ["NVDA", "MSFT"]
_env = (os.getenv("TICKERS") or "").strip()
if _env:
    TICKERS = [t.strip().upper() for t in _env.split(",") if t.strip()]
else:
    TICKERS = _DEFAULT_TICKERS


class PriceTool(AgentTool):
    name = "get_prices"
    description = (
        "Liefert eine Historie der Schlusskurse für einen Ticker "
        "bis einschließlich clock.today(). Der LLM wählt die Fensterlänge."
    )
    parameters = {
        "operation": "must be 'get'",
        "operand1": "ticker (NVDA | MSFT)",
        "operand2": "number of days of history as string (default '1', max '365')",
    }
    returns = (
        '{"symbol": str, "prices": [{"date": "YYYY-MM-DD", "close": float}, ...], '
        '"latest": {"date": str, "close": float}}'
    )

    def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        if args.get("operation") != "get":
            return {"error": f"unsupported operation '{args.get('operation')}'"}

        symbol = args.get("operand1") or ""
        if symbol not in TICKERS:
            return {"error": f"unknown ticker '{symbol}'"}

        try:
            days = max(1, min(365, int(float(args.get("operand2") or "1"))))
        except Exception:
            days = 1

        as_of = clock.today()

        # 1) Preferred: aus Cache (deterministisch, schnell)
        if price_cache.is_loaded():
            prices = price_cache.get_prices_up_to(symbol, as_of, days)
        else:
            # 2) Fallback: Live yfinance (nur ohne Cache)
            print(f"[get_prices] live yfinance call {symbol} {days}d")
            hist = yf.Ticker(symbol).history(period=f"{days}d" if days > 1 else "1d")
            if hist.empty:
                return {"error": f"no price data for {symbol}"}
            prices = [
                {"date": idx.strftime("%Y-%m-%d"), "close": float(row["Close"])}
                for idx, row in hist.iterrows()
            ]

        if not prices:
            return {"error": f"no price data for {symbol} as of {as_of}"}

        return {"symbol": symbol, "prices": prices, "latest": prices[-1]}