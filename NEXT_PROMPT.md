# Prompt para implementação local no Claude Code

Cole o bloco abaixo numa sessão do Claude Code, em uma pasta vazia, numa máquina
com acesso a `api.binance.com` e `fapi.binance.com`.

O prompt não contém nenhum resultado, nenhuma expectativa de retorno e nenhuma
constante escolhida a mão. Só regras de derivação e invariantes. Os quatro
únicos números livres estão declarados como axiomas de política de risco.

---

```
Você é um engenheiro quant. Construa um bot de arbitragem de funding
delta-neutra (cash-and-carry) para Binance, com backtest sobre DADOS REAIS e
operação em testnet.

## Princípio que governa todo o trabalho

Valide o MECANISMO, não o resultado.

Não escolha nenhum parâmetro maximizando retorno, Sharpe, drawdown ou
qualquer combinação deles. Não use faixa de resultado como teste de sanidade.
Não me diga que um número "parece bom" ou "parece alto" — não é critério.

Todo parâmetro é uma de duas coisas:
  (a) um AXIOMA de política de risco, declarado antes de ver qualquer dado;
  (b) uma CONSEQUÊNCIA aritmética de (a) mais uma estatística de mercado.

Se você se pegar escolhendo um número porque o backtest melhora, pare: esse é
o erro que este prompt existe para impedir.

## Axiomas (as únicas entradas livres)

Declare estes quatro no topo do módulo de calibração, com comentário dizendo
que são política de risco e não são ajustáveis por resultado:

  payback_days      prazo em que uma posição no limiar paga o custo de entrada
  fee_budget        teto de taxas como fração do funding bruto
  slippage_budget   impacto de mercado aceito por execução
  margin_headroom   folga exigida do funding sobre o custo de margem

Escolha valores que você defenderia para um comitê de risco antes de ver
qualquer backtest, e não os toque depois.

## Passo 1 — Dados reais primeiro (bloqueante)

Baixe e cacheie em data/real/, antes de escrever qualquer estratégia:
- funding de 8h via ccxt fetch_funding_rate_history (fapi, público, sem key)
- OHLCV 1d spot dos mesmos pares
- volume 24h e informações de mercado de cada par

Universo: os perpétuos USDT-M com spot no mesmo par. Descarte e me diga quais
não têm histórico suficiente para a janela pedida.

Nunca gere dados sintéticos como substituto silencioso. Se a rede falhar,
falhe com mensagem explícita.

Valide o parsing por IDENTIDADE, não por expectativa de nível:
- o número de intervalos de funding por dia tem que bater com o intervalo
  publicado pela própria exchange (fundingIntervalHours no endpoint de
  informações); o funding diário é a SOMA dos intervalos do dia, não a média
- nenhuma taxa pode exceder o cap publicado pela exchange para aquele par
- não pode haver buraco maior que um intervalo na série

Me mostre a saída dessas três checagens. Não me diga se o nível "parece
razoável" — a identidade passa ou não passa.

## Passo 2 — Derive os parâmetros, sem backtest

Escreva calibration.py que produz TODOS os parâmetros operacionais a partir
dos axiomas e de estatísticas de MERCADO. Nenhum retorno da estratégia pode
entrar nessa conta. Nenhuma constante literal além dos axiomas.

  RT              = (taxa + slippage) × 2
  f_realizado     = funding médio MEDIDO nos H dias SEGUINTES ao gatilho
  hold_empate     = RT / f_realizado
  hold_mínimo     = hold_empate / fee_budget
  limiar_entrada  = RT / payback_days
  margem_troca    = RT / hold_mínimo
  limiar_saída    = limiar_entrada − margem_troca
  giro_máximo     = n_posições / hold_mínimo
  janela_da_EMA   = meia-vida da autocorrelação de ordem 1 do funding
  capacidade      = ADV × (slippage_budget / vol_diária)²
  n_posições      = ceil(notional_alvo / capacidade), limitado pelos elegíveis
  alavancagem     = 1x se f_realizado < margin_headroom × custo_margem_diário
  perda_do_processo = pior média de funding sustentada por hold_mínimo × alav.

Cinco armadilhas específicas. Todas produzem P&L plausível, então nenhuma é
detectável olhando resultado:

1. Empatar não é o critério. taxas/bruto = RT/(H·f). Respeitar o fee_budget
   exige hold igual ao de empate dividido pelo orçamento — várias vezes maior.

2. O sinal decai depois que você age sobre ele. Medir f no dia da entrada
   superestima a receita: o símbolo é escolhido num pico e o pico não dura.
   Meça a média nos H dias SEGUINTES ao cruzamento do limiar.

3. A janela da EMA não é escolha. Suavizar mais que a persistência do sinal
   descarta informação; menos, deixa passar ruído que vira giro. Estime o
   coeficiente autorregressivo de ordem 1 da série e use a meia-vida.

4. O número de posições não é gosto. Cada posição extra é, por construção,
   pior que a anterior no ranking. Use o MENOR número que acomoda o notional
   dentro do limite de impacto por par.

5. A banda de histerese não é uma fração arbitrária do limiar de entrada.
   Sair e voltar custa um round-trip; a banda tem que ser exatamente o
   round-trip amortizado no hold mínimo.

Resolva (1) e (2) juntas num ponto fixo: o limiar sobe até o funding realizado
pagar o round-trip dentro do orçamento, num hold abaixo do teto que você
declarar como exposição máxima a regime.

Me mostre a tabela de parâmetros derivados ANTES de rodar qualquer backtest.

## Passo 3 — Estratégia

Sleeve único, cash-and-carry: long spot + short perp, mesmo notional.

Sinal: EMA (janela derivada) do funding diário, calculada ATÉ D−1.
Seleção: entra acima do limiar de entrada; só sai abaixo do limiar de saída;
respeita o hold mínimo; só troca se a vantagem passar da margem de troca.
Dimensionamento: notional por símbolo limitado pela capacidade derivada; o
excedente vai para caixa, não para mais notional.
Gate: quando nenhum símbolo cruza o limiar de entrada, o sleeve vai a caixa.
Kill switch: derivado da perda_do_processo — reduz exposição ao atingir essa
perda, zera num múltiplo dela que você declare como axioma.

NÃO implemente compra de dip com alvo fixo nem qualquer sleeve com retorno
garantido. Se você escrever algo como `pnl += size * constante`, apague.

## Passo 4 — Trilha de auditoria

Toda variação de equity precisa ter origem declarada, por dia: funding bruto,
taxas, custo de margem, caixa, notional girado, delta, número de posições,
dias de hold por posição.

Sem isso nenhum invariante do Passo 5 é verificável.

## Passo 5 — Invariantes de processo (nenhum olha lucro)

Escreva estes testes e me mostre a saída real:

1. Causalidade: perturbe o funding depois do dia k; o equity até k tem que ser
   idêntico bit a bit. Pega look-ahead imediatamente.
2. Conservação: variação de equity == soma dos fluxos auditados. Pega PnL
   entrando por caminho não declarado.
3. Reconciliação de taxas: recalcule as taxas à parte, a partir do notional
   girado × tabela de custos. Cubra TODOS os caminhos que cobram taxa (rotação
   normal E fechamento pelo gate) — se um ficar de fora, o teste acusa uma
   diferença que é dele, não do engine.
4. Uma troca custa UM round-trip. Se você contar rotação por diferença
   simétrica, ela já inclui a saída do antigo e a entrada do novo; multiplicar
   por 2 em cima disso cobra o dobro. Esse erro só se manifesta como resultado
   levemente pior e sobrevive a revisão de código.
5. Delta zero em TODO passo, não em média.
6. Limites nunca excedidos: alavancagem, posições, hold mínimo.
7. Determinismo: mesma entrada, mesma saída.
8. Calibração independe de escala: dobrar o capital inicial não pode mudar
   nenhum parâmetro derivado.
9. A aritmética prevê o processo: taxas/bruto previsto no Passo 2 tem que
   bater com o medido. Se divergir por um fator inteiro, procure uma contagem
   em duplicidade antes de qualquer outra hipótese.
10. A perda observada tem que caber na perda_do_processo prevista no Passo 2.

Limites de aprovação: todos derivados dos mesmos parâmetros do Passo 2 —
taxas/bruto ≤ fee_budget, giro ≤ n_posições/hold_mínimo, hold médio ≥ hold
mínimo, delta = 0, alavancagem ≤ a derivada. Nenhum número mágico.

Uma estratégia pode ser lucrativa e reprovar aqui. Quando isso acontecer,
conserte o mecanismo e me diga o que estava errado. NUNCA afrouxe o limite.

## Passo 6 — Falsificação, não otimização

Com os parâmetros do Passo 2 fixos, sem reotimizar nada:
- out-of-sample na parte final da janela
- bootstrap em blocos, com comprimento de bloco igual à meia-vida medida no
  Passo 2 (bloco menor que a persistência destrói a autocorrelação e infla a
  robustez); reporte os percentis da distribuição
- stress com a pior sequência de funding negativo OBSERVADA na série, não uma
  inventada
- rode com taxas zeradas e compare, para medir a dependência de execução barata

Se reprovar, me diga. Descartar a estratégia é resultado válido e é a saída
correta quando os invariantes não fecham.

## Passo 7 — Testnet

ccxt com set_sandbox_mode(True). Spot: testnet.binance.vision (login GitHub).
Futuros: testnet.binancefuture.com (conta separada, faucet próprio).
Credenciais em .env, no .gitignore.

Manda o short perp primeiro, confirma o fill, depois o spot. Se a segunda perna
falhar, desfaz a primeira imediatamente. Nunca deixe perna solta.

Período do loop: derive do intervalo de funding publicado pela exchange, não
de um número redondo. Decidir com frequência maior que o pagamento só produz
giro. Dashboard: equity, posições e dias de hold, sinal por símbolo, funding
acumulado, taxas pagas, taxas/bruto corrente, drawdown contra a
perda_do_processo.

## Passo 8 — Entregáveis

README com setup das duas testnets. REPORT.md nesta ordem: axiomas, tabela de
parâmetros derivados, decomposição de custos, invariantes com OK/VIOLADO,
falsificação do Passo 6, e o P&L POR ÚLTIMO, rotulado como consequência.
Gráficos de equity e drawdown. Um parágrafo sobre o que o backtest não modela:
execução, liquidação em squeeze, risco de exchange, transferência de margem.

## Como quero que você trabalhe

Vá por passos e me mostre a saída de cada um antes de seguir. Se um invariante
reprovar, conserte o mecanismo e me explique a causa raiz — nunca ajuste o
limite para passar. Se a estratégia não sobreviver sob custos reais, me diga
isso.

Não me apresente o P&L como argumento de que algo está certo, em nenhum
momento. Se eu perguntar se está bom, responda pelos invariantes.

Comece pelo Passo 1 e me mostre as três checagens de identidade antes de
escrever qualquer lógica de estratégia.
```

---

## Por que o prompt está escrito assim

Cada instrução corresponde a um erro que aconteceu de verdade na construção
anterior. Nenhuma linha desta tabela cita resultado — só o mecanismo que
falhou e o invariante que o pega.

| Instrução | Erro que ela previne |
|---|---|
| "Valide o mecanismo, não o resultado" | O otimizador maximizava uma função de CAGR, Sharpe e drawdown — ajuste ao passado por construção |
| "Não use faixa de resultado como sanidade" | Uma banda de Sharpe aprova estratégia quebrada que caia dentro dela e reprova estratégia boa |
| Axiomas declarados antes dos dados | Sem isso, toda constante vira ajuste disfarçado |
| Validação do parsing por identidade | Confundir soma e média nos intervalos de 8h erra o funding por um fator inteiro |
| Teste de causalidade | Seleção usava o funding do próprio dia que ia receber |
| Conservação de caixa | Um sleeve com lucro garantido gerava PnL sem origem declarada |
| "Uma troca custa um round-trip" | Contagem em duplicidade cobrou o dobro de taxa por várias rodadas |
| "A aritmética prevê o processo" | Foi a divergência entre previsto e medido que expôs a duplicidade |
| Janela da EMA pela meia-vida | Era um número redondo escolhido a mão |
| Posições pela capacidade | Era um número redondo escolhido a mão |
| Banda de histerese pelo round-trip | Era uma fração arbitrária do limiar |
| Kill switch pela perda do processo | Era um percentual escolhido a mão |
| Bloco do bootstrap pela meia-vida | Bloco curto demais destrói a autocorrelação e infla a robustez |
| Stress com a pior sequência observada | Cenário inventado testa a imaginação, não a estratégia |
| "Conserte o processo, não afrouxe o limite" | A tentação em toda iteração |
