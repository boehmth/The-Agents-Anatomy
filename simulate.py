# simulate.py — Multi-day Simulator (CLI + Library).

import argparse
import json
import math
import os
import shutil
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

import pandas as pd

import clock
import price_cache
import tools.portfolio as _pf_mod
from tools import TICKERS
from runner import run_agent
from model import get_provider, set_model


INITIAL_CASH = 10_000.0

USER_GOAL = (
    "Du bist ein täglich laufender Trading-Agent.\n"
    "Ziel: den Gesamtwert des Portfolios (Cash + Aktien) langfristig maximieren.\n"
    "Halte dich strikt an die Regeln im System-Prompt.\n"
    "Setze done=true, sobald deine Tagesentscheidung ausgeführt ist.\n"
)


# ------------------------- Helpers -------------------------
def _rm(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)


def _reset_state() -> None:
    _rm(_pf_mod.PORTFOLIO_FILE)
    _rm(_pf_mod.TRADES_FILE)
    _rm(os.path.join(os.getenv("DATA_DIR", "data"), "agent_log.jsonl"))


def _last_close(ticker: str, as_of: date) -> float:
    prices = price_cache.get_prices_up_to(ticker, as_of, 1)
    if not prices:
        return 0.0
    close = float(prices[-1]["close"])
    return close if math.isfinite(close) else 0.0


def _active_model_name(cli_model: Optional[str]) -> str:
    if cli_model:
        return cli_model
    provider = get_provider()
    if provider == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if provider == "gemini":
        return os.getenv("GEMINI_MODEL", "models/gemini-flash-latest")
    return os.getenv("SAP_GENAI_MODEL", "<from env>")


def _portfolio_value(as_of: date) -> Dict[str, Any]:
    pf_file = _pf_mod.PORTFOLIO_FILE
    if not os.path.exists(pf_file):
        return {"cash": 0.0, "equity": 0.0, "total": 0.0,
                "holdings": {t: 0.0 for t in TICKERS}}
    df = pd.read_csv(pf_file)
    if df.empty:
        return {"cash": 0.0, "equity": 0.0, "total": 0.0,
                "holdings": {t: 0.0 for t in TICKERS}}
    last = df.iloc[-1]
    cash = float(last["cash"])
    holdings = {t: float(last[t]) for t in TICKERS}
    equity = sum(holdings[t] * _last_close(t, as_of) for t in TICKERS)
    return {"cash": cash, "equity": equity, "total": cash + equity, "holdings": holdings}


def audit_cash_conservation() -> Dict[str, Any]:
    pf_file = _pf_mod.PORTFOLIO_FILE
    trades_file = _pf_mod.TRADES_FILE
    result: Dict[str, Any] = {"ok": True, "trades": 0, "issues": [],
                              "initial_cash": None,
                              "final_cash_expected": None,
                              "final_cash_actual": None}
    if not os.path.exists(pf_file):
        return {"ok": False, "issues": ["no portfolio.csv"]}
    pf = pd.read_csv(pf_file)
    if pf.empty:
        return {"ok": False, "issues": ["portfolio.csv empty"]}
    initial_cash = float(pf.iloc[0]["cash"])
    result["initial_cash"] = initial_cash

    if os.path.exists(trades_file):
        trades = pd.read_csv(trades_file)
    else:
        trades = pd.DataFrame(columns=["action", "shares", "price", "cash_delta"])
    result["trades"] = int(len(trades))

    for i, row in trades.iterrows():
        cd = float(row["cash_delta"])
        expected = -float(row["shares"]) * float(row["price"]) if row["action"] == "buy" \
            else +float(row["shares"]) * float(row["price"])
        if abs(cd - expected) > 1e-6:
            result["issues"].append(f"trade {i}: cash_delta {cd} vs {expected}")

    exp_cash = initial_cash + (trades["cash_delta"].sum() if not trades.empty else 0.0)
    act_cash = float(pf.iloc[-1]["cash"])
    result["final_cash_expected"] = float(exp_cash)
    result["final_cash_actual"] = float(act_cash)
    if abs(exp_cash - act_cash) > 1e-6:
        result["issues"].append(f"final cash mismatch: {exp_cash:.4f} vs {act_cash:.4f}")
    result["ok"] = not result["issues"]
    return result


# ------------------------- Main -------------------------
def run_simulation(days: int = 5,
                   start: Optional[str] = None,
                   end: Optional[str] = None,
                   model: Optional[str] = None,
                   prompt_version: Optional[str] = None,
                   data_dir: str = "data",
                   keep_portfolio: bool = False,
                   initial_cash: float = INITIAL_CASH,
                   plot: bool = True,
                   ) -> Dict[str, Any]:
    """Führt eine Simulation aus. Schreibt in data_dir und gibt Summary zurück."""
    if model:
        set_model(model)
    if prompt_version:
        os.environ["PROMPT_VERSION"] = prompt_version

    _pf_mod.set_data_dir(data_dir)
    os.environ["DATA_DIR"] = data_dir
    os.makedirs(data_dir, exist_ok=True)

    end_d = date.fromisoformat(end) if end else date.today()
    start_d = date.fromisoformat(start) if start else end_d - timedelta(days=days * 2)

    active_model = _active_model_name(model)
    active_prompt = prompt_version or os.getenv("PROMPT_VERSION", "v1")

    print(f"[simulate] Zeitraum : {start_d} .. {end_d}")
    print(f"[simulate] Provider : {get_provider()}")
    print(f"[simulate] Modell   : {active_model}")
    print(f"[simulate] Prompts  : {active_prompt}")
    print(f"[simulate] Output   : {data_dir}")

    if not keep_portfolio:
        _reset_state()

    price_cache.preload(TICKERS, start=start_d, end=end_d, lookback_days=400)

    trading_days = price_cache.trading_days_between(start_d, end_d)
    if days:
        trading_days = trading_days[-days:]
    if not trading_days:
        summary = {
            "error": "no trading days",
            "hint": "Wähle ggf. ein historisches --end-Datum, für das Kursdaten existieren.",
            "model": active_model,
            "provider": get_provider(),
            "prompt_version": active_prompt,
            "tickers": TICKERS,
            "requested_start_date": start_d.isoformat(),
            "requested_end_date": end_d.isoformat(),
        }
        summary_path = os.path.join(data_dir, "summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print("[simulate] FEHLER: keine Handelstage im gewählten Zeitraum gefunden.")
        print("[simulate] Tipp  : Nutze z. B. --end 2025-11-14 für historische Daten.")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return summary

    print(f"[simulate] {len(trading_days)} Handelstage: "
          f"{trading_days[0]} .. {trading_days[-1]}")

    # Portfolio-Seed
    start_row = {"date": trading_days[0].isoformat(),
                 "cash": initial_cash,
                 **{t: 0.0 for t in TICKERS}}
    pd.DataFrame([start_row]).to_csv(_pf_mod.PORTFOLIO_FILE, index=False)

    # Handels-Loop
    equity_log: List[Dict[str, Any]] = []
    for i, d in enumerate(trading_days, 1):
        print(f"\n#### Tag {i}/{len(trading_days)}: {d}")
        clock.set_today(d)
        try:
            run_agent(USER_GOAL, as_of=d.isoformat())
        except Exception as e:
            print(f"[simulate] Agent-Fehler an {d}: {e}")

        pv = _portfolio_value(d)
        equity_log.append({"date": d.isoformat(), **pv})
        print(f"[simulate] {d}: cash={pv['cash']:.2f}  equity={pv['equity']:.2f}  "
              f"total={pv['total']:.2f}")

    # Ausgabe
    log_df = pd.DataFrame(equity_log)
    equity_path = os.path.join(data_dir, "simulation_equity.csv")
    log_df.to_csv(equity_path, index=False)

    first_total = float(log_df.iloc[0]["total"]) if not log_df.empty else initial_cash
    last_total = float(log_df.iloc[-1]["total"]) if not log_df.empty else initial_cash
    pnl_abs = last_total - first_total
    pnl_pct = (pnl_abs / first_total * 100) if first_total else 0.0
    trades_count = len(pd.read_csv(_pf_mod.TRADES_FILE)) if os.path.exists(_pf_mod.TRADES_FILE) else 0

    audit = audit_cash_conservation()

    summary: Dict[str, Any] = {
        "model": active_model,
        "provider": get_provider(),
        "prompt_version": active_prompt,
        "tickers": TICKERS,
        "days": len(trading_days),
        "start_date": trading_days[0].isoformat(),
        "end_date": trading_days[-1].isoformat(),
        "initial_cash": initial_cash,
        "start_total": first_total,
        "end_total": last_total,
        "pnl_abs": pnl_abs,
        "pnl_pct": pnl_pct,
        "trades": trades_count,
        "audit_ok": audit.get("ok", False),
        "audit_issues": audit.get("issues", []),
    }

    summary_path = os.path.join(data_dir, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if plot:
        try:
            from plot import plot_simulation
            plot_simulation(equity_path=equity_path,
                            trades_path=_pf_mod.TRADES_FILE,
                            out_path=os.path.join(data_dir, "simulation.png"))
        except Exception as e:
            print(f"[simulate] Plot übersprungen: {e}")

    return summary


# ------------------------- CLI -------------------------
def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=5)
    p.add_argument("--start", type=str, default=None)
    p.add_argument("--end", type=str, default=None)
    p.add_argument("--model", type=str, default=None,
                   help="SAP GenAI Hub Modell, überschreibt SAP_GENAI_MODEL")
    p.add_argument("--prompt-version", type=str, default=None,
                   help="prompts/<version>/, überschreibt PROMPT_VERSION")
    p.add_argument("--data-dir", type=str, default="data")
    p.add_argument("--keep-portfolio", action="store_true")
    p.add_argument("--no-plot", action="store_true")
    return p.parse_args()


def main():
    args = _parse_args()
    run_simulation(
        days=args.days,
        start=args.start,
        end=args.end,
        model=args.model,
        prompt_version=args.prompt_version,
        data_dir=args.data_dir,
        keep_portfolio=args.keep_portfolio,
        plot=not args.no_plot,
    )


if __name__ == "__main__":
    main()