# price_cache.py — Einmaliges Vorabladen der Kurshistorien.
#
# Vorteile:
#   - Deterministische Simulation (keine flatternden yfinance-Calls).
#   - Schnell: ein Netz-Call pro Ticker statt hunderte.
#   - PriceTool kann jederzeit "as of <day>" abfragen.

from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf


# ticker -> DataFrame mit Index=DatetimeIndex, Spalte "Close"
_CACHE: Dict[str, pd.DataFrame] = {}


def preload(tickers: List[str],
            start: date,
            end: Optional[date] = None,
            lookback_days: int = 400) -> None:
    """Lädt für alle Ticker eine ausreichend große Historie vor.

    Wir laden bewusst etwas mehr Historie *vor* start, damit der Agent
    an Tag 1 der Simulation auch schon 30/60/... Tage zurückschauen kann.
    """
    if end is None:
        end = date.today()

    real_start = start - timedelta(days=lookback_days)

    for t in tickers:
        print(f"[price_cache] preload {t} {real_start} -> {end}")
        df = yf.Ticker(t).history(start=real_start.isoformat(),
                                  end=(end + timedelta(days=1)).isoformat())
        if df.empty:
            print(f"[price_cache] WARN: no data for {t}")
            _CACHE[t] = pd.DataFrame(columns=["Close"])
            continue
        # Nur Close behalten, fehlende Werte entfernen und tz-normalisieren.
        # yfinance kann für einzelne Tage NaN liefern; das darf später nicht
        # zu NaN in simulation_equity.csv / summary.json führen.
        df = df[["Close"]].copy()
        df = df.dropna(subset=["Close"])
        if df.empty:
            print(f"[price_cache] WARN: only NaN close data for {t}")
            _CACHE[t] = pd.DataFrame(columns=["Close"])
            continue
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        _CACHE[t] = df


def is_loaded() -> bool:
    return bool(_CACHE)


def get_prices_up_to(ticker: str, as_of: date, days: int) -> List[dict]:
    """Gibt die letzten `days` Handelstage <= as_of für `ticker` zurück."""
    if ticker not in _CACHE:
        return []
    df = _CACHE[ticker]
    as_of_ts = pd.Timestamp(as_of)
    sub = df[df.index <= as_of_ts]
    if sub.empty:
        return []
    sub = sub.tail(max(1, days))
    return [
        {"date": idx.strftime("%Y-%m-%d"), "close": float(row["Close"])}
        for idx, row in sub.iterrows()
    ]


def trading_days_between(start: date, end: date) -> List[date]:
    """Handelstage (aus der geladenen Historie irgendeines Tickers) im Bereich."""
    if not _CACHE:
        return []
    any_df = next(iter(_CACHE.values()))
    idx = any_df.index
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    return [d.date() for d in idx if start_ts <= d <= end_ts]