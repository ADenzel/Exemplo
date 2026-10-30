// Conteudo do artigo: fonte unica para o .docx e para a versao em texto.
// Marcacao inline: $x$ italico (variavel), _{..} subscrito, ^{..} sobrescrito, *..* italico, **..** negrito.
const fs = require("fs");
const T3 = JSON.parse(fs.readFileSync(__dirname + "/tab3.json", "utf8"));
const f = (x, nd) => x.toFixed(nd).replace(".", ",").replace("-", "−");
const sg = (x, nd) => (x >= 0 ? "+" : "") + f(x, nd);

const tab3rows = T3.map(r => [
  String(r[0]), String(r[1]),
  f(r[2], 2), f(r[3], 2), sg(r[4], 0),
  f(r[5], 2), f(r[6], 2), sg(r[7], 0),
  f(r[8], 2), f(r[9], 2), sg(r[10], 1)]);

module.exports = [
  { t: "title", text: "Reprojeto do indutor boost de um PFC de 1,2 kW com núcleo de pó nanocristalino: volume e perdas frente ao Kool Mµ de 85 a 265 VAC" },
  { t: "author", text: "Andre Denzel" },
  { t: "affil", text: "PPGEE e LMAG, Escola Politécnica da Universidade de São Paulo, São Paulo, Brasil" },

  { t: "abstract", label: "Resumo:", text: "O indutor boost de referência de um PFC CCM de 1,2 kW (85 a 265 VAC, 100 kHz), com dois toroides Kool Mµ 60µ, foi reprojetado com pó nanocristalino de mesma permeabilidade. Mantidos a indutância exigida, as espiras, o fio e os diâmetros do toroide, a menor queda de permeabilidade do pó reduziu a altura do núcleo de 30,7 para 21,4 mm, com núcleo 30 % e componente 26 % menores. Com os 248 mT dos ensaios do pó lidos como pico a pico, a perda no núcleo subiu de 91 % a 145 %, e a do cobre caiu até 22 %. A perda total, a plena carga, caiu 16 % em 85 V e subiu 29 % em 230 V; com 20 % de carga, subiu de 55 % a 122 %." },
  { t: "keywords", label: "Palavras-chave:", text: "correção do fator de potência; indutor boost; núcleo de pó nanocristalino; perda no núcleo." },

  { t: "h1", text: "I. Introdução" },
  { t: "p", text: "A demanda mundial de eletricidade deve crescer mais de 3,5 % ao ano até 2030 [1]. Contribuem para isso a frota de veículos elétricos, com mais de 20 milhões de carros vendidos em 2025, e a infraestrutura de recarga que a acompanha [2]; os centros de dados, cujo consumo, estimado em 415 TWh em 2024, deve chegar a cerca de 945 TWh em 2030 com a expansão da inteligência artificial [3]; e a eletrificação do aquecimento, de que é exemplo a Alemanha, onde a emenda de 2023 à lei de energia em edificações passou a exigir, a partir de 2024, que novos sistemas de aquecimento usassem ao menos 65 % de energia renovável, o que favorece as bombas de calor [4]. Do lado da geração, a expansão das fontes renováveis, com cerca de 4 600 GW a acrescentar entre 2025 e 2030 [5], amplia a parcela da energia processada por conversores eletrônicos. Nos conversores que absorvem energia da rede, o estágio de entrada precisa atender aos limites de harmônicas de corrente da IEC 61000-3-2 [6], e as suas perdas se somam às do sistema." },
  { t: "p", text: "No estágio de correção do fator de potência (PFC) do tipo boost em modo de condução contínua (CCM), o controle de corrente média impõe à corrente de entrada a forma da tensão retificada da rede, com fator de potência próximo da unidade, e regula o barramento CC em 400 V [7]. O indutor boost conduz a corrente de linha com a ondulação de chaveamento sobreposta. Em núcleo de pó, a polarização dessa corrente reduz a permeabilidade, e o componente é dimensionado na crista da menor tensão de entrada, condição de maior corrente e de maiores perdas [7]. As perdas no núcleo e no cobre do indutor reduzem o rendimento do estágio PFC, que multiplica o do conversor CC-CC seguinte, e o volume do indutor pesa na densidade de potência. No projeto de referência de 1,2 kW da Infineon [7], o indutor usa dois toroides de pó Kool Mµ (Fe-Si-Al) de permeabilidade 60. Jiang *et al.* [8] produziram toroides de pó nanocristalino (Fe-Cu-Nb-Si-B) com a mesma permeabilidade e os compararam, sob excitação senoidal de 100 a 600 kHz, com quatro pós comerciais, entre eles o Kool Mµ." },
  { t: "p", text: "Os ensaios de [8] caracterizam o material sem aplicá-lo a um indutor de PFC: não informam quanto menor ficaria o indutor de [7] com o pó nanocristalino, nem como variariam as suas perdas no núcleo e no cobre ao longo do semiciclo da rede, de 85 a 265 VAC, em diferentes cargas. Além disso, o nível de 248 mT dos ensaios de [8] é chamado de valor de pico em um trecho do texto, enquanto os demais dados do artigo indicam valor pico a pico; a distinção muda a perda calculada do pó por um fator de 4,03. Este trabalho reprojeta o indutor de [7] com o pó nanocristalino, sob o mesmo requisito de indutância e com o mesmo fio, e compara volume e perdas com a referência em 85, 115, 230 e 265 V e em 20 %, 50 % e 100 % de carga, com os dados de [8] lidos como pico a pico." },

  { t: "h1", text: "II. Métodos" },
  { t: "h2", text: "A. Conversor e indutor de referência" },
  { t: "p", text: "O conversor é o de [7]: 85 a 265 VAC, 60 Hz; 400 V; 1200 W; 100 kHz. A ondulação de projeto, 25 % da corrente de crista em 85 V a plena carga, exige $L$ ≥ 168,5 µH a 19,97 A, com corrente máxima de 22,5 A [7]. O indutor de referência tem dois toroides Kool Mµ 60µ 0077083A7 empilhados, cada um com 40,77 × 23,32 × 15,37 mm, $A$_{e} = 107 mm^{2}, $l$_{e} = 98,4 mm e $V$_{e} = 10,6 cm^{3} [9], e 64 espiras de fio de cobre de 1,15 mm. Segundo [7], a indutância é de 680 µH sem polarização e de cerca de 165 µH em 85 V a plena carga, a resistência CC é de 70 mΩ e a perda no núcleo nesse ponto é de 0,62 W. Esses valores foram tomados como corretos e não foram recalculados. A corrente de entrada foi calculada com rendimento unitário, como em [7]." },
  { t: "h2", text: "B. Propriedades dos materiais" },
  { t: "p", text: "Para os dois pós, a queda da permeabilidade incremental com o campo de polarização $H$ = $N i$/$l$_{e} é escrita como" },
  { t: "eq", n: 1, plain: "µinc(H)/µi = 1/[1 + (H/H0)^n]" },
  { t: "p", noindent: true, text: "Para o Kool Mµ, o ajuste do catálogo, 1/(0,01 + 2,142·10^{−6}·$H$^{1,855}) com $H$ em Oe [10, p. 63], equivale a $H$_{0} = 75,6 A/cm e $n$ = 1,855. No indutor de referência, mantido $n$, $H$_{0} = 70,3 A/cm reproduz os 680 e 165 µH de [7]. Para o pó nanocristalino, (1) ajustada aos pontos da curva de polarização de [8, Fig. 4] dá $H$_{0} = 93,0 A/cm e $n$ = 1,71, com $μ$_{i} = 60 [8]. A curva $B$($H$) usada é a integrada," },
  { t: "eq", n: 2, plain: "B(H) = µ0 µi ∫[0,H] µinc(h)/µi dh" },
  { t: "p", noindent: true, text: "e não a razão $μ$_{inc}/$μ$_{i} aplicada ao campo total. As leis de perda são as de Steinmetz ajustadas a ensaios senoidais: para o Kool Mµ, $P$ = 44,30 $B̂$^{1,988} $f$^{1,541}, em mW/cm^{3}, com $B̂$ = Δ$B$/2 em T e $f$ em kHz [10, pp. 23 e 109]; para o pó nanocristalino, $P$ = 89,38 $f$^{1,193} Δ$B$^{2,01}, em kW/m^{3}, com $f$ em kHz e Δ$B$ em T [8, Seç. IV-B]. A Tabela I reúne as propriedades." },
  { t: "h2", text: "C. Leitura dos 248 mT de [8]" },
  { t: "p", text: "Em [8], o nível de 248 mT dos ensaios a 100, 150 e 200 kHz é chamado de valor de pico em uma frase da Seção IV-A. As demais ocorrências indicam pico a pico: a iGSE de [8] é escrita com Δ$B$ pico a pico (Eq. 3 de [8]); os eixos das Figs. 10 a 12 e 15 de [8] são Δ$B$; nas Figs. 7 a 9 de [8], as cotas de 248 mT e 3,0 kA/m cobrem a altura e a largura totais do laço, e 3,0 kA/m confere com $N I$_{pp}/$l$_{e} = 3,06 kA/m para 9,1 A pico a pico; e os pares (248 mT; 9,1 A), (75 mT; 2,8 A) e (233 mT; 8,49 A) implicam permeabilidade de 63 a 65 na leitura pico a pico, contra 60 na Tabela III de [8], e de 127 a 130 na leitura de pico. Na leitura pico a pico, o ajuste do catálogo [10] reproduz a perda do Kool Mµ medida em [8] no núcleo de 28,6 cm^{3} (25,4 e 59 W a 100 e 200 kHz) com erros de −5,0 % e +19,0 %, e o ajuste de [8] reproduz a do pó nanocristalino (38,2 e 81 W) com −1,3 % e +6,4 % (Fig. 1(b)); na leitura de pico, o erro do Kool Mµ seria de +277 % e +372 %. O nível foi, portanto, tratado como Δ$B$ pico a pico, o que, na forma de amplitude, multiplica o coeficiente de [8] por 2^{2,01} = 4,03." },
  { t: "h2", text: "D. Reprojeto com pó nanocristalino" },
  { t: "p", text: "O indutor nanocristalino foi projetado pelo requisito de [7], $L$ ≥ 168,5 µH a 19,97 A, com o fio de 1,15 mm, as 64 espiras e os diâmetros externo e interno do 0077083A7; a altura $h$ do núcleo é a variável de projeto. Com $N$ e $l$_{e} fixos, o campo na crista, 129,9 A/cm, é o mesmo da referência, e a indutância é proporcional à seção, $A$_{e} = 107 mm^{2} · $h$/15,37 mm, com $μ$_{i} nominal de 60 [8]. A menor altura que atende ao requisito é 21,37 mm, e adotou-se $h$ = 21,4 mm. Para situar a escolha, o projeto foi repetido de 40 a 96 espiras, com a menor altura que atende ao requisito em cada caso. A espira média e as dimensões externas do componente enrolado foram calculadas com o mesmo modelo geométrico nos dois indutores: fio esmaltado de 1,22 mm, 56 espiras por camada na face interna e uma camada na face externa." },
  { t: "h2", text: "E. Formas de onda e perdas" },
  { t: "p", text: "Cada período de chaveamento foi tratado como quase estático em 400 pontos do semiciclo, com $v$_{in} = √2 $V$_{ac} |sen $θ$| e corrente média de período $i$ = √2 ($P$_{o}/$V$_{ac}) |sen $θ$|. Em CCM, $D$ = 1 − $v$_{in}/$V$_{o}, e a excursão de indução no período é" },
  { t: "eq", n: 3, plain: "ΔB = vin D Ts/(N Ae)" },
  { t: "p", noindent: true, text: "que não depende do material. A indutância incremental $L$($i$) = $L$_{0} $μ$_{inc}($H$)/$μ$_{i} fixa a ondulação Δ$i$ = $v$_{in} $D T$_{s}/$L$($i$); quando Δ$i$ > 2$i$, o período foi tratado em modo descontínuo (DCM), com o tempo de condução ajustado para manter a corrente média. A perda no núcleo de cada período é dada pela iGSE [11]," },
  { t: "eq", n: 4, plain: "Pv = (1/Ts) ∫[0,Ts] ki |dB/dt|^α ΔB^(β−α) dt" },
  { t: "eq", n: 5, plain: "ki = k / [(2π)^(α−1) ∫[0,2π] |cos θ|^α 2^(β−α) dθ]" },
  { t: "p", noindent: true, text: "em que $k$, $α$ e $β$ são os da forma $P$_{v} = $k f$^{$α$} $B̂$^{$β$}. Para fluxo triangular, (4) se reduz a $k$_{i} Δ$B$^{$β$} $f$_{s}^{$α$} ($d$_{1}^{1−$α$} + $d$_{2}^{1−$α$}), com $d$_{1} e $d$_{2} as frações do período em subida e em descida. Para que a perda média em 85 V a plena carga seja os 0,62 W de [7], a lei do catálogo foi multiplicada por 0,928 no indutor de referência; a lei de [8] foi usada sem ajuste. A perda no cobre é" },
  { t: "eq", n: 6, plain: "PCu = RCC Ief² + Σ[n=1..60] RCC FR(n fs) In²/2" },
  { t: "p", noindent: true, text: "com $I$_{ef} a corrente eficaz de linha, $I$_{n} as amplitudes harmônicas da ondulação de cada período [12] e $F$_{R} o fator de Dowell para fio redondo [13], com uma camada e resistividade do cobre a 20 °C. A resistência do indutor nanocristalino é a de [7] multiplicada pela razão entre as espiras médias, 66,0/84,7 mm, o que dá 54,6 mΩ. Não foi usado FEM (FEMM ou Ansys Maxwell): no toroide com entreferro distribuído e enrolamento uniforme, as curvas (1) já são definidas com $H$ = $N i$/$l$_{e}, que é o campo de que o modelo precisa, e um mapa local de $B$ exigiria a curva $B$($H$) intrínseca do pó, que [8] e [10] não fornecem. Com fluxo senoidal, (4) reproduz a equação de Steinmetz, e a potência média de entrada calculada é de 1200,0 W." },

  { t: "table", n: "I", caption: "Propriedades dos materiais, com a fonte de cada valor", widths: [1240, 1900, 1900], size: 15,
    header: [["Item", "Kool Mµ 60µ", "Pó nanocristalino 60µ"]],
    rows: [
      ["Origem dos dados", "Catálogo do fabricante [10]", "Ensaio da literatura [8]"],
      ["$μ$_{i}", "60 [10]", "60 [8, Tab. III]"],
      ["Queda de $μ$, (1)", "$H$_{0} = 75,6 A/cm; $n$ = 1,855 [10, p. 63]", "$H$_{0} = 93,0 A/cm; $n$ = 1,71 [8, Fig. 4]"],
      ["$μ$_{inc}/$μ$_{i} a 129,9 A/cm", "26,8 % (24,3 % no indutor de [7])", "36,1 %"],
      ["$B$ integrada, (2), a 129,9 A/cm", "0,59 T", "0,65 T"],
      ["Lei de perda", "$P$ = 44,30 $B̂$^{1,988} $f$^{1,541} [10, p. 109]", "$P$ = 89,38 $f$^{1,193} Δ$B$^{2,01} [8, Seç. IV-B]"],
      ["Unidades; indução", "mW/cm^{3}, kHz, T; $B̂$ = Δ$B$/2 [10, p. 23]", "kW/m^{3}, kHz, T; Δ$B$ pico a pico (Seç. II-C)"],
      ["$P$_{v} a 100 kHz e Δ$B$ = 100 mT", "139 kW/m^{3}", "212 kW/m^{3}"],
      ["Reprodução de [8], 100 e 200 kHz", "−5,0 %; +19,0 %", "−1,3 %; +6,4 %"]] },

  { t: "fig", n: 1, file: "fig1.png", caption: "(a) Permeabilidade incremental relativa a $μ$_{i} em função do campo de polarização: Kool Mµ pelo catálogo [10] e no indutor de [7], com $H$_{0} ajustado aos valores de [7], e pó nanocristalino [8]. (b) Densidade de perda a 100 kHz sob excitação senoidal em função de Δ$B$ pico a pico, pelas leis de [10] e [8], e perdas medidas em [8] com 248 mT pico a pico no núcleo de 28,6 cm^{3}." },

  { t: "h1", text: "III. Resultados" },
  { t: "h2", text: "A. Propriedades dos materiais" },
  { t: "p", text: "Na crista de 85 V, 129,9 A/cm, o pó nanocristalino retém 36,1 % de $μ$_{i}, contra 26,8 % do Kool Mµ pelo catálogo e 24,3 % no indutor de [7] (Fig. 1(a) e Tabela I); nesse campo, a curva integrada (2) dá 0,65 T no pó nanocristalino e 0,59 T no Kool Mµ. Com o mesmo Δ$B$, a perda do pó nanocristalino é maior: a 100 kHz e Δ$B$ = 100 mT, 212 contra 139 kW/m^{3}, razão de 1,53 (Fig. 1(b)), com expoentes de indução próximos (2,01 e 1,988)." },
  { t: "h2", text: "B. Reprojeto e tamanho" },
  { t: "p", text: "O núcleo nanocristalino de 21,4 mm atende ao requisito com 168,8 µH a 19,97 A (Fig. 2(a)). Sem polarização, a indutância cai de 680 para 468 µH, mas acima de 18,6 A o indutor nanocristalino tem indutância maior que a da referência: 147 contra 139 µH a 22,5 A. A Tabela II compara os dois componentes. O volume efetivo do núcleo cai 30,4 %, de 21,2 para 14,8 cm^{3}, e o da envoltória do componente enrolado cai 26,2 %, de 52,2 para 38,5 cm^{3}. A espira média encurta 22,1 %, assim como a resistência CC e a massa de cobre. A seção menor eleva o Δ$B$ máximo no semiciclo de 73,0 para 104,9 mT e a indução máxima em 85 V de 0,60 para 0,70 T." },
  { t: "p", text: "No espaço de projeto (Fig. 2(b)), mais espiras reduzem o núcleo e a perda em 230 V e elevam a perda em 85 V; o degrau perto de 78 % do volume corresponde à segunda camada na face interna, a partir de 57 espiras. De 40 a 96 espiras, a perda total a plena carga fica entre 79 % e 98 % da referência em 85 V e entre 111 % e 163 % em 230 V." },

  { t: "table", n: "II", caption: "Indutor de referência e indutor reprojetado com pó nanocristalino", widths: [1830, 1180, 1180, 850], size: 15,
    header: [["Item", "Referência, Kool Mµ [7]", "Pó nanocristalino", "Variação"]],
    rows: [
      ["Núcleo", "2 × 0077083A7 empilhados", "Toroide, mesmos diâmetros", ""],
      ["Diâmetros × altura (mm)", "40,77 × 23,32 × 30,74", "40,77 × 23,32 × 21,4", "−30,4 %"],
      ["$A$_{e} (mm^{2}); $V$_{e} (cm^{3})", "214; 21,2", "149; 14,8", "−30,4 %"],
      ["Espiras; fio; ocupação da janela", "64; 1,15 mm; 17,5 %", "64; 1,15 mm; 17,5 %", "0"],
      ["Espira média (mm)", "84,7", "66,0", "−22,1 %"],
      ["Resistência CC (mΩ)", "70 [7]", "54,6", "−22,1 %"],
      ["$L$ sem polarização (µH)", "680 [7]", "468", "−31,2 %"],
      ["$L$ a 19,97 A; a 22,5 A (µH)", "165 [7]; 139", "168,8; 147", "+2,3 %; +6,1 %"],
      ["$B$ máxima em 85 V (T)", "0,60", "0,70", "+16,6 %"],
      ["Δ$B$ máxima no semiciclo (mT)", "73,0", "104,9", "+43,7 %"],
      ["Envoltória enrolada, diâmetro × altura (mm)", "43,2 × 35,6", "43,2 × 26,3", "−26,2 %"],
      ["Volume da envoltória (cm^{3})", "52,2", "38,5", "−26,2 %"],
      ["Massa de cobre (g)", "50,4", "39,3", "−22,1 %"]] },

  { t: "fig", n: 2, file: "fig2.png", caption: "(a) Indutância incremental em função da corrente de polarização no indutor de referência e no nanocristalino de 21,4 mm, com os valores de [7] e o requisito de 168,5 µH a 19,97 A. (b) Espaço de projeto do indutor nanocristalino: perda total a plena carga em 85 e 230 V e volume efetivo do núcleo, relativos à referência, de 40 a 96 espiras, cada projeto com a menor altura que atende ao requisito; marcadores maiores: 64 espiras." },

  { t: "h2", text: "C. Perdas ao longo do semiciclo" },
  { t: "p", text: "A Fig. 3 mostra as perdas em cada período a plena carga. Em 85 V, o cobre domina e acompanha o quadrado da corrente, com máximo na crista: 28,6 W na referência e 22,3 W no indutor nanocristalino. A perda no núcleo também é máxima na crista, onde Δ$B$ é máximo: 1,01 contra 2,41 W. Em 230 V, Δ$B$ é máximo onde $v$_{in} = $V$_{o}/2, em $θ$ = 38° e 142°, e a perda no núcleo tem dois máximos, de 1,32 W na referência e de 3,35 W no indutor nanocristalino; nesses ângulos, a perda no núcleo do indutor nanocristalino é 2,7 vezes a do seu cobre." },
  { t: "fig", n: 3, file: "fig3.png", caption: "Perda no núcleo e no cobre (componentes de rede e de chaveamento) em cada período ao longo do semiciclo da rede, a plena carga: (a) 85 V; (b) 230 V. Entre parênteses, as médias no semiciclo." },
  { t: "h2", text: "D. Perdas de 85 a 265 VAC e em três cargas" },
  { t: "p", text: "A Fig. 4 e a Tabela III mostram as perdas médias. Em CCM, a perda no núcleo não depende da carga, porque Δ$B$ é imposto pela tensão em (3); as curvas de 50 % e 100 % coincidem, e a de 20 % se separa quando parte do semiciclo entra em DCM, a partir de 150 V no indutor nanocristalino e de 181 V na referência (em 230 V, 50,5 % e 31,5 % do semiciclo). Nos dois indutores, a perda no núcleo é máxima perto de 176 V; no nanocristalino, ela é de 91 % a 145 % maior. A perda no cobre varia com o quadrado da corrente; no indutor nanocristalino, é de 20 % a 22 % menor a plena carga, e a diferença se anula com 20 % de carga em tensão alta, em que a menor indutância sem polarização aumenta a parcela de chaveamento." },
  { t: "p", text: "A plena carga, a perda total do indutor nanocristalino é 15,9 % menor em 85 V e 6,4 % menor em 115 V, iguala a da referência em 131 V e é 28,6 % e 29,2 % maior em 230 e 265 V. Com 50 % de carga, a diferença vai de +0,5 % em 85 V a +80,9 % perto de 234 V; com 20 % de carga, de +55,5 % em 85 V a +121,5 % perto de 173 V." },

  { t: "table", n: "III", caption: "Perdas médias no semiciclo (W) e variação do indutor nanocristalino em relação à referência", size: 14,
    widths: [400, 500, 460, 460, 460, 460, 460, 460, 460, 460, 460],
    header: [
      [{ text: "$V$_{ac} (V)", rowSpan: 2 }, { text: "Carga (%)", rowSpan: 2 }, { text: "Núcleo", colSpan: 3 }, { text: "Cobre", colSpan: 3 }, { text: "Total", colSpan: 3 }],
      ["Ref.", "Nano", "Δ (%)", "Ref.", "Nano", "Δ (%)", "Ref.", "Nano", "Δ (%)"]],
    rows: tab3rows },

  { t: "fig", n: 4, file: "fig4.png", caption: "Perdas médias no semiciclo em função da tensão de entrada, com 100 % (linha cheia), 50 % (tracejada) e 20 % (pontilhada) de carga; Kool Mµ em preto e pó nanocristalino em cinza: (a) núcleo, em que as curvas de 50 % e 100 % coincidem; (b) cobre; (c) variação da perda total do indutor nanocristalino em relação à referência." },

  { t: "h1", text: "IV. Discussão" },
  { t: "h2", text: "A. Origem da redução de volume" },
  { t: "p", text: "Com as mesmas espiras e o mesmo $l$_{e}, os dois indutores operam com o mesmo campo na crista, e a indutância exigida passa a depender só de $μ$_{inc} nesse campo e da seção. Como o pó nanocristalino retém 36,1 % de $μ$_{i}, contra 24,3 % no indutor de [7], a mesma indutância exige cerca de 70 % da seção, daí a altura de 21,4 mm e a redução de 30,4 % no volume do núcleo. A envoltória cai menos, 26,2 %, porque o enrolamento acrescenta a mesma espessura aos dois componentes, e o cobre cai 22,1 %, porque só a parcela da espira que acompanha a altura encurta." },
  { t: "h2", text: "B. Origem das perdas" },
  { t: "p", text: "A plena carga, a perda no núcleo do indutor nanocristalino é 2,25 vezes a da referência em 85 V e 2,38 vezes em 230 V. O fator se decompõe em duas parcelas. A seção menor multiplica Δ$B$ por 1/0,696; com $β$ ≈ 2 e volume 0,696 vez o da referência, isso multiplica a perda por 1,44. A lei de perda do pó, frente à do Kool Mµ ajustada a [7], responde pelo restante: 1,56 em 85 V e 1,65 em 230 V. A perda no cobre cai na proporção da espira média enquanto domina a componente de rede; em carga leve e tensão alta, a componente de chaveamento, maior no indutor nanocristalino pela menor indutância sem polarização, anula a redução. O resultado total depende, portanto, da proporção entre cobre e núcleo: o indutor nanocristalino perde menos onde o cobre domina, em tensão baixa e carga alta, e mais onde o núcleo domina, em tensão alta ou carga leve." },
  { t: "h2", text: "C. Efeito da leitura dos 248 mT" },
  { t: "p", text: "Se os 248 mT de [8] fossem lidos como pico, como na frase da Seção IV-A de [8], a perda no núcleo do indutor nanocristalino seria dividida por 4,03 e ficaria abaixo da referência em todos os pontos; a perda total a plena carga passaria de +28,6 % para −26,6 % em 230 V, e a conclusão se inverteria. A leitura pico a pico, apoiada pelos demais dados de [8] e pela concordância com o catálogo [10], é a que sustenta os resultados acima." },
  { t: "h2", text: "D. Escala no conversor" },
  { t: "p", text: "As diferenças são de componente. Referidas à potência de saída, equivalem a −0,20 % em 85 V e +0,07 % em 230 V a plena carga, e a +0,28 % e +0,40 % com 20 % de carga (240 W). Em fontes que operam a maior parte do tempo em tensão alta e carga parcial, como as de servidores em centros de dados, o pó nanocristalino de [8] aumenta a perda do indutor; em aplicações limitadas por volume e dimensionadas para tensão baixa, reduz o volume e a perda no pior caso." },

  { t: "h1", text: "V. Conclusão" },
  { t: "p", text: "No indutor boost de 1,2 kW de [7], o pó nanocristalino de [8], com as mesmas espiras, o mesmo fio e o mesmo requisito de indutância, permite um núcleo 30 % menor e um componente 26 % menor que o Kool Mµ, porque retém mais permeabilidade sob polarização. A seção menor e a lei de perda mais alta do pó mais que dobram a perda no núcleo, enquanto a espira mais curta reduz a perda no cobre. O indutor nanocristalino perde menos em tensão baixa e carga alta, em que o cobre domina, e mais em tensão alta e em carga leve, em que o núcleo domina, com os 248 mT de [8] lidos como pico a pico, como indicam os dados do próprio artigo; a leitura de pico inverteria essa conclusão. Como trabalho futuro, propõe-se medir os dois indutores em bancada, com polarização CC e a forma de onda do PFC, e acoplar um modelo térmico ao projeto." },

  { t: "h1", text: "Declarações" },
  { t: "p", text: "*Conflito de interesses.* O autor trabalha na CBMM, produtora de nióbio, elemento presente na liga do pó nanocristalino de [8]. A pesquisa é independente, sem financiamento nem participação da empresa." },
  { t: "p", text: "*Uso de IA.* O assistente Claude (Anthropic) foi usado na implementação dos cálculos, na geração das figuras e na redação; o autor responde pelo conteúdo." },

  { t: "h1", text: "Referências" },
  { t: "refs", items: [
    "International Energy Agency, “Electricity 2026: Analysis and forecast to 2030,” IEA, Paris, France, Feb. 2026. [Online]. Available: https://www.iea.org/reports/electricity-2026",
    "International Energy Agency, “Global EV Outlook 2026,” IEA, Paris, France, May 2026. [Online]. Available: https://www.iea.org/reports/global-ev-outlook-2026",
    "International Energy Agency, “Energy and AI,” IEA, Paris, France, Apr. 2025. [Online]. Available: https://www.iea.org/reports/energy-and-ai",
    "“Gesetz zur Änderung des Gebäudeenergiegesetzes, zur Änderung der Verordnung über Heizkostenabrechnung, zur Änderung der Betriebskostenverordnung und zur Änderung der Kehr- und Überprüfungsordnung,” *Bundesgesetzblatt*, 2023 I, no. 280, Oct. 2023.",
    "International Energy Agency, “Renewables 2025: Analysis and forecast to 2030,” IEA, Paris, France, Oct. 2025. [Online]. Available: https://www.iea.org/reports/renewables-2025",
    "*Electromagnetic Compatibility (EMC), Part 3-2: Limits, Limits for Harmonic Current Emissions (Equipment Input Current ≤ 16 A per Phase)*, IEC 61000-3-2:2018+AMD1:2020, 2020.",
    "S. Abdel-Rahman, F. Stückler, and K. Siu, “PFC boost converter design guide: 1200 W design example,” Infineon Technologies AG, Munich, Germany, Application Note, rev. 1.1, Feb. 2016. [Online]. Available: https://www.infineon.com/assets/row/public/documents/24/42/infineon-applicationnote-pfcccmboostconverterdesignguide-applicationnotes-en.pdf",
    "C. Jiang, X. Li, S. S. Ghosh, H. Zhao, Y. Shen, and T. Long, “Nanocrystalline powder cores for high-power high-frequency power electronics applications,” *IEEE Trans. Power Electron.*, vol. 35, no. 10, pp. 10821 a 10830, Oct. 2020, doi: 10.1109/TPEL.2020.2979069.",
    "Magnetics, “0077083A7 Kool Mµ toroid,” datasheet, rev. 6 Oct. 2021. [Online]. Available: https://www.mag-inc.com/Media/Magnetics/Datasheets/0077083A7.pdf",
    "Magnetics, “2025 Magnetics powder cores catalog,” Pittsburgh, PA, USA, 2025. [Online]. Available: https://www.mag-inc.com/Media/Magnetics/File-Library/Product%20Literature/Powder%20Core%20Literature/Magnetics-Powder-Core-Catalog.pdf",
    "K. Venkatachalam, C. R. Sullivan, T. Abdallah, and H. Tacca, “Accurate prediction of ferrite core loss with nonsinusoidal waveforms using only Steinmetz parameters,” in *Proc. IEEE Workshop Comput. Power Electron. (COMPEL)*, Mayagüez, Puerto Rico, 2002, pp. 36 a 41, doi: 10.1109/CIPE.2002.1196712.",
    "N. Kondrath and M. K. Kazimierczuk, “Inductor winding loss owing to skin and proximity effects including harmonics in non-isolated pulse-width modulated dc-dc converters operating in continuous conduction mode,” *IET Power Electron.*, vol. 3, no. 6, pp. 989 a 1000, Nov. 2010, doi: 10.1049/iet-pel.2009.0299.",
    "P. L. Dowell, “Effects of eddy currents in transformer windings,” *Proc. IEE*, vol. 113, no. 8, pp. 1387 a 1394, Aug. 1966, doi: 10.1049/piee.1966.0236."] }
];
