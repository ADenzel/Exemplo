"""Carga de dados REAIS da Binance (funding historico + OHLCV spot) via ccxt.

Nao usa a testnet: funding historico so existe em produção (endpoint publico,
sem necessidade de API key). Os dados sao cacheados em data/real/ para que o
backtest seja reproduzivel offline.

    python -m engine.realdata --start 2020-09-06 --end 2025-09-06

Se a rede do ambiente bloquear a Binance, o comando falha com uma mensagem
explicita -- ele nunca inventa dados.
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import ccxt
import numpy as np
import pandas as pd

import config
from engine.market import Market

REAL_DIR = config.DATA_DIR / "real"
REAL_DIR.mkdir(parents=True, exist_ok=True)

FUNDING_CSV = REAL_DIR / "funding_real.csv"
PRICES_CSV = REAL_DIR / "prices_real.csv"


def _client() -> ccxt.binance:
    """Cliente de PRODUCAO (dados publicos). Sandbox nao tem historico."""
    return ccxt.binance({"enableRateLimit": True, "options": {"defaultType": "future"}})


def fetch_funding_history(symbol: str, start: str, end: str, ex=None) -> pd.DataFrame:
    """Funding de 8h do perpetuo, paginado ate cobrir a janela."""
    ex = ex or _client()
    market = f"{symbol}:USDT"
    since = ex.parse8601(f"{start}T00:00:00Z")
    until = ex.parse8601(f"{end}T00:00:00Z")
    rows = []
    while since < until:
        batch = ex.fetch_funding_rate_history(market, since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        nxt = batch[-1]["timestamp"] + 1
        if nxt <= since:
            break
        since = nxt
        time.sleep(ex.rateLimit / 1000)
    if not rows:
        return pd.DataFrame(columns=["ts", "rate"])
    df = pd.DataFrame([{"ts": r["timestamp"], "rate": float(r["fundingRate"])} for r in rows])
    df = df[df["ts"] < until].drop_duplicates("ts").sort_values("ts")
    return df


def fetch_ohlcv(symbol: str, start: str, end: str, ex=None) -> pd.DataFrame:
    ex = ex or ccxt.binance({"enableRateLimit": True})
    since = ex.parse8601(f"{start}T00:00:00Z")
    until = ex.parse8601(f"{end}T00:00:00Z")
    rows = []
    while since < until:
        batch = ex.fetch_ohlcv(symbol, timeframe="1d", since=since, limit=1000)
        if not batch:
            break
        rows.extend(batch)
        nxt = batch[-1][0] + 86_400_000
        if nxt <= since:
            break
        since = nxt
        time.sleep(ex.rateLimit / 1000)
    df = pd.DataFrame(rows, columns=["ts", "o", "h", "l", "c", "v"])
    return df[df["ts"] < until].drop_duplicates("ts").sort_values("ts")


def download(start: str, end: str, symbols=None) -> None:
    symbols = symbols or config.SYMBOLS
    fut, spot = _client(), ccxt.binance({"enableRateLimit": True})
    f_frames, p_frames = {}, {}
    for sym in symbols:
        print(f"  {sym} ...", flush=True)
        try:
            fh = fetch_funding_history(sym, start, end, fut)
            oh = fetch_ohlcv(sym, start, end, spot)
        except ccxt.NetworkError as e:
            raise SystemExit(
                f"\nRede bloqueada para a Binance ({type(e).__name__}). "
                "Rode este comando em uma maquina com acesso a api.binance.com "
                "e fapi.binance.com."
            ) from e
        if fh.empty or oh.empty:
            print(f"    sem dados para {sym}, pulando")
            continue
        fh["date"] = pd.to_datetime(fh["ts"], unit="ms").dt.floor("D")
        # 3 pagamentos de 8h por dia -> funding diario e a SOMA do dia
        f_frames[sym] = fh.groupby("date")["rate"].sum()
        oh["date"] = pd.to_datetime(oh["ts"], unit="ms").dt.floor("D")
        p_frames[sym] = oh.set_index("date")["c"]

    pd.DataFrame(f_frames).to_csv(FUNDING_CSV)
    pd.DataFrame(p_frames).to_csv(PRICES_CSV)
    print(f"\nSalvo: {FUNDING_CSV}\n       {PRICES_CSV}")


def load(start: str | None = None, end: str | None = None) -> Market:
    """Carrega o cache real como um `Market` consumivel pelo backtest."""
    if not (FUNDING_CSV.exists() and PRICES_CSV.exists()):
        raise FileNotFoundError(
            f"Cache real ausente. Rode: python -m engine.realdata "
            f"--start {start or '2020-09-06'} --end {end or '2025-09-06'}"
        )
    f = pd.read_csv(FUNDING_CSV, index_col=0, parse_dates=True)
    p = pd.read_csv(PRICES_CSV, index_col=0, parse_dates=True)
    idx = f.index.intersection(p.index)
    if start:
        idx = idx[idx >= pd.Timestamp(start)]
    if end:
        idx = idx[idx < pd.Timestamp(end)]
    cols = [c for c in f.columns if c in p.columns]
    f, p = f.loc[idx, cols].ffill().fillna(0.0), p.loc[idx, cols].ffill()
    return Market(pd.DatetimeIndex(idx), p.reset_index(drop=True), f.reset_index(drop=True))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2020-09-06")
    ap.add_argument("--end", default="2025-09-06")
    args = ap.parse_args()
    print(f"Baixando dados reais da Binance {args.start} -> {args.end}")
    download(args.start, args.end)
