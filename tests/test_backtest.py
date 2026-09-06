"""Teste 1 - Backtest completo 2021-2026."""
import json

import pytest

import config
from engine.backtest import run_backtest
from engine.market import generate


@pytest.fixture(scope="module")
def result():
    params = config.load_best_params() or {}
    return run_backtest(params, market=generate(), keep_log=True)


def test_horizonte_completo(result):
    assert result.metrics["Days"] >= 1800, "backtest deve cobrir 2021-2026"


def test_cagr(result):
    assert result.metrics["CAGR"] > 1.0, f"CAGR={result.metrics['CAGR']:.3f}"


def test_max_drawdown(result):
    assert result.metrics["MaxDD"] > -0.05, f"MaxDD={result.metrics['MaxDD']:.4f}"
    assert result.metrics["MaxDD30d"] > -0.05, "DD em janela de 30d acima do limite"


def test_capital_final(result):
    assert result.metrics["FinalCapital"] > 5_000_000, \
        f"Final={result.metrics['FinalCapital']:,.0f}"


def test_delta_neutro_e_limites(result):
    p = result.params
    assert p["LEVERAGE_CORE"] <= 3.0
    assert p["LEVERAGE_TURBO"] <= 1.0
    assert abs(p["ALOCATION_CORE"] + p["ALOCATION_TURBO"] + p["ALOCATION_LOTTO"] - 1.0) < 1e-9


def test_sharpe_positivo(result):
    assert result.metrics["Sharpe"] > 1.0
