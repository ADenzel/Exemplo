"""MAIN LOOP - bot de arbitragem delta-neutra na Binance Testnet.

Loop de 60s: puxa funding real, roda Core/Turbo/Lotto, atualiza o dashboard
Rich e persiste equity/funding diarios. Rebalanceamento mensal dos sleeves.

    python main.py               # live testnet (precisa de .env)
    python main.py --sim         # modo simulado, sem rede (dados sinteticos)
    python main.py --interval 5  # muda o passo do loop
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

import pandas as pd
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

import config
from engine import core as core_mod
from engine.backtest import rebalance
from engine.core import CoreEngine
from engine.lotto import LottoEngine, detect_crash
from engine.market import generate
from engine.turbo import TurboEngine

console = Console()
EQUITY_CSV = config.DATA_DIR / "equity.csv"
FUNDING_CSV = config.DATA_DIR / "funding_history.csv"


class Bot:
    def __init__(self, sim: bool = False):
        self.sim = sim
        self.params = config.load_best_params() or {}
        self.p = config.validate(dict(config.as_dict(), **self.params))
        self.core = CoreEngine(params=self.p)
        self.turbo = TurboEngine(params=self.p)
        self.lotto = LottoEngine(params=self.p)
        self.sleeves = {
            "core": config.CAPITAL_INICIAL * self.p["ALOCATION_CORE"],
            "turbo": config.CAPITAL_INICIAL * self.p["ALOCATION_TURBO"],
            "lotto": config.CAPITAL_INICIAL * self.p["ALOCATION_LOTTO"],
        }
        self.equity = sum(self.sleeves.values())
        self.peak = self.equity
        self.ticks = 0
        self.last_saved_day = None
        self.last_rebalance_month = None
        self.last_info = {}
        self._sim_market = generate() if sim else None
        self._sim_i = 0

    # --------------------------------------------------------------- dados
    def fetch_fundings(self) -> dict[str, float]:
        if self.sim:
            m = self._sim_market
            i = self._sim_i % len(m)
            self._sim_i += 1
            return {s: float(m.funding[s].iloc[i]) for s in m.funding.columns}
        return core_mod.get_funding_rates(config.SYMBOLS)

    def fetch_crashes(self) -> list[str]:
        if self.sim:
            m = self._sim_market
            i = max(self._sim_i - 1, 0)
            return [s for s in m.prices.columns
                    if i >= config.LOTTO_CRASH_LOOKBACK
                    and m.prices[s].iloc[i] / m.prices[s].iloc[i - config.LOTTO_CRASH_LOOKBACK] - 1
                    <= config.LOTTO_CRASH_THRESHOLD]
        out = []
        for sym in config.SYMBOLS:
            try:
                if detect_crash(sym):
                    out.append(sym)
            except Exception:
                continue
        return out

    # ---------------------------------------------------------------- ciclo
    def tick(self) -> None:
        fundings = self.fetch_fundings()
        if not fundings:
            return
        crashes = self.fetch_crashes()

        pnl_c, info_c = self.core.step(self.sleeves["core"], fundings)
        pnl_t, info_t = self.turbo.step(self.sleeves["turbo"], fundings)
        pnl_l, info_l = self.lotto.step(self.sleeves["lotto"], crashes)

        self.sleeves["core"] += pnl_c
        self.sleeves["turbo"] += pnl_t
        self.sleeves["lotto"] += pnl_l
        self.equity = sum(self.sleeves.values())
        self.peak = max(self.peak, self.equity)
        self.ticks += 1
        self.last_info = {"core": info_c, "turbo": info_t, "lotto": info_l,
                          "pnl": (pnl_c, pnl_t, pnl_l), "fundings": fundings}

        now = datetime.now(timezone.utc)
        if self.last_rebalance_month != now.month:
            self.sleeves = rebalance(self.sleeves, self.equity)
            self.last_rebalance_month = now.month
        self.persist(now, fundings)

    @property
    def drawdown(self) -> float:
        return self.equity / self.peak - 1.0 if self.peak else 0.0

    def persist(self, now: datetime, fundings: dict) -> None:
        """Grava equity e funding uma vez por dia."""
        day = now.date()
        if self.last_saved_day == day:
            return
        self.last_saved_day = day
        pd.DataFrame([{
            "date": day, "equity": self.equity, "core": self.sleeves["core"],
            "turbo": self.sleeves["turbo"], "lotto": self.sleeves["lotto"],
            "drawdown": self.drawdown,
        }]).to_csv(EQUITY_CSV, mode="a", header=not EQUITY_CSV.exists(), index=False)
        pd.DataFrame([{"date": day, **fundings}]).to_csv(
            FUNDING_CSV, mode="a", header=not FUNDING_CSV.exists(), index=False)

    # ------------------------------------------------------------ dashboard
    def render(self) -> Layout:
        info = self.last_info
        pnl = info.get("pnl", (0, 0, 0))
        fundings = info.get("fundings", {})

        head = Table.grid(expand=True)
        head.add_column(justify="left")
        head.add_column(justify="right")
        ret = self.equity / config.CAPITAL_INICIAL - 1
        head.add_row(
            f"[bold]Equity[/] [bold green]${self.equity:,.2f}[/]  "
            f"([{'green' if ret >= 0 else 'red'}]{ret:+.2%}[/] vs inicial)",
            f"[dim]{'SIM' if self.sim else 'TESTNET'} | tick {self.ticks} | "
            f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z[/]",
        )

        t = Table(expand=True, header_style="bold cyan")
        for c in ("Sleeve", "Capital", "PnL ciclo", "Estado"):
            t.add_column(c)
        ci = info.get("core", {})
        t.add_row("CORE", f"${self.sleeves['core']:,.2f}", f"{pnl[0]:+,.2f}",
                  f"{ci.get('mode', '-')} {','.join(s.split('/')[0] for s in ci.get('symbols', []))}")
        ti = info.get("turbo", {})
        t.add_row("TURBO", f"${self.sleeves['turbo']:,.2f}", f"{pnl[1]:+,.2f}",
                  f"{ti.get('open', 0)} posicao(oes): "
                  f"{','.join(s.split('/')[0] for s in self.turbo.positions)}")
        li = info.get("lotto", {})
        t.add_row("LOTTO", f"${self.sleeves['lotto']:,.2f}", f"{pnl[2]:+,.2f}",
                  f"{li.get('trades', 0)} trade(s) | total {self.lotto.trades}")

        f_btc = fundings.get("BTC/USDT", 0.0)
        dd = self.drawdown
        risk = Table.grid(expand=True)
        risk.add_column(); risk.add_column(); risk.add_column()
        risk.add_row(
            f"Funding BTC/dia: [{'green' if f_btc >= 0 else 'red'}]{f_btc:+.4%}[/]",
            f"Drawdown: [{'green' if dd > config.MAX_DD_LIMIT else 'red'}]{dd:+.2%}[/] "
            f"(limite {config.MAX_DD_LIMIT:.0%})",
            f"Delta: [green]0.00 (neutro)[/]",
        )

        params = " | ".join(f"{k}={v}" for k, v in (self.params or self.p).items()
                            if k in config.PARAM_GRID)

        layout = Layout()
        layout.split_column(
            Layout(Panel(head, title="TURBO ARB BOT", border_style="green"), size=4),
            Layout(Panel(t, title="Sleeves", border_style="cyan"), size=9),
            Layout(Panel(risk, title="Risco", border_style="yellow"), size=3),
            Layout(Panel(params or "rode `python -m optimizer.grid_search`",
                         title="Melhores parametros", border_style="magenta"), size=3),
        )
        return layout

    def run(self, interval: int = 60) -> None:
        with Live(self.render(), console=console, refresh_per_second=4, screen=False) as live:
            while True:
                try:
                    self.tick()
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    console.log(f"[red]erro no ciclo:[/] {type(e).__name__}: {e}")
                live.update(self.render())
                time.sleep(interval)


def main() -> None:
    ap = argparse.ArgumentParser(description="Bot de arbitragem delta-neutra")
    ap.add_argument("--sim", action="store_true", help="modo simulado, sem rede")
    ap.add_argument("--interval", type=int, default=60, help="segundos por ciclo")
    ap.add_argument("--ticks", type=int, default=0, help="parar apos N ciclos (0 = infinito)")
    args = ap.parse_args()

    bot = Bot(sim=args.sim)
    if args.ticks:
        for _ in range(args.ticks):
            bot.tick()
        console.print(bot.render())
        return
    try:
        bot.run(args.interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Encerrado pelo usuario.[/]")


if __name__ == "__main__":
    main()
