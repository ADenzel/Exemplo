# Estratégia: Cash-and-Carry Cross-Sectional com Rotação Cost-Aware

Este documento contém **regras, não resultados**. Nenhum número aqui veio de
uma execução de backtest. Os resultados medidos ficam em `REALISTIC_REPORT.md`
e na saída de `falsify.py`, separados de propósito: misturar os dois é como o
viés entra.

## Tese

O lucro não vem de "capturar funding". Vem de **capturar a diferença de funding
entre símbolos**, segurando tempo suficiente para o custo de entrada se pagar.

Duas consequências definem a estratégia inteira:

1. **A seleção é o alfa.** Segurar um único par delta-neutro rende o funding
   médio do mercado; selecionar o topo da seção cruzada rende a média dos
   melhores. A diferença é a estratégia.
2. **O holding period não é livre.** O round-trip custa taxa e slippage nas
   duas pernas. Abaixo de um certo hold, as taxas superam o funding e a
   estratégia é estruturalmente perdedora — sem que isso apareça como erro.

## Os únicos números livres

Quatro axiomas de política de risco, declarados em `engine/calibration.py`
antes de olhar qualquer dado, e não ajustáveis por resultado:

| Axioma | O que significa |
|---|---|
| `payback_days` | prazo em que uma posição no limiar paga o custo de entrada |
| `fee_budget` | teto de taxas como fração do funding bruto |
| `slippage_budget` | impacto de mercado aceito por execução |
| `margin_headroom` | folga exigida do funding sobre o custo de margem |

Todo o resto é consequência aritmética destes quatro mais estatísticas de
mercado. `tests/test_invariants.py::test_nenhuma_constante_magica_na_calibracao`
falha se alguém acrescentar um quinto.

## Cadeia de derivação

Nenhum P&L entra em nenhuma linha:

```
RT                = (custo_spot + custo_perp + latência) × 2     # SOMA das pernas
f_realizado       = funding médio MEDIDO nos H dias SEGUINTES ao gatilho
hold_empate       = RT / f_realizado
hold_mínimo       = hold_empate / fee_budget
limiar_entrada    = RT / payback_days
margem_troca      = RT / hold_mínimo
limiar_saída      = limiar_entrada − margem_troca
giro_máximo       = n_posições / hold_mínimo
janela_da_EMA     = meia-vida da autocorrelação de ordem 1 do funding
capacidade        = ADV × (slippage_budget / vol_diária)²
n_posições        = ceil(notional_alvo / capacidade), limitado pelos elegíveis
alavancagem       = 1x se f_realizado < margin_headroom × custo_margem_diário
perda_do_processo = pior média de funding sustentada por hold_mínimo × alavancagem
```

### Seis pontos onde a derivação é contraintuitiva

Cada um produz P&L plausível quando errado. Nenhum é detectável olhando
resultado.

1. **Empatar não é o critério.** `taxas/bruto = RT/(H·f)`. Respeitar o
   orçamento exige hold igual ao de empate **dividido pelo orçamento** — várias
   vezes maior que o de empate.
2. **O sinal decai depois que se age sobre ele.** O símbolo é escolhido num
   pico de funding e o pico não dura. Usar o funding *da entrada* superestima a
   receita; `f_realizado` mede a média nos dias **seguintes** ao gatilho.
3. **A janela da EMA não é escolha.** Suavizar mais que a persistência do sinal
   descarta informação; menos, deixa passar ruído que vira giro. Sai da
   meia-vida da autocorrelação.
4. **O número de posições não é gosto.** Cada posição extra é, por construção,
   pior que a anterior no ranking. Usa-se o menor número que acomoda o notional
   dentro do limite de impacto por par.
5. **A banda de histerese não é uma fração arbitrária do limiar.** Sair e
   voltar custa um round-trip; a banda é exatamente o round-trip amortizado no
   hold mínimo.
6. **O custo é a SOMA das pernas, nunca a média.** As duas carregam o notional
   cheio. Promediar subestima pela metade, e um número único de taxa não deixa
   nenhum teste conferir — cada componente precisa ter nome próprio.

Os pontos 1 e 2 se resolvem juntos num ponto fixo: o limiar sobe até o funding
realizado pagar o round-trip dentro do orçamento, num hold abaixo do teto de
exposição a regime.

## Regras operacionais

**Universo.** Perpétuos USDT-M com spot líquido no mesmo par. Rejeitar por
iliquidez é decisão de risco, não de retorno: sem spot líquido não há hedge, e
sem hedge não há delta neutro.

**Sinal.** EMA (janela derivada) do funding diário, calculada **até D−1**.
Nunca o print do dia em que se vai receber.

**Seleção.** Entra acima do limiar de entrada; só sai abaixo do limiar de
saída; respeita o hold mínimo; só troca se a vantagem passar da margem de
troca.

**Dimensionamento.** Notional por símbolo limitado pela capacidade derivada. O
excedente vai para **caixa, não para mais notional** — carry tem teto de
capital, e empurrar tamanho num par ilíquido gera slippage, não funding.

**Alavancagem.** A regra de folga de margem decide, antes de qualquer backtest.
Se o funding realizado não cobre o custo de margem com a folga exigida, a
resposta é 1x. (O piso de 1,5x do enunciado original foi removido: era uma
restrição arbitrária que a derivação contradiz.)

**Gates.** Nenhum símbolo cruza o limiar → sleeve vai a caixa. Kill switch
derivado da `perda_do_processo`, não de um percentual escolhido.

**Execução — é condição de viabilidade, não otimização.** Ordem passiva no
perpétuo; no instante em que ela executa, o spot é enviado a mercado. O hedge
nunca fica aberto por mais que a latência, que é cobrada explicitamente em vez
de tratada como grátis. Se a segunda perna falhar, desfaz a primeira na hora.

**Nunca passiva nas duas pernas.** Se uma executa e a outra não, a posição vira
direcional — exatamente o que a estratégia proíbe. O modelo de execução recusa
essa combinação com erro.

Um ponto que costuma ser assumido errado: no nível base da Binance, ordem
passiva no **spot não reduz taxa nenhuma** (maker e taker são iguais). A
economia vem da perna de perpétuo e de não cruzar o spread.

Sob ordem a mercado nas duas pernas, com o custo contabilizado corretamente, os
invariantes de processo **reprovam**. `tests/test_invariants.py::test_all_taker_reprova`
trava esse resultado: se algum dia taker puro passar, é sinal de que o modelo
de custo voltou a subestimar.

## O que não entra, e por quê

- **Compra de dip com alvo fixo de lucro.** Um alvo garantido é um gerador de
  dinheiro sem risco: viola conservação de caixa e domina qualquer backtest.
  Resolvida contra o caminho real de preços, a aposta não tem edge.
- **Sleeve de funding extremo com hold curto.** Hold curto conflita
  diretamente com a aritmética de round-trip acima, e funding extremo costuma
  vir acompanhado de risco de listagem, depeg ou squeeze.

## Critérios de aprovação

Todos de processo, todos derivados dos mesmos parâmetros. `python falsify.py`.

| Invariante | Limite | Origem |
|---|---|---|
| taxas / funding bruto | ≤ `fee_budget` | axioma |
| (taxas + margem) / bruto | ≤ 2 × `fee_budget` | axioma |
| giro por dia | ≤ n_posições / hold_mínimo | derivado |
| hold médio | ≥ hold_mínimo | derivado |
| delta máximo | = 0 | definição de delta-neutro |
| alavancagem | ≤ a derivada | regra de folga de margem |

Mais os invariantes de `tests/test_invariants.py`, nenhum dos quais olha
lucro: causalidade (perturbar o futuro não muda o passado), conservação de
caixa, reconciliação de taxas contra a tabela recalculada à parte, uma troca =
um round-trip, delta zero em todo passo, determinismo, invariância de escala da
calibração, coerência entre a previsão aritmética e o processo medido, e a
perda observada cabendo na prevista.

**Uma estratégia pode ser lucrativa e reprovar aqui.** Quando isso acontecer, o
conserto é no mecanismo. Afrouxar o limite para passar é o erro que todo o
resto deste documento existe para impedir.

## Falsificação

Com os parâmetros fixos, sem reotimizar: out-of-sample na parte final da
janela; bootstrap em blocos com comprimento igual à meia-vida medida (bloco
menor que a persistência destrói a autocorrelação e infla a robustez); stress
com a pior sequência de funding negativo observada na série, não uma inventada;
e uma passada com taxas zeradas para medir a dependência de execução barata.

Reprovar é resultado válido.

## O que continua fora do modelo

Risco de execução (as pernas não entram ao mesmo preço), liquidação da perna
short num squeeze, risco de exchange, transferência de margem entre spot e
futuros, e mudança de regra de funding pela própria exchange. Nenhum aparece
num backtest e todos já custaram dinheiro real.

A constante do modelo de impacto de mercado usado na fórmula de capacidade está
em 1,0 e o ADV é o de um dia, o que deixa a capacidade conservadora. Ela precisa
ser calibrada contra fills reais — e ajustá-la para produzir um número mais
confortável seria exatamente o ajuste por resultado que esta estratégia rejeita.
