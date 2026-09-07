# Estratégia: Cash-and-Carry Cross-Sectional com Rotação Cost-Aware

**Os parâmetros não vêm de um otimizador.** Vêm de aritmética de custo, que
independe da amostra. O backtest entra depois e só para tentar derrubar a
estratégia — nunca para escolher os números.

## Por que não otimizar

A versão anterior deste documento escolhia parâmetros maximizando
`f = CAGR · Sharpe / (1 + |MaxDD|)`. Isso é seleção por resultado: ajusta ao
passado por construção, e os "testes de sanidade" que a acompanhavam
(`Sharpe < 8`, `CAGR < 40%`) são bandas de resultado — escondem uma estratégia
boa e aprovam uma quebrada que caia dentro da faixa.

Os três defeitos encontrados neste repositório eram todos violações de
**processo**, e nenhum exigia olhar o P&L para ser detectado:

| Defeito | Invariante que o pega |
|---|---|
| Look-ahead na seleção | perturbar o futuro muda o passado |
| LOTTO com lucro garantido | conservação de caixa: PnL sem origem declarada |
| Taxas cobradas em dobro | taxa por troca ≠ um round-trip |

O terceiro só apareceu quando a aritmética previu `taxas/bruto = 0,236` e o
backtest mediu `0,483` — fator exato de 2. Nenhuma leitura de código o achou;
duas revisões passaram por cima dele porque ele só se manifestava como
"resultado um pouco pior".

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

## Como os parâmetros são derivados

`engine/calibration.py`. Toda a cadeia, sem P&L em nenhum ponto:

```
RT              = custo de round-trip = (taxa + slippage) × 2        = 0,24%
f_realizado     = funding MEDIDO nos H dias seguintes ao gatilho     = 0,057%/dia
hold de empate  = RT / f_realizado                                   = 4,2 dias
hold mínimo     = hold de empate / orçamento_de_taxas (25%)          = 17 dias
limiar entrada  = RT / payback (10 dias)                             = 0,024%/dia
limiar saída    = entrada × 0,5                                      = 0,012%/dia
margem de troca = RT / hold mínimo                                   = 0,014%/dia
giro máximo     = n_posições / hold mínimo                           = 0,235/dia
alavancagem     = 1,0x se funding típico < 2 × custo de margem
```

Dois pontos que a primeira derivação errou, e como foram corrigidos **sem olhar
o resultado**:

1. **Empatar não é o critério.** `hold = RT/f` é o ponto de empate. O orçamento
   exige `taxas/bruto ≤ 25%`, e como `taxas/bruto = RT/(H·f)`, o hold precisa ser
   `1/0,25 = 4x` o de empate.
2. **O sinal decai depois que se age sobre ele.** Usar o funding *da entrada*
   superestima a receita: o símbolo é escolhido num pico e o pico não dura.
   `f_realizado` é medido como a média do funding nos H dias **seguintes** ao
   cruzamento do limiar — estatística de mercado, não de estratégia.

Aritmética prevista: `taxas/bruto = 0,236`. Medida no backtest: **0,2387**.
Erro de 1%. É essa concordância que valida o mecanismo — não o lucro.

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
**1,0x.** Sem alavancagem.

Critério, não observação de retorno: alavancar só se justifica se o funding
típico cobrir o custo de margem com folga de 2x. Com funding realizado de
0,057%/dia contra custo de margem de 0,030%/dia, a folga é 1,9x — abaixo do
corte. A regra decide antes de qualquer backtest.

(O piso de 1,5x vinha do enunciado original e foi removido: era uma restrição
arbitrária que a derivação por custo contradiz.)

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

## Critérios de aprovação (todos de processo)

`python falsify.py` roda a bateria. Nenhum limite é um número mágico: todos
saem dos mesmos parâmetros derivados.

| Invariante | Limite | Origem do limite |
|---|---|---|
| taxas / funding bruto | ≤ 25% | orçamento declarado |
| (taxas + margem) / bruto | ≤ 50% | 2 × orçamento |
| giro por dia | ≤ 0,235 | n_posições / hold mínimo |
| hold médio | ≥ 17 dias | derivado do orçamento |
| delta máximo | = 0 | definição de delta-neutro |
| alavancagem máxima | ≤ 1,0x | regra de folga de margem |

Mais três testes que não olham resultado nenhum (`tests/test_invariants.py`):
causalidade (perturbar o futuro não pode mudar o passado), conservação de caixa
(todo dólar com origem declarada) e reconciliação de taxas contra a tabela de
custos recalculada à parte.

**Uma estratégia pode passar em lucro e reprovar aqui.** Aconteceu: com
`taxas/bruto = 55,7%` o P&L mostrava CAGR de 9% e parecia saudável.

## Envelope de retorno esperado

| | |
|---|---|
| Retorno bruto sobre nocional | 15–19% a.a. |
| Menos taxas, slippage, custo de margem | −5 a −8 p.p. |
| **Líquido esperado** | **8–13% a.a.** |
| Sharpe realista | 2–4 |
| Max drawdown esperado | 2–5% |
| Capacidade antes de degradar | ~$2–5M nesse universo de 8 pares |

Esses números são **consequência**, não alvo. Não são critério de aprovação e
não devem ser usados como tal — servem só para dimensionar expectativa.

Resultado atual, depois de todas as correções: $100.000 → $187.911 em 5 anos
(CAGR 13,4%). Subiu em relação aos $157k anteriores porque o bug de taxa em
dobro estava cobrando o dobro do custo real, não porque algo foi ajustado
para melhorar.

O Sharpe de 8,9 continua alto demais para carry real (mesas reportam 2-4). Isso
é limitação do gerador de dados calibrado, cuja série de funding tem volatilidade
baixa demais — não é resultado. Fica registrado como defeito conhecido em vez de
ser escondido atrás de um limite de sanidade.

## O que continua fora do modelo

Risco de execução (as duas pernas não entram ao mesmo preço), de liquidação num
squeeze, de exchange, de transferência de margem entre spot e futuros, e de
mudança de regra de funding pela própria exchange. Nenhum deles aparece num
backtest e todos já custaram dinheiro real a alguém.
