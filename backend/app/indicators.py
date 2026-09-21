# -*- coding: utf-8 -*-
"""指标计算层（纯 Python，不依赖 numpy/pandas，便于部署）"""
from decimal import Decimal


def _f(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def sma(values, n):
    """简单移动平均，返回与输入等长、前 n-1 位为 None"""
    out, s = [], 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        out.append(round(s / n, 3) if i >= n - 1 else None)
    return out


def ema(values, n):
    out, k, prev = [], 2.0 / (n + 1), None
    for v in values:
        prev = v if prev is None else v * k + prev * (1 - k)
        out.append(prev)
    return out


def macd(closes, fast=12, slow=26, signal=9):
    """返回 (dif, dea, macd柱)"""
    ef, es = ema(closes, fast), ema(closes, slow)
    dif = [round(a - b, 4) for a, b in zip(ef, es)]
    dea = [round(v, 4) for v in ema(dif, signal)]
    bar = [round((a - b) * 2, 4) for a, b in zip(dif, dea)]
    return dif, dea, bar


def kdj(highs, lows, closes, n=9, m1=3, m2=3):
    """返回 (K, D, J)"""
    k_list, d_list, j_list = [], [], []
    k, d = 50.0, 50.0
    for i in range(len(closes)):
        if i < n - 1:
            k_list.append(None); d_list.append(None); j_list.append(None)
            continue
        hh = max(highs[i - n + 1:i + 1])
        ll = min(lows[i - n + 1:i + 1])
        rsv = 50.0 if hh == ll else (closes[i] - ll) / (hh - ll) * 100
        k = (m1 - 1) / m1 * k + 1.0 / m1 * rsv
        d = (m2 - 1) / m2 * d + 1.0 / m2 * k
        k_list.append(round(k, 3))
        d_list.append(round(d, 3))
        j_list.append(round(3 * k - 2 * d, 3))
    return k_list, d_list, j_list


def rsi(closes, n=14):
    out = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains, losses = 0.0, 0.0
    for i in range(1, n + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0)
        losses += max(-ch, 0)
    ag, al = gains / n, losses / n
    out[n] = round(100.0 if al == 0 else 100 - 100 / (1 + ag / al), 3)
    for i in range(n + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (n - 1) + max(ch, 0)) / n
        al = (al * (n - 1) + max(-ch, 0)) / n
        out[i] = round(100.0 if al == 0 else 100 - 100 / (1 + ag / al), 3)
    return out


def boll(closes, n=20, k=2):
    """返回 (上轨, 中轨, 下轨)"""
    mid = sma(closes, n)
    up, low = [], []
    for i in range(len(closes)):
        if mid[i] is None:
            up.append(None); low.append(None); continue
        seg = closes[i - n + 1:i + 1]
        mean = sum(seg) / n
        var = sum((x - mean) ** 2 for x in seg) / n
        sd = var ** 0.5
        up.append(round(mid[i] + k * sd, 3))
        low.append(round(mid[i] - k * sd, 3))
    return up, mid, low


def compute_all(bars):
    """bars: [{trade_date, open, high, low, close, volume, ...}] 升序
    返回 [{trade_date, ma5, ..., vol_ma5}]"""
    if not bars:
        return []
    closes = [float(b["close"]) for b in bars]
    highs = [float(b["high"]) for b in bars]
    lows = [float(b["low"]) for b in bars]
    vols = [int(b.get("volume") or 0) for b in bars]

    ma5, ma10, ma20, ma60 = sma(closes, 5), sma(closes, 10), sma(closes, 20), sma(closes, 60)
    dif, dea, bar = macd(closes)
    kk, dd, jj = kdj(highs, lows, closes)
    r6, r14 = rsi(closes, 6), rsi(closes, 14)
    bu, bm, bl = boll(closes)
    vma5 = sma([float(v) for v in vols], 5)

    out = []
    for i, b in enumerate(bars):
        out.append({
            "symbol": b.get("symbol"),
            "trade_date": b["trade_date"],
            "ma5": ma5[i], "ma10": ma10[i], "ma20": ma20[i], "ma60": ma60[i],
            "dif": dif[i], "dea": dea[i], "macd": bar[i],
            "k": kk[i], "d": dd[i], "j": jj[i],
            "rsi6": r6[i], "rsi14": r14[i],
            "boll_up": bu[i], "boll_mid": bm[i], "boll_low": bl[i],
            "vol_ma5": int(vma5[i]) if vma5[i] is not None else None,
        })
    return out
