# plot.py
#
# Rendert die Simulations-Ergebnisse als PNG.
#
# Standalone-Verwendung:
#   python plot.py
#   python plot.py --equity data/simulation_equity.csv --trades data/trades.csv --out data/simulation.png

import argparse
import os
from typing import Optional

import pandas as pd
import matplotlib

matplotlib.use("Agg")  # kein interaktives Fenster nötig
import matplotlib.pyplot as plt


def plot_simulation(equity_path: str = "data/simulation_equity.csv",
                    trades_path: Optional[str] = "data/trades.csv",
                    out_path: str = "data/simulation.png") -> str:
    """Zeichnet:
      - oben: Total, Cash, Equity über die Zeit; Buy/Sell als Marker.
      - unten: kumulativer Cashflow aus den Trades (zur Kontrolle).
    Speichert nach out_path und gibt den Pfad zurück.
    """
    if not os.path.exists(equity_path):
        raise FileNotFoundError(f"missing equity file: {equity_path}")

    eq = pd.read_csv(equity_path)
    if eq.empty:
        raise ValueError("equity file is empty")

    eq["date"] = pd.to_datetime(eq["date"])
    eq = eq.sort_values("date")

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    # --- oben: Equity-Kurve ---
    ax_top.plot(eq["date"], eq["total"], label="Total (Cash + Equity)",
                linewidth=2, color="tab:blue")
    ax_top.plot(eq["date"], eq["cash"], label="Cash",
                linewidth=1, linestyle="--", color="tab:green")
    ax_top.plot(eq["date"], eq["equity"], label="Equity (Aktienwert)",
                linewidth=1, linestyle="--", color="tab:orange")

    ax_top.set_ylabel("Wert")
    ax_top.set_title("The Agents Anatomy – Simulationsergebnis")
    ax_top.grid(True, alpha=0.3)

    # Buy/Sell-Marker (und set_cash separat als Info-Marker)
    trades_df = None
    if trades_path and os.path.exists(trades_path):
        trades_df = pd.read_csv(trades_path)
        if not trades_df.empty:
            trades_df["date"] = pd.to_datetime(trades_df["date"])
            merged = trades_df.merge(eq[["date", "total"]], on="date", how="left")
            buys = merged[merged["action"] == "buy"]
            sells = merged[merged["action"] == "sell"]
            fund = merged[merged["action"] == "set_cash"]
            if not buys.empty:
                ax_top.scatter(buys["date"], buys["total"], marker="^",
                               s=80, color="tab:green", edgecolors="black",
                               zorder=5, label=f"buy ({len(buys)})")
            if not sells.empty:
                ax_top.scatter(sells["date"], sells["total"], marker="v",
                               s=80, color="tab:red", edgecolors="black",
                               zorder=5, label=f"sell ({len(sells)})")
            if not fund.empty:
                ax_top.scatter(fund["date"], fund["total"], marker="*",
                               s=150, color="gold", edgecolors="black",
                               zorder=6, label=f"set_cash ({len(fund)})")

    ax_top.legend(loc="best")

    # --- unten: kumulativer Cashflow aus Trades ---
    if trades_df is not None and not trades_df.empty:
        # Sortieren und kumulieren
        t = trades_df.sort_values("date").copy()
        t["cum_cashflow"] = t["cash_delta"].cumsum()
        ax_bot.step(t["date"], t["cum_cashflow"], where="post",
                    color="tab:purple", label="Kumulativer Cashflow aus Trades")
        ax_bot.axhline(0, color="gray", linewidth=0.5)
        ax_bot.legend(loc="best")
        ax_bot.grid(True, alpha=0.3)
    else:
        ax_bot.text(0.5, 0.5, "Keine Trades im Log",
                    transform=ax_bot.transAxes, ha="center", va="center",
                    color="gray")
        ax_bot.set_yticks([])

    ax_bot.set_xlabel("Datum")
    ax_bot.set_ylabel("Δ Cash (kumul.)")

    fig.autofmt_xdate()
    fig.tight_layout()

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)

    print(f"[plot] geschrieben nach {out_path}")
    return out_path


def _parse():
    p = argparse.ArgumentParser()
    p.add_argument("--equity", default="data/simulation_equity.csv")
    p.add_argument("--trades", default="data/trades.csv")
    p.add_argument("--out", default="data/simulation.png")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse()
    plot_simulation(args.equity, args.trades, args.out)