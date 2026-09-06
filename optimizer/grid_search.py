"""OTIMIZADOR - grid search sobre os parametros do bot.

Varre FUNDING_THRESHOLD_CORE x FUNDING_THRESHOLD_TURBO x LEVERAGE_CORE x
TURBO_HOLD_DAYS, roda o backtest 2021-2026 em dados sinteticos e ranqueia por

    f = CAGR * Sharpe / (1 + |MaxDD|)

sujeito a MaxDD em janela de 30 dias > -5%.

Uso:  python -m optimizer.grid_search
"""
from __future__ import annotations

import itertools
import json

import pandas as pd

import config
from engine.backtest import run_backtest
from engine.market import Market, generate

RESULTS_CSV = config.DATA_DIR / "optimization_results.csv"


def param_combinations(grid: dict | None = None):
    grid = grid or config.PARAM_GRID
    keys = list(grid)
    for values in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, values))


def run_grid(market: Market | None = None, grid: dict | None = None,
             enforce_dd: bool = True, verbose: bool = True) -> pd.DataFrame:
    mkt = market if market is not None else generate()
    rows = []
    combos = list(param_combinations(grid))
    for i, combo in enumerate(combos, 1):
        try:
            res = run_backtest(combo, market=mkt)
        except ValueError:
            continue
        m = res.metrics
        feasible = m["MaxDD30d"] > config.MAX_DD_LIMIT
        rows.append({
            **combo,
            "ALOCATION_CORE": res.params["ALOCATION_CORE"],
            "ALOCATION_TURBO": res.params["ALOCATION_TURBO"],
            "ALOCATION_LOTTO": res.params["ALOCATION_LOTTO"],
            "STOP_FUNDING_NEGATIVE": res.params["STOP_FUNDING_NEGATIVE"],
            "CAGR": m["CAGR"], "MaxDD": m["MaxDD"], "MaxDD30d": m["MaxDD30d"],
            "Sharpe": m["Sharpe"], "FinalCapital": m["FinalCapital"],
            "TimeTo10x_days": m["TimeTo10x_days"],
            "Objective": m["Objective"], "Feasible": feasible,
        })
        if verbose and i % 50 == 0:
            print(f"  {i}/{len(combos)} combinacoes avaliadas")

    df = pd.DataFrame(rows)
    if enforce_dd and df["Feasible"].any():
        df = df.sort_values(["Feasible", "Objective"], ascending=[False, False])
    else:
        df = df.sort_values("Objective", ascending=False)
    return df.reset_index(drop=True)


def top_n(df: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    ok = df[df["Feasible"]] if df["Feasible"].any() else df
    return ok.nlargest(n, "Objective")


def best_params(df: pd.DataFrame) -> dict:
    row = top_n(df, 1).iloc[0]
    return {k: (int(row[k]) if k == "TURBO_HOLD_DAYS" else float(row[k]))
            for k in config.PARAM_GRID}


def main() -> pd.DataFrame:
    print("Grid search 2021-2026 (dados sinteticos, 4 regimes)...")
    df = run_grid()
    df.to_csv(RESULTS_CSV, index=False)
    print(f"\nResultados salvos em {RESULTS_CSV} ({len(df)} combinacoes)")

    top = top_n(df, 3)
    cols = list(config.PARAM_GRID) + ["CAGR", "Sharpe", "MaxDD30d", "FinalCapital", "Objective"]
    print("\nTOP 3 por f = CAGR * Sharpe / (1 + |MaxDD|):")
    print(top[cols].to_string(index=False))

    bp = best_params(df)
    config.BEST_PARAMS_FILE.write_text(json.dumps(bp, indent=2))
    print(f"\nMelhores parametros salvos em {config.BEST_PARAMS_FILE}:\n{bp}")
    return df


if __name__ == "__main__":
    main()
