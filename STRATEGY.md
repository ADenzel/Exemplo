# Estratégia: Cash-and-Carry Cross-Sectional com Rotação Cost-Aware

Desenhada a partir do que os testes deste repositório mostraram — inclusive
do que eles derrubaram.

## A tese em uma frase

O lucro não vem de "capturar funding". Vem de **capturar a diferença de funding
entre símbolos**, segurando tempo suficiente para o custo de entrada se pagar.

## Por que essa é a tese certa (medido)

| Medição | Valor |
|---|---|
| Funding médio do BTC | 7,9% a.a. |
| Funding médio da cesta top-4 (seleção cross-sectional) | 19,1% a.a. |
| **Ganho da seleção sobre só segurar BTC** | **+11,2 p.p. a.a.** |
| Dispersão média (melhor símbolo − mediana) | 24,2% a.a. |
| Round-trip delta-neutro (spot + perp, entrada + saída) | 0,24% do nocional |
| Dias de funding para pagar um round-trip — BTC | **11,1 dias** |
| Dias de funding para pagar um round-trip — cesta top-4 | **4,6 dias** |

Duas consequências que definem a estratégia inteira:

1. **A seleção é o alfa.** Segurar BTC delta-neutro rende ~8% a.a.; selecionar o
   topo da seção cruzada rende ~19%. Mais que dobra, e não vem de alavancagem.
2. **O holding period não é livre.** Menos de ~5 dias, as taxas comem o carry.
   No teste original, girar 0,6 símbolo/dia custou $88k de taxas contra $69k de
   funding bruto. A estratégia era estruturalmente perdedora e parecia lucrativa
   só porque outro sleeve imprimia dinheiro.

## Regras

### 1. Universo
Perpétuos USDT-M com spot líquido no mesmo par. Filtros diários:
- volume spot 30d > $20M (garante saída sem mover o preço)
- listado há mais de 60 dias (evita o funding errático de listagem)
- book depth a 0,1% > 2x o tamanho pretendido

Rejeitar um símbolo é decisão de risco, não de retorno: sem spot líquido não há
hedge, e sem hedge não há delta neutro.

### 2. Sinal
`f_ema(s) = EMA_7d( funding_8h(s) × 3 )`, calculado **até D−1**.

Nunca o print do dia. O funding diário é ruidoso e persistente ao mesmo tempo —
a EMA extrai a persistência e joga fora o ruído que causa o giro. Usar o print
do dia em que se vai receber é look-ahead: custou 5% de retorno no teste.

### 3. Seleção com histerese cost-aware
- **Entrada:** `f_ema(s) ≥ 0,03%/dia` (~11% a.a.), até 4 posições.
- **Saída:** só quando `f_ema(s) < 0,015%/dia` (metade do gatilho de entrada).
- **Hold mínimo:** 7 dias — abaixo disso o round-trip não se paga.
- **Troca:** substituir a pior posição por um candidato **só se**
  `f_ema(candidato) − f_ema(atual) > 0,025%/dia`, que é o round-trip de 0,24%
  amortizado no hold esperado de 10 dias.

A banda entre entrada e saída é o que impede o giro. Não é conservadorismo —
é aritmética de custo.

### 4. Dimensionamento e capacidade
Nocional por símbolo limitado ao menor entre:
- `equity × leverage / n_posições`
- `$400k` (ou 0,5% do volume spot 24h do par, o que for menor)

**O excedente vai para caixa, não para nocional.** Empurrar tamanho num par
ilíquido não gera funding proporcional — gera slippage. Uma estratégia de carry
tem teto de capital, e fingir que não tem é o erro que produziu $1,1 trilhão no
primeiro backtest.

### 5. Alavancagem
`1,0x a 1,5x`. Não mais.

O grid testou até 3x e a mediana do capital final ficou plana (1,5x → $139k;
3,0x → $141k). Razão: o custo de margem em USDT (~11% a.a.) consome quase todo
o funding incremental (~15-19% a.a.), enquanto o risco de liquidação da perna
short cresce linearmente. Alavancagem aqui compra risco, não retorno.

### 6. Gates de risco
- **Gate de regime:** `f_ema` do melhor símbolo < −0,02%/dia → fecha tudo, caixa.
- **Buffer de liquidação:** margem da perna short mantida acima de 3x a margem
  de manutenção; um squeeze de 30% não pode liquidar o hedge.
- **Concentração:** máximo 40% do equity num único símbolo, 100% numa exchange
  (e essa é a exposição que não some — a FTX caiu dentro da janela testada).
- **Kill switch:** drawdown de 3% em 30 dias → reduz a 50%; 5% → zera e para.

### 7. Execução
- Entrar com **limit maker nas duas pernas** sempre que possível: perp maker
  0,02% vs taker 0,05%. Ao longo de dezenas de rotações isso é material.
- Nunca deixar perna solta: se o short falhar, desfaz o spot imediatamente.
- Entrar escalonado, não de uma vez, em pares fora de BTC/ETH.

### 8. O que **não** entra
- **Compra de dip com alvo fixo.** Testado: sem o "+3% garantido" destrói capital
  em 100% das sementes. O otimizador zerou a alocação sozinho.
- **Turbo com hold curto em funding extremo.** Funding extremo é extremo por um
  motivo — costuma vir com risco de listagem, de depeg ou de squeeze. O sleeve
  contribuiu $12k contra $67k do core, com muito mais risco por dólar.

## Envelope de retorno esperado

| | |
|---|---|
| Retorno bruto sobre nocional | 15–19% a.a. |
| Menos taxas, slippage, custo de margem | −5 a −8 p.p. |
| **Líquido esperado** | **8–13% a.a.** |
| Sharpe realista | 2–4 |
| Max drawdown esperado | 2–5% |
| Capacidade antes de degradar | ~$2–5M nesse universo de 8 pares |

**Qualquer backtest que entregue muito acima disso está com defeito.** Foi assim
que os três erros deste repositório foram encontrados: não pela leitura do
código, mas por um resultado bom demais.

## O que continua fora do modelo

Risco de execução (as duas pernas não entram ao mesmo preço), de liquidação num
squeeze, de exchange, de transferência de margem entre spot e futuros, e de
mudança de regra de funding pela própria exchange. Nenhum deles aparece num
backtest e todos já custaram dinheiro real a alguém.
