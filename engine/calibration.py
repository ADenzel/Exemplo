"""Derivacao dos parametros a partir do CUSTO, nao do resultado.

Um grid search que maximiza `CAGR * Sharpe / (1 + |MaxDD|)` seleciona os
parametros que melhor se ajustam ao passado -- e a definicao de overfitting.
Aqui os parametros saem de aritmetica de custo, que independe da amostra:

    RT   = custo de round-trip (entrar e sair das duas pernas)
    f    = funding diario da posicao
    H    = dias de permanencia

Uma posicao so se paga se `f * H > RT`. Isso fixa, sem olhar para o P&L:

    limiar de entrada  = RT / H_payback    (funding minimo que se paga no prazo)
    limiar de saida    = entrada * banda   (histerese: sair e voltar custa 2*RT)
    hold minimo        = RT / (f_tipico * orcamento_de_taxas)
    margem de troca    = RT / H_esperado   (vantagem minima para justificar girar)

O backtest entra depois, e so para FALSIFICAR: se a estrategia nao sobrevive,
ela e descartada. Ele nunca escolhe os numeros.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

import config


def round_trip_cost() -> float:
    """Custo de abrir e fechar a posicao hedgeada, em fracao do nocional.

    config.FEE_RATE ja e a media ponderada das DUAS pernas (spot 0.10% +
    perp 0.04%) por sentido; o mesmo vale para SLIPPAGE. Portanto o
    round-trip e apenas x2 (ida e volta), nao x4.
    """
    one_way = config.FEE_RATE + config.SLIPPAGE
    return one_way * 2


# ---------------------------------------------------------------- axiomas
# As UNICAS entradas livres. Sao escolhas de politica de risco, declaradas
# antes de qualquer dado, e nao sao ajustaveis olhando resultado. Todo o resto
# do modulo e consequencia aritmetica destas quatro linhas.
POLICY = {
    "payback_days": 10,        # prazo em que uma posicao no limiar paga a entrada
    "fee_budget": 0.25,        # teto de taxas como fracao do funding bruto
    "slippage_budget": 0.0005, # impacto de mercado aceito por execucao
    "margin_headroom": 2.0,    # folga exigida do funding sobre o custo de margem
}


def persistence_span(funding) -> int:
    """Janela da EMA, derivada da MEIA-VIDA do funding.

    Suavizar mais que a persistencia do sinal joga fora informacao; menos, deixa
    passar ruido que vira giro. A janela certa e a meia-vida da autocorrelacao
    de ordem 1 -- uma estatistica da serie, nao uma escolha.
    """
    a = np.asarray(funding, dtype=float)
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    phis = []
    for j in range(a.shape[1]):
        col = a[:, j]
        col = col[np.isfinite(col)]
        if col.size < 30:
            continue
        x, y = col[:-1], col[1:]
        xc, yc = x - x.mean(), y - y.mean()
        denom = float((xc ** 2).sum())
        if denom > 0:
            phis.append(float((xc * yc).sum() / denom))
    phi = float(np.clip(np.median(phis), 1e-6, 0.999)) if phis else 0.5
    half_life = np.log(0.5) / np.log(phi)
    return max(int(np.ceil(half_life)), 1)


def capacity_from_liquidity(adv_usd: float, daily_vol: float,
                            slippage_budget: float | None = None) -> float:
    """Nocional maximo por simbolo, a partir do impacto de mercado.

    Impacto ~ sigma * sqrt(V / ADV) (raiz quadrada, padrao de microestrutura).
    Igualando ao orcamento de slippage e resolvendo para V:

        V = ADV * (slippage / sigma)^2

    O tamanho sai da liquidez do par, nao de um teto redondo escolhido a mao.
    """
    s = POLICY["slippage_budget"] if slippage_budget is None else slippage_budget
    if adv_usd <= 0 or daily_vol <= 0:
        return 0.0
    # NOTA: a constante do modelo de impacto esta implicitamente em 1.0 e o ADV
    # e o de 1 dia, entao o numero sai conservador. Ela precisa ser calibrada
    # contra fills reais -- e ajusta-la para "dar um numero bonito" seria
    # exatamente o ajuste por resultado que este modulo existe para evitar.
    return float(adv_usd * (s / daily_vol) ** 2)


def positions_from_capacity(target_notional: float, capacity_per_symbol: float,
                            available: int) -> int:
    """Numero de posicoes = o minimo que a capacidade permite.

    Diversificar alem do necessario dilui o funding: cada posicao extra e, por
    construcao, pior que a anterior no ranking. Entao mantem-se o MENOR numero
    de posicoes que acomoda o nocional dentro do limite de impacto por par.
    """
    if capacity_per_symbol <= 0:
        return available
    return int(min(max(np.ceil(target_notional / capacity_per_symbol), 1), available))


def drawdown_capacity(funding, hold_days: int, leverage: float) -> float:
    """Perda maxima que o PROCESSO consegue produzir, medida na serie.

    Nao e uma tolerancia escolhida: e a pior media de funding sustentada por
    `hold_days` observada no mercado, vezes a alavancagem. Define o kill switch
    a partir do que a estrategia pode perder, nao do que se gostaria de perder.
    """
    a = np.asarray(funding, dtype=float)
    if a.ndim == 1:
        a = a.reshape(-1, 1)
    piores = []
    for j in range(a.shape[1]):
        col = a[:, j][np.isfinite(a[:, j])]
        if col.size <= hold_days:
            continue
        janelas = np.convolve(col, np.ones(hold_days) / hold_days, mode="valid")
        piores.append(float(janelas.min()))
    if not piores:
        return 0.0
    return float(np.median(piores) * hold_days * leverage)


@dataclass
class DerivedParams:
    round_trip: float
    entry_threshold: float
    exit_threshold: float
    min_hold_days: int
    switch_edge: float
    max_leverage: float
    payback_days: int
    fee_budget: float
    breakeven_hold: float
    max_positions: int = 4
    observed_typical_funding: float = 0.0
    admitted_fraction: float = 0.0
    ema_span: int = 1
    autocorr_half_life: int = 1
    drawdown_capacity: float = 0.0

    @property
    def max_turnover_per_day(self) -> float:
        """Giro implicado: n_posicoes / hold minimo. Nao e um numero magico."""
        return self.max_positions / self.min_hold_days

    def as_config(self) -> dict:
        return {
            "FUNDING_THRESHOLD_CORE": self.entry_threshold,
            "CORE_EXIT_FRACTION": self.exit_threshold / self.entry_threshold,
                "CORE_MIN_HOLD_DAYS": self.min_hold_days,
            "CORE_SWITCH_EDGE": self.switch_edge,
            "LEVERAGE_CORE": self.max_leverage,
        }

    def report(self) -> str:
        return (
            f"  round-trip (ida e volta, 2 pernas) : {self.round_trip:.4%} do nocional\n"
            f"  payback exigido                    : {self.payback_days} dias\n"
            f"  -> limiar de entrada               : {self.entry_threshold:.4%}/dia "
            f"({self.entry_threshold * 365:.1%} a.a.)\n"
            f"  -> limiar de saida (histerese)     : {self.exit_threshold:.4%}/dia\n"
            f"  -> hold de empate                  : {self.breakeven_hold:.1f} dias\n"
            f"  -> hold minimo (empate / orcamento): {self.min_hold_days} dias\n"
            f"  -> giro maximo implicado           : {self.max_turnover_per_day:.3f} trocas/dia\n"
            f"  -> margem de troca                 : {self.switch_edge:.4%}/dia\n"
            f"  -> alavancagem maxima              : {self.max_leverage:.2f}x\n"
            f"  orcamento de taxas                 : {self.fee_budget:.0%} do funding bruto\n"
            f"  funding REALIZADO no hold (medido) : {self.observed_typical_funding:.4%}/dia\n"
            f"  fracao do mercado admitida         : {self.admitted_fraction:.1%} dos pares-dia\n"
            f"  meia-vida do funding (medida)      : {self.autocorr_half_life} dias\n"
            f"  -> janela da EMA                   : {self.ema_span} dias\n"
            f"  -> posicoes simultaneas            : {self.max_positions}\n"
            f"  perda que o processo pode gerar    : {self.drawdown_capacity:.2%}"
        )


def derive(payback_days: int = 10, exit_band: float = 0.5,
           expected_hold: int = 10, fee_budget: float = 0.25,
           borrow_daily: float | None = None,
           typical_funding: float | None = None) -> DerivedParams:
    """Todos os parametros operacionais, a partir do custo.

    `payback_days`  : prazo em que uma posicao no limiar precisa pagar a entrada.
    `exit_band`     : fracao do limiar de entrada abaixo da qual se sai.
    `expected_hold` : horizonte usado para amortizar o custo de uma troca.
    `fee_budget`    : teto de taxas como fracao do funding bruto (checado depois).
    """
    rt = round_trip_cost()
    borrow = config.BORROW_DAILY if borrow_daily is None else borrow_daily

    entry = rt / payback_days
    exit_thr = entry * exit_band
    switch = rt / expected_hold
    f_typ = typical_funding if typical_funding is not None else entry * 1.7

    # Hold minimo: empatar NAO e o criterio. A fracao de taxas sobre o funding
    # bruto de uma posicao e  RT / (H * f), entao para respeitar o orcamento
    # `fee_budget` e preciso  H >= RT / (f * fee_budget)  -- ou seja, 1/budget
    # vezes o hold de empate. Com budget de 25%, quatro vezes mais longo.
    breakeven_hold = rt / max(f_typ, 1e-9)
    min_hold = int(np.ceil(breakeven_hold / max(fee_budget, 1e-9)))

    # Alavancagem: cada unidade extra custa `borrow` ao dia e rende `f_typ`.
    # So se justifica se o funding tipico cobrir o custo com folga de 2x.
    max_lev = 1.0 if f_typ < borrow * 2 else min(1.0 + (f_typ - borrow) / borrow, 1.5)

    return DerivedParams(rt, entry, exit_thr, min_hold, switch,
                         round(max_lev, 2), payback_days, fee_budget,
                         breakeven_hold)


def apply(dp: DerivedParams) -> dict:
    """Escreve os parametros derivados no config e devolve o dict aplicado."""
    cfg = dp.as_config()
    for k, v in cfg.items():
        setattr(config, k, v)
    return cfg


def forward_funding(funding_2d, threshold: float, horizon: int) -> float:
    """Funding medio REALIZADO nos `horizon` dias apos cruzar `threshold`.

    Estatistica de mercado, nao de estrategia: mede a DECAIDA do sinal. Um
    simbolo e escolhido num pico de funding e o pico nao dura -- usar o funding
    da entrada como se fosse o do periodo inteiro superestima a receita e e a
    razao pela qual a primeira calibracao errou o orcamento de taxas.
    """
    a = np.asarray(funding_2d, dtype=float)
    n, m = a.shape
    vals = []
    for j in range(m):
        col = a[:, j]
        for i in range(n - horizon):
            if np.isfinite(col[i]) and col[i] >= threshold:
                w = col[i:i + horizon]
                w = w[np.isfinite(w)]
                if w.size:
                    vals.append(w.mean())
    return float(np.mean(vals)) if vals else 0.0


def calibrate_from_market(funding, payback_days: int = 10, fee_budget: float = 0.25,
                          max_iter: int = 12) -> DerivedParams:
    """Ponto fixo entre o limiar de entrada e o funding tipico que ele admite.

    `f_tipico` NAO e assumido: e medido na propria serie de funding -- uma
    estatistica de MERCADO, nao de P&L. Nenhum retorno da estrategia entra aqui.
    O limiar sobe ate que o funding medio dos simbolos admitidos pague o
    round-trip dentro do orcamento de taxas num hold aceitavel.
    """
    arr = np.asarray(funding, dtype=float)
    arr = arr[np.isfinite(arr)]
    rt = round_trip_cost()

    grid = np.asarray(funding, dtype=float)
    if grid.ndim == 1:
        grid = grid.reshape(-1, 1)

    # Ponto fixo: o limiar sobe ate que o funding REALIZADO no hold pague o
    # round-trip dentro do orcamento. Criterio: RT / (H * f_fwd) <= fee_budget.
    entry = rt / payback_days
    hold = payback_days
    f_fwd = 0.0
    for _ in range(max_iter):
        f_fwd = forward_funding(grid, entry, hold)
        if f_fwd <= 0:
            break
        need_hold = rt / (f_fwd * fee_budget)
        new_hold = int(np.ceil(min(need_hold, MAX_ACCEPTABLE_HOLD)))
        # se nem no hold maximo o orcamento fecha, exige funding melhor
        new_entry = (entry if need_hold <= MAX_ACCEPTABLE_HOLD
                     else rt / (MAX_ACCEPTABLE_HOLD * fee_budget))
        if abs(new_entry - entry) < 1e-7 and new_hold == hold:
            hold = new_hold
            break
        entry, hold = new_entry, new_hold

    admitted = arr[arr >= entry]
    dp = derive(payback_days=payback_days, fee_budget=fee_budget,
                typical_funding=max(f_fwd, 1e-9))
    dp.entry_threshold = entry
    dp.exit_threshold = entry * 0.5
    dp.min_hold_days = max(hold, 1)
    dp.breakeven_hold = rt / max(f_fwd, 1e-9)
    dp.switch_edge = rt / max(dp.min_hold_days, 1)
    # Banda de histerese = exatamente o round-trip amortizado. Sair e voltar
    # custa RT; a banda tem que ser larga o bastante para nao pagar isso a toa.
    dp.exit_threshold = max(entry - dp.switch_edge, 0.0)
    dp.observed_typical_funding = f_fwd
    dp.admitted_fraction = float((arr >= entry).mean())
    dp.autocorr_half_life = persistence_span(grid)
    dp.ema_span = dp.autocorr_half_life
    dp.drawdown_capacity = drawdown_capacity(grid, dp.min_hold_days, dp.max_leverage)
    return dp


MAX_ACCEPTABLE_HOLD = 30       # acima disso a posicao vira exposicao a regime


# ---------------------------------------------------------------- diagnostico


def process_health(log) -> dict:
    """Metricas de PROCESSO -- todas independentes do lucro obtido."""
    gross = log["gross"].sum()
    fees = log["fees"].sum()
    borrow = log["borrow"].sum()
    days = len(log)
    holds = [d for row in log["core_held_days"] for d in row.values()] or [0]
    return {
        "fee_ratio": fees / gross if gross else float("inf"),
        "cost_ratio": (fees + borrow) / gross if gross else float("inf"),
        "turnover_per_day": log["rotated"].sum() / days,
        "avg_hold_days": float(np.mean(holds)),
        "deployed_fraction": float((log["n_core"] > 0).mean()),
        "max_delta": float(log["delta"].abs().max()),
        "max_leverage": float(log["leverage"].max()),
    }


def health_limits(dp: DerivedParams) -> dict:
    """Limites DERIVADOS dos mesmos parametros -- nenhum numero magico."""
    return {
        "fee_ratio": ("<=", dp.fee_budget),
        "cost_ratio": ("<=", dp.fee_budget * 2),
        "turnover_per_day": ("<=", dp.max_turnover_per_day),
        "avg_hold_days": (">=", float(dp.min_hold_days)),
        "max_delta": ("<=", 1e-9),
        "max_leverage": ("<=", dp.max_leverage),
    }


# limites fixos usados quando nao ha um DerivedParams em maos
HEALTH_LIMITS = {
    "fee_ratio": ("<=", 0.30),
    "cost_ratio": ("<=", 0.50),
    "avg_hold_days": (">=", 7.0),
    "max_delta": ("<=", 1e-9),
    "max_leverage": ("<=", 1.5),
}


def check_health(health: dict, limits: dict | None = None) -> list[str]:
    """Devolve a lista de violacoes de processo (vazia = saudavel)."""
    bad = []
    for key, (op, limit) in (limits or HEALTH_LIMITS).items():
        v = health.get(key)
        if v is None:
            continue
        if (op == "<=" and v > limit) or (op == ">=" and v < limit):
            bad.append(f"{key}={v:.4g} viola {op} {limit}")
    return bad
