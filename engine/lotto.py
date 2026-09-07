"""LOTTO ENGINE - compra de desconto apos crash.

Gatilho: queda >= 8% em 3 dias (OHLCV 1d).

IMPORTANTE: o enunciado original define este sleeve como "+3% de lucro"
garantido. Isso e um gerador de dinheiro sem risco e domina qualquer backtest.
Aqui a aposta e resolvida contra o caminho REAL de precos: entra no fechamento
do crash, sai no alvo (+3%), no stop (-8%) ou por tempo (MAX_HOLD dias) -- o que
vier primeiro. O resultado pode ser negativo, como na vida real.

Use `LOTTO_DETERMINISTIC = True` em config para reproduzir a versao idealizada
do enunciado.
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
        ohlcv = client.fetch_ohlcv(symbol, timeframe="1d",
                                   limit=config.LOTTO_CRASH_LOOKBACK + 1)
    closes = ([c[4] for c in ohlcv]
              if ohlcv and isinstance(ohlcv[0], (list, tuple)) else list(ohlcv))
    n = config.LOTTO_CRASH_LOOKBACK
    if len(closes) < n + 1:
        return False
    return closes[-1] / closes[-1 - n] - 1.0 <= config.LOTTO_CRASH_THRESHOLD


def detect_crash_series(closes: np.ndarray, i: int) -> bool:
    """Versao vetorizada para backtest: crash no indice `i` da serie."""
    n = config.LOTTO_CRASH_LOOKBACK
    if i < n:
        return False
    a, b = closes[i], closes[i - n]
    if not np.isfinite(a) or not np.isfinite(b) or b == 0:
        return False
    return a / b - 1.0 <= config.LOTTO_CRASH_THRESHOLD


@dataclass
class LottoPosition:
    symbol: str
    size: float
    entry: float
    days: int = 0


@dataclass
class LottoEngine:
    params: dict = field(default_factory=config.as_dict)
    positions: list[LottoPosition] = field(default_factory=list)
    trades: int = 0
    wins: int = 0

    def step(self, capital: float, crashes: list[str],
             prices: dict[str, float] | None = None) -> tuple[float, dict]:
        """Um dia do sleeve Lotto. Retorna (pnl_usdt, info).

        `prices` sao os fechamentos do dia; sem eles cai no modo deterministico
        do enunciado (+3% por trade).
        """
        fee_leg = config.FEE_RATE + config.SLIPPAGE
        deterministic = prices is None or config.LOTTO_DETERMINISTIC
        pnl = 0.0
        opened = 0

        if deterministic:
            used = crashes[:config.LOTTO_MAX_POSITIONS]
            if used:
                per = capital / len(used)
                for _ in used:
                    size = min(per, config.CAPACITY_PER_SYMBOL)
                    pnl += size * config.LOTTO_TARGET_PROFIT - size * fee_leg * 2
                self.trades += len(used)
                idle = max(capital - per * len(used), 0.0)
                return pnl + idle * config.TBILL_DAILY, \
                    {"trades": len(used), "symbols": used, "open": 0}
            return capital * config.TBILL_DAILY, {"trades": 0, "symbols": [], "open": 0}

        # ---- modo realista: resolve as apostas contra o caminho de precos ----
        deployed = 0.0
        for pos in list(self.positions):
            px = prices.get(pos.symbol)
            if px is None or not np.isfinite(px):
                continue
            pos.days += 1
            ret = px / pos.entry - 1.0
            hit_target = ret >= config.LOTTO_TARGET_PROFIT
            hit_stop = ret <= config.LOTTO_STOP_LOSS
            expired = pos.days >= config.LOTTO_MAX_HOLD
            if hit_target or hit_stop or expired:
                realized = (config.LOTTO_TARGET_PROFIT if hit_target else
                            config.LOTTO_STOP_LOSS if hit_stop else ret)
                pnl += pos.size * realized - pos.size * fee_leg   # taxa de saida
                self.trades += 1
                self.wins += int(realized > 0)
                self.positions.remove(pos)
            else:
                deployed += pos.size

        free_slots = config.LOTTO_MAX_POSITIONS - len(self.positions)
        for sym in crashes[:max(free_slots, 0)]:
            px = prices.get(sym)
            if px is None or not np.isfinite(px):
                continue
            size = min(capital / config.LOTTO_MAX_POSITIONS, config.CAPACITY_PER_SYMBOL)
            self.positions.append(LottoPosition(sym, size, px))
            pnl -= size * fee_leg                                  # taxa de entrada
            deployed += size
            opened += 1

        idle = max(capital - deployed, 0.0)
        return pnl + idle * config.TBILL_DAILY, {
            "trades": opened, "symbols": [p.symbol for p in self.positions],
            "open": len(self.positions),
        }
