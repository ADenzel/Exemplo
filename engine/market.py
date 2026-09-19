"""Gerador de mercado sintetico realista para 2021-2026.

Quatro regimes (bull 2021, bear 2022, recovery 2023, bull 2024-2025) com preco
por GBM (drift/vol por regime). O funding e endogeno ao preco:

    funding_day = 0.0003 + ret_30 * 0.12,  clipado em [-0.05%, +0.25%] ao dia

isto e: mercado subindo -> perp em premio -> funding alto pago ao short.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import config

# regime: (inicio, fim, drift anual, vol anual)
REGIMES = [
    ("2021-01-01", "2022-01-01", 1.10, 0.85),   # bull 2021
    ("2022-01-01", "2023-01-01", -0.70, 0.95),  # bear 2022
    ("2023-01-01", "2024-01-01", 0.45, 0.60),   # recovery 2023
    ("2024-01-01", "2026-01-01", 0.85, 0.70),   # bull 2024-2025
]

# beta de vol/drift por simbolo (altcoins mais agressivas que BTC)
SYMBOL_BETA = {
    "BTC/USDT": 1.00, "ETH/USDT": 1.20, "SOL/USDT": 1.60, "ENA/USDT": 2.10,
    "W/USDT": 2.20, "ZRO/USDT": 2.00, "ARB/USDT": 1.70, "OP/USDT": 1.70,
}

FUNDING_BASE = 0.0003
FUNDING_BETA = 0.12
FUNDING_MIN = -0.0005
FUNDING_MAX = 0.0025


@dataclass
class Market:
    dates: pd.DatetimeIndex
    prices: pd.DataFrame     # colunas = SYMBOLS
    funding: pd.DataFrame    # funding diario por simbolo

    def __len__(self) -> int:
        return len(self.dates)

    def slice(self, start=None, end=None) -> "Market":
        idx = self.dates
        mask = np.ones(len(idx), dtype=bool)
        if start is not None:
            mask &= idx >= pd.Timestamp(start)
        if end is not None:
            mask &= idx < pd.Timestamp(end)
        return Market(idx[mask], self.prices.loc[mask].reset_index(drop=True),
                      self.funding.loc[mask].reset_index(drop=True))


def _regime_params(dates: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    drift = np.zeros(len(dates))
    vol = np.zeros(len(dates))
    for start, end, mu, sg in REGIMES:
        m = (dates >= pd.Timestamp(start)) & (dates < pd.Timestamp(end))
        drift[m], vol[m] = mu, sg
    # fora dos regimes definidos usa o ultimo
    if (vol == 0).any():
        drift[vol == 0] = REGIMES[-1][2]
        vol[vol == 0] = REGIMES[-1][3]
    return drift, vol


def generate(start: str = config.BACKTEST_START, end: str = config.BACKTEST_END,
             symbols=None, seed: int = 42) -> Market:
    """Gera precos GBM por regime e o funding derivado do retorno de 30 dias."""
    symbols = symbols or config.SYMBOLS
    dates = pd.date_range(start, end, freq="D", inclusive="left")
    n = len(dates)
    rng = np.random.default_rng(seed)
    drift, vol = _regime_params(dates)
    dt = 1.0 / 365.0

    prices, fundings = {}, {}
    for k, sym in enumerate(symbols):
        beta = SYMBOL_BETA.get(sym, 1.5)
        mu = drift * beta
        sg = vol * beta
        shocks = rng.standard_normal(n)
        # componente de mercado comum + idiossincratico (correlacao ~0.6)
        common = rng.standard_normal(n) if k == 0 else common
        z = 0.6 * common + 0.8 * shocks
        logret = (mu - 0.5 * sg ** 2) * dt + sg * np.sqrt(dt) * z
        px = 100.0 * np.exp(np.cumsum(logret))
        prices[sym] = px

        ret30 = np.zeros(n)
        ret30[30:] = px[30:] / px[:-30] - 1.0
        f = np.clip(FUNDING_BASE + ret30 * FUNDING_BETA, FUNDING_MIN, FUNDING_MAX)
        fundings[sym] = f

    return Market(dates, pd.DataFrame(prices, columns=symbols),
                  pd.DataFrame(fundings, columns=symbols))
