"""Parametros globais e espaco de busca do otimizador.

Todos os valores marcados como "otimizavel" possuem um range associado em
`PARAM_GRID`, consumido por `optimizer/grid_search.py`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")

# ----------------------------------------------------------------- credenciais
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET = os.getenv("BINANCE_SECRET", "")
TESTNET = True

# --------------------------------------------------------------------- capital
CAPITAL_INICIAL = 100_000.0

# ------------------------------------------------------- alocacao (soma == 1.0)
ALOCATION_CORE = 0.70
ALOCATION_TURBO = 0.25
ALOCATION_LOTTO = 0.05

# ------------------------------------------------------------------ alavancagem
LEVERAGE_CORE = 3.0          # otimizavel [1.5, 3.0]
LEVERAGE_TURBO = 1.0         # trava dura: Turbo <= 1x

# --------------------------------------------------------------------- universo
SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "ENA/USDT",
    "W/USDT", "ZRO/USDT", "ARB/USDT", "OP/USDT",
]

# ----------------------------------------------------------------- thresholds
FUNDING_THRESHOLD_CORE = 0.00015    # otimizavel [0.00005, 0.0003]  (ao dia)
FUNDING_THRESHOLD_TURBO = 0.0012    # otimizavel [0.0008, 0.0020]   (ao dia)
STOP_FUNDING_NEGATIVE = -0.0002     # otimizavel [-0.0005, -0.0001] (ao dia)
TURBO_HOLD_DAYS = 3                 # otimizavel [1, 5]

# ------------------------------------------------------------------ mecanica
MAX_CORE_POSITIONS = 4
# Histerese: so troca de simbolo se o candidato bater o atual por uma margem que
# pague o round-trip. Sem isso a estrategia gira todo dia e as taxas comem o carry.
CORE_EXIT_FRACTION = 0.5            # segura enquanto funding >= threshold * 0.5
CORE_SWITCH_EDGE = 0.00025          # vantagem diaria minima para trocar
CORE_MIN_HOLD_DAYS = 7
# O funding diario e ruidoso mas persistente: a decisao usa uma EMA, nao o print
# do dia. Sem isso a estrategia gira ~0.6 simbolo/dia e as taxas superam o carry.
SIGNAL_EMA_DAYS = 7
# Flags de auditoria: reproduzem o modelo ORIGINAL (com os defeitos) para medir
# quanto cada correcao vale. Ver bridge.py. Nao mexa para rodar a estrategia.
USE_LOOKAHEAD_SIGNAL = False        # True = decide com o funding do proprio dia
CORE_CAPACITY_MODE = "cap"          # "cap" = excedente em caixa; "decay" = original
MAX_TURBO_POSITIONS = 4
TBILL_DAILY = 0.00014               # 0.014% ao dia (caixa / gatekeeper ligado)
FEE_RATE = 0.0004                   # taker por perna, por giro de nocional
SLIPPAGE = 0.0002                   # por perna
LOTTO_CRASH_LOOKBACK = 3            # dias
LOTTO_CRASH_THRESHOLD = -0.08       # -8% em 3 dias
LOTTO_TARGET_PROFIT = 0.03          # +3% no repique (alvo)
LOTTO_STOP_LOSS = -0.08             # stop se afundar mais 8%
LOTTO_MAX_HOLD = 5                  # dias ate sair a mercado
LOTTO_MAX_POSITIONS = 3
# True reproduz o enunciado (+3% garantido por trade, sem risco).
# False (padrao) resolve a aposta contra o caminho real de precos.
LOTTO_DETERMINISTIC = False
FUNDING_INTERVALS_PER_DAY = 3       # funding a cada 8h

# --------------------------------------------------- capacidade / custo de capital
# Arbitragem de funding tem capacidade finita: acima de CAPACITY_PER_SYMBOL de
# nocional o proprio fluxo comprime a base e o funding efetivamente capturado cai
# com sqrt(capacidade / nocional). Sem isso o backtest compoe ate numeros irreais.
CAPACITY_PER_SYMBOL = 600_000.0     # nocional (USDT) sem degradacao
CAPACITY_EXP = 0.5
BORROW_DAILY = 0.00025              # custo diario da parte alavancada (lev - 1)

# ------------------------------------------------------------ rebalanceamento
REBALANCE_TURBO_CAP = 0.35          # Turbo > 35% do equity -> move 85% do excesso
REBALANCE_TURBO_MOVE = 0.85
REBALANCE_LOTTO_CAP = 0.20          # Lotto > 20% do equity -> move 100% do excesso
REBALANCE_LOTTO_MOVE = 1.00

# --------------------------------------------------------------- restricoes
MAX_DD_LIMIT = -0.05                # janela de 30 dias
LEVERAGE_CORE_MAX = 3.0
LEVERAGE_TURBO_MAX = 1.0

# ------------------------------------------------------------ janela backtest
BACKTEST_START = "2021-01-01"
BACKTEST_END = "2026-01-01"
IS_END = "2024-01-01"               # in-sample  2021-2023
OOS_START = "2024-01-01"            # out-of-sample 2024-2026

# ------------------------------------------------------------ grid do otimizador
# Combinacoes de alocacao (core, turbo, lotto) que somam 1.0
ALLOCATION_COMBOS = [
    (0.70, 0.25, 0.05),   # do enunciado
    (0.75, 0.25, 0.00),
    (0.70, 0.30, 0.00),
    (0.80, 0.20, 0.00),
    (0.60, 0.40, 0.00),
    (0.90, 0.10, 0.00),
    (0.65, 0.30, 0.05),
    (1.00, 0.00, 0.00),
]

PARAM_GRID = {
    "ALLOCATION": ALLOCATION_COMBOS,
    "FUNDING_THRESHOLD_CORE": [0.00005, 0.0001, 0.00015, 0.0002, 0.00025, 0.0003],
    "FUNDING_THRESHOLD_TURBO": [0.0008, 0.0012, 0.0016, 0.0020],
    "LEVERAGE_CORE": [1.5, 2.0, 2.5, 3.0],
    "TURBO_HOLD_DAYS": [1, 2, 3, 4, 5],
}

PARAM_RANGES = {
    "ALOCATION_CORE": (0.0, 1.0),
    "ALOCATION_TURBO": (0.0, 1.0),
    "ALOCATION_LOTTO": (0.0, 1.0),
    "LEVERAGE_CORE": (1.5, 3.0),
    "FUNDING_THRESHOLD_CORE": (0.00005, 0.0003),
    "FUNDING_THRESHOLD_TURBO": (0.0008, 0.0020),
    "STOP_FUNDING_NEGATIVE": (-0.0005, -0.0001),
    "TURBO_HOLD_DAYS": (1, 5),
}

BEST_PARAMS_FILE = DATA_DIR / "best_params.json"


def as_dict() -> dict:
    """Snapshot dos parametros correntes (usado por engines e backtest)."""
    return {
        "CAPITAL_INICIAL": CAPITAL_INICIAL,
        "ALOCATION_CORE": ALOCATION_CORE,
        "ALOCATION_TURBO": ALOCATION_TURBO,
        "ALOCATION_LOTTO": ALOCATION_LOTTO,
        "LEVERAGE_CORE": LEVERAGE_CORE,
        "LEVERAGE_TURBO": LEVERAGE_TURBO,
        "FUNDING_THRESHOLD_CORE": FUNDING_THRESHOLD_CORE,
        "FUNDING_THRESHOLD_TURBO": FUNDING_THRESHOLD_TURBO,
        "STOP_FUNDING_NEGATIVE": STOP_FUNDING_NEGATIVE,
        "TURBO_HOLD_DAYS": TURBO_HOLD_DAYS,
    }


def validate(params: dict | None = None) -> dict:
    """Valida restricoes duras. Levanta ValueError se violadas."""
    p = params or as_dict()
    total = p["ALOCATION_CORE"] + p["ALOCATION_TURBO"] + p["ALOCATION_LOTTO"]
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"Alocacoes devem somar 1.0 (soma={total:.6f})")
    if not (1.5 <= p["LEVERAGE_CORE"] <= LEVERAGE_CORE_MAX):
        raise ValueError("LEVERAGE_CORE fora de [1.5, 3.0]")
    if p["LEVERAGE_TURBO"] > LEVERAGE_TURBO_MAX:
        raise ValueError("LEVERAGE_TURBO deve ser <= 1.0")
    if p["STOP_FUNDING_NEGATIVE"] >= 0:
        raise ValueError("STOP_FUNDING_NEGATIVE deve ser negativo")
    return p


def load_best_params() -> dict | None:
    if BEST_PARAMS_FILE.exists():
        return json.loads(BEST_PARAMS_FILE.read_text())
    return None


def apply(params: dict) -> None:
    """Aplica um dict de parametros ao modulo (usado apos o grid search)."""
    g = globals()
    for k, v in params.items():
        if k in g:
            g[k] = v
