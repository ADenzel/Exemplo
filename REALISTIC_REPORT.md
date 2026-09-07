# Backtest realista — 5 anos (2020-09-06 → 2025-09-06)

## Resposta direta

| | |
|---|---|
| **Valor investido** | **$100.000,00** |
| **Valor final após 5 anos** | **$157.094,52** |
| **Lucro líquido** | **$57.094,52** |
| Retorno total | +57,09% |
| CAGR | 9,45% |
| Max Drawdown | −3,49% |
| Max DD (janela 30d) | −1,68% |
| Sharpe | 4,73 |
| Vol anualizada | 1,92% |
| Caixa em T-Bill (4,5% a.a.) | $124.496 |
| **Excesso sobre o caixa** | **+$32.598** |

Faixa em 30 caminhos independentes (mesmos parâmetros, sementes diferentes):

| | Final | CAGR |
|---|---|---|
| p10 | $155.737 | 9% |
| **mediana** | **$179.575** | **12%** |
| p90 | $197.480 | 15% |

30/30 sementes lucrativas; 30/30 respeitando MaxDD 30d > −5%.

## Origem dos dados

**Este ambiente não tem acesso de rede à Binance.** A política de egresso bloqueia
`api.binance.com`, `fapi.binance.com`, `data-api.binance.vision` e `api.bybit.com`
(403 no CONNECT do proxy). Os números acima vêm do cenário **calibrado** de
`engine/realistic.py`, não do histórico real.

Para rodar sobre os dados de verdade, em uma máquina com acesso à Binance:

```bash
python -m engine.realdata --start 2020-09-06 --end 2025-09-06   # baixa e cacheia
python realistic_backtest.py                                     # usa o cache automaticamente
pytest tests/test_realistic.py -v
```

`realistic_backtest.py` prefere `data/real/` sempre que o cache existir; o fallback
calibrado é usado só na ausência dele, e a fonte é impressa no topo da saída.

## O que foi calibrado

| Item | Valor usado |
|---|---|
| Funding médio BTC | 7,9% a.a. (0,0217%/dia), 35% dos dias negativo |
| Funding médio alts | 10–20% a.a., com caudas maiores |
| Cap de funding da exchange | ±0,05%/8h majors, ±0,30%/8h alts |
| Datas de listagem | reais (ENA 04/2024, W 04/2024, ZRO 06/2024, ARB 03/2023, OP 06/2022) |
| Taxa taker | 0,10% spot + 0,04% perp por perna |
| Slippage | 0,05% por perna |
| Round-trip delta-neutro | ~0,24% do nocional |
| Custo de margem | 0,030%/dia (~11% a.a.) sobre a parte alavancada |
| Capacidade por símbolo | $400k de nocional; excedente fica em caixa |

## Parâmetros ótimos (grid de 3.840 combinações)

```json
{
  "ALOCATION_CORE": 0.60,
  "ALOCATION_TURBO": 0.40,
  "ALOCATION_LOTTO": 0.00,
  "FUNDING_THRESHOLD_CORE": 0.0003,
  "FUNDING_THRESHOLD_TURBO": 0.0016,
  "LEVERAGE_CORE": 1.5,
  "TURBO_HOLD_DAYS": 5
}
```

## Walk-forward

Otimizado só em 2020-09 → 2023-09, validado em 2023-09 → 2025-09:

| Janela | CAGR | Sharpe | MaxDD 30d |
|---|---|---|---|
| In-Sample (2020-09 → 2023-09) | 3,42% | 2,23 | −1,30% |
| Out-of-Sample (2023-09 → 2025-09) | 18,62% | 7,56 | −2,09% |

Regra `CAGR_OOS > 80% · CAGR_IS`: **OK**. O OOS é melhor porque 2024-2025 teve
regime de funding mais rico (ETF, halving, pós-eleição) que 2022-2023.

Stress de 15 dias com funding −0,05%/dia: drawdown de **−0,72%** (limite −2,5%).

## Três correções que mudaram o resultado em duas ordens de grandeza

O modelo do enunciado dava $42M. Sob premissas reais dá $157k. A diferença:

**1. O sleeve LOTTO como especificado é dinheiro de graça.**
"Compra desconto simulando +3% de lucro" = lucro garantido, sem perda possível.
Ele sozinho gerou $10,65M dos $8M de lucro do primeiro teste realista (o Core
perdia $2,7M). Corrigido: a aposta é resolvida contra o caminho real de preços
(alvo +3%, stop −8%, saída a mercado em 5 dias). Sem o lucro garantido o sleeve
**destrói capital em 100% das sementes**, e o otimizador zera sua alocação.
Efeito medido no cenário do enunciado: **$39,7M com o +3% garantido vs $4,37M sem**.

**2. Look-ahead na seleção.** O engine entrava no símbolo usando o funding que
ele mesmo ia receber naquele dia. Corrigido: decide com EMA de 7 dias até D−1.

**3. Giro sem histerese.** Decidindo pelo print diário, a estratégia trocava
~0,6 símbolo por dia; a $0,24% de round-trip isso custou **$88k de taxas contra
$69k de funding bruto** — o Core era estruturalmente perdedor. Corrigido com
EMA de 7 dias, hold mínimo de 7 dias e margem de troca que precisa pagar o
round-trip.

Também foi corrigido o dimensionamento: em vez de sofrer decaimento de captura
ao empurrar nocional infinito num par ilíquido, o Core agora deploya até a
capacidade e deixa o excedente em caixa — que é o que uma mesa real faz.

## O que continua otimista

- Sem risco de execução: as duas pernas entram simultaneamente ao mesmo preço.
- Sem risco de liquidação da perna short num squeeze.
- Sem risco de exchange (FTX aconteceu dentro desta janela).
- Sem custo de transferência de margem entre spot e futuros.
- A calibração de funding é aproximada, por memória dos níveis históricos.

Um Sharpe de 4,7 é alto mesmo para carry; mesas reais reportam 2–4 nesta
estratégia. Trate 9–12% a.a. como o teto do que este modelo justifica, não como
projeção.
