"""LOTTO ENGINE - compra de desconto apos crash.

Se um simbolo cai mais de 8% em 3 dias, compra o desconto e simula +3% de lucro
no repique. Fora disso o sleeve fica em T-Bill.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import config
from engine import exchange


def detect_crash(symbol: str, ohlcv=None, client=None) -> bool:
    """True se o fechamento caiu >= 8% nos ultimos 3 dias (OHLCV 1d)."""
    if ohlcv is None:
        client = client or exchange.spot()
        ohlcv = client.fetch_ohlcv(symbol, timeframe="1d", limit=config.LOTTO_CRASH_LOOKBACK + 1)
    closes = [c[4] for c in ohlcv] if ohlcv and isinstance(ohlcv[0], (list, tuple)) else list(ohlcv)
    n = config.LOTTO_CRASH_LOOKBACK
    if len(closes) < n + 1:
        return False
    ret = closes[-1] / closes[-1 - n] - 1.0
    return ret <= config.LOTTO_CRASH_THRESHOLD


def detect_crash_series(closes: np.ndarray, i: int) -> bool:
    """Versao vetorizada para backtest: crash no indice `i` da serie."""
    n = config.LOTTO_CRASH_LOOKBACK
    if i < n:
        return False
    return closes[i] / closes[i - n] - 1.0 <= config.LOTTO_CRASH_THRESHOLD


@dataclass
class LottoEngine:
    params: dict = field(default_factory=config.as_dict)
    trades: int = 0

    def step(self, capital: float, crashes: list[str]) -> tuple[float, dict]:
        """Um dia do sleeve Lotto. Retorna (pnl_usdt, info)."""
        if not crashes:
            return capital * config.TBILL_DAILY, {"trades": 0, "symbols": []}
        used = crashes[:3]
        per = capital / len(used)
        fee_leg = config.FEE_RATE + config.SLIPPAGE
        pnl = 0.0
        for _ in used:
            size = min(per, config.CAPACITY_PER_SYMBOL)
            pnl += size * config.LOTTO_TARGET_PROFIT - size * fee_leg * 2
        self.trades += len(used)
        idle = max(capital - per * len(used), 0.0)
        return pnl + idle * config.TBILL_DAILY, {"trades": len(used), "symbols": used}
