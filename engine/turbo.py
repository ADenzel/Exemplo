"""TURBO ENGINE - captura de funding extremo, delta neutro, alavancagem <= 1x.

Varre o universo procurando funding diario acima de FUNDING_THRESHOLD_TURBO,
abre posicoes hedgeadas (multiplas simultaneas) e segura por TURBO_HOLD_DAYS.
Fora de posicao o capital do sleeve rende T-Bill.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import config
from engine import core


@dataclass
class TurboPosition:
    symbol: str
    notional: float
    days_held: int = 0
    entry_funding: float = 0.0
    accrued: float = 0.0


@dataclass
class TurboEngine:
    params: dict = field(default_factory=config.as_dict)
    positions: dict[str, TurboPosition] = field(default_factory=dict)

    @property
    def leverage(self) -> float:
        lev = self.params.get("LEVERAGE_TURBO", 1.0)
        return min(lev, config.LEVERAGE_TURBO_MAX)

    # ------------------------------------------------------------------ scan
    def scan_extreme_funding(self, fundings: dict[str, float]) -> list[str]:
        """Simbolos com funding extremo ainda sem posicao aberta."""
        thr = self.params["FUNDING_THRESHOLD_TURBO"]
        cand = [(s, f) for s, f in fundings.items()
                if f > thr and s not in self.positions]
        cand.sort(key=lambda x: -x[1])
        free = config.MAX_TURBO_POSITIONS - len(self.positions)
        return [s for s, _ in cand[: max(free, 0)]]

    def scan_live(self, symbols=None) -> list[str]:
        """Versao live: puxa o funding real da testnet antes de varrer."""
        return self.scan_extreme_funding(core.get_funding_rates(symbols))

    # ------------------------------------------------------------------ step
    def step(self, capital: float, fundings: dict[str, float],
             signal: dict[str, float] | None = None) -> tuple[float, dict]:
        """Avanca um dia no sleeve Turbo. `signal` = funding observavel na
        decisao (D-1); `fundings` = o que e pago hoje."""
        signal = signal if signal is not None else fundings
        hold = int(self.params["TURBO_HOLD_DAYS"])
        stop = self.params["STOP_FUNDING_NEGATIVE"]
        pnl = 0.0
        fee_leg = config.FEE_RATE + config.SLIPPAGE

        # 1) novas entradas
        for sym in self.scan_extreme_funding(signal):
            if sym in fundings:
                self.positions[sym] = TurboPosition(sym, 0.0, 0, signal[sym])

        # 2) dimensiona: o sleeve inteiro e dividido entre as posicoes vivas
        if self.positions:
            per = min(capital / len(self.positions) * self.leverage,
                      config.CAPACITY_PER_SYMBOL)
            for pos in self.positions.values():
                if pos.notional == 0.0:                       # entrada de hoje
                    pnl -= per * fee_leg * 2                  # taxa de abertura
                pos.notional = per

        # 3) carrega funding e envelhece
        deployed = 0.0
        closed: list[str] = []
        for sym, pos in list(self.positions.items()):
            f = fundings.get(sym, 0.0)
            gain = pos.notional * f
            pnl += gain
            pos.accrued += gain
            pos.days_held += 1
            deployed += pos.notional / max(self.leverage, 1e-9)
            if pos.days_held >= hold or f < stop:
                pnl -= pos.notional * fee_leg * 2             # taxa de fechamento
                closed.append(sym)
        for sym in closed:
            del self.positions[sym]

        # 4) capital ocioso do sleeve rende T-Bill
        idle = max(capital - deployed, 0.0)
        pnl += idle * config.TBILL_DAILY
        return pnl, {"open": len(self.positions), "closed": closed, "idle": idle}
