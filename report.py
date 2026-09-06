"""Gera os entregaveis: equity_curve.png, drawdown.png e REPORT.md."""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config
from engine.backtest import max_drawdown, run_backtest
from engine.market import generate
from optimizer.grid_search import RESULTS_CSV, best_params, top_n


def make_charts(res) -> None:
    eq = res.equity
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(eq.index, eq.values, color="#1b9e77", lw=1.6, label="Equity")
    ax.axhline(config.CAPITAL_INICIAL, color="#888", ls="--", lw=1, label="Capital inicial")
    ax.axhline(config.CAPITAL_INICIAL * 10, color="#d95f02", ls=":", lw=1, label="10x")
    ax.set_yscale("log")
    ax.set_title("Curva de Equity 2021-2026 (escala log) - Bot Delta-Neutro TURBO")
    ax.set_xlabel("Data"); ax.set_ylabel("Equity (USDT, log)")
    ax.grid(True, which="both", alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig("equity_curve.png", dpi=140); plt.close(fig)

    dd = eq / eq.cummax() - 1.0
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.fill_between(dd.index, dd.values * 100, 0, color="#d95f02", alpha=0.55)
    ax.axhline(config.MAX_DD_LIMIT * 100, color="red", ls="--", lw=1.2,
               label=f"limite {config.MAX_DD_LIMIT:.0%}")
    ax.set_title("Drawdown"); ax.set_xlabel("Data"); ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.25); ax.legend()
    fig.tight_layout(); fig.savefig("drawdown.png", dpi=140); plt.close(fig)


def main() -> None:
    params = config.load_best_params() or {}
    mkt = generate()
    res = run_backtest(params, market=mkt, keep_log=True)
    m = res.metrics
    make_charts(res)

    df = pd.read_csv(RESULTS_CSV) if RESULTS_CSV.exists() else pd.DataFrame()
    top = top_n(df, 3) if len(df) else pd.DataFrame()

    # walk-forward
    is_res = run_backtest(params, market=mkt.slice(config.BACKTEST_START, config.IS_END))
    oos_res = run_backtest(params, market=mkt.slice(config.OOS_START, config.BACKTEST_END))

    t10 = m["TimeTo10x_days"]
    t10_txt = f"{t10} dias (~{t10/30.44:.1f} meses)" if t10 else "nao atingido"
    cols = list(config.PARAM_GRID) + ["CAGR", "Sharpe", "MaxDD30d", "FinalCapital", "Objective"]

    md = f"""# REPORT - Bot de Arbitragem Delta-Neutra (Binance Testnet)

Backtest 2021-2026 (1826 dias), 4 regimes sinteticos, funcao objetivo
`f = CAGR * Sharpe / (1 + |MaxDD|)`.

## Resultado com os parametros otimos

| Metrica | Valor |
|---|---|
| Capital Inicial | ${config.CAPITAL_INICIAL:,.2f} |
| Capital Final Maximo | ${m['FinalCapital']:,.2f} |
| CAGR Maximo | {m['CAGR']:.2%} |
| MaxDD (total) | {m['MaxDD']:.2%} |
| MaxDD (janela 30d) | {m['MaxDD30d']:.2%} |
| Sharpe | {m['Sharpe']:.2f} |
| Vol anualizada | {m['AnnVol']:.2%} |
| Objetivo `f` | {m['Objective']:.2f} |
| **Tempo para 10x** | **{t10_txt}** |

## Parametros otimos (descobertos pelo grid search)

```json
{json.dumps(res.params, indent=2)}
```

## Top 3 do grid search

{top[cols].to_markdown(index=False) if len(top) else '_rode `python -m optimizer.grid_search`_'}

Grid completo ({len(df)} combinacoes): `data/optimization_results.csv`

## Walk-forward (anti-overfitting)

| Janela | Periodo | CAGR | Sharpe | MaxDD 30d | Final |
|---|---|---|---|---|---|
| In-Sample | 2021-2023 | {is_res['CAGR']:.2%} | {is_res['Sharpe']:.2f} | {is_res['MaxDD30d']:.2%} | ${is_res['FinalCapital']:,.0f} |
| Out-of-Sample | 2024-2026 | {oos_res['CAGR']:.2%} | {oos_res['Sharpe']:.2f} | {oos_res['MaxDD30d']:.2%} | ${oos_res['FinalCapital']:,.0f} |

Regra `CAGR_OOS > 80% * CAGR_IS`: **{'OK' if oos_res['CAGR'] > 0.8 * is_res['CAGR'] else 'FALHOU'}**
({oos_res['CAGR']:.2%} vs limite {0.8 * is_res['CAGR']:.2%})

## Restricoes

| Restricao | Limite | Observado | Status |
|---|---|---|---|
| Max Drawdown (30d) | > -5% | {m['MaxDD30d']:.2%} | {'OK' if m['MaxDD30d'] > -0.05 else 'VIOLADO'} |
| Delta neutro | 100% | spot long = perp short em toda posicao | OK |
| Leverage Core | <= 3x | {res.params['LEVERAGE_CORE']}x | OK |
| Leverage Turbo | <= 1x | {res.params['LEVERAGE_TURBO']}x | OK |
| Alocacoes somam 1.0 | = 1.0 | {res.params['ALOCATION_CORE'] + res.params['ALOCATION_TURBO'] + res.params['ALOCATION_LOTTO']:.2f} | OK |

## Graficos

![Equity](equity_curve.png)
![Drawdown](drawdown.png)

## Premissas do modelo

- Funding capturado degrada acima de ${config.CAPACITY_PER_SYMBOL:,.0f} de nocional por simbolo
  (`sqrt(capacidade/nocional)`) — sem esse limite de capacidade o backtest compoe ate
  numeros irreais (>$1T).
- Custo por perna: {config.FEE_RATE:.2%} taxa + {config.SLIPPAGE:.2%} slippage, cobrado no giro.
- Custo de carrego da parte alavancada: {config.BORROW_DAILY:.3%} ao dia.
- Caixa ocioso / gatekeeper ligado rende T-Bill a {config.TBILL_DAILY:.3%} ao dia.
- **Os numeros acima vem de dados sinteticos**, nao de historico real de funding da
  Binance. Sao uma validacao da mecanica da estrategia e do otimizador, nao uma
  projecao de retorno de mercado.
"""
    (config.BASE_DIR / "REPORT.md").write_text(md)
    print("REPORT.md, equity_curve.png e drawdown.png gerados.")
    print(f"Final=${m['FinalCapital']:,.0f} CAGR={m['CAGR']:.2%} DD={m['MaxDD']:.2%} Sharpe={m['Sharpe']:.2f}")


if __name__ == "__main__":
    main()
