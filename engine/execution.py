"""Modelo de execucao: cada componente de custo com nome proprio.

Motivo de existir: `FEE_RATE` era um numero unico documentado de duas formas
contraditorias ("taker por perna" no config, "media ponderada das duas pernas"
no perfil realista) e aplicado UMA vez sobre o nocional cheio. Nas duas leituras
o custo saia subestimado, e nenhum teste conseguia pegar porque nao havia
componente separado para conferir.

Aqui o round-trip e a SOMA de itens nomeados, e um invariante verifica isso.

Tabela de referencia (Binance VIP0, sem desconto BNB):
    spot   maker 0.1000%   taker 0.1000%   <- spot NAO tem desconto de maker
    perp   maker 0.0200%   taker 0.0500%   <- a economia de maker esta aqui

Isto e um ponto que costuma ser assumido errado: postar limit no spot da
Binance nao reduz taxa nenhuma no nivel base. A economia de maker vem da perna
de perpetuo e de nao cruzar o spread.

Confira contra `fetch_trading_fees()` da sua conta antes de usar em producao --
o nivel VIP e o desconto de BNB mudam a tabela.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class FeeSchedule:
    """Taxas por perna, como fracao do nocional. Nada de media entre pernas."""
    spot_maker: float = 0.0010
    spot_taker: float = 0.0010
    perp_maker: float = 0.0002
    perp_taker: float = 0.0005

    @classmethod
    def with_bnb(cls) -> "FeeSchedule":
        """Desconto de BNB: 25% no spot, 10% em futuros."""
        return cls(spot_maker=0.00075, spot_taker=0.00075,
                   perp_maker=0.00018, perp_taker=0.00045)


@dataclass(frozen=True)
class ExecutionProfile:
    """Como as duas pernas sao executadas, e o que isso custa de verdade."""
    name: str
    fees: FeeSchedule
    spread_half: float = 0.0002       # meio spread pago ao cruzar o book
    perp_is_maker: bool = False
    spot_is_maker: bool = False
    maker_fill_prob: float = 1.0      # ordem passiva pode nao executar
    latency_adverse: float = 0.0      # custo do intervalo entre as duas pernas

    # ------------------------------------------------------------- por perna
    def __post_init__(self):
        # Passiva nas duas pernas deixa a posicao direcional quando so uma
        # executa. A estrategia proibe isso por construcao, entao o proprio
        # modelo de execucao proibe a combinacao.
        if self.spot_is_maker and self.perp_is_maker:
            raise ValueError(
                "passiva nas duas pernas quebra o hedge: se uma executa e a "
                "outra nao, a posicao vira direcional")
        if not 0.0 <= self.maker_fill_prob <= 1.0:
            raise ValueError("maker_fill_prob fora de [0, 1]")

    def perp_cost(self) -> float:
        if not self.perp_is_maker:
            return self.fees.perp_taker + self.spread_half
        p = self.maker_fill_prob
        # nao executou -> cruza como taker (a estrategia nao fica sem hedge)
        return (p * self.fees.perp_maker
                + (1 - p) * (self.fees.perp_taker + self.spread_half))

    def spot_cost(self) -> float:
        if not self.spot_is_maker:
            return self.fees.spot_taker + self.spread_half
        p = self.maker_fill_prob
        return (p * self.fees.spot_maker
                + (1 - p) * (self.fees.spot_taker + self.spread_half))

    # -------------------------------------------------------------- agregado
    def one_way(self) -> float:
        """Custo de montar (ou desmontar) a posicao hedgeada inteira.

        SOMA das duas pernas -- ambas carregam o nocional cheio -- mais o custo
        do intervalo em que a primeira perna ja executou e a segunda nao.
        """
        return self.spot_cost() + self.perp_cost() + self.latency_adverse

    def round_trip(self) -> float:
        return self.one_way() * 2

    def components(self) -> dict:
        return {
            "spot": self.spot_cost(),
            "perp": self.perp_cost(),
            "latencia": self.latency_adverse,
            "one_way": self.one_way(),
            "round_trip": self.round_trip(),
        }

    def as_config(self) -> dict:
        """Traduz para os campos que o engine consome.

        FEE_RATE passa a ser o custo one-way COMPLETO da posicao hedgeada e
        SLIPPAGE vai a zero: o spread ja esta dentro de cada perna. Manter os
        dois evita mudar a assinatura do engine, mas agora sem dupla contagem.
        """
        return {"FEE_RATE": self.one_way(), "SLIPPAGE": 0.0}


# ------------------------------------------------------------------- perfis

def all_taker(fees: FeeSchedule | None = None) -> ExecutionProfile:
    """Mercado nas duas pernas. Execucao garantida, custo maximo."""
    return ExecutionProfile("all_taker", fees or FeeSchedule())


def maker_perp(fees: FeeSchedule | None = None, fill_prob: float = 0.85,
               latency_adverse: float = 0.00005) -> ExecutionProfile:
    """Passiva no perpetuo, agressiva no spot assim que a perna passiva executa.

    E a forma correta de usar maker numa estrategia hedgeada: a perna passiva
    fica no book, e no instante em que executa a outra e enviada a mercado. O
    hedge nunca fica aberto por mais que a latencia -- que e cobrada em
    `latency_adverse` em vez de ser tratada como gratis.

    Nao se posta passiva nas DUAS pernas: se uma executa e a outra nao, a
    posicao vira direcional, que e exatamente o que a estrategia proibe.
    """
    return ExecutionProfile("maker_perp", fees or FeeSchedule(),
                            perp_is_maker=True, maker_fill_prob=fill_prob,
                            latency_adverse=latency_adverse)


def maker_perp_bnb(fill_prob: float = 0.85) -> ExecutionProfile:
    p = maker_perp(FeeSchedule.with_bnb(), fill_prob)
    return p


PROFILES = {
    "all_taker": all_taker,
    "maker_perp": maker_perp,
    "maker_perp_bnb": lambda: maker_perp_bnb(),
}


class use_profile:
    """Context manager que aplica um perfil de execucao ao config global."""

    def __init__(self, profile: ExecutionProfile):
        self.profile = profile

    def __enter__(self):
        import config
        self._saved = {k: getattr(config, k) for k in ("FEE_RATE", "SLIPPAGE")}
        for k, v in self.profile.as_config().items():
            setattr(config, k, v)
        return self.profile

    def __exit__(self, *exc):
        import config
        for k, v in self._saved.items():
            setattr(config, k, v)
        return False
