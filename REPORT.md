# REPORT - Bot de Arbitragem Delta-Neutra (Binance Testnet)

Backtest 2021-2026 (1826 dias), 4 regimes sinteticos, funcao objetivo
`f = CAGR * Sharpe / (1 + |MaxDD|)`.

## Resultado com os parametros otimos

| Metrica | Valor |
|---|---|
| Capital Inicial | $100,000.00 |
| Capital Final Maximo | $4,370,266.44 |
| CAGR Maximo | 112.78% |
| MaxDD (total) | -0.72% |
| MaxDD (janela 30d) | -0.72% |
| Sharpe | 33.33 |
| Vol anualizada | 2.27% |
| Objetivo `f` | 37.32 |
| **Tempo para 10x** | **1106 dias (~36.3 meses)** |

## Parametros otimos (descobertos pelo grid search)

```json
{
  "CAPITAL_INICIAL": 100000.0,
  "ALOCATION_CORE": 0.6,
  "ALOCATION_TURBO": 0.4,
  "ALOCATION_LOTTO": 0.0,
  "LEVERAGE_CORE": 1.5,
  "LEVERAGE_TURBO": 1.0,
  "FUNDING_THRESHOLD_CORE": 0.0003,
  "FUNDING_THRESHOLD_TURBO": 0.002,
  "STOP_FUNDING_NEGATIVE": -0.0002,
  "TURBO_HOLD_DAYS": 5
}
```

## Top 3 do grid search

|   ALOCATION_CORE |   ALOCATION_TURBO |   ALOCATION_LOTTO |   FUNDING_THRESHOLD_CORE |   FUNDING_THRESHOLD_TURBO |   LEVERAGE_CORE |   TURBO_HOLD_DAYS |    CAGR |   Sharpe |    MaxDD30d |   FinalCapital |   Objective |
|-----------------:|------------------:|------------------:|-------------------------:|--------------------------:|----------------:|------------------:|--------:|---------:|------------:|---------------:|------------:|
|              0.6 |               0.4 |                 0 |                  0.0003  |                     0.002 |             1.5 |                 5 | 1.12776 |  33.3272 | -0.00723086 |    4.37027e+06 |     37.3152 |
|              0.6 |               0.4 |                 0 |                  0.00025 |                     0.002 |             1.5 |                 5 | 1.1236  |  33.3282 | -0.00815067 |    4.32777e+06 |     37.1449 |
|              0.6 |               0.4 |                 0 |                  0.0002  |                     0.002 |             1.5 |                 5 | 1.12261 |  33.3479 | -0.00815553 |    4.31768e+06 |     37.134  |

Grid completo (3840 combinacoes): `data/optimization_results.csv`

## Walk-forward (anti-overfitting)

| Janela | Periodo | CAGR | Sharpe | MaxDD 30d | Final |
|---|---|---|---|---|---|
| In-Sample | 2021-2023 | 112.79% | 31.02 | -0.72% | $963,508 |
| Out-of-Sample | 2024-2026 | 153.50% | 43.71 | -0.83% | $644,237 |

Regra `CAGR_OOS > 80% * CAGR_IS`: **OK**
(153.50% vs limite 90.23%)

## Restricoes

| Restricao | Limite | Observado | Status |
|---|---|---|---|
| Max Drawdown (30d) | > -5% | -0.72% | OK |
| Delta neutro | 100% | spot long = perp short em toda posicao | OK |
| Leverage Core | <= 3x | 1.5x | OK |
| Leverage Turbo | <= 1x | 1.0x | OK |
| Alocacoes somam 1.0 | = 1.0 | 1.00 | OK |

## Graficos

![Equity](equity_curve.png)
![Drawdown](drawdown.png)

## Premissas do modelo

- Funding capturado degrada acima de $600,000 de nocional por simbolo
  (`sqrt(capacidade/nocional)`) — sem esse limite de capacidade o backtest compoe ate
  numeros irreais (>$1T).
- Custo por perna: 0.04% taxa + 0.02% slippage, cobrado no giro.
- Custo de carrego da parte alavancada: 0.025% ao dia.
- Caixa ocioso / gatekeeper ligado rende T-Bill a 0.014% ao dia.
- **Os numeros acima vem de dados sinteticos**, nao de historico real de funding da
  Binance. Sao uma validacao da mecanica da estrategia e do otimizador, nao uma
  projecao de retorno de mercado.
