# TURBO ARB BOT — Arbitragem Delta-Neutra de Funding (Binance Testnet)

Bot de *cash-and-carry* (spot long + perpétuo short) que captura **funding rate**
com delta líquido zero, dividido em três sleeves:

| Sleeve | O que faz | Leverage |
|---|---|---|
| **CORE** | Carry contínuo nos símbolos com funding saudável; gatekeeper para T-Bill quando o funding vira negativo | até 3x |
| **TURBO** | Captura de funding extremo (`> FUNDING_THRESHOLD_TURBO`), múltiplas posições, hold de N dias | ≤ 1x |
| **LOTTO** | Compra de desconto após crash (−8% em 3 dias), alvo +3% | 1x |

Função objetivo otimizada: `f = CAGR * Sharpe / (1 + |MaxDD|)`
Restrições: MaxDD 30d > −5%, 100% delta-neutro, Core ≤ 3x, Turbo ≤ 1x.

---

## 1. Instalação

```bash
pip install -r requirements.txt
```

Dependências: `ccxt`, `numpy`, `pandas`, `matplotlib`, `rich`, `python-dotenv`, `pytest`.

## 2. Conta e saldo na Testnet

A Binance tem **duas** testnets independentes — o bot usa as duas (spot + futuros):

**Spot — https://testnet.binance.vision**
1. Acesse o site e clique em **Log In with GitHub** (a testnet spot autentica via GitHub, não pede conta Binance).
2. Em **Generate HMAC_SHA256 Key**, dê um nome à chave e clique em *Generate*.
3. **Copie a API Key e a Secret na hora** — a Secret só aparece uma vez.
4. **Faucet:** a conta já nasce com saldo fictício (BTC, ETH, USDT etc.). Se zerar, clique em
   **Reset** / gere uma nova chave — a testnet spot recarrega os saldos automaticamente.
   O saldo aparece na própria página, em *Account Information*.

**Futuros USDT-M — https://testnet.binancefuture.com**
1. Registre-se com um e-mail qualquer (é um ambiente isolado, não é sua conta real).
2. Vá em **API Key** no rodapé do painel e gere a chave.
3. O faucet dá **10.000 USDT** de teste; para recarregar, use o botão de *transfer/faucet*
   no painel da testnet de futuros.

> As chaves da testnet **não** têm valor real e não funcionam em produção.

## 3. Configuração

```bash
cp .env.example .env
```

Preencha:

```
BINANCE_API_KEY=sua_chave_testnet
BINANCE_SECRET=seu_secret_testnet
```

O `.env` está no `.gitignore` — nunca comite suas chaves.
Todos os parâmetros ajustáveis ficam em `config.py` (alocações, leverage, thresholds,
grid do otimizador).

## 4. Uso

```bash
# 1) descobre os melhores parâmetros (grid search 480 combinações)
python -m optimizer.grid_search

# 2) roda a bateria de testes obrigatórios
pytest -v

# 3) gera REPORT.md + equity_curve.png + drawdown.png
python report.py

# 4) loop ao vivo na testnet (ciclo de 60s, dashboard Rich)
python main.py

# variantes
python main.py --sim              # simulação offline, sem rede
python main.py --interval 5       # ciclo mais curto
python main.py --sim --ticks 50   # roda 50 ciclos e imprime o dashboard
```

## 5. Estrutura

```
config.py                    parâmetros + espaço de busca + validação de restrições
main.py                      loop 60s, dashboard Rich, persistência diária
report.py                    gráficos e REPORT.md
engine/exchange.py           clientes ccxt com set_sandbox_mode(True)
engine/core.py               funding diário, execute_delta_neutral, gatekeeper T-Bill
engine/turbo.py              scan_extreme_funding, múltiplas posições, hold N dias
engine/lotto.py              detect_crash via OHLCV 1d
engine/market.py             gerador sintético 2021-2026 (4 regimes, GBM, funding endógeno)
engine/backtest.py           loop diário, métricas, rebalanceamento mensal
optimizer/grid_search.py     grid search + ranking pela função objetivo
tests/                       backtest, walk-forward, integração testnet
data/                        optimization_results.csv, equity.csv, funding_history.csv
```

## 6. Testes

| Arquivo | O que valida |
|---|---|
| `tests/test_backtest.py` | Backtest 2021-2026: CAGR > 1.0, MaxDD > −5%, Final > $5M |
| `tests/test_forward.py` | Walk-forward IS 2021-2023 → OOS 2024-2026 (`CAGR_OOS > 80% CAGR_IS`) + stress de 15 dias com funding −0,05%/dia (DD < 2,5%) |
| `tests/test_paper.py` | Integração real na testnet: saldo > 0, funding é `float`, 1 trade hedgeado |

`test_paper.py` **pula com mensagem explícita** se faltarem credenciais no `.env` ou se a
rede não alcançar a testnet — ele nunca passa "de mentira". Rode-o na sua máquina com as
chaves configuradas para exercitar o caminho de ordem de verdade
(`PAPER_DRY_RUN=1 pytest tests/test_paper.py` monta o trade sem enviar ordens).

## 7. Rebalanceamento

Mensal: se o sleeve **Turbo > 35%** do equity, move **85% do excesso** para o Core;
se o **Lotto > 20%**, move **100% do excesso**.

## 8. Aviso

Os resultados de `REPORT.md` vêm de **dados sintéticos** (GBM por regime com funding
endógeno ao retorno de 30 dias), não de histórico real de funding da Binance. Servem para
validar a mecânica da estratégia e o otimizador — **não são projeção de retorno de
mercado**. O modelo inclui limite de capacidade por símbolo, taxas, slippage e custo de
carrego; sem o limite de capacidade a composição diária leva a números irreais.
Use apenas em testnet.
