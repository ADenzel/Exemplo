# Prompt para implementação local no Claude Code

Cole o bloco abaixo numa sessão do Claude Code, em uma pasta vazia, numa máquina
com acesso à internet (`api.binance.com` e `fapi.binance.com`).

---

```
Você é um engenheiro quant. Construa um bot de arbitragem de funding
delta-neutra (cash-and-carry) para Binance, com backtest sobre DADOS REAIS e
operação em testnet.

## Regra número um

Backtest bom demais é bug, não alfa. O envelope realista desta estratégia é
8-13% a.a. líquido, Sharpe 2-4, drawdown 2-5%. Se o seu backtest sair acima
disso, PARE e ache o defeito antes de continuar. Não ajuste os asserts para o
resultado passar — investigue de onde veio o dinheiro.

## Passo 1 — Dados reais primeiro (bloqueante)

Antes de escrever qualquer estratégia, baixe e cacheie em data/real/:
- histórico de funding de 8h via ccxt fetch_funding_rate_history (fapi, público,
  sem API key), de 5 anos atrás até hoje
- OHLCV 1d spot dos mesmos pares
- volume 24h e informações de mercado de cada par

Universo inicial: BTC, ETH, SOL, LINK, AVAX, ARB, OP, ENA (todos /USDT).
Se algum par não tiver histórico suficiente, descarte e diga qual.

Nunca gere dados sintéticos como substituto silencioso. Se a rede falhar, falhe
com mensagem explícita.

Ao terminar, me mostre: funding médio anualizado por par, % de dias negativos,
e a dispersão média entre o melhor par e a mediana. Confira se batem com o
esperado (BTC ~5-12% a.a., 30-40% dos dias negativo). Se não baterem, o parsing
está errado — funding de 8h precisa ser SOMADO por dia, não tirada a média.

## Passo 2 — Estratégia

Sleeve único, cash-and-carry: long spot + short perp, mesmo notional, delta zero.

Sinal: EMA de 7 dias do funding diário, calculada ATÉ D-1. Nunca use o funding
do dia em que a posição vai receber — isso é look-ahead.

Seleção com histerese (isto é o coração da estratégia, não um detalhe):
- entra se f_ema >= 0,03%/dia, até 4 posições simultâneas
- só sai se f_ema < 0,015%/dia (banda de saída = metade da de entrada)
- hold mínimo de 7 dias
- troca a pior posição por um candidato só se a vantagem for > 0,025%/dia

Motivo: o round-trip custa 0,24% do notional (spot taker 0,10% + perp taker
0,05%, nas duas pontas, mais slippage). A 0,05%/dia de funding isso leva ~5 dias
só para empatar. Sem histerese a estratégia gira todo dia e as taxas superam o
funding bruto — ela fica perdedora e não é óbvio no código.

Dimensionamento: notional por símbolo = min(equity*lev/n, $400k, 0,5% do volume
24h do par). O excedente vai para caixa rendendo T-Bill, NÃO para mais notional.

Alavancagem: 1,0-1,5x, nunca mais. Custo de margem USDT ~11% a.a. consome quase
todo o funding incremental e o risco de liquidação do short cresce junto.

Gates: se o melhor f_ema < -0,02%/dia, fecha tudo e vai para caixa. Drawdown de
3% em 30 dias reduz a exposição à metade; 5% zera.

NÃO implemente: compra de dip com alvo fixo de lucro, nem qualquer sleeve com
retorno garantido. Se você se pegar escrevendo `pnl += size * 0.03`, apague.

## Passo 3 — Contabilidade de custos (onde backtests mentem)

Cobre explicitamente, e me mostre cada linha separada no relatório:
- taxa taker spot 0,10% e perp 0,05% por perna (maker 0,02% no perp se usar limit)
- slippage 0,05% por perna
- custo de margem sobre a parte alavancada, ~0,03%/dia
- funding pago quando a taxa vira negativa e a posição ainda está aberta

O relatório final precisa mostrar: funding bruto, taxas totais, custo de margem,
e o líquido. Se as taxas passarem de 30% do funding bruto, o giro está alto
demais — aperte a histerese.

## Passo 4 — Validação anti-autoengano (obrigatória)

1. Walk-forward: otimize só nos primeiros 3 anos, valide nos 2 últimos.
   Reprove se CAGR out-of-sample < 50% do in-sample.
2. Bootstrap em blocos: 200 reamostragens de blocos de 30 dias da série real de
   funding. Reporte p10/mediana/p90 do capital final. Se o p10 for negativo,
   a estratégia não é robusta.
3. Sanidade: teste que falha se Sharpe > 8 ou CAGR > 40% a.a. Esses limites
   existem para pegar bug, não para limitar retorno.
4. Custo zero: rode com todas as taxas zeradas e compare. A diferença mede sua
   dependência de execução barata.
5. Stress: 30 dias seguidos de funding -0,05%/dia.

Rode os testes e me mostre a saída real. Se algum falhar, me diga qual e por quê
antes de mexer em qualquer coisa.

## Passo 5 — Execução em testnet

ccxt com set_sandbox_mode(True). Spot: testnet.binance.vision (login via GitHub).
Futuros: testnet.binancefuture.com (conta separada, faucet de 10k USDT).
Credenciais em .env, .env no .gitignore.

Ordem de execução hedgeada: manda o short perp primeiro, confirma o fill, depois
o spot. Se a segunda perna falhar, desfaz a primeira imediatamente e loga. Nunca
deixe perna solta — um hedge quebrado vira posição direcional sem ninguém pedir.

Loop de 1h (não 60s — o funding só muda a cada 8h, e ver o book de minuto em
minuto só provoca giro). Dashboard com: equity, posições abertas e há quantos
dias, f_ema por símbolo, funding acumulado, taxas pagas, drawdown.

## Passo 6 — Entregáveis

- README com setup, incluindo como pegar saldo nas duas testnets
- REPORT.md com a decomposição de custos do Passo 3 e os resultados do Passo 4
- Gráficos de equity e drawdown
- Um parágrafo honesto sobre o que o backtest NÃO modela: risco de execução,
  liquidação num squeeze, risco de exchange, transferência de margem

## Como quero que você trabalhe

Vá por passos e me mostre a saída de cada um antes de seguir. Se um número
parecer bom demais, investigue antes de comemorar. Se a estratégia não funcionar
sob custos reais, me diga isso — é um resultado válido e mais útil que um
backtest bonito e errado.

Comece pelo Passo 1 e me mostre as estatísticas de funding antes de escrever
qualquer lógica de estratégia.
```

---

## Por que o prompt está escrito assim

Cada instrução acima corresponde a um erro que aconteceu de verdade neste
repositório:

| Instrução no prompt | Erro que ela previne |
|---|---|
| "Backtest bom demais é bug" | O primeiro resultado foi $1,1 trilhão |
| "funding de 8h somado, não médio" | Erro de parsing que dá 3x de diferença |
| EMA até D−1 | Look-ahead: escolhia pelo funding que ia receber |
| Histerese com banda e hold mínimo | $88k de taxas contra $69k de funding bruto |
| Excedente em caixa, não em notional | Capacidade infinita → $1,1T |
| Alavancagem ≤ 1,5x | Grid mostrou retorno plano de 1,5x a 3x |
| "Se escrever `pnl += size * 0.03`, apague" | O LOTTO com +3% garantido valia 9x o resultado |
| Teste que falha se Sharpe > 8 | Sharpe 33 passou despercebido por duas rodadas |
| Bootstrap com p10 | Uma semente só não é resultado |
