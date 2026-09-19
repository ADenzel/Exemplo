"""Teste 4 - Cenario REALISTA de 5 anos (2020-09-06 -> 2025-09-06).

Roda sobre os dados reais da Binance quando o cache `data/real/` existe; caso
contrario usa o cenario calibrado de `engine/realistic.py` (funding nos niveis
observados, custos reais, datas de listagem, caps da exchange).

Os asserts aqui sao os que uma mesa real usaria -- nao os alvos idealizados do
enunciado.
"""
import numpy as np
import pytest

import config
from engine import realistic
from engine.backtest import max_drawdown, run_backtest

START, END = "2020-09-06", "2025-09-06"

PARAMS = {
    "ALOCATION_CORE": 0.60, "ALOCATION_TURBO": 0.40, "ALOCATION_LOTTO": 0.00,
    "FUNDING_THRESHOLD_CORE": 0.0003, "FUNDING_THRESHOLD_TURBO": 0.0016,
    "LEVERAGE_CORE": 1.5, "TURBO_HOLD_DAYS": 5,
}


def _market(seed: int = 7):
    try:
        from engine import realdata
        return realdata.load(START, END)
    except (FileNotFoundError, ImportError):
        return realistic.generate(START, END, seed=seed)


@pytest.fixture(scope="module")
def result():
    with realistic.real_costs():
        yield run_backtest(PARAMS, market=_market(), keep_log=True)


def test_periodo_de_5_anos(result):
    assert 1780 <= result.metrics["Days"] <= 1840


def test_lucro_liquido_positivo(result):
    assert result.metrics["FinalCapital"] > config.CAPITAL_INICIAL


def test_bate_o_caixa(result):
    """Precisa superar simplesmente deixar o dinheiro em T-Bill."""
    with realistic.real_costs():
        caixa = config.CAPITAL_INICIAL * (1 + config.TBILL_DAILY) ** result.metrics["Days"]
    assert result.metrics["FinalCapital"] > caixa


def test_drawdown_dentro_do_limite(result):
    assert result.metrics["MaxDD30d"] > -0.05


def test_sharpe_plausivel(result):
    """Sharpe alto e esperado em carry, mas acima de ~10 indica modelo quebrado."""
    assert 1.0 < result.metrics["Sharpe"] < 10.0


def test_cagr_em_faixa_plausivel(result):
    """Funding carry entrega ~5-25% a.a. Fora disso o modelo esta irreal."""
    assert 0.02 < result.metrics["CAGR"] < 0.30


def test_robustez_multiplas_sementes():
    """30 caminhos independentes: o resultado nao pode depender de uma semente."""
    finals = []
    with realistic.real_costs():
        for seed in range(1, 31):
            m = run_backtest(PARAMS, market=realistic.generate(START, END, seed=seed))
            finals.append(m.metrics["FinalCapital"])
    finals = np.array(finals)
    assert (finals > config.CAPITAL_INICIAL).mean() >= 0.90, \
        f"so {(finals > config.CAPITAL_INICIAL).mean():.0%} das sementes deram lucro"
    assert np.percentile(finals, 10) > config.CAPITAL_INICIAL


def test_stress_funding_negativo():
    """15 dias de funding -0.05%/dia: sobreviver com DD < 2.5%."""
    with realistic.real_costs():
        mkt = realistic.generate(START, END)
        i0 = len(mkt) // 2
        mkt.funding.iloc[i0:i0 + 15, :] = -0.0005
        res = run_backtest(PARAMS, market=mkt)
    dd = max_drawdown(res.equity.to_numpy()[i0 - 5:i0 + 25])
    assert dd > -0.025, f"DD no stress = {dd:.4f}"


def test_lotto_sem_edge_real():
    """Sem o '+3% garantido', o sleeve LOTTO destroi capital.

    E por isso que o otimizador zera ALOCATION_LOTTO.
    """
    with realistic.real_costs():
        mkt = _market()
        com = run_backtest(dict(PARAMS, ALOCATION_CORE=0.55, ALOCATION_TURBO=0.40,
                                ALOCATION_LOTTO=0.05), market=mkt)
        sem = run_backtest(PARAMS, market=mkt)
    assert sem.metrics["FinalCapital"] > com.metrics["FinalCapital"]
