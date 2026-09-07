"""Ponte entre o resultado ORIGINAL ($42.3M) e o REALISTA (~$157k).

Liga uma correcao de cada vez e mede o capital final em cada degrau, para que a
diferenca entre os dois numeros seja auditavel em vez de declarada.

    python bridge.py
"""
from __future__ import annotations

import contextlib

import config
from engine import realistic
from engine.backtest import run_backtest
from engine.market import generate as generate_spec

# parametros originais (grid do primeiro run, sobre o modelo original)
P_ORIG = {"ALOCATION_CORE": 0.70, "ALOCATION_TURBO": 0.25, "ALOCATION_LOTTO": 0.05,
          "FUNDING_THRESHOLD_CORE": 0.0003, "FUNDING_THRESHOLD_TURBO": 0.0020,
          "LEVERAGE_CORE": 1.5, "TURBO_HOLD_DAYS": 5}
# parametros reotimizados sobre o engine corrigido
P_NOVO = {"ALOCATION_CORE": 0.60, "ALOCATION_TURBO": 0.40, "ALOCATION_LOTTO": 0.00,
          "FUNDING_THRESHOLD_CORE": 0.0003, "FUNDING_THRESHOLD_TURBO": 0.0016,
          "LEVERAGE_CORE": 1.5, "TURBO_HOLD_DAYS": 5}

# estado do modelo ORIGINAL (todos os defeitos ligados)
ORIGINAL = {
    "LOTTO_DETERMINISTIC": True,      # +3% garantido por trade
    "USE_LOOKAHEAD_SIGNAL": True,     # decide com o funding que vai receber
    "SIGNAL_EMA_DAYS": 1,             # sem suavizacao
    "CORE_MIN_HOLD_DAYS": 0,          # sem hold minimo
    "CORE_SWITCH_EDGE": 0.0,          # troca por qualquer vantagem
    "CORE_EXIT_FRACTION": 1.0,        # sem histerese na saida
    "CORE_CAPACITY_MODE": "decay",    # empurra capital e sofre decaimento
}


@contextlib.contextmanager
def state(**overrides):
    saved = {k: getattr(config, k) for k in overrides}
    for k, v in overrides.items():
        setattr(config, k, v)
    try:
        yield
    finally:
        for k, v in saved.items():
            setattr(config, k, v)


def run(flags: dict, params: dict, market) -> float:
    with state(**flags):
        return run_backtest(params, market=market)["FinalCapital"]


def main() -> None:
    spec = generate_spec()                                   # mercado do enunciado
    real = realistic.generate("2020-09-06", "2025-09-06")    # mercado calibrado

    steps = []
    f = dict(ORIGINAL)

    steps.append(("0. Modelo original, como entregue", run(f, P_ORIG, spec)))

    f["USE_LOOKAHEAD_SIGNAL"] = False
    steps.append(("1. + remove o look-ahead na selecao", run(f, P_ORIG, spec)))

    f.update(SIGNAL_EMA_DAYS=7, CORE_MIN_HOLD_DAYS=7,
             CORE_SWITCH_EDGE=0.00025, CORE_EXIT_FRACTION=0.5)
    steps.append(("2. + histerese (EMA 7d, hold 7d, margem de troca)", run(f, P_ORIG, spec)))

    f["CORE_CAPACITY_MODE"] = "cap"
    steps.append(("3. + capacidade real (excedente em caixa)", run(f, P_ORIG, spec)))

    f["LOTTO_DETERMINISTIC"] = False
    steps.append(("4. + LOTTO vira aposta de verdade (fim do +3% gratis)",
                  run(f, P_ORIG, spec)))

    steps.append(("5. + parametros reotimizados no engine corrigido",
                  run(f, P_NOVO, spec)))

    with realistic.real_costs():
        v = run(f, P_NOVO, real)
    steps.append(("6. + funding e custos calibrados ao mercado real", v))

    print("\nPONTE  $42,3M  ->  $157k   (sempre $100.000 investidos)\n")
    w = 58
    print(f"{'degrau':<{w}} {'capital final':>16} {'fator':>9}")
    print("-" * (w + 27))
    prev = None
    for name, val in steps:
        fator = "-" if prev is None else f"{val / prev:>8.2f}x"
        print(f"{name:<{w}} {val:>16,.0f} {fator:>9}")
        prev = val
    print("-" * (w + 27))
    print(f"{'reducao total':<{w}} {steps[-1][1] / steps[0][1]:>16.5f}x")


if __name__ == "__main__":
    main()
