"""Validacao por FALSIFICACAO, nao por maximizacao.

Os parametros vem de `engine.calibration.derive()` -- aritmetica de custo, sem
olhar o P&L. O backtest entra so para tentar DERRUBAR a estrategia:

  1. invariantes de processo (delta, giro, taxas/bruto, hold medio)
  2. sobrevivencia out-of-sample sem reotimizar nada
  3. sobrevivencia em 200 reamostragens em blocos

Nenhum parametro e escolhido aqui. Se algo reprova, a estrategia e descartada
ou reprojetada -- nunca se ajusta o limiar ate passar.

    python falsify.py
"""
from __future__ import annotations

import numpy as np

import config
from engine import calibration, realistic
from engine.backtest import run_backtest

START, END = "2020-09-06", "2025-09-06"
BASE = {"ALOCATION_CORE": 1.0, "ALOCATION_TURBO": 0.0, "ALOCATION_LOTTO": 0.0,
        "FUNDING_THRESHOLD_TURBO": 0.0020, "TURBO_HOLD_DAYS": 5}


def build_params(dp):
    cfg = calibration.apply(dp)
    # SIGNAL_EMA_DAYS e MAX_CORE_POSITIONS ja foram escritos no config por apply()
    return dict(BASE, FUNDING_THRESHOLD_CORE=cfg["FUNDING_THRESHOLD_CORE"],
                LEVERAGE_CORE=cfg["LEVERAGE_CORE"])


def block_bootstrap(funding, rng, block=30):
    """Reamostra a serie de funding em blocos, preservando a autocorrelacao."""
    n = len(funding)
    idx = []
    while len(idx) < n:
        start = rng.integers(0, max(n - block, 1))
        idx.extend(range(start, min(start + block, n)))
    return funding.iloc[idx[:n]].reset_index(drop=True)


def main() -> None:
    with realistic.real_costs():
        mkt0 = realistic.generate(START, END)
        # o limiar sai da estatistica de funding do MERCADO, nao do P&L
        dp = calibration.calibrate_from_market(mkt0.funding.to_numpy())
        calibration.apply(dp)
        print("1) PARAMETROS DERIVADOS DO CUSTO (backtest nao participou)\n")
        print(dp.report())

        params = build_params(dp)
        mkt = mkt0
        res = run_backtest(params, market=mkt, keep_log=True)
        health = calibration.process_health(res.log)
        limits = calibration.health_limits(dp)

        print("\n2) INVARIANTES DE PROCESSO\n")
        for k, v in health.items():
            op, lim = limits.get(k, (None, None))
            if op is None:
                print(f"  {k:20} {v:>10.4g}")
            else:
                ok = (v <= lim) if op == "<=" else (v >= lim)
                print(f"  {k:20} {v:>10.4g}   limite {op} {lim:<8.4g} "
                      f"{'OK' if ok else 'VIOLADO'}")
        bad = calibration.check_health(health, limits)
        print(f"\n  veredito: {'SAUDAVEL' if not bad else 'REPROVADO -> ' + '; '.join(bad)}")

        # 3) out-of-sample sem reotimizar
        print("\n3) OUT-OF-SAMPLE (mesmos parametros, sem reotimizar)\n")
        is_m, oos_m = mkt.slice(START, "2023-09-06"), mkt.slice("2023-09-06", END)
        r_is, r_oos = run_backtest(params, market=is_m), run_backtest(params, market=oos_m)
        for lbl, r in [("in-sample  2020-2023", r_is), ("out-sample 2023-2025", r_oos)]:
            print(f"  {lbl}: CAGR {r['CAGR']:>7.2%}  Sharpe {r['Sharpe']:>5.2f}  "
                  f"DD30 {r['MaxDD30d']:>7.2%}")

        # 4) bootstrap em blocos
        print("\n4) BOOTSTRAP EM BLOCOS (200 reamostragens de 30 dias)\n")
        rng = np.random.default_rng(0)
        finals = []
        for _ in range(200):
            m2 = realistic.Market(mkt.dates, mkt.prices,
                                  block_bootstrap(mkt.funding, rng))
            finals.append(run_backtest(params, market=m2)["FinalCapital"])
        finals = np.array(finals)
        for lbl, v in [("p05", np.percentile(finals, 5)),
                       ("p50", np.median(finals)),
                       ("p95", np.percentile(finals, 95))]:
            print(f"  {lbl}  ${v:>12,.0f}")
        win = (finals > config.CAPITAL_INICIAL).mean()
        print(f"\n  reamostragens lucrativas: {win:.1%}")
        print(f"  veredito: {'SOBREVIVE' if np.percentile(finals, 5) > config.CAPITAL_INICIAL else 'REPROVADO (p05 abaixo do capital)'}")

        print(f"\n5) RESULTADO (consequencia, nao objetivo)\n")
        print(f"  $100.000 -> ${res.metrics['FinalCapital']:,.0f}  "
              f"| CAGR {res.metrics['CAGR']:.2%} | Sharpe {res.metrics['Sharpe']:.2f}"
              f" | DD {res.metrics['MaxDD']:.2%}")


if __name__ == "__main__":
    main()
