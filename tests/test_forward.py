"""Teste 2 - Walk-forward anti-overfitting + stress de funding negativo."""
import numpy as np
import pytest

import config
from engine.backtest import run_backtest, max_drawdown
from engine.market import generate
from optimizer.grid_search import best_params, run_grid


@pytest.fixture(scope="module")
def market():
    return generate()


@pytest.fixture(scope="module")
def walk_forward(market):
    is_mkt = market.slice(config.BACKTEST_START, config.IS_END)      # 2021-2023
    oos_mkt = market.slice(config.OOS_START, config.BACKTEST_END)    # 2024-2026
    df_is = run_grid(market=is_mkt, verbose=False)
    params = best_params(df_is)
    res_is = run_backtest(params, market=is_mkt)
    res_oos = run_backtest(params, market=oos_mkt)
    return params, res_is, res_oos


def test_oos_nao_degrada(walk_forward):
    _, res_is, res_oos = walk_forward
    cagr_is, cagr_oos = res_is.metrics["CAGR"], res_oos.metrics["CAGR"]
    assert cagr_oos > 0.8 * cagr_is, \
        f"overfitting: CAGR_IS={cagr_is:.3f} CAGR_OOS={cagr_oos:.3f}"


def test_oos_respeita_drawdown(walk_forward):
    _, _, res_oos = walk_forward
    assert res_oos.metrics["MaxDD30d"] > -0.05


def test_stress_funding_negativo(market):
    """15 dias seguidos de funding -0.05% ao dia: sobreviver com DD < 2.5%."""
    params = config.load_best_params() or {}
    stressed = generate()
    n = len(stressed.dates)
    start = n // 2
    stressed.funding.iloc[start:start + 15, :] = -0.0005

    res = run_backtest(params, market=stressed)
    window = res.equity.to_numpy()[start - 5:start + 25]
    dd = max_drawdown(window)
    assert dd > -0.025, f"DD no stress = {dd:.4f}"
    assert res.equity.iloc[-1] > config.CAPITAL_INICIAL, "estrategia nao sobreviveu"
