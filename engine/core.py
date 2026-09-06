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

    @property
    def leverage(self) -> float:
        return self.params["LEVERAGE_CORE"]

    def select(self, fundings: dict[str, float]) -> list[str]:
        """Simbolos elegiveis, ordenados por funding decrescente."""
        thr = self.params["FUNDING_THRESHOLD_CORE"]
        elig = [(s, f) for s, f in fundings.items() if f >= thr]
        elig.sort(key=lambda x: -x[1])
        return [s for s, _ in elig[: config.MAX_CORE_POSITIONS]]

    def step(self, capital: float, fundings: dict[str, float]) -> tuple[float, dict]:
        """Avanca um dia. Retorna (pnl_usdt, info)."""
        stop = self.params["STOP_FUNDING_NEGATIVE"]
        chosen = self.select(fundings)
        best = max(fundings.values()) if fundings else 0.0

        # Gatekeeper: funding do mercado abaixo do stop -> zera tudo e vai pra T-Bill
        if best < stop or not chosen:
            turnover = len(self.open_symbols)
            self.open_symbols = []
            self.gatekeeper_on = True
            fees = capital * (config.FEE_RATE + config.SLIPPAGE) * 2 * min(turnover, 1)
            pnl = capital * config.TBILL_DAILY - fees
            return pnl, {"mode": "tbill", "symbols": [], "funding": best}

        self.gatekeeper_on = False
        rotated = len(set(chosen) ^ set(self.open_symbols))
        self.open_symbols = chosen

        per = capital / len(chosen)
        gross = 0.0
        for sym in chosen:
            # PnL = allocation * funding_day * leverage, com decaimento de capacidade
            notional = per * self.leverage
            gross += notional * fundings[sym] * capacity_factor(notional)

        # custos so no giro (entradas/saidas), sobre o nocional alavancado
        turn_notional = per * self.leverage * rotated
        fees = turn_notional * (config.FEE_RATE + config.SLIPPAGE) * 2
        # custo de carrego da parte alavancada
        borrow = capital * max(self.leverage - 1.0, 0.0) * config.BORROW_DAILY
        avg_f = sum(fundings[s] for s in chosen) / len(chosen)
        return gross - fees - borrow, {"mode": "carry", "symbols": chosen, "funding": avg_f}
