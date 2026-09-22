# -*- coding: utf-8 -*-
"""Market Hub — 行情数据服务 API"""
import json
import time
import threading
from datetime import datetime, date

from fastapi import FastAPI, Header, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os

from . import config, db, auth, indicators
from .providers import (market, fetch_new_stocks, fetch_company_profile,
                        fetch_stock_news, fetch_index_snapshot, fetch_rankings)

app = FastAPI(title="Market Hub", version="1.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- 快照内存缓存（防重复打数据源） ----------------
_snap_cache = {"ts": 0, "data": None}
_snap_lock = threading.Lock()
SNAP_TTL = 5


def get_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    info = auth.parse_token(authorization[7:])
    if not info:
        raise HTTPException(401, "登录已失效")
    return info


def _json_default(o):
    """统一处理数据库返回的特殊类型：
    - Decimal  -> float（价格、涨跌幅等）
    - datetime -> ISO8601 字符串
    - date     -> YYYY-MM-DD
    - 其他     -> str 兜底
    """
    from decimal import Decimal
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, datetime):
        return o.isoformat(sep=" ")
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, (bytes, bytearray)):
        return o.decode("utf-8", "replace")
    if isinstance(o, set):
        return list(o)
    return str(o)


def ok(data, **extra):
    """统一响应。用 json.dumps(default=...) 处理 Decimal/datetime，
    再交给 Response 返回（JSONResponse 不支持 default 参数）。"""
    body = {"code": 0, "data": data}
    body.update(extra)
    payload = json.dumps(body, default=_json_default, ensure_ascii=False)
    return Response(content=payload, media_type="application/json; charset=utf-8")


# ==================== 认证 ====================
class LoginReq(BaseModel):
    username: str
    password: str


@app.post("/api/v1/auth/login")
def login(req: LoginReq):
    rows = db.query("SELECT * FROM user WHERE username=%s", (req.username,))
    if not rows or not auth.verify_password(req.password, rows[0]["password"]):
        raise HTTPException(401, "用户名或密码错误")
    u = rows[0]
    db.execute("UPDATE user SET last_login=NOW() WHERE id=%s", (u["id"],))
    return ok({
        "token": auth.make_token(u["username"], u["role"], u["id"]),
        "username": u["username"], "role": u["role"],
    })


@app.get("/api/v1/auth/me")
def me(user=Depends(get_user)):
    return ok(user)


# ==================== 行情 ====================
@app.get("/api/v1/quote")
def quote(symbols: str = Query(..., description="逗号分隔，如 600000,000001"),
          user=Depends(get_user)):
    syms = [s.strip() for s in symbols.split(",") if s.strip()][:100]
    if not syms:
        raise HTTPException(400, "symbols 为空")
    try:
        res = market.quote(syms)
    except Exception as e:
        raise HTTPException(502, "行情获取失败: %s" % e)
    return ok(res["data"], source=res["source"], ts=datetime.now().isoformat())


@app.get("/api/v1/quote/{symbol}")
def quote_one(symbol: str, user=Depends(get_user)):
    """优先读数据库快照，兜底实时拉取"""
    rows = db.query("SELECT * FROM quote_snapshot WHERE symbol=%s", (symbol,))
    if rows:
        return ok(rows[0], cached=True)
    try:
        res = market.quote([symbol])
        return ok(res["data"][0] if res["data"] else None, source=res["source"])
    except Exception as e:
        raise HTTPException(502, "行情获取失败: %s" % e)


# 支持的 K 线周期
PERIODS = ("1min", "5min", "15min", "30min", "60min",
           "daily", "weekly", "monthly")


@app.get("/api/v1/kline")
def kline(symbol: str, period: str = "daily", adjust: str = "qfq",
          limit: int = Query(500, le=2000), user=Depends(get_user)):
    """K线。日线优先读库（前复权），分钟/周/月线实时拉取。"""
    if period not in PERIODS:
        raise HTTPException(400, "period 不支持: %s" % period)

    if period == "daily" and limit <= 2000:
        rows = db.query(
            "SELECT trade_date, open, high, low, close, volume, amount "
            "FROM kline_daily WHERE symbol=%s ORDER BY trade_date DESC LIMIT %s",
            (symbol, limit))
        if rows and len(rows) >= min(limit, 60):
            return ok(list(reversed(rows)), source="local_db")
    try:
        res = market.kline(symbol, period, adjust, limit)
    except Exception as e:
        raise HTTPException(502, "K线获取失败: %s" % e)
    return ok(res["data"], source=res["source"])


@app.get("/api/v1/minute")
def minute(symbol: str, user=Depends(get_user)):
    """当日分时线（1 分钟粒度，含均价线）。盘中每隔几秒拉一次即可。"""
    try:
        res = market.minute(symbol)
    except Exception as e:
        raise HTTPException(502, "分时获取失败: %s" % e)
    return ok(res["data"], source=res["source"],
              ts=datetime.now().isoformat())


@app.get("/api/v1/periods")
def periods(user=Depends(get_user)):
    """可用的 K 线周期列表（供前端渲染切换按钮）"""
    labels = {"1min": "1分", "5min": "5分", "15min": "15分",
              "30min": "30分", "60min": "60分",
              "daily": "日K", "weekly": "周K", "monthly": "月K"}
    return ok([{"value": p, "label": labels[p]} for p in PERIODS])


@app.get("/api/v1/indicator")
def indicator(symbol: str, limit: int = Query(300, le=2000), user=Depends(get_user)):
    rows = db.query(
        "SELECT * FROM indicator_daily WHERE symbol=%s ORDER BY trade_date DESC LIMIT %s",
        (symbol, limit))
    if rows:
        return ok(list(reversed(rows)), source="local_db")
    # 兜底：实时算
    try:
        res = market.kline(symbol, "daily", "qfq", max(limit, 120))
        bars = sorted(res["data"], key=lambda x: x["trade_date"])
        for b in bars:
            b["symbol"] = symbol
        return ok(indicators.compute_all(bars)[-limit:], source="computed")
    except Exception as e:
        raise HTTPException(502, "指标获取失败: %s" % e)


# ---------------- 新上股票（未来 N 天内 A 股上市） ----------------
_ipo_cache = {"ts": 0, "data": None, "err": None}
_ipo_lock = threading.Lock()
IPO_TTL = 1800  # 30 分钟缓存，新股日历变动很慢，也避免打爆数据源


@app.get("/api/v1/ipo/upcoming")
def ipo_upcoming(days: int = Query(31, ge=1, le=90), refresh: int = 0,
                 user=Depends(get_user)):
    """未来 days 天内将在 A 股正式上市的股票列表"""
    now = time.time()
    with _ipo_lock:
        if (not refresh and _ipo_cache["data"] is not None
                and now - _ipo_cache["ts"] < IPO_TTL):
            return ok(_ipo_cache["data"], source="cache",
                      cached_at=int(_ipo_cache["ts"]))
    try:
        rows = fetch_new_stocks(days)
        with _ipo_lock:
            _ipo_cache.update(ts=now, data=rows, err=None)
        return ok(rows, source="eastmoney")
    except Exception as e:
        # 失败时：有旧缓存就用旧的，否则返回空列表 + 错误说明（前端友好展示）
        msg = str(e)[:160]
        with _ipo_lock:
            stale = _ipo_cache["data"]
            _ipo_cache["err"] = msg
        if stale is not None:
            return ok(stale, source="stale_cache", err=msg)
        return ok([], source="none", err=msg)


@app.get("/api/v1/company/{symbol}")
def company_profile(symbol: str, user=Depends(get_user)):
    """公司档案：行业、公司性质、盈利情况、是否龙头等"""
    sym = _norm_symbol(symbol)
    if not sym.isdigit():
        raise HTTPException(400, "股票代码格式错误")
    try:
        return ok(fetch_company_profile(sym), source="eastmoney")
    except Exception as e:
        raise HTTPException(502, "公司信息获取失败: %s" % e)


@app.get("/api/v1/news/{symbol}")
def stock_news(symbol: str, refresh: int = 0, user=Depends(get_user)):
    """个股新闻 + 公告（东财双源，15 分钟缓存/股）"""
    sym = _norm_symbol(symbol)
    if not sym.isdigit():
        raise HTTPException(400, "股票代码格式错误")
    try:
        return ok(fetch_stock_news(sym, refresh=refresh), source="eastmoney")
    except Exception as e:
        raise HTTPException(502, "新闻获取失败: %s" % e)


# ==================== 行情中心 ====================
@app.get("/api/v1/market/index")
def market_index(user=Depends(get_user)):
    """大盘指数条：上证指数 / 深证成指 / 创业板指 / 科创50"""
    try:
        return ok(fetch_index_snapshot(), source="eastmoney")
    except Exception as e:
        raise HTTPException(502, "指数获取失败: %s" % e)


@app.get("/api/v1/market/rank")
def market_rank(type: str = Query("pct", description="pct=涨跌幅 vol=成交量 amt=成交额"),
                size: int = Query(10, ge=3, le=30), user=Depends(get_user)):
    """A 股榜单（30 秒缓存）"""
    fid = {"pct": "f3", "vol": "f5", "amt": "f6"}.get(type)
    if not fid:
        raise HTTPException(400, "type 仅支持 pct/vol/amt")
    try:
        return ok(fetch_rankings(fid, size), source="eastmoney")
    except Exception as e:
        raise HTTPException(502, "榜单获取失败: %s" % e)


# ==================== 自选池 ====================
class PoolAdd(BaseModel):
    symbols: list


@app.get("/api/v1/pool")
def pool_list(user=Depends(get_user)):
    """自选池：名称优先取快照（最新），兜底取 security 基础表。"""
    rows = db.query(
        "SELECT w.symbol, w.grp, w.sort_no, "
        "       COALESCE(q.name, s.name) AS name, "
        "       q.price, q.change_pct, q.updated_at "
        "FROM watchlist w "
        "LEFT JOIN quote_snapshot q ON q.symbol = w.symbol "
        "LEFT JOIN security s ON s.symbol = w.symbol "
        "WHERE w.user_id=%s ORDER BY w.sort_no, w.id", (user["uid"],))
    return ok(rows)


@app.post("/api/v1/pool")
def pool_add(req: PoolAdd, user=Depends(get_user)):
    n = 0
    for s in req.symbols:
        s = s.strip()
        if not s:
            continue
        try:
            db.execute(
                "INSERT IGNORE INTO watchlist (user_id, symbol, created_at) VALUES (%s,%s,NOW())",
                (user["uid"], s))
            n += 1
        except Exception:
            pass
    return ok({"added": n})


@app.delete("/api/v1/pool/{symbol}")
def pool_del(symbol: str, user=Depends(get_user)):
    n = db.execute("DELETE FROM watchlist WHERE user_id=%s AND symbol=%s",
                   (user["uid"], symbol))
    return ok({"deleted": n})


# ==================== 持仓 ====================
class PositionAdd(BaseModel):
    symbol: str
    buy_date: str          # YYYY-MM-DD
    buy_price: float
    qty: int = 100


class SellReq(BaseModel):
    symbol: str
    sell_price: float
    sell_date: str         # YYYY-MM-DD


def _norm_symbol(s: str) -> str:
    """去掉 sh/sz/bj 前缀，统一存纯数字代码（与 watchlist 一致）"""
    s = (s or "").strip().lower()
    for pfx in ("sh", "sz", "bj"):
        if s.startswith(pfx):
            return s[len(pfx):]
    return s


@app.get("/api/v1/portfolio")
def portfolio_list(user=Depends(get_user)):
    """持仓总览：按股票聚合（平均成本）+ 实时行情 -> 浮动盈亏 + 已实现盈亏汇总"""
    uid = user["uid"]
    rows = db.query(
        "SELECT * FROM position WHERE user_id=%s AND status=1 ORDER BY buy_date, id",
        (uid,))
    by_sym = {}
    for r in rows:
        by_sym.setdefault(r["symbol"], []).append(r)

    qmap = {}
    src = None
    if by_sym:
        try:
            res = market.quote(list(by_sym.keys()))
            src = res["source"]
            qmap = {q["symbol"]: q for q in res["data"]}
        except Exception:
            qmap = {}

    open_list = []
    for sym, lots in by_sym.items():
        total_qty = sum(int(l["qty"]) for l in lots)
        total_cost = sum(float(l["buy_price"]) * int(l["qty"]) for l in lots)
        avg = total_cost / total_qty if total_qty else 0.0
        q = qmap.get(sym) or {}
        price = q.get("price")
        mv = price * total_qty if price else None
        upnl = (price - avg) * total_qty if price else None
        upct = ((price - avg) / avg * 100) if (price and avg) else None
        open_list.append({
            "symbol": sym,
            "name": q.get("name") or lots[0].get("name") or sym,
            "lots": [{"id": l["id"], "buy_date": l["buy_date"],
                      "buy_price": float(l["buy_price"]), "qty": l["qty"]}
                     for l in lots],
            "first_buy": lots[0]["buy_date"],
            "total_qty": total_qty,
            "avg_cost": round(avg, 3),
            "total_cost": round(total_cost, 2),
            "price": price,
            "change_pct": q.get("change_pct"),
            "market_value": round(mv, 2) if mv is not None else None,
            "unrealized_pnl": round(upnl, 2) if upnl is not None else None,
            "unrealized_pct": round(upct, 2) if upct is not None else None,
        })

    sold_rows = db.query(
        "SELECT * FROM position WHERE user_id=%s AND status=0 ORDER BY sell_date DESC, sell_at DESC",
        (uid,))
    realized = sum((float(r["sell_price"]) - float(r["buy_price"])) * int(r["qty"])
                   for r in sold_rows
                   if r["sell_price"] is not None)

    summary = {
        "market_value": round(sum(x["market_value"] for x in open_list
                                  if x["market_value"] is not None), 2),
        "total_cost": round(sum(x["total_cost"] for x in open_list), 2),
        "unrealized_pnl": round(sum(x["unrealized_pnl"] for x in open_list
                                    if x["unrealized_pnl"] is not None), 2),
        "realized_pnl": round(realized, 2),
        "count": len(open_list),
    }
    summary["total_pnl"] = round(summary["unrealized_pnl"] + summary["realized_pnl"], 2)
    return ok({"open": open_list, "summary": summary}, source=src)


@app.get("/api/v1/portfolio/closed")
def portfolio_closed(user=Depends(get_user)):
    """已清仓记录：按 (symbol, sell_date) 聚合，含每轮盈亏"""
    rows = db.query(
        "SELECT * FROM position WHERE user_id=%s AND status=0 "
        "ORDER BY sell_date DESC, sell_at DESC", (user["uid"],))
    groups = {}
    order = []
    for r in rows:
        key = (r["symbol"], str(r["sell_date"]))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    out = []
    for key in order:
        lots = groups[key]
        sym = key[0]
        total_qty = sum(int(l["qty"]) for l in lots)
        cost = sum(float(l["buy_price"]) * int(l["qty"]) for l in lots)
        pnl = sum((float(lots[0]["sell_price"]) - float(l["buy_price"])) * int(l["qty"])
                  for l in lots)
        out.append({
            "symbol": sym,
            "name": lots[0].get("name") or sym,
            "buy_date": min(str(l["buy_date"]) for l in lots),
            "sell_date": key[1],
            "sell_price": float(lots[0]["sell_price"]),
            "avg_cost": round(cost / total_qty, 3) if total_qty else 0,
            "total_qty": total_qty,
            "cost": round(cost, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl / cost * 100, 2) if cost else None,
            "lots": [{"buy_date": l["buy_date"], "buy_price": float(l["buy_price"]),
                      "qty": l["qty"]} for l in lots],
        })
    return ok(out)


@app.post("/api/v1/portfolio")
def portfolio_add(req: PositionAdd, user=Depends(get_user)):
    sym = _norm_symbol(req.symbol)
    if not sym.isdigit():
        raise HTTPException(400, "股票代码格式错误")
    if req.qty <= 0 or req.buy_price <= 0:
        raise HTTPException(400, "价格/数量必须大于 0")
    name = ""
    try:
        q = market.quote([sym])["data"]
        if q:
            name = q[0].get("name") or ""
    except Exception:
        pass
    n = db.execute(
        "INSERT INTO position (user_id, symbol, name, buy_date, buy_price, qty, status, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,1,NOW())",
        (user["uid"], sym, name, req.buy_date, req.buy_price, req.qty))
    return ok({"added": n, "symbol": sym, "name": name})


@app.delete("/api/v1/portfolio/symbol/{symbol}")
def portfolio_del_symbol(symbol: str, user=Depends(get_user)):
    """删除某只股票的【全部持仓记录】（含已卖出的历史），不写卖出价，直接从账本移除。
    注意：本路由必须注册在 /portfolio/{pid} 之前，否则 symbol 会被当作 pid 解析。"""
    sym = _norm_symbol(symbol)
    lots = db.query(
        "SELECT id FROM position WHERE user_id=%s AND symbol=%s", (user["uid"], sym))
    if not lots:
        raise HTTPException(404, "没有该股票的持仓记录")
    n = db.execute("DELETE FROM position WHERE user_id=%s AND symbol=%s", (user["uid"], sym))
    return ok({"deleted": n, "symbol": sym})


@app.delete("/api/v1/portfolio/{pid}")
def portfolio_del(pid: int, user=Depends(get_user)):
    n = db.execute("DELETE FROM position WHERE id=%s AND user_id=%s AND status=1",
                   (pid, user["uid"]))
    if not n:
        raise HTTPException(404, "持仓记录不存在或已卖出")
    return ok({"deleted": n})


@app.post("/api/v1/portfolio/sell")
def portfolio_sell(req: SellReq, user=Depends(get_user)):
    """卖出某只股票的全部持仓（整股清仓），按填写价格与日期记账"""
    sym = _norm_symbol(req.symbol)
    lots = db.query(
        "SELECT * FROM position WHERE user_id=%s AND symbol=%s AND status=1",
        (user["uid"], sym))
    if not lots:
        raise HTTPException(404, "没有该股票的持仓")
    n = db.execute(
        "UPDATE position SET status=0, sell_price=%s, sell_date=%s, sell_at=NOW() "
        "WHERE user_id=%s AND symbol=%s AND status=1",
        (req.sell_price, req.sell_date, user["uid"], sym))
    cost = sum(float(l["buy_price"]) * int(l["qty"]) for l in lots)
    qty = sum(int(l["qty"]) for l in lots)
    pnl = (req.sell_price - cost / qty) * qty if qty else 0
    return ok({"sold_lots": n, "qty": qty, "cost": round(cost, 2), "pnl": round(pnl, 2)})


# ==================== 板块（东财行业板块） ====================
@app.get("/api/v1/sector")
def sector(user=Depends(get_user)):
    rows = db.query(
        "SELECT * FROM sector_daily WHERE trade_date=(SELECT MAX(trade_date) FROM sector_daily) "
        "ORDER BY change_pct DESC LIMIT 100")
    return ok(rows)


# ==================== 数据管理 ====================
@app.get("/api/v1/admin/sync-status")
def sync_status(user=Depends(get_user)):
    rows = db.query("SELECT * FROM sync_log ORDER BY last_run DESC")
    counts = db.query(
        "SELECT (SELECT COUNT(*) FROM security) AS sec, "
        "(SELECT COUNT(*) FROM kline_daily) AS kline, "
        "(SELECT COUNT(*) FROM indicator_daily) AS ind, "
        "(SELECT COUNT(*) FROM quote_snapshot) AS snap")
    return ok({"tasks": rows, "counts": counts[0] if counts else {}})


@app.post("/api/v1/admin/sync/{task}")
def trigger_sync(task: str, user=Depends(get_user)):
    if user.get("role") != "admin":
        raise HTTPException(403, "需要管理员权限")
    if task not in ("daily", "snapshot", "indicator"):
        raise HTTPException(400, "未知任务")
    t = threading.Thread(target=_run_sync, args=(task,), daemon=True)
    t.start()
    return ok({"started": task})


def _run_sync(task):
    from . import sync
    try:
        if task == "daily":
            sync.sync_daily_all()
        elif task == "snapshot":
            sync.sync_snapshot()
        elif task == "indicator":
            sync.sync_indicators()
    except Exception as e:
        db.log_sync(task, "error", str(e))


@app.get("/api/v1/health")
def health():
    try:
        db.query("SELECT 1")
        return {"status": "ok", "db": True, "ts": datetime.now().isoformat()}
    except Exception as e:
        return JSONResponse({"status": "degraded", "db": False, "err": str(e)}, 503)


# ==================== 静态前端 ====================
_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.isdir(_dist):
    # 1) 先挂静态资源目录（assets 等），让 /assets/* 命中真实文件
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    # 2) 根路径返回 index.html
    @app.get("/")
    def _index():
        return FileResponse(os.path.join(_dist, "index.html"))

    # 3) SPA 路由回退：所有未匹配的非 API 路径都回退到 index.html
    #    否则用户刷新 /detail、/login 等前端路由会 404
    @app.get("/{full_path:path}")
    def _spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "接口不存在")
        candidate = os.path.join(_dist, full_path)
        # 防目录穿越
        if os.path.isfile(candidate) and os.path.abspath(candidate).startswith(os.path.abspath(_dist)):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_dist, "index.html"))


@app.on_event("startup")
def _startup():
    db.init_schema()
    pwd = auth.ensure_admin()
    if pwd:
        print("[init] 已创建管理员账号 admin / %s" % pwd)
    else:
        # 账号已存在时，兜底补种自选池（幂等）
        auth._seed_watchlist()
    print("[init] Market Hub 启动完成")
