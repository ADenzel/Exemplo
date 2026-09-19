"""Teste 3 - Integracao real com a Binance Testnet.

Conecta em testnet.binance.vision (sandbox ccxt), busca saldo, funding real e
executa 1 trade hedgeado de teste.

O teste PULA (skip) quando faltam credenciais no .env ou quando a rede nao
alcanca a testnet -- nunca passa "de mentira". Para rodar de verdade:

    cp .env.example .env   # e preencha BINANCE_API_KEY / BINANCE_SECRET
    pytest tests/test_paper.py -v
"""
import os

import pytest

import config
from engine import core, exchange

TEST_SYMBOL = "BTC/USDT"
TEST_NOTIONAL = float(os.getenv("PAPER_TEST_NOTIONAL", "200"))

pytestmark = pytest.mark.integration


def _require_creds():
    if not (config.BINANCE_API_KEY and config.BINANCE_SECRET):
        pytest.skip("BINANCE_API_KEY/BINANCE_SECRET ausentes no .env")


def _skip_if_offline(exc: Exception):
    import ccxt
    if isinstance(exc, (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout)):
        pytest.skip(f"testnet inacessivel a partir deste ambiente: {type(exc).__name__}")
    raise exc


@pytest.fixture(scope="module")
def spot_client():
    _require_creds()
    exchange.reset()
    client = exchange.spot()
    try:
        client.load_markets()
    except Exception as e:
        _skip_if_offline(e)
    return client


def test_sandbox_mode_ativo():
    """set_sandbox_mode(True) deve apontar as URLs para a testnet."""
    exchange.reset()
    client = exchange.spot()
    urls = str(client.urls.get("api", {}))
    assert "testnet" in urls, f"cliente nao esta em sandbox: {urls[:120]}"


def test_saldo_positivo(spot_client):
    try:
        balance = exchange.fetch_usdt_balance(spot_client)
    except Exception as e:
        _skip_if_offline(e)
    assert isinstance(balance, float)
    assert balance > 0, "saldo zerado: pegue fundos no faucet da testnet.binance.vision"


def test_funding_real_e_float():
    _require_creds()
    try:
        rate = core.get_funding_rate(TEST_SYMBOL)
    except Exception as e:
        _skip_if_offline(e)
    assert isinstance(rate, float)
    assert -0.01 < rate < 0.01, f"funding diario implausivel: {rate}"


def test_trade_hedgeado(spot_client):
    """Executa 1 trade delta neutro (BUY SPOT + SELL PERP) e confere o hedge."""
    try:
        price = float(spot_client.fetch_ticker(TEST_SYMBOL)["last"])
        plan = core.execute_delta_neutral(
            TEST_SYMBOL, allocation=TEST_NOTIONAL, leverage=1.0, price=price,
            dry_run=os.getenv("PAPER_DRY_RUN", "0") == "1",
        )
    except Exception as e:
        _skip_if_offline(e)
    assert plan["spot"]["amount"] == pytest.approx(plan["perp"]["amount"])
    assert plan["spot"]["side"] == "buy" and plan["perp"]["side"] == "sell"
    assert plan["delta"] == 0.0
    if "spot_order" in plan:
        core.close_delta_neutral(TEST_SYMBOL, plan["qty"])
