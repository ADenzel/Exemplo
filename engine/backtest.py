"""Motor de backtest diario que orquestra Core + Turbo + Lotto.

Contabiliza tres sleeves separados (para permitir o rebalanceamento mensal
exigido) e produz a curva de equity + as metricas da funcao objetivo

    f = CAGR * Sharpe / (1 + |MaxDD|)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

import config
from engine.core import CoreEngine
from engine.lotto import LottoEngine, detect_crash_series
from engine.market import Market, generate
from engine.turbo import TurboEngine


@dataclass
class BacktestResult:
    equity: pd.Series
    daily_returns: pd.Series
    metrics: dict
    params: dict
    log: pd.DataFrame = field(default_factory=pd.DataFrame)

    def __getitem__(self, k):
        return self.metrics[k]


# ------------------------------------------------------------------- metricas


def max_drawdown(equity: np.ndarray) -> float:
    peak = np.maximum.accumulate(equity)
    return float((equity / peak - 1.0).min())


def rolling_max_drawdown(equity: np.ndarray, window: int = 30) -> float:
    """Pior queda pico-a-vale dentro de qualquer janela de `window` dias."""
    worst = 0.0
    n = len(equity)
    if n <= 1:
        return 0.0
    s = pd.Series(equity)
    roll_peak = s.rolling(window, min_periods=1).max()
    worst = float((s / roll_peak - 1.0).min())
    return worst


def compute_metrics(equity: np.ndarray, initial: float) -> dict:
    eq = np.asarray(equity, dtype=float)
    n = len(eq)
    years = n / 365.0
    final = float(eq[-1])
    cagr = (final / initial) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    rets = np.diff(eq) / eq[:-1]
    vol = float(rets.std(ddof=1)) if len(rets) > 1 else 0.0
    sharpe = float(rets.mean() / vol * np.sqrt(365.0)) if vol > 1e-12 else 0.0
    mdd = max_drawdown(eq)
    mdd30 = rolling_max_drawdown(eq, 30)
    objective = cagr * sharpe / (1.0 + abs(mdd)) if sharpe > 0 else 0.0
    return {
        "CAGR": cagr,
        "Sharpe": sharpe,
        "MaxDD": mdd,
        "MaxDD30d": mdd30,
        "FinalCapital": final,
        "Objective": objective,
        "Days": n,
        "AnnVol": vol * np.sqrt(365.0),
    }


def time_to_multiple(equity: np.ndarray, initial: float, mult: float = 10.0):
    """Dias ate multiplicar o capital por `mult` (None se nunca atingiu)."""
    hits = np.where(np.asarray(equity) >= initial * mult)[0]
    return int(hits[0]) if len(hits) else None


# ------------------------------------------------------------------- backtest


def run_backtest(params: dict | None = None, market: Market | None = None,
                 capital: float | None = None, keep_log: bool = False) -> BacktestResult:
    p = config.validate(dict(config.as_dict(), **(params or {})))
    mkt = market if market is not None else generate()
    cap0 = capital if capital is not None else config.CAPITAL_INICIAL

    core = CoreEngine(params=p)
    turbo = TurboEngine(params=p)
    lotto = LottoEngine(params=p)

    sleeves = {
        "core": cap0 * p["ALOCATION_CORE"],
        "turbo": cap0 * p["ALOCATION_TURBO"],
        "lotto": cap0 * p["ALOCATION_LOTTO"],
    }

    symbols = list(mkt.funding.columns)
    f_arr = mkt.funding.to_numpy()
    px_arr = mkt.prices.to_numpy()
    n = len(mkt.dates)

    equity = np.empty(n)
    rows = []
    # EMA do funding = sinal de decisao (defasado 1 dia), suaviza o ruido diario
    alpha = 2.0 / (config.SIGNAL_EMA_DAYS + 1.0)
    ema = {}
    prev_ema: dict[str, float] = {}
    for i in range(n):
        # NaN = par ainda nao listado -> nao negociavel
        fundings = {s: float(f_arr[i, j]) for j, s in enumerate(symbols)
                    if not np.isnan(f_arr[i, j])}
        crashes = [s for j, s in enumerate(symbols)
                   if detect_crash_series(px_arr[:, j], i)]

        # decisao usa a EMA do funding ate D-1 (unico observavel ao entrar)
        if config.USE_LOOKAHEAD_SIGNAL:
            signal = dict(fundings)                       # modelo original
        else:
            signal = dict(prev_ema) if prev_ema else dict(fundings)
            signal = {s: v for s, v in signal.items() if s in fundings}

        pnl_c, info_c = core.step(sleeves["core"], fundings, signal)
        pnl_t, info_t = turbo.step(sleeves["turbo"], fundings, signal)
        prices_today = {s: float(px_arr[i, j]) for j, s in enumerate(symbols)}
        pnl_l, info_l = lotto.step(sleeves["lotto"], crashes, prices_today)

        sleeves["core"] += pnl_c
        sleeves["turbo"] += pnl_t
        sleeves["lotto"] += pnl_l

        for s_, f_ in fundings.items():
            ema[s_] = f_ if s_ not in ema else ema[s_] + alpha * (f_ - ema[s_])
        prev_ema = dict(ema)

        total = sum(sleeves.values())
        # rebalanceamento mensal
        if i > 0 and mkt.dates[i].day == 1:
            sleeves = rebalance(sleeves, total)
        equity[i] = total

        if keep_log:
            rows.append({
                "date": mkt.dates[i], "equity": total,
                "core": sleeves["core"], "turbo": sleeves["turbo"],
                "lotto": sleeves["lotto"],
                "core_pnl": pnl_c, "turbo_pnl": pnl_t, "lotto_pnl": pnl_l,
                "core_mode": info_c["mode"], "turbo_open": info_t["open"],
                "lotto_trades": info_l["trades"],
                "funding_btc": fundings.get("BTC/USDT", 0.0),
            })

    metrics = compute_metrics(equity, cap0)
    metrics["TimeTo10x_days"] = time_to_multiple(equity, cap0, 10.0)
    eq = pd.Series(equity, index=mkt.dates, name="equity")
    return BacktestResult(
        equity=eq,
        daily_returns=eq.pct_change().fillna(0.0),
        metrics=metrics,
        params=p,
        log=pd.DataFrame(rows) if keep_log else pd.DataFrame(),
    )


def rebalance(sleeves: dict, total: float) -> dict:
    """Se Turbo > 35% do equity move 85% do excesso pro Core.
    Se Lotto > 20% do equity move 100% do excesso pro Core."""
    s = dict(sleeves)
    cap_t = total * config.REBALANCE_TURBO_CAP
    if s["turbo"] > cap_t:
        move = (s["turbo"] - cap_t) * config.REBALANCE_TURBO_MOVE
        s["turbo"] -= move
        s["core"] += move
    cap_l = total * config.REBALANCE_LOTTO_CAP
    if s["lotto"] > cap_l:
        move = (s["lotto"] - cap_l) * config.REBALANCE_LOTTO_MOVE
        s["lotto"] -= move
        s["core"] += move
    return s
