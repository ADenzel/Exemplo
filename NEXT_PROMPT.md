# Prompt para implementação local no Claude Code

Cole o bloco abaixo numa sessão do Claude Code, em uma pasta vazia, numa máquina
com acesso à internet (`api.binance.com` e `fapi.binance.com`).

---

```
Você é um engenheiro quant. Construa um bot de arbitragem de funding
delta-neutra (cash-and-carry) para Binance, com backtest sobre DADOS REAIS e
operação em testnet.

## Princípio que governa todo o trabalho

Valide o MECANISMO, não o resultado.

Não escolha parâmetro maximizando retorno, Sharpe ou qualquer combinação
deles — isso é ajustar ao passado por construção. Os parâmetros saem de
aritmética de custo, que independe da amostra. O backtest entra depois e só
para tentar DERRUBAR a estratégia.

Também não use bandas de resultado como teste de sanidade ("reprove se
Sharpe > 8"). Elas escondem uma estratégia boa e aprovam uma quebrada que
caia dentro da faixa. Teste invariantes que precisam valer mesmo que a
estratégia perca dinheiro.

## Passo 1 — Dados reais primeiro (bloqueante)

Baixe e cacheie em data/real/, antes de escrever qualquer estratégia:
- funding de 8h via ccxt fetch_funding_rate_history (fapi, público, sem key),
  5 anos até hoje
- OHLCV 1d spot dos mesmos pares
- volume 24h de cada par

Universo: BTC, ETH, SOL, LINK, AVAX, ARB, OP, ENA (todos /USDT). Descarte e
me diga quais não têm histórico suficiente.

Nunca gere dados sintéticos como substituto silencioso. Se a rede falhar,
falhe com mensagem explícita.

Me mostre: funding médio anualizado por par, % de dias negativos, dispersão
entre o melhor par e a mediana. Funding de 8h precisa ser SOMADO por dia,
não promediado — se as médias saírem 3x acima do esperado (BTC ~5-12% a.a.),
é esse o erro.

## Passo 2 — Derive os parâmetros do custo, sem backtest

Escreva um módulo calibration.py que produz TODOS os parâmetros operacionais
a partir da tabela de custos e de estatísticas de MERCADO. Nenhum retorno da
estratégia pode entrar nessa conta.

  RT             = (taxa + slippage) × 2          # round-trip do par hedgeado
  f_realizado    = funding médio MEDIDO nos H dias SEGUINTES ao gatilho
  hold_empate    = RT / f_realizado
  hold_mínimo    = hold_empate / orçamento_de_taxas
  limiar_entrada = RT / payback_desejado
  limiar_saída   = limiar_entrada × 0,5
  margem_troca   = RT / hold_mínimo
  giro_máximo    = n_posições / hold_mínimo
  alavancagem    = 1,0x se f_realizado < 2 × custo_de_margem_diário

Duas armadilhas específicas nessa derivação:

1. Empatar não é o critério. taxas/bruto = RT/(H·f), então respeitar um
   orçamento de 25% exige hold 4x maior que o de empate. Se você usar o hold
   de empate, as taxas vão comer metade do funding e o P&L ainda vai parecer
   aceitável.

2. O sinal decai depois que você age sobre ele. Medir f no dia da entrada
   superestima a receita — o símbolo é escolhido num pico e o pico não dura.
   Meça a média do funding nos H dias SEGUINTES ao cruzamento do limiar.

Resolva os dois num ponto fixo: o limiar sobe até o funding realizado pagar o
round-trip dentro do orçamento, num hold aceitável (teto de 30 dias).

Me mostre a tabela de parâmetros derivados ANTES de rodar qualquer backtest.

## Passo 3 — Estratégia

Sleeve único, cash-and-carry: long spot + short perp, mesmo notional.

Sinal: EMA de 7 dias do funding diário, calculada ATÉ D-1.
Seleção: entra acima do limiar de entrada, até 4 posições; só sai abaixo do
limiar de saída; respeita o hold mínimo; só troca se a vantagem passar da
margem de troca.
Dimensionamento: notional por símbolo = min(equity·lev/n, $400k, 0,5% do
volume 24h). Excedente vai para caixa, não para mais notional.
Gate: melhor f_ema < -0,02%/dia fecha tudo. DD de 3% em 30d corta pela metade;
5% zera.

NÃO implemente compra de dip com alvo fixo nem qualquer sleeve com retorno
garantido. Se você escrever `pnl += size * 0.03`, apague.

## Passo 4 — Trilha de auditoria

Toda variação de equity precisa ter origem declarada, por dia:
funding_bruto, taxas, custo_de_margem, caixa, notional_girado, delta,
n_posições, dias_de_hold por posição.

Sem isso nenhum invariante do Passo 5 é verificável — e foi assim que um
sleeve com lucro garantido passou despercebido por duas rodadas.

## Passo 5 — Invariantes de processo (nenhum olha lucro)

Escreva estes testes e me mostre a saída real:

1. Causalidade: perturbe o funding depois do dia k; o equity até k tem que ser
   idêntico bit a bit. Pega look-ahead na hora.
2. Conservação: equity_final - equity_inicial == soma dos fluxos auditados.
   Pega PnL entrando por caminho não declarado.
3. Reconciliação de taxas: recalcule as taxas à parte, a partir do notional
   girado × tabela de custos, e compare. Cubra TODOS os caminhos que cobram
   taxa (rotação normal E fechamento pelo gate) — se um ficar de fora o teste
   acusa diferença que é dele, não do engine.
4. Uma troca custa UM round-trip. Se você usa diferença simétrica para contar
   rotação, ela já conta a saída do antigo e a entrada do novo: multiplicar por
   2 em cima disso cobra o dobro. Esse bug só aparece como "resultado um pouco
   pior" e sobrevive a revisão de código.
5. Delta zero em TODO passo, não em média.
6. Limites nunca excedidos: alavancagem, número de posições, hold mínimo.
7. Determinismo: mesma entrada, mesma saída.
8. A aritmética prevê o processo: taxas/bruto previsto no Passo 2 tem que bater
   com o medido dentro de 25%. Se não bater, você não entendeu o mecanismo —
   ache a diferença antes de seguir. Foi esse teste que expôs a taxa em dobro
   (previsto 0,236, medido 0,483, fator exato de 2).

Limites de aprovação: taxas/bruto ≤ orçamento, (taxas+margem)/bruto ≤ 2×
orçamento, giro ≤ n_posições/hold_mínimo, hold médio ≥ hold_mínimo, delta = 0.
Todos derivados dos mesmos parâmetros — nenhum número mágico.

Uma estratégia pode ser lucrativa e reprovar aqui. Quando isso acontecer,
conserte o processo, NÃO afrouxe o limite.

## Passo 6 — Falsificação (não otimização)

Com os parâmetros fixos do Passo 2, sem reotimizar nada:
- out-of-sample nos 2 últimos anos
- bootstrap em blocos de 30 dias, 200 reamostragens, reporte p05/p50/p95
- stress de 30 dias com funding -0,05%/dia
- rode com taxas zeradas e compare, para medir a dependência de execução barata

Se reprovar, me diga — descartar a estratégia é resultado válido.

## Passo 7 — Testnet

ccxt com set_sandbox_mode(True). Spot: testnet.binance.vision (login GitHub).
Futuros: testnet.binancefuture.com (conta separada, faucet 10k USDT).
Credenciais em .env, no .gitignore.

Manda o short perp primeiro, confirma o fill, depois o spot. Se a segunda perna
falhar, desfaz a primeira imediatamente. Nunca deixe perna solta.

Loop de 1h — o funding só muda a cada 8h; olhar de minuto em minuto só provoca
giro. Dashboard: equity, posições e dias de hold, f_ema por símbolo, funding
acumulado, taxas pagas, taxas/bruto corrente, drawdown.

## Passo 8 — Entregáveis

README com setup das duas testnets. REPORT.md com a tabela de parâmetros
derivados, a decomposição de custos, os invariantes com OK/VIOLADO, e os
resultados do Passo 6 — nessa ordem, com o P&L por último e rotulado como
consequência, não objetivo. Gráficos de equity e drawdown. Um parágrafo sobre
o que o backtest não modela: execução, liquidação em squeeze, risco de
exchange, transferência de margem.

## Como quero que você trabalhe

Vá por passos e me mostre a saída de cada um antes de seguir. Se um invariante
reprovar, conserte o mecanismo e me diga o que estava errado — nunca ajuste o
limite para passar. Se a estratégia não sobreviver sob custos reais, me diga
isso: é mais útil que um backtest bonito e errado.

Comece pelo Passo 1 e me mostre as estatísticas de funding antes de escrever
qualquer lógica.
```

---

## Por que o prompt está escrito assim

Cada instrução acima corresponde a um erro que aconteceu de verdade neste
repositório:

| Instrução no prompt | Erro que ela previne |
|---|---|
| "Valide o mecanismo, não o resultado" | O otimizador maximizava `CAGR·Sharpe/(1+DD)` — overfitting por construção |
| "Não use bandas de resultado como sanidade" | `Sharpe < 8` aprova estratégia quebrada e reprova estratégia boa |
| Teste de causalidade | Look-ahead: pegaria na primeira execução |
| Conservação de caixa | O LOTTO imprimia $10,6M sem origem declarada |
| "Uma troca custa UM round-trip" | Taxas cobradas em dobro por duas rodadas |
| "A aritmética prevê o processo" | Foi o teste que expôs a taxa em dobro (0,236 vs 0,483) |
| "Conserte o processo, não afrouxe o limite" | A tentação em toda iteração |
| "funding de 8h somado, não médio" | Erro de parsing que dá 3x de diferença |
| EMA até D−1 | Look-ahead: escolhia pelo funding que ia receber |
| Histerese com banda e hold mínimo | $88k de taxas contra $69k de funding bruto |
| Excedente em caixa, não em notional | Capacidade infinita → $1,1T |
| Alavancagem ≤ 1,5x | Grid mostrou retorno plano de 1,5x a 3x |
| "Se escrever `pnl += size * 0.03`, apague" | O LOTTO com +3% garantido valia 9x o resultado |
| Teste que falha se Sharpe > 8 | Sharpe 33 passou despercebido por duas rodadas |
| Bootstrap com p10 | Uma semente só não é resultado |
