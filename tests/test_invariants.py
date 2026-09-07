"""Invariantes de PROCESSO.

Nenhum assert aqui olha para lucro, CAGR ou Sharpe. Todos verificam que o
mecanismo esta correto -- propriedades que precisam valer mesmo que a
estrategia perca dinheiro, e que continuariam valendo se ela ganhasse muito.

Motivo: testar o resultado enviesa o teste. Uma banda do tipo `Sharpe < 8`
esconde uma estrategia boa e aprova uma quebrada que caia dentro da faixa.
Os tres defeitos encontrados neste repositorio (look-ahead, lucro garantido,
taxas em dobro) sao todos violacoes de processo -- nenhum exigia olhar o P&L.
"""
import numpy as np
import pytest

import config
from engine import calibration, realistic
from engine.backtest import run_backtest

START, END = "2020-09-06", "2025-09-06"


@pytest.fixture(scope="module")
def derived():
    with realistic.real_costs():
        mkt = realistic.generate(START, END)
        yield calibration.calibrate_from_market(mkt.funding.to_numpy()), mkt


@pytest.fixture(scope="module")
def run(derived):
    dp, mkt = derived
    with realistic.real_costs():
        calibration.apply(dp)
        params = {"ALOCATION_CORE": 1.0, "ALOCATION_TURBO": 0.0, "ALOCATION_LOTTO": 0.0,
                  "FUNDING_THRESHOLD_CORE": dp.entry_threshold,
                  "FUNDING_THRESHOLD_TURBO": 0.002, "TURBO_HOLD_DAYS": 5,
                  "LEVERAGE_CORE": dp.max_leverage}
        yield run_backtest(params, market=mkt, keep_log=True), params, dp


# --------------------------------------------------------------- causalidade

def test_nenhuma_decisao_usa_o_futuro():
    """Perturbar o funding DEPOIS do dia k nao pode mudar o equity ate k.

    Este e o teste que teria pegado o look-ahead imediatamente. Ele nao depende
    de o resultado ser bom ou ruim -- so de o tempo andar numa direcao so.
    """
    with realistic.real_costs():
        params = {"ALOCATION_CORE": 1.0, "ALOCATION_TURBO": 0.0, "ALOCATION_LOTTO": 0.0,
                  "FUNDING_THRESHOLD_CORE": 0.0003, "FUNDING_THRESHOLD_TURBO": 0.002,
                  "TURBO_HOLD_DAYS": 5, "LEVERAGE_CORE": 1.0}
        base = realistic.generate(START, END)
        k = len(base) // 2

        alterado = realistic.generate(START, END)
        rng = np.random.default_rng(123)
        shape = alterado.funding.iloc[k + 1:, :].shape
        alterado.funding.iloc[k + 1:, :] = rng.uniform(-0.002, 0.004, shape)

        a = run_backtest(params, market=base).equity.to_numpy()[:k + 1]
        b = run_backtest(params, market=alterado).equity.to_numpy()[:k + 1]
    np.testing.assert_allclose(a, b, rtol=0, atol=1e-9)


def test_determinismo():
    """Mesmas entradas, mesma saida. Sem isso nenhum outro teste vale."""
    with realistic.real_costs():
        mkt = realistic.generate(START, END)
        p = {"ALOCATION_CORE": 1.0, "ALOCATION_TURBO": 0.0, "ALOCATION_LOTTO": 0.0,
             "FUNDING_THRESHOLD_CORE": 0.0003, "FUNDING_THRESHOLD_TURBO": 0.002,
             "TURBO_HOLD_DAYS": 5, "LEVERAGE_CORE": 1.0}
        a, b = run_backtest(p, market=mkt), run_backtest(p, market=mkt)
    np.testing.assert_array_equal(a.equity.to_numpy(), b.equity.to_numpy())


# ------------------------------------------------------------- conservacao

def test_conservacao_de_caixa(run):
    """Todo dolar de variacao do equity tem origem declarada.

    equity_final - equity_inicial == funding bruto - taxas - margem + caixa.
    Se nao fechar, existe PnL entrando por um caminho nao auditado -- que foi
    exatamente como o LOTTO imprimia dinheiro sem aparecer na conta.
    """
    res, _, _ = run
    log = res.log
    fluxos = (log["gross"] - log["fees"] - log["borrow"] + log["carry"]).sum()
    variacao = res.equity.iloc[-1] - config.CAPITAL_INICIAL
    assert abs(fluxos - variacao) < 1e-6 * max(abs(variacao), 1.0), \
        f"fluxos={fluxos:,.2f} != variacao={variacao:,.2f}"


def test_taxas_batem_com_o_giro(run):
    """Taxas cobradas == nocional girado x tabela de custos, recalculado à parte.

    Cobre os DOIS caminhos que cobram taxa (rotacao normal e fechamento pelo
    gatekeeper) -- a primeira versao deste teste so cobria um e acusou 17% de
    diferenca, que era o proprio teste incompleto, nao o engine.
    """
    res, _, _ = run
    log = res.log
    with realistic.real_costs():
        esperado = (log["turn_notional"] * (config.FEE_RATE + config.SLIPPAGE)).sum()
    assert abs(esperado - log["fees"].sum()) < 1e-6 * max(log["fees"].sum(), 1.0), \
        f"esperado {esperado:,.2f} vs cobrado {log['fees'].sum():,.2f}"


def test_taxa_por_troca_e_um_round_trip(run):
    """Uma troca de simbolo custa exatamente UM round-trip, nao dois.

    A diferenca simetrica ja conta a saida do antigo e a entrada do novo; cobrar
    x2 em cima disso dobrava o custo. O bug sobreviveu a duas rodadas de revisao
    porque so aparecia como 'resultado um pouco pior', nunca como erro.
    """
    res, _, _ = run
    log = res.log
    trocas = log["rotated"].sum()
    with realistic.real_costs():
        custo_por_unidade = log["fees"].sum() / (log["turn_notional"].sum())
        assert abs(custo_por_unidade - (config.FEE_RATE + config.SLIPPAGE)) < 1e-12
    assert trocas > 0


# ------------------------------------------------------------------ limites

def test_delta_neutro_em_todo_passo(run):
    """Nao 'em media': em todo dia. Um hedge quebrado vira aposta direcional."""
    res, _, _ = run
    assert res.log["delta"].abs().max() == 0.0


def test_alavancagem_nunca_excede(run):
    res, params, dp = run
    assert res.log["leverage"].max() <= dp.max_leverage + 1e-12


def test_numero_de_posicoes_respeitado(run):
    res, _, _ = run
    assert res.log["n_core"].max() <= config.MAX_CORE_POSITIONS


def test_hold_minimo_respeitado(run):
    """Nenhuma posicao pode ser fechada antes do hold minimo por decisao propria."""
    res, _, dp = run
    assert calibration.process_health(res.log)["avg_hold_days"] >= dp.min_hold_days


# ------------------------------------------- coerencia entre modelo e execucao

def test_aritmetica_preve_o_processo(run):
    """A previsao de taxas/bruto feita SEM backtest bate com o observado.

    Este e o teste mais forte do conjunto: se o modelo de custo prediz o
    comportamento medido, o mecanismo esta entendido. Foi ele que expos as
    taxas cobradas em dobro (previsto 0,236; medido 0,483 -- fator exato de 2).
    """
    res, _, dp = run
    previsto = dp.round_trip / (dp.min_hold_days * dp.observed_typical_funding)
    medido = calibration.process_health(res.log)["fee_ratio"]
    assert abs(medido - previsto) / previsto < 0.25, \
        f"previsto {previsto:.4f} vs medido {medido:.4f}"


def test_saude_de_processo_sem_olhar_lucro(run):
    """Veredito operacional. Pode reprovar mesmo com o P&L positivo."""
    res, _, dp = run
    violacoes = calibration.check_health(
        calibration.process_health(res.log), calibration.health_limits(dp))
    assert not violacoes, "; ".join(violacoes)


def test_calibracao_independe_de_escala(derived):
    """Dobrar o capital nao pode mudar um unico parametro derivado.

    Se mudasse, algum resultado da estrategia teria vazado para a calibracao --
    e o modulo estaria escolhendo numeros pelo P&L sem admitir.
    """
    dp, mkt = derived
    with realistic.real_costs():
        a = calibration.calibrate_from_market(mkt.funding.to_numpy())
        config.CAPITAL_INICIAL *= 2
        try:
            b = calibration.calibrate_from_market(mkt.funding.to_numpy())
        finally:
            config.CAPITAL_INICIAL /= 2
    for campo in ("entry_threshold", "exit_threshold", "min_hold_days",
                  "switch_edge", "max_leverage", "ema_span"):
        assert getattr(a, campo) == getattr(b, campo), f"{campo} mudou com a escala"


def test_perda_observada_cabe_na_prevista(run):
    """O drawdown realizado tem que caber na perda que o processo pode gerar.

    A previsao sai da pior media de funding sustentada observada no mercado,
    calculada sem rodar a estrategia. Se o realizado estourar a previsao, existe
    uma fonte de perda fora do modelo.
    """
    res, _, dp = run
    observado = res.metrics["MaxDD"]
    previsto = dp.drawdown_capacity
    assert observado >= previsto * 1.5, \
        f"DD observado {observado:.4%} estoura a capacidade prevista {previsto:.4%}"


def test_nenhuma_constante_magica_na_calibracao():
    """Os unicos numeros livres do modulo sao os quatro axiomas declarados."""
    assert set(calibration.POLICY) == {
        "payback_days", "fee_budget", "slippage_budget", "margin_headroom"}
