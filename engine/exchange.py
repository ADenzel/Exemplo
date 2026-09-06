"""Conexao ccxt com a Binance Testnet (sandbox)."""
from __future__ import annotations

import ccxt

import config

_SPOT = None
_PERP = None


def _build(default_type: str) -> ccxt.binance:
    ex = ccxt.binance({
        "apiKey": config.BINANCE_API_KEY,
        "secret": config.BINANCE_SECRET,
        "enableRateLimit": True,
        "options": {"defaultType": default_type, "adjustForTimeDifference": True},
    })
    ex.set_sandbox_mode(config.TESTNET)
    return ex


def spot() -> ccxt.binance:
    """Cliente spot testnet (testnet.binance.vision)."""
    global _SPOT
    if _SPOT is None:
        _SPOT = _build("spot")
    return _SPOT


def perp() -> ccxt.binance:
    """Cliente de futuros USDT-M testnet (testnet.binancefuture.com)."""
    global _PERP
    if _PERP is None:
        _PERP = _build("future")
    return _PERP


def reset() -> None:
    global _SPOT, _PERP
    _SPOT = _PERP = None


def fetch_usdt_balance(client: ccxt.binance | None = None) -> float:
    """Saldo livre em USDT. Levanta a excecao do ccxt em caso de falha."""
    client = client or spot()
    bal = client.fetch_balance()
    free = bal.get("free", {})
    return float(free.get("USDT", bal.get("USDT", {}).get("free", 0.0) or 0.0))
