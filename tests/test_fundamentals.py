"""Unit tests for fundamentals (Hardcore)."""
import pytest
import numpy as np
from fundamentals import quality_score, value_score, simple_dcf, pe_distribution_from_prices, _clamp


def test_clamp():
    assert _clamp(0.5) == 0.5
    assert _clamp(-1) == 0.0
    assert _clamp(2) == 1.0
    assert _clamp(float("nan")) == 0.5


def test_quality_score_basic():
    income = [{"revenue": 120}, {"revenue": 100}]
    balance = [{}]
    cashflow = [{}]
    rttm = {
        "grossProfitMarginTTM": 0.45,
        "netProfitMarginTTM": 0.18,
        "returnOnEquityTTM": 0.22,
        "currentRatioTTM": 1.8,
        "debtEquityRatioTTM": 0.4,
    }
    q = quality_score(income, balance, cashflow, rttm)
    assert 0 <= q["score"] <= 100
    assert "factors" in q
    assert q["rev_cagr"] is not None


def test_simple_dcf():
    cf = [{"freeCashFlow": 1e9}, {"freeCashFlow": 0.9e9}]
    d = simple_dcf(cf, shares_out=1e9, price=50.0, growth=0.08)
    assert d["intrinsic_value"] is not None
    assert "assumptions" in d
    assert d["assumptions"]["growth"] == 0.08


def test_pe_from_prices_empty():
    r = pe_distribution_from_prices([], [])
    assert r["median"] is None
    assert r["n"] == 0
