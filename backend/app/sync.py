# -*- coding: utf-8 -*-
"""采集 / ETL 任务

设计原则：
  · 盘后全量（低频）为主，盘中快照（仅自选池，5 秒）为辅
  · 单源限流 1.5 秒/次，失败指数退避 —— 不轰炸、不用代理池
  · 所有任务记录水位线到 sync_log，支持断点续采
"""
import time
import traceback
from datetime import datetime, date, timedelta

from . import db, config, indicators
from .providers import market


def _is_trading_time():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return (9 * 60 + 25) <= t <= (15 * 60 + 5)


# ==================== 自选池快照（盘中） ====================
def sync_snapshot(symbols=None):
    """拉取自选池实时快照并入库"""
    if symbols is None:
        rows = db.query("SELECT DISTINCT symbol FROM watchlist LIMIT 200")
        symbols = [r["symbol"] for r in rows] or config.DEFAULT_POOL
    if not symbols:
        return 0

    total = 0
    # 分批，每批 50 只
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i + 50]
        try:
            res = market.quote(batch)
        except Exception as e:
            db.log_sync("snapshot", "error", "批次 %d 失败: %s" % (i, e))
            continue

        rows = []
        now = datetime.now()
        for q in res["data"]:
            if not q.get("price"):
                continue
            rows.append((
                q["symbol"], q.get("name"), q.get("price"), q.get("prev_close"),
                q.get("open"), q.get("high"), q.get("low"), q.get("change_pct"),
                q.get("volume"), q.get("amount"), q.get("turnover"),
                q.get("pe"), q.get("pb"), json_dumps_bid(q), now,
            ))
        if rows:
            db.executemany(
                """INSERT INTO quote_snapshot
                   (symbol,name,price,prev_close,open,high,low,change_pct,volume,
                    amount,turnover,pe,pb,bid,updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE
                     name=VALUES(name), price=VALUES(price), prev_close=VALUES(prev_close),
                     open=VALUES(open), high=VALUES(high), low=VALUES(low),
                     change_pct=VALUES(change_pct), volume=VALUES(volume),
                     amount=VALUES(amount), turnover=VALUES(turnover),
                     pe=VALUES(pe), pb=VALUES(pb), bid=VALUES(bid),
                     updated_at=VALUES(updated_at)""",
                rows)
            total += len(rows)

    db.log_sync("snapshot", "ok", "入库 %d 条" % total, rows_ok=total)
    return total


def json_dumps_bid(q):
    import json
    return json.dumps(q.get("bid") or [], ensure_ascii=False)[:250]


# ==================== 日线全量（盘后） ====================
def sync_daily_all(symbols=None, days=500):
    """全量日线同步（默认自选池 + 沪深300 等的简化版：仅自选池）"""
    if symbols is None:
        rows = db.query("SELECT DISTINCT symbol FROM watchlist LIMIT 300")
        symbols = [r["symbol"] for r in rows] or config.DEFAULT_POOL

    ok_cnt, fail_cnt = 0, 0
    for sym in symbols:
        try:
            _sync_one_daily(sym, days)
            ok_cnt += 1
        except Exception as e:
            fail_cnt += 1
            print("[sync_daily] %s 失败: %s" % (sym, e))
        time.sleep(0.3)

    db.log_sync("daily", "ok" if fail_cnt == 0 else "partial",
                "成功 %d / 失败 %d" % (ok_cnt, fail_cnt), rows_ok=ok_cnt,
                last_date=date.today())
    return ok_cnt


def _sync_one_daily(symbol, days=500):
    """拉单只日线并入库 + 更新证券基础信息"""
    res = market.kline(symbol, "daily", "qfq", days)
    bars = sorted(res["data"], key=lambda x: x["trade_date"])
    if not bars:
        return 0

    rows = []
    for b in bars:
        d = b["trade_date"].replace("-", "")
        if len(d) == 8:
            d = "%s-%s-%s" % (d[:4], d[4:6], d[6:])
        rows.append((symbol, d, b["open"], b["high"], b["low"], b["close"],
                     b.get("volume") or 0, b.get("amount") or 0))

    db.executemany(
        """INSERT INTO kline_daily
           (symbol,trade_date,open,high,low,close,volume,amount)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
           ON DUPLICATE KEY UPDATE
             open=VALUES(open), high=VALUES(high), low=VALUES(low),
             close=VALUES(close), volume=VALUES(volume), amount=VALUES(amount)""",
        rows)

    # 记录证券基础信息
    try:
        q = market.quote([symbol])["data"]
        if q:
            db.execute(
                """INSERT INTO security (symbol,name,market,sec_type,updated_at)
                   VALUES (%s,%s,%s,'stock',NOW())
                   ON DUPLICATE KEY UPDATE name=VALUES(name), updated_at=NOW()""",
                (symbol, q[0].get("name"), _guess_market(symbol)))
    except Exception:
        pass

    return len(rows)


def _guess_market(symbol):
    s = symbol.lower()
    if s.startswith("sh"):
        return "sh"
    if s.startswith("sz"):
        return "sz"
    if s.startswith("bj"):
        return "bj"
    return "sh" if s.startswith(("6", "5", "9")) else "sz"


# ==================== 指标预计算 ====================
def sync_indicators(symbols=None):
    """对库中已有日线的证券预计算指标"""
    if symbols is None:
        rows = db.query("SELECT DISTINCT symbol FROM kline_daily")
        symbols = [r["symbol"] for r in rows]

    ok_cnt = 0
    for sym in symbols:
        try:
            bars = db.query(
                "SELECT trade_date, open, high, low, close, volume "
                "FROM kline_daily WHERE symbol=%s ORDER BY trade_date", (sym,))
            if len(bars) < 60:
                continue
            for b in bars:
                b["symbol"] = sym
                b["trade_date"] = str(b["trade_date"])
            recs = indicators.compute_all(bars)
            rows_i = []
            for r in recs:
                rows_i.append((
                    sym, r["trade_date"], r["ma5"], r["ma10"], r["ma20"], r["ma60"],
                    r["dif"], r["dea"], r["macd"], r["k"], r["d"], r["j"],
                    r["rsi6"], r["rsi14"], r["boll_up"], r["boll_mid"],
                    r["boll_low"], r["vol_ma5"],
                ))
            db.executemany(
                """INSERT INTO indicator_daily
                   (symbol,trade_date,ma5,ma10,ma20,ma60,dif,dea,macd,k,d,j,
                    rsi6,rsi14,boll_up,boll_mid,boll_low,vol_ma5)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE
                     ma5=VALUES(ma5), ma10=VALUES(ma10), ma20=VALUES(ma20), ma60=VALUES(ma60),
                     dif=VALUES(dif), dea=VALUES(dea), macd=VALUES(macd),
                     k=VALUES(k), d=VALUES(d), j=VALUES(j),
                     rsi6=VALUES(rsi6), rsi14=VALUES(rsi14),
                     boll_up=VALUES(boll_up), boll_mid=VALUES(boll_mid),
                     boll_low=VALUES(boll_low), vol_ma5=VALUES(vol_ma5)""",
                rows_i)
            ok_cnt += 1
        except Exception as e:
            print("[sync_indicators] %s 失败: %s" % (sym, e))

    db.log_sync("indicator", "ok", "计算 %d 只" % ok_cnt, rows_ok=ok_cnt)
    return ok_cnt


# ==================== 调度器 ====================
def run_scheduler():
    """后台调度：盘后 ETL + 盘中快照"""
    from apscheduler.schedulers.background import BackgroundScheduler
    sch = BackgroundScheduler(timezone="Asia/Shanghai")

    # 盘后 ETL：15:30
    sch.add_job(sync_daily_all, "cron", hour=config.ETL_HOUR,
                minute=config.ETL_MINUTE, id="etl_daily")
    # 指标计算：15:50
    sch.add_job(sync_indicators, "cron", hour=15, minute=50, id="etl_indicator")
    # 盘中快照：每 5 秒
    sch.add_job(sync_snapshot, "interval", seconds=config.SNAPSHOT_INTERVAL,
                id="snapshot")
    sch.start()
    print("[scheduler] 已启动：盘后 ETL 15:30 / 指标 15:50 / 盘中快照 %ds" % config.SNAPSHOT_INTERVAL)
    return sch
