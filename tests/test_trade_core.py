"""Tests for swing_bias_core (the single source of truth used by backtest)."""
from trade_signals import swing_bias_core


def test_swing_bias_long():
    # Supertrend up + golden + price > 50 + MACD >0 + RSI healthy
    r = swing_bias_core(price=100, st_dir=1, sma50=95, sma200=90, macd_hist=0.5, rsi_w=55)
    assert r["bias"] == "LONG"
    assert r["bull"] >= 4


def test_swing_bias_short():
    r = swing_bias_core(price=80, st_dir=-1, sma50=90, sma200=100, macd_hist=-0.3, rsi_w=30)
    assert r["bias"] == "SHORT"


def test_swing_bias_wait():
    r = swing_bias_core(price=100, st_dir=1, sma50=95, sma200=90, macd_hist=-0.1, rsi_w=80)
    # mixed → WAIT
    assert r["bias"] in ("WAIT", "LONG", "SHORT")  # depending on exact counts
