"""CORE ENGINE - cash-and-carry delta neutro (spot long + perp short).

O modulo tem duas faces:
  * live   : `get_funding_rate` / `execute_delta_neutral` falam com a Binance
             Testnet via ccxt;
  * sim    : `core_step` roda o mesmo racional de PnL no backtest.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import config
from engine import exchange

# ------------------------------------------------------------------ live side


def get_funding_rate(symbol: str, client=None) -> float:
    """Funding DIARIO do simbolo.

    A Binance paga funding a cada 8h; `fetch_funding_rate` devolve a taxa do
    intervalo de 8h, entao rate_day = rate_8h * 3.
    """
    client = client or exchange.perp()
    info = client.fetch_funding_rate(symbol)
    rate_8h = info.get("fundingRate")
    if rate_8h is None:
        raise ValueError(f"funding indisponivel para {symbol}")
    return float(rate_8h) * config.FUNDING_INTERVALS_PER_DAY


def get_funding_rates(symbols=None, client=None) -> dict[str, float]:
    """Funding diario de varios simbolos; simbolos indisponiveis sao ignorados."""
    out: dict[str, float] = {}
    for sym in (symbols or config.SYMBOLS):
        try:
            out[sym] = get_funding_rate(sym, client=client)
        except Exception:
            continue
    return out


def execute_delta_neutral(symbol: str, allocation: float, leverage: float,
                          price: float | None = None, dry_run: bool = False) -> dict:
    """Abre a perna dupla: BUY SPOT + SELL PERP * leverage. Sempre hedgeado.

    `allocation` e o notional em USDT do lado spot. O short em perp usa o mesmo
    notional multiplicado pela alavancagem, e o spot e escalado junto para que o
    delta liquido permaneca zero.
    """
    if leverage > config.LEVERAGE_CORE_MAX:
        raise ValueError("leverage acima do limite de 3x")
    notional = allocation * leverage
    spot_c, perp_c = exchange.spot(), exchange.perp()
    price = price or float(spot_c.fetch_ticker(symbol)["last"])
    qty = notional / price

    plan = {
        "symbol": symbol,
        "price": price,
        "qty": qty,
        "notional": notional,
        "leverage": leverage,
        "spot": {"side": "buy", "amount": qty},
        "perp": {"side": "sell", "amount": qty},
        "delta": 0.0,
    }
    if dry_run:
        plan["dry_run"] = True
        return plan

    perp_symbol = f"{symbol}:USDT"
    try:
        perp_c.set_leverage(int(leverage), perp_symbol)
    except Exception:
        pass
    plan["spot_order"] = spot_c.create_order(symbol, "market", "buy", qty)
    try:
        plan["perp_order"] = perp_c.create_order(perp_symbol, "market", "sell", qty)
    except Exception:
        # nunca deixar perna solta: desfaz o spot se o short falhar
        spot_c.create_order(symbol, "market", "sell", qty)
        raise
    return plan


def close_delta_neutral(symbol: str, qty: float) -> dict:
    """Fecha as duas pernas de uma posicao delta neutra."""
    spot_c, perp_c = exchange.spot(), exchange.perp()
    return {
        "spot_order": spot_c.create_order(symbol, "market", "sell", qty),
        "perp_order": perp_c.create_order(f"{symbol}:USDT", "market", "buy", qty),
    }


# ------------------------------------------------------------------- sim side


def capacity_factor(notional: float) -> float:
    """Fracao do funding efetivamente capturada dado o tamanho da posicao."""
    cap = config.CAPACITY_PER_SYMBOL
    if notional <= cap:
        return 1.0
    return (cap / notional) ** config.CAPACITY_EXP


@dataclass
class CoreEngine:
    """Sleeve CORE: seleciona simbolos com funding saudavel e roda cash-and-carry."""

    params: dict = field(default_factory=config.as_dict)
    open_symbols: list[str] = field(default_factory=list)
    gatekeeper_on: bool = False
    held_days: dict = field(default_factory=dict)

    @property
    def leverage(self) -> float:
        return self.params["LEVERAGE_CORE"]

    def select(self, fundings: dict[str, float]) -> list[str]:
        """Cesta alvo com histerese: mantem o que esta bom, troca so com margem."""
        thr = self.params["FUNDING_THRESHOLD_CORE"]
        exit_thr = thr * config.CORE_EXIT_FRACTION

        # 1) mantem posicoes cujo funding ainda paga, respeitando hold minimo
        keep = [s for s in self.open_symbols
                if fundings.get(s, -1.0) >= exit_thr
                or self.held_days.get(s, 0) < config.CORE_MIN_HOLD_DAYS]
        keep = [s for s in keep if s in fundings]

        # 2) candidatos novos acima do threshold de entrada
        cand = sorted(((s, f) for s, f in fundings.items()
                       if f >= thr and s not in keep), key=lambda x: -x[1])

        free = config.MAX_CORE_POSITIONS - len(keep)
        chosen = keep + [s for s, _ in cand[:max(free, 0)]]
        cand = cand[max(free, 0):]

        # 3) substituicao so se o candidato bater o pior mantido pela margem
        for sym, f in cand:
            if not chosen:
                break
            worst = min(chosen, key=lambda s: fundings.get(s, 0.0))
            if (self.held_days.get(worst, 0) >= config.CORE_MIN_HOLD_DAYS
                    and f - fundings.get(worst, 0.0) > config.CORE_SWITCH_EDGE):
                chosen[chosen.index(worst)] = sym
        return chosen[: config.MAX_CORE_POSITIONS]

    def step(self, capital: float, fundings: dict[str, float],
             signal: dict[str, float] | None = None) -> tuple[float, dict]:
        """Avanca um dia. `signal` = funding OBSERVAVEL na decisao (D-1);
        `fundings` = funding efetivamente pago hoje. Retorna (pnl_usdt, info)."""
        signal = signal if signal is not None else fundings
        stop = self.params["STOP_FUNDING_NEGATIVE"]
        chosen = [s for s in self.select(signal) if s in fundings]
        best = max(signal.values()) if signal else 0.0

        # Gatekeeper: funding do mercado abaixo do stop -> zera tudo e vai pra T-Bill
        if best < stop or not chosen:
            turnover = len(self.open_symbols)
            self.open_symbols = []
            self.held_days = {}
            self.gatekeeper_on = True
            # gatekeeper fecha as posicoes: um sentido apenas
            turn_notional = capital * min(turnover, 1)
            fees = turn_notional * (config.FEE_RATE + config.SLIPPAGE)
            carry = capital * config.TBILL_DAILY
            return carry - fees, {
                "mode": "tbill", "symbols": [], "funding": best,
                "gross": 0.0, "fees": fees, "borrow": 0.0, "carry": carry,
                "notional": 0.0, "idle": capital, "rotated": min(turnover, 1),
                "turn_notional": turn_notional,
                "delta": 0.0,
            }

        self.gatekeeper_on = False
        rotated = len(set(chosen) ^ set(self.open_symbols))
        self.held_days = {s: self.held_days.get(s, 0) + 1 for s in chosen}
        self.open_symbols = chosen

        # Capacidade: um desk real nao empurra nocional infinito num par ilíquido.
        # Aloca ate CAPACITY_PER_SYMBOL de nocional por simbolo; o excedente
        # fica em caixa rendendo T-Bill em vez de sofrer decaimento de captura.
        if config.CORE_CAPACITY_MODE == "decay":
            # modo original: empurra todo o capital e sofre decaimento de captura
            notional = capital * self.leverage
            per_notional = notional / len(chosen)
            equity_used, idle = capital, 0.0
            gross = sum(per_notional * fundings[sym] * capacity_factor(per_notional)
                        for sym in chosen)
        else:
            max_notional = config.CAPACITY_PER_SYMBOL * len(chosen)
            notional = min(capital * self.leverage, max_notional)
            per_notional = notional / len(chosen)
            equity_used = notional / self.leverage
            idle = max(capital - equity_used, 0.0)
            gross = sum(per_notional * fundings[sym] for sym in chosen)

        # custos so no giro (entradas/saidas), sobre o nocional alavancado
        # `rotated` e a diferenca simetrica: ja conta a saida do simbolo antigo
        # E a entrada do novo. Cada um desses e UM sentido, entao o custo e
        # one-way por unidade de `rotated` -- multiplicar por 2 aqui cobraria
        # dois round-trips por uma unica troca.
        turn_notional = per_notional * rotated
        fees = turn_notional * (config.FEE_RATE + config.SLIPPAGE)
        # custo de carrego apenas sobre a parte efetivamente tomada emprestada
        borrow = (capital * max(self.leverage - 1.0, 0.0) * config.BORROW_DAILY
                  if config.CORE_CAPACITY_MODE == "decay"
                  else max(notional - equity_used, 0.0) * config.BORROW_DAILY)
        carry = idle * config.TBILL_DAILY

        avg_f = sum(fundings[s] for s in chosen) / len(chosen)
        return gross - fees - borrow + carry, {
            "mode": "carry", "symbols": chosen, "funding": avg_f,
            "gross": gross, "fees": fees, "borrow": borrow, "carry": carry,
            "notional": notional, "idle": idle, "rotated": rotated,
            "turn_notional": turn_notional,
            # delta liquido: cada posicao e long spot + short perp de mesmo
            # nocional, logo a exposicao direcional e zero por construcao
            "delta": 0.0,
            "held_days": dict(self.held_days),
        }
