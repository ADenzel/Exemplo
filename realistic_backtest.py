"""Backtest REALISTA de 5 anos (2020-09-06 -> 2025-09-06).

Roda sobre dados reais da Binance quando o cache existe (`data/real/`), e sobre
o cenario calibrado de `engine/realistic.py` caso contrario. Sempre com o quadro
de custos reais (taker spot 0.10% + perp 0.04%, slippage, custo de margem).

    python realistic_backtest.py
"""
from __future__ import annotations

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import config
from engine import realistic
from engine.backtest import run_backtest
from optimizer.grid_search import PARAM_COLUMNS, best_params, run_grid

START, END = "2020-09-06", "2025-09-06"
OUT_CSV = config.DATA_DIR / "realistic_results.csv"


def load_market():
    try:
        from engine import realdata
        mkt = realdata.load(START, END)
        return mkt, "DADOS REAIS DA BINANCE (data/real/)"
    except (FileNotFoundError, ImportError):
        return realistic.generate(START, END), \
            "CENARIO CALIBRADO (sem rede para a Binance neste ambiente)"


def main() -> None:
    mkt, source = load_market()
    print(f"Fonte: {source}")
    print(f"Periodo: {mkt.dates[0]:%Y-%m-%d} -> {mkt.dates[-1]:%Y-%m-%d} ({len(mkt)} dias)\n")

    with realistic.real_costs():
        print("Otimizando (grid search com custos reais)...")
        df = run_grid(market=mkt, verbose=False)
        df.to_csv(OUT_CSV, index=False)
        params = best_params(df)
        res = run_backtest(params, market=mkt, keep_log=True)

        # comparativo: caixa em T-Bill. (Sem buy&hold: no cenario calibrado o
        # processo de preco nao tem drift de mercado -- so o funding e calibrado.)
        tbill = config.CAPITAL_INICIAL * (1 + config.TBILL_DAILY) ** len(mkt)

    m = res.metrics
    inicial = config.CAPITAL_INICIAL
    final = m["FinalCapital"]
    anos = len(mkt) / 365.25

    print("\nMelhores parametros:", json.dumps(params))
    print("\n" + "=" * 62)
    print(f"  Valor investido      : ${inicial:>18,.2f}")
    print(f"  Valor final          : ${final:>18,.2f}")
    print(f"  Lucro liquido        : ${final - inicial:>18,.2f}")
    print(f"  Retorno total        : {final / inicial - 1:>18.2%}")
    print(f"  CAGR                 : {m['CAGR']:>18.2%}")
    print(f"  Max Drawdown         : {m['MaxDD']:>18.2%}")
    print(f"  Max DD janela 30d    : {m['MaxDD30d']:>18.2%}")
    print(f"  Sharpe               : {m['Sharpe']:>18.2f}")
    print(f"  Vol anualizada       : {m['AnnVol']:>18.2%}")
    print("-" * 62)
    print(f"  Caixa (T-Bill 4.5%)  : ${tbill:>18,.2f}")
    print(f"  Excesso sobre caixa  : ${final - tbill:>18,.2f}")
    print("=" * 62)

    eq = res.equity
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                 gridspec_kw={"height_ratios": [2, 1]})
    a1.plot(eq.index, eq.values, color="#1b9e77", lw=1.6, label="Bot delta-neutro")
    a1.axhline(inicial, color="#888", ls="--", lw=1, label="Capital investido")
    a1.plot(eq.index, tbill_curve(len(eq), inicial, eq.index), color="#7570b3",
            ls=":", lw=1.2, label="Caixa T-Bill")
    a1.set_ylabel("Equity (USDT)"); a1.grid(alpha=.25); a1.legend()
    a1.set_title(f"Backtest realista {START} -> {END}  |  {source}")
    dd = (eq / eq.cummax() - 1) * 100
    a2.fill_between(dd.index, dd.values, 0, color="#d95f02", alpha=.55)
    a2.set_ylabel("Drawdown (%)"); a2.set_xlabel("Data"); a2.grid(alpha=.25)
    fig.tight_layout(); fig.savefig("realistic_equity.png", dpi=140); plt.close(fig)

    res.log.to_csv(config.DATA_DIR / "realistic_equity.csv", index=False)
    print(f"\nGraficos: realistic_equity.png | grid: {OUT_CSV}")


def tbill_curve(n, initial, index):
    return pd.Series([initial * (1 + config.TBILL_DAILY) ** i for i in range(n)], index=index)


if __name__ == "__main__":
    main()
