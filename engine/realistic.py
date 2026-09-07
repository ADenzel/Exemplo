"""Cenario REALISTA calibrado a niveis observados de funding na Binance.

Diferencas para `engine/market.py` (que segue a formula sintetica do enunciado
`funding = 0.0003 + ret_30*0.12`, otimista demais):

1. Funding calibrado por periodo aos niveis efetivamente observados na Binance
   (media em % por intervalo de 8h), com AR(1) e episodios negativos reais.
2. Cap de funding da propria exchange: +-0.05%/8h em BTC/ETH, +-0.30%/8h em alts.
3. Datas de listagem: cada alt so e negociavel a partir da listagem real do perp.
4. Custos reais: taker spot 0.10% + taker perp 0.04% por perna, slippage,
   e custo de margem para a parte alavancada.

Calibracao aproximada por memoria dos niveis historicos -- NAO substitui o
histórico real. Use `engine/realdata.py` para rodar sobre os dados de verdade.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config
from engine.market import Market

# (inicio, fim, media %/8h do BTC, desvio %/8h)
FUNDING_REGIMES = [
    ("2020-09-06", "2021-01-01", 0.0100, 0.012),   # alta pos-halving
    ("2021-01-01", "2021-05-15", 0.0280, 0.025),   # euforia, funding no teto
    ("2021-05-15", "2021-10-01", 0.0040, 0.018),   # pos-crash de maio, negativo
    ("2021-10-01", "2022-01-01", 0.0110, 0.016),   # topo de novembro
    ("2022-01-01", "2023-01-01", 0.0020, 0.012),   # bear, LUNA/FTX, muito negativo
    ("2023-01-01", "2023-10-01", 0.0050, 0.010),   # lateral
    ("2023-10-01", "2024-04-01", 0.0190, 0.020),   # rally do ETF + halving
    ("2024-04-01", "2024-10-01", 0.0080, 0.014),   # correcao/lateral
    ("2024-10-01", "2025-02-01", 0.0170, 0.020),   # rally pos-eleicao
    ("2025-02-01", "2025-09-06", 0.0060, 0.013),   # normalizacao
]

# multiplicador de media / volatilidade do funding vs BTC
SYMBOL_FUNDING = {
    "BTC/USDT": (1.00, 1.00), "ETH/USDT": (1.05, 1.15), "SOL/USDT": (1.40, 1.80),
    "ENA/USDT": (2.30, 2.60), "W/USDT": (1.80, 2.40), "ZRO/USDT": (1.60, 2.30),
    "ARB/USDT": (1.25, 1.90), "OP/USDT": (1.25, 1.90),
}

# listagem real do perpetuo USDT-M
LISTING = {
    "BTC/USDT": "2019-09-08", "ETH/USDT": "2019-11-27", "SOL/USDT": "2020-09-14",
    "ARB/USDT": "2023-03-23", "OP/USDT": "2022-06-01", "ENA/USDT": "2024-04-02",
    "W/USDT": "2024-04-03", "ZRO/USDT": "2024-06-20",
}

# cap de funding da exchange, por intervalo de 8h
CAP_MAJOR = 0.0005    # 0.05%
CAP_ALT = 0.0030      # 0.30%
MAJORS = {"BTC/USDT", "ETH/USDT"}

# volatilidade anual de preco por periodo (para o sleeve Lotto)
PRICE_VOL = {"BTC/USDT": 0.55, "ETH/USDT": 0.70, "SOL/USDT": 0.95, "ENA/USDT": 1.20,
             "W/USDT": 1.25, "ZRO/USDT": 1.15, "ARB/USDT": 1.00, "OP/USDT": 1.00}

PHI = 0.85            # persistencia AR(1) diaria do funding


def _regime_series(dates: pd.DatetimeIndex):
    mu = np.full(len(dates), FUNDING_REGIMES[-1][2])
    sd = np.full(len(dates), FUNDING_REGIMES[-1][3])
    for start, end, m, s in FUNDING_REGIMES:
        mask = (dates >= pd.Timestamp(start)) & (dates < pd.Timestamp(end))
        mu[mask], sd[mask] = m, s
    return mu / 100.0, sd / 100.0     # % -> fracao, por 8h


def generate(start: str = "2020-09-06", end: str = "2025-09-06",
             symbols=None, seed: int = 7) -> Market:
    symbols = symbols or config.SYMBOLS
    dates = pd.date_range(start, end, freq="D", inclusive="left")
    n = len(dates)
    rng = np.random.default_rng(seed)
    mu8, sd8 = _regime_series(dates)

    # choque comum de mercado (funding e fortemente correlacionado entre pares)
    common = np.zeros(n)
    e = rng.standard_normal(n)
    for i in range(1, n):
        common[i] = PHI * common[i - 1] + np.sqrt(1 - PHI ** 2) * e[i]

    fundings, prices = {}, {}
    for sym in symbols:
        fmul, fvol = SYMBOL_FUNDING.get(sym, (1.3, 2.0))
        idio = np.zeros(n)
        ei = rng.standard_normal(n)
        for i in range(1, n):
            idio[i] = PHI * idio[i - 1] + np.sqrt(1 - PHI ** 2) * ei[i]
        z = 0.75 * common + 0.66 * idio
        rate8 = mu8 * fmul + sd8 * fvol * z
        cap = CAP_MAJOR if sym in MAJORS else CAP_ALT
        rate8 = np.clip(rate8, -cap, cap)
        daily = rate8 * config.FUNDING_INTERVALS_PER_DAY

        # antes da listagem o par nao existe -> funding neutro e nao elegivel
        listed = pd.Timestamp(LISTING.get(sym, start))
        daily = np.where(dates >= listed, daily, np.nan)
        fundings[sym] = daily

        vol = PRICE_VOL.get(sym, 1.0)
        # preco correlacionado ao funding (funding alto = mercado esticado)
        shocks = 0.5 * common + 0.87 * rng.standard_normal(n)
        logret = (-0.5 * vol ** 2) / 365 + vol / np.sqrt(365) * shocks
        px = 100.0 * np.exp(np.cumsum(logret))
        prices[sym] = np.where(dates >= listed, px, np.nan)

    return Market(dates, pd.DataFrame(prices, columns=symbols),
                  pd.DataFrame(fundings, columns=symbols))


# --------------------------------------------------------------- custos reais
REAL_COSTS = {
    "FEE_RATE": 0.0007,             # media ponderada spot 0.10% / perp 0.04%
    "SLIPPAGE": 0.0005,
    "BORROW_DAILY": 0.00030,        # margem USDT ~ 11% a.a.
    "TBILL_DAILY": 0.00012,         # ~4.5% a.a.
    "CAPACITY_PER_SYMBOL": 400_000.0,
}


class real_costs:
    """Context manager que aplica o quadro de custos reais ao config global."""

    def __enter__(self):
        self._saved = {k: getattr(config, k) for k in REAL_COSTS}
        for k, v in REAL_COSTS.items():
            setattr(config, k, v)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            setattr(config, k, v)
        return False
