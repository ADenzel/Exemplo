"""Compara perfis de execucao sob os MESMOS invariantes de processo.

O perfil de execucao muda o round-trip, que e a entrada da calibracao inteira.
Entao cada perfil produz seus proprios parametros derivados e e julgado pelos
seus proprios limites -- nada e reaproveitado entre eles.

    python compare_execution.py
"""
from __future__ import annotations

import config
from engine import calibration as C, execution as X, realistic
from engine.backtest import run_backtest

START, END = "2020-09-06", "2025-09-06"
BASE = {"ALOCATION_CORE": 1.0, "ALOCATION_TURBO": 0.0, "ALOCATION_LOTTO": 0.0,
        "FUNDING_THRESHOLD_TURBO": 0.002, "TURBO_HOLD_DAYS": 5}

PERFIS = [
    ("all_taker (base)", X.all_taker()),
    ("all_taker + BNB", X.all_taker(X.FeeSchedule.with_bnb())),
    ("maker_perp", X.maker_perp()),
    ("maker_perp + BNB", X.maker_perp_bnb()),
    ("maker_perp fill 60%", X.maker_perp(fill_prob=0.60)),
    ("maker_perp+BNB fill 60%", X.maker_perp(X.FeeSchedule.with_bnb(), 0.60)),
]


def main() -> None:
    mkt = realistic.generate(START, END)
    print(f"{'perfil':>24} {'RT':>8} {'hold':>5} {'limiar':>9} "
          f"{'fee_ratio':>10} {'giro':>7} {'veredito':>10} {'final':>12}")
    print("-" * 96)
    for nome, perfil in PERFIS:
        with realistic.real_costs(), X.use_profile(perfil):
            dp = C.calibrate_from_market(mkt.funding.to_numpy())
            C.apply(dp)
            p = dict(BASE, FUNDING_THRESHOLD_CORE=dp.entry_threshold,
                     LEVERAGE_CORE=dp.max_leverage)
            res = run_backtest(p, market=mkt, keep_log=True)
            h = C.process_health(res.log)
            ruins = C.check_health(h, C.health_limits(dp))
            print(f"{nome:>24} {perfil.round_trip():>7.3%} {dp.min_hold_days:>5} "
                  f"{dp.entry_threshold:>8.4%} {h['fee_ratio']:>10.3f} "
                  f"{h['turnover_per_day']:>7.3f} "
                  f"{'SAUDAVEL' if not ruins else 'REPROVADO':>10} "
                  f"${res.metrics['FinalCapital']:>11,.0f}")
    print("\n  RT        = round-trip, custo de montar e desmontar a posicao")
    print("  hold      = hold minimo derivado (dias)")
    print("  fee_ratio = taxas / funding bruto (limite = fee_budget, 0.25)")
    print("  veredito  = invariantes de processo; o capital final e consequencia")


if __name__ == "__main__":
    main()
