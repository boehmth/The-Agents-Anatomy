# report.py — Baut aus data/leaderboard.csv eine HTML-Übersicht.
#
# Verwendung:
#   python report.py
#   python report.py --leaderboard data/leaderboard.csv --out docs/index.html

import argparse
import os
from html import escape
from typing import List, Optional

import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _collect_trades(run_root: str) -> pd.DataFrame:
    """Sammelt alle Trades aus data/runs/<datum>/<modell>/trades.csv.

    Jede Zeile wird um die Spalten run_date und model ergänzt, damit die
    Historie über alle Läufe hinweg nachvollziehbar ist.
    """
    frames: List[pd.DataFrame] = []
    if not os.path.isdir(run_root):
        return pd.DataFrame(columns=["run_date", "model", "date", "action",
                                     "ticker", "shares", "price", "cash_delta",
                                     "cash_after"])
    for run_date in sorted(os.listdir(run_root)):
        date_dir = os.path.join(run_root, run_date)
        if not os.path.isdir(date_dir):
            continue
        for model in sorted(os.listdir(date_dir)):
            trades_file = os.path.join(date_dir, model, "trades.csv")
            if not os.path.exists(trades_file):
                continue
            try:
                df = pd.read_csv(trades_file)
            except Exception as e:
                print(f"[report] WARN: {trades_file} nicht lesbar: {e}")
                continue
            if df.empty:
                continue
            df = df.copy()
            df.insert(0, "run_date", run_date)
            df.insert(1, "model", model)
            frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["run_date", "model", "date", "action",
                                     "ticker", "shares", "price", "cash_delta",
                                     "cash_after"])
    return pd.concat(frames, ignore_index=True)


def _plot_pnl_history(leaderboard: pd.DataFrame, out_png: str) -> None:
    """Zeichnet Zeitreihe des P&L pro Modell."""
    if leaderboard.empty:
        return
    fig, ax = plt.subplots(figsize=(11, 5))

    for model, sub in leaderboard.groupby("model"):
        sub = sub.sort_values("run_date")
        ax.plot(sub["run_date"], sub["pnl_pct"], marker="o", label=model)

    ax.axhline(0, color="gray", linewidth=0.5)
    ax.set_title("Daily benchmark: P&L in % pro Modell")
    ax.set_xlabel("Run-Datum")
    ax.set_ylabel("P&L in %")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def build_report(leaderboard_path: str = "data/leaderboard.csv",
                 out_path: str = "docs/index.html",
                 run_root: str = "data/runs") -> Optional[str]:
    if not os.path.exists(leaderboard_path):
        print(f"[report] Kein leaderboard.csv unter {leaderboard_path}. Nichts zu tun.")
        return None

    lb = pd.read_csv(leaderboard_path)
    if lb.empty:
        print("[report] Leaderboard ist leer.")
        return None

    # Sortieren, ansprechend darstellen
    lb["pnl_pct"] = pd.to_numeric(lb["pnl_pct"], errors="coerce")
    lb["run_date"] = lb["run_date"].astype(str)

    # Plot
    out_dir = os.path.dirname(out_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, "pnl_history.png")
    _plot_pnl_history(lb, png_path)

    # Trade-Historie aus den Run-Verzeichnissen sammeln
    trades = _collect_trades(run_root)
    if not trades.empty:
        trades = trades.sort_values(["date", "run_date", "model"]).reset_index(drop=True)
    print(f"[report] {len(trades)} Trades aus {run_root} geladen.")

    # Aggregat pro Modell
    agg = (lb.groupby("model")
             .agg(runs=("run_date", "count"),
                  avg_pnl_pct=("pnl_pct", "mean"),
                  best_pnl_pct=("pnl_pct", "max"),
                  worst_pnl_pct=("pnl_pct", "min"),
                  avg_trades=("trades", "mean"))
             .reset_index()
             .sort_values("avg_pnl_pct", ascending=False))

    # HTML
    style = """
    <style>
      body { font-family: system-ui, sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 1em; }
      h1, h2 { border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
      table { border-collapse: collapse; width: 100%; margin: 1em 0; }
      th, td { border: 1px solid #ddd; padding: 0.4em 0.6em; text-align: right; }
      th { background: #f6f6f6; text-align: left; }
      td:first-child, th:first-child { text-align: left; }
      tr:nth-child(even) { background: #fafafa; }
      .pos { color: #2b8a3e; font-weight: 600; }
      .neg { color: #c92a2a; font-weight: 600; }
      img { max-width: 100%; height: auto; margin: 1em 0; }
      code { background: #f4f4f4; padding: 0.1em 0.3em; border-radius: 3px; }
    </style>
    """

    def _fmt_pct(v):
        try:
            v = float(v)
        except (TypeError, ValueError):
            return "—"
        cls = "pos" if v > 0 else ("neg" if v < 0 else "")
        return f'<span class="{cls}">{v:+.2f} %</span>'

    # Aggregat-Tabelle
    agg_rows = ""
    for _, row in agg.iterrows():
        agg_rows += (
            f"<tr>"
            f"<td>{escape(str(row['model']))}</td>"
            f"<td>{int(row['runs'])}</td>"
            f"<td>{_fmt_pct(row['avg_pnl_pct'])}</td>"
            f"<td>{_fmt_pct(row['best_pnl_pct'])}</td>"
            f"<td>{_fmt_pct(row['worst_pnl_pct'])}</td>"
            f"<td>{row['avg_trades']:.1f}</td>"
            f"</tr>"
        )

    # Letzter Lauf pro Modell
    last_date = lb["run_date"].max()
    last_runs = lb[lb["run_date"] == last_date].sort_values("pnl_pct", ascending=False)
    last_rows = ""
    for _, row in last_runs.iterrows():
        last_rows += (
            f"<tr>"
            f"<td>{escape(str(row['model']))}</td>"
            f"<td>{escape(str(row.get('prompt_version', '')))}</td>"
            f"<td>{row['trades']}</td>"
            f"<td>{row['start_total']:.2f}</td>"
            f"<td>{row['end_total']:.2f}</td>"
            f"<td>{_fmt_pct(row['pnl_pct'])}</td>"
            f"<td>{'✔' if row.get('audit_ok') else '✘'}</td>"
            f"</tr>"
        )

    # Trade-Historie (was wurde wann gekauft/verkauft)
    trade_rows = ""
    if trades.empty:
        trade_rows = (
            "<tr><td colspan='8' style='text-align:center;color:#888'>"
            "Keine Trades in den Run-Verzeichnissen gefunden.</td></tr>"
        )
    else:
        for _, t in trades.iterrows():
            action = str(t.get("action", "")).lower()
            if action == "buy":
                action_label = '<span class="pos">Kauf</span>'
            elif action == "sell":
                action_label = '<span class="neg">Verkauf</span>'
            else:
                action_label = escape(str(t.get("action", "")))
            try:
                shares = float(t.get("shares", 0))
                price = float(t.get("price", 0))
                cash_delta = float(t.get("cash_delta", 0))
                shares_s = f"{shares:g}"
                price_s = f"{price:.2f}"
                cash_s = f"{cash_delta:+.2f}"
            except (TypeError, ValueError):
                shares_s = escape(str(t.get("shares", "")))
                price_s = escape(str(t.get("price", "")))
                cash_s = escape(str(t.get("cash_delta", "")))
            trade_rows += (
                f"<tr>"
                f"<td>{escape(str(t.get('date', '')))}</td>"
                f"<td>{escape(str(t.get('run_date', '')))}</td>"
                f"<td>{escape(str(t.get('model', '')))}</td>"
                f"<td>{action_label}</td>"
                f"<td>{escape(str(t.get('ticker', '')))}</td>"
                f"<td>{shares_s}</td>"
                f"<td>{price_s}</td>"
                f"<td>{cash_s}</td>"
                f"</tr>"
            )

    html = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="utf-8"><title>The Agents Anatomy — Benchmark</title>{style}</head>
<body>
  <h1>The Agents Anatomy — täglicher Modell-Benchmark</h1>
  <p>
    Automatisch generiert aus <code>{escape(leaderboard_path)}</code>.
    Insgesamt {len(lb)} Läufe, {lb['model'].nunique()} Modelle,
    Zeitraum {lb['run_date'].min()} bis {lb['run_date'].max()}.
  </p>

  <h2>Letzter Lauf ({escape(str(last_date))})</h2>
  <table>
    <thead><tr>
      <th>Modell</th><th>Prompt</th><th>Trades</th>
      <th>Start</th><th>Ende</th><th>P&L %</th><th>Audit</th>
    </tr></thead>
    <tbody>{last_rows}</tbody>
  </table>

  <h2>Aggregat (alle Läufe)</h2>
  <table>
    <thead><tr>
      <th>Modell</th><th>Runs</th><th>Ø P&L %</th>
      <th>Best %</th><th>Worst %</th><th>Ø Trades</th>
    </tr></thead>
    <tbody>{agg_rows}</tbody>
  </table>

  <h2>Trade-Historie ({len(trades)} Trades)</h2>
  <table>
    <thead><tr>
      <th>Datum</th><th>Run</th><th>Modell</th><th>Aktion</th>
      <th>Ticker</th><th>Stück</th><th>Preis</th><th>Cash-Δ</th>
    </tr></thead>
    <tbody>{trade_rows}</tbody>
  </table>

  <h2>Verlauf</h2>
  <img src="pnl_history.png" alt="P&L history per model">
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[report] geschrieben nach {out_path}")
    return out_path


def _parse():
    p = argparse.ArgumentParser()
    p.add_argument("--leaderboard", type=str, default="data/leaderboard.csv")
    p.add_argument("--out", type=str, default="docs/index.html")
    p.add_argument("--run-root", type=str, default="data/runs")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse()
    build_report(args.leaderboard, args.out, args.run_root)
