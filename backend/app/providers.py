# -*- coding: utf-8 -*-
"""数据源适配层（统一 Provider 协议）

关键设计：
  1. 所有外部请求统一走 _get()，在这里处理 IPv4 强制、UA 伪装、限流
  2. 数据源互换：东方财富 / 腾讯，任一可用即可切换
  3. 不做代理池、不做并发轰炸 —— 个人研究用途，低频合规访问
"""
import json
import time
import socket
import threading
import requests
from requests.adapters import HTTPAdapter
from . import config

# ---------- 强制 IPv4：本机 IPv6 无出口，不处理会全部超时 ----------
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


if config.FORCE_IPV4:
    socket.getaddrinfo = _ipv4_only_getaddrinfo

# ---------- 限流器：每个域名独立令牌间隔 ----------
_last_call = {}
_rate_lock = threading.Lock()


def _throttle(key):
    with _rate_lock:
        now = time.time()
        prev = _last_call.get(key, 0)
        wait = config.MIN_REQUEST_INTERVAL - (now - prev)
        if wait > 0:
            time.sleep(wait)
        _last_call[key] = time.time()


_session = requests.Session()
_session.mount("https://", HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=2))
_session.mount("http://", HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=2))


def _get(url, headers, key, timeout=None):
    """统一出口：限流 + IPv4 + UA 伪装"""
    _throttle(key)
    r = _session.get(url, headers=headers, timeout=timeout or config.REQUEST_TIMEOUT)
    r.raise_for_status()
    return r


def _num(v):
    try:
        if v is None or v == "" or v == "-":
            return None
        return float(v)
    except Exception:
        return None


def _avg_price(amount, volume):
    """均价 = 成交额(元) / 成交量(手) / 100。任一缺失或为 0 时返回 None。"""
    a = _num(amount)
    v = _num(volume)
    if a is None or v is None or v == 0:
        return None
    try:
        return round(a / v / 100, 3)
    except Exception:
        return None


# 快照里所有需要保证是「数字或 None」的字段
# 东财在停牌/无数据时会把数值字段返回字符串 "-"，直接写库会
# 触发 pymysql DataError(1366 Incorrect decimal value)，必须统一清洗
_NUMERIC_FIELDS = (
    "price", "prev_close", "open", "high", "low", "change_pct", "change_amt",
    "volume", "amount", "turnover", "amplitude", "volume_ratio", "speed",
    "pe", "pe_dyn", "pe_static", "pe_ttm", "pb",
    "total_mcap", "float_mcap", "total_shares", "float_shares",
    "outer", "inner", "avg_price", "limit_up", "limit_down",
)


def _enrich(row):
    """补齐派生字段：股本（股）= 市值(元) / 现价。统一市值单位为「元」。

    同时把所有数值字段规范成 float 或 None —— 防止上游返回 "-" 之类的
    非数字字符串污染下游（DB DECIMAL 列写入会直接报 DataError）。
    """
    # 1) 统一数值化
    for k in _NUMERIC_FIELDS:
        if k in row:
            row[k] = _num(row[k])

    # 2) 市值单位统一为「元」（腾讯给「亿」，东财给「元」）
    tm = row.get("total_mcap")
    fm = row.get("float_mcap")
    if tm is not None:
        row["total_mcap"] = tm * 1e8 if tm < 1e7 else tm
    if fm is not None:
        row["float_mcap"] = fm * 1e8 if fm < 1e7 else fm

    # 3) 派生股本 = 市值 / 现价
    price = row.get("price")
    if price and row.get("total_mcap"):
        row["total_shares"] = row["total_mcap"] / price
    if price and row.get("float_mcap"):
        row["float_shares"] = row["float_mcap"] / price
    return row


# ============================================================
#  Provider: 东方财富（主源，字段最全）
# ============================================================
class EastmoneyProvider:
    name = "eastmoney"
    _host = "push2.eastmoney.com"

    # 东财 secid 前缀：0=深市 1=沪市 116=港股 105/106/107=美股
    @staticmethod
    def secid(symbol: str) -> str:
        s = symbol.strip().lower()
        if s.startswith(("sh", "sz", "bj")):
            code, mk = s[2:], s[:2]
        else:
            code = s
            mk = "sh" if code.startswith(("6", "5", "9")) else "sz"
        pfx = {"sh": "1", "sz": "0", "bj": "0"}[mk]
        return "%s.%s" % (pfx, code)

    def quote(self, symbols):
        """批量实时快照

        f12(代码) f14(名称) f2(现价) f3(涨跌幅) f4(涨跌额) f5(成交量手)
            f6(成交额元) f7(振幅) f8(换手) f9(市盈动) f10(量比) f15(最高)
            f16(最低) f17(今开) f18(昨收) f20(总市值元) f21(流通市值元)
            f22(涨速) f23(市净率) f114(市盈静) f115(市盈TTM)
        """
        secids = ",".join(self.secid(s) for s in symbols)
        url = ("https://%s/api/qt/ulist.np/get?fltt=2&invt=2&secids=%s"
               "&fields=f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f15,f16,f17,f18,"
               "f20,f21,f22,f23,f114,f115"
               % (self._host, secids))
        r = _get(url, config.HEADERS_EM, self._host)
        data = r.json().get("data") or {}
        out = []
        for d in (data.get("diff") or []):
            code = str(d.get("f12", ""))
            out.append(_enrich({
                "symbol": code,
                "name": d.get("f14"),
                "price": d.get("f2"),
                "change_pct": d.get("f3"),
                "change_amt": d.get("f4"),
                "volume": d.get("f5"),
                "amount": d.get("f6"),
                "amplitude": d.get("f7"),
                "turnover": d.get("f8"),
                "pe": d.get("f9"),
                "pe_dyn": d.get("f9"),
                "pe_static": d.get("f114"),
                "pe_ttm": d.get("f115"),
                "volume_ratio": d.get("f10"),
                "speed": d.get("f22"),
                "high": d.get("f15"),
                "low": d.get("f16"),
                "open": d.get("f17"),
                "prev_close": d.get("f18"),
                "total_mcap": d.get("f20"),
                "float_mcap": d.get("f21"),
                "pb": d.get("f23"),
                "outer": None, "inner": None,
                # 东财快照无均价字段，用 成交额 / (成交量手 × 100) 反推
                "avg_price": _avg_price(d.get("f6"), d.get("f5")),
                "limit_up": None, "limit_down": None,
            }))
        return out

    def quote_detail(self, symbol):
        """单只详细快照（含五档）"""
        url = ("https://%s/api/qt/stock/get?invt=2&fltt=2&secid=%s"
               "&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f168,f169,f170,"
               "f31,f32,f33,f34,f35,f36,f37,f38,f39,f40,f19,f20,f17,f18,f15,f16"
               % (self._host, self.secid(symbol)))
        r = _get(url, config.HEADERS_EM, self._host)
        d = r.json().get("data") or {}
        if not d:
            return None
        return {
            "symbol": str(d.get("f57", symbol)),
            "name": d.get("f58"),
            "price": d.get("f43"),
            "high": d.get("f44"),
            "low": d.get("f45"),
            "open": d.get("f46"),
            "volume": d.get("f47"),
            "amount": d.get("f48"),
            "prev_close": d.get("f60"),
            "turnover": d.get("f168"),
            "change_pct": d.get("f170"),
            "change_amt": d.get("f169"),
            "bid": [{"price": d.get("f19"), "vol": d.get("f20")}],
            "ask": [{"price": d.get("f39"), "vol": d.get("f40")}],
        }

    def kline(self, symbol, period="daily", adjust="qfq", limit=500):
        """K线。period: 1min/5min/15min/30min/60min/daily/weekly/monthly"""
        klt = {"1min": 1, "5min": 5, "15min": 15, "30min": 30,
               "60min": 60, "daily": 101, "weekly": 102, "monthly": 103}[period]
        fqt = {"none": 0, "qfq": 1, "hfq": 2}[adjust]
        url = ("https://%s/api/qt/stock/kline/get?secid=%s&klt=%d&fqt=%d"
               "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57"
               "&end=20500101&lmt=%d"
               % (self._host, self.secid(symbol), klt, fqt, limit))
        r = _get(url, config.HEADERS_EM, self._host)
        d = r.json().get("data") or {}
        bars = []
        for line in (d.get("klines") or []):
            p = line.split(",")
            bars.append({
                "trade_date": p[0],
                "open": float(p[1]),
                "close": float(p[2]),
                "high": float(p[3]),
                "low": float(p[4]),
                "volume": int(float(p[5])),
                "amount": float(p[6]) if len(p) > 6 else 0,
            })
        return bars

    def minute(self, symbol):
        """东财分时（备用实现）。主用腾讯，此处返回 None 走降级。"""
        return None


# ============================================================
#  Provider: 腾讯行情（备用源，速度快）
# ============================================================
class TencentProvider:
    name = "tencent"
    _host = "qt.gtimg.cn"
    # 分钟线（mkline）走 ifzq.gtimg.cn；注意 web.ifzq / web2 / web3 均无法解析
    _mhost = "ifzq.gtimg.cn"
    # 分时（当日）与日/周/月 K 线走 web.ifzq.gtimg.cn
    _khost = "web.ifzq.gtimg.cn"

    @staticmethod
    def _code(symbol: str) -> str:
        s = symbol.strip().lower()
        if s.startswith(("sh", "sz", "bj")):
            return s
        return ("sh" if s.startswith(("6", "5", "9")) else "sz") + s

    def quote(self, symbols):
        codes = ",".join(self._code(s) for s in symbols)
        url = "https://%s/q=%s" % (self._host, codes)
        r = _get(url, config.HEADERS_TX, self._host)
        out = []
        for line in r.text.split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            body = line.split("=", 1)[1].strip('"')
            p = body.split("~")
            if len(p) < 40:
                continue
            def f(i):
                return _num(p[i]) if len(p) > i else None
            amt = f(37)
            out.append(_enrich({
                "symbol": p[2],
                "name": p[1],
                "price": f(3),
                "prev_close": f(4),
                "open": f(5),
                "volume": f(6),
                "outer": f(7),               # 外盘（手）
                "inner": f(8),               # 内盘（手）
                "high": f(33),
                "low": f(34),
                "change_pct": f(32),
                "change_amt": f(31),
                "amount": amt * 1e4 if amt is not None else None,   # 万 -> 元
                "turnover": f(38),
                "pe": f(39),                 # TTM
                "pe_ttm": f(39),
                "pe_dyn": f(52) if len(p) > 52 else None,
                "pe_static": f(53) if len(p) > 53 else None,
                "amplitude": f(43),
                "float_mcap": f(44),         # 亿
                "total_mcap": f(45),         # 亿
                "pb": f(46) if len(p) > 46 else None,
                "limit_up": f(47) if len(p) > 47 else None,
                "limit_down": f(48) if len(p) > 48 else None,
                "volume_ratio": f(49) if len(p) > 49 else None,
                "avg_price": f(51) if len(p) > 51 else None,
                "speed": None,
            }))
        return out

    def kline(self, symbol, period="daily", adjust="qfq", limit=500):
        """日/周/月/分钟 K 线。

        注意两个不同端点：
          · 分钟线(m1/m5/m15/m30/m60) -> ifzq.gtimg.cn/appstock/app/kline/mkline
          · 日周月(day/week/month)   -> web.ifzq.gtimg.cn/appstock/app/fqkline/get
        腾讯返回的字段顺序是 [时间, 开, 收, 高, 低, 量, {}, 额]（开-收-高-低）。
        """
        code = self._code(symbol)

        # ---- 分钟线 ----
        if period in ("1min", "5min", "15min", "30min", "60min"):
            kmap = {"1min": "m1", "5min": "m5", "15min": "m15",
                    "30min": "m30", "60min": "m60"}
            k = kmap[period]
            url = ("https://%s/appstock/app/kline/mkline?param=%s,%s,,%d"
                   % (self._mhost, code, k, limit))
            r = _get(url, config.HEADERS_TX, self._mhost)
            d = r.json().get("data") or {}
            node = d.get(code) or {}
            arr = node.get(k) or node.get("qfq" + k) or []
            bars = []
            for p in arr:
                if len(p) < 6:
                    continue
                bars.append({
                    "trade_date": self._fmt_minute_ts(p[0]),
                    "open": float(p[1]),
                    "close": float(p[2]),
                    "high": float(p[3]),
                    "low": float(p[4]),
                    "volume": int(float(p[5])),
                    "amount": float(p[7]) if len(p) > 7 and p[7] else 0,
                })
            return bars

        # ---- 日/周/月 ----
        kmap = {"daily": "day", "weekly": "week", "monthly": "month"}
        k = kmap.get(period, "day")
        fq = {"none": "", "qfq": "qfq", "hfq": "hfq"}[adjust]
        url = ("https://%s/appstock/app/fqkline/get?param=%s,%s,,,%d,%s"
               % (self._khost, code, k, limit, fq))
        r = _get(url, config.HEADERS_TX, self._khost)
        d = r.json().get("data") or {}
        node = d.get(code) or {}
        arr = node.get("%s%s" % (fq, k)) or node.get(k) or []
        bars = []
        for p in arr:
            if len(p) < 6:
                continue
            bars.append({
                "trade_date": p[0],
                "open": float(p[1]),
                "close": float(p[2]),
                "high": float(p[3]),
                "low": float(p[4]),
                "volume": int(float(p[5])),
                "amount": 0,
            })
        return bars

    @staticmethod
    def _fmt_minute_ts(ts):
        """202609211130 -> 2026-09-21 11:30"""
        s = str(ts)
        if len(s) >= 12:
            return "%s-%s-%s %s:%s" % (s[0:4], s[4:6], s[6:8], s[8:10], s[10:12])
        return s

    def minute(self, symbol):
        """当日分时（1 分钟粒度，含均价线）。

        腾讯原始格式："0930 1259.00 241 30341900.00"
                        时间  价格   成交量 成交额
        注意单位：成交量是「手」（1 手 = 100 股），成交额是「元」。
        所以每股均价 = 累计成交额 / (累计成交量 * 100)。
        """
        code = self._code(symbol)
        url = ("https://%s/appstock/app/minute/query?code=%s"
               % (self._khost, code))
        r = _get(url, config.HEADERS_TX, self._khost)
        d = r.json().get("data") or {}
        node = d.get(code) or {}
        inner = node.get("data") or {}
        date_s = inner.get("date") or ""
        date_fmt = self._fmt_date(date_s)

        # 昨收（算涨跌幅 + 分时基准线）
        pre = None
        try:
            pre = float(node.get("prec") or 0) or None
        except Exception:
            pass
        if not pre:
            qt = node.get("qt")
            q = qt.get(code) if isinstance(qt, dict) else None
            if q and len(q) > 4:
                try:
                    pre = float(q[4])
                except Exception:
                    pass

        out = []
        cum_amt = 0.0
        cum_vol = 0.0
        for raw in (inner.get("data") or []):
            parts = str(raw).split()
            if len(parts) < 2:
                continue
            hhmm = parts[0]
            try:
                price = float(parts[1])
                vol_lots = float(parts[2]) if len(parts) > 2 else 0   # 单位：手
                amt = float(parts[3]) if len(parts) > 3 else 0        # 单位：元
            except Exception:
                continue
            cum_amt += amt
            cum_vol += vol_lots
            # 累计均价（每股）：元 / (手 * 100 股)
            avg = (cum_amt / (cum_vol * 100.0)) if cum_vol > 0 else price
            out.append({
                "time": hhmm,
                "price": price,
                "avg": round(avg, 3),
                "volume": int(vol_lots),          # 手
                "amount": amt,                    # 元
                "change_pct": (round((price - pre) / pre * 100, 3)
                               if pre else None),
            })

        return {
            "symbol": symbol,
            "date": date_fmt,
            "prev_close": pre,
            "points": out,
        }

    @staticmethod
    def _fmt_date(d):
        s = str(d or "")
        if len(s) == 8:
            return "%s-%s-%s" % (s[0:4], s[4:6], s[6:8])
        return s


# ============================================================
#  新股（IPO）与公司概况
# ============================================================
_IPO_HOST = "push2.eastmoney.com"
_F10_HOST = "https://datacenter.eastmoney.com"
_F10_WEB_HOST = "https://datacenter-web.eastmoney.com"

# 新股列表字段：f12=代码 f14=名称 f2=价格 f26=上市日期 f13=市场(0深/1沪)
_IPO_FIELDS = "f12,f14,f2,f26,f152,f13,f1,f3,f4,f5,f6,f7,f8,f9,f10,f15,f16,f17,f18"


def _ymd(v):
    """东财日期整数 20260910 -> '2026-09-10'；非日期返回 None"""
    if not isinstance(v, int) or v <= 10000101:
        return None
    s = str(v)
    if len(s) != 8:
        return None
    try:
        return "%s-%s-%s" % (s[:4], s[4:6], s[6:])
    except Exception:
        return None


def _d10(v):
    """'2026-09-22 00:00:00' / '2026-09-22' -> datetime.date；失败返回 None"""
    import datetime
    if not v:
        return None
    s = str(v).strip()[:10]
    try:
        return datetime.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    except Exception:
        return None


def fetch_new_stocks(days=31):
    """未来 N 天内将在 A 股正式上市的股票（含已招股但尚未定上市日的）。

    数据源：东财 datacenter 报表 RPT_NEWSTOCK_ISSUEINFO
      - host: datacenter-web.eastmoney.com
      - 排序: LISTING_DATE 倒序（未定上市日的 LISTING_DATE 为空，排在最前）
      - 关键字段: CORRECODE(代码) / SECURITY_NAME_ABBR(名称) / LISTING_DATE(上市日)
                  DAT_ZHAOGURIQI(招股日) / ISSUE_PRICE(发行价) / PE_RATIO_AFTER(发行后PE)
                  ISSUE_NUM(发行数量) / LISTING_BOARD(板块) / TRADE_MARKET(市场)
                  LEAD_UNDERWRITER(主承销商) / SECUCODE
    注意：该报表同一只股票会重复出现，必须按 CORRECODE 去重（保留信息最全的一条）。
    """
    import datetime
    today = datetime.date.today()
    limit = today + datetime.timedelta(days=days)

    url = (_F10_WEB_HOST + "/api/data/v1/get?reportName=RPT_NEWSTOCK_ISSUEINFO"
           "&columns=ALL&quoteColumns=&pageNumber=1&pageSize=200"
           "&sortTypes=-1,-1&sortColumns=LISTING_DATE,DAT_ZHAOGURIQI"
           "&source=WEB&client=WEB")
    r = _get(url, config.HEADERS_EM, "datacenter-web.eastmoney.com#ipo")
    rows = (((r.json() or {}).get("result") or {}).get("data") or [])

    merged = {}
    for d in rows:
        code = str(d.get("CORRECODE") or "").strip()
        if not code.isdigit():
            continue
        ld = _d10(d.get("LISTING_DATE"))
        zg = _d10(d.get("DAT_ZHAOGURIQI"))

        # 已定上市日：只保留「今天起 days 天内」的
        if ld is not None:
            if not (today <= ld <= limit):
                continue
        else:
            # 未定上市日：只保留近期招股的（14 天内），视为「即将上市待定档」
            if zg is None or (today - zg).days > 14:
                continue

        item = {
            "symbol": code,
            "name": d.get("SECURITY_NAME_ABBR"),
            "list_date": ld.isoformat() if ld else None,
            "days_left": (ld - today).days if ld else None,
            "status": "listed_date_set" if ld else "pending",
            "issue_price": _num(d.get("ISSUE_PRICE")),
            "issue_pe": _num(d.get("PE_RATIO_AFTER")),
            "issue_num": _num(d.get("ISSUE_NUM")),
            "board": d.get("LISTING_BOARD"),
            "market": d.get("TRADE_MARKET"),
            "apply_date": zg.isoformat() if zg else None,
            "lead_underwriter": d.get("LEAD_UNDERWRITER"),
            "secucode": d.get("SECUCODE"),
        }
        # 同码去重：优先保留有上市日、字段更全的那条
        old = merged.get(code)
        if old is None:
            merged[code] = item
        else:
            old_score = (old["list_date"] is not None, sum(
                1 for k in ("issue_price", "board", "market", "lead_underwriter")
                if old.get(k) not in (None, "")))
            new_score = (item["list_date"] is not None, sum(
                1 for k in ("issue_price", "board", "market", "lead_underwriter")
                if item.get(k) not in (None, "")))
            if new_score > old_score:
                merged[code] = item

    out = list(merged.values())
    # 排序：先按上市日（未定的排最后），再按代码
    out.sort(key=lambda x: (x["list_date"] is None, x["list_date"] or "9999-99-99", x["symbol"]))
    return out


def _secucode_of(sym):
    """股票代码 -> 东财 SECUCODE 后缀。
    60/68 -> 沪；92/43/83/87 -> 北交所(.BJ)；其余(00/30/20) -> 深。"""
    if sym.startswith(("60", "68", "90")):
        return sym + ".SH"
    if sym.startswith(("92", "43", "83", "87", "88")):
        return sym + ".BJ"
    return sym + ".SZ"


def fetch_company_profile(symbol):
    """公司概况（东财 F10）。返回行业、公司性质、盈利、龙头等维度的原始信息。"""
    sym = str(symbol).strip()
    secucode = _secucode_of(sym)

    result = {"symbol": sym, "secucode": secucode}

    # ---------- 1) 基本组织信息 ----------
    try:
        url = (_F10_HOST + "/securities/api/data/v1/get?reportName=RPT_F10_BASIC_ORGINFO"
               "&columns=ALL&filter=(SECUCODE=%22" + secucode + "%22)&source=HSF10&client=PC")
        r = _get(url, config.HEADERS_EM, "datacenter.eastmoney.com#f10")
        data = (((r.json() or {}).get("result") or {}).get("data") or [])
        if data:
            d = data[0]
            result.update({
                "name": d.get("SECURITY_NAME_ABBR"),
                "org_name": d.get("ORG_NAME"),
                "org_name_en": d.get("ORG_NAME_EN"),
                "former_name": d.get("FORMERNAME"),
                "security_type": d.get("SECURITY_TYPE"),
                "trade_market": d.get("TRADE_MARKET"),
                # 行业：东财 2016 分类（如「食品饮料-饮料-白酒」）
                "industry_em": d.get("EM2016"),
                # 行业：证监会分类（如「制造业-酒、饮料和精制茶制造业」）
                "industry_csrc": d.get("INDUSTRYCSRC1"),
                # 实际控制人（公司性质判定依据，如「贵州省人民政府国有资产监督管理委员会」）
                "actual_holder": d.get("ACTUAL_HOLDER"),
                "main_business": d.get("MAIN_BUSINESS"),
                "chairman": d.get("CHAIRMAN"),
                "legal_person": d.get("LEGAL_PERSON"),
                "president": d.get("PRESIDENT"),
                "secretary": d.get("SECRETARY"),
                "reg_capital": _num(d.get("REG_CAPITAL")),
                "emp_num": d.get("EMP_NUM"),
                "province": d.get("PROVINCE"),
                "address": d.get("ADDRESS"),
                "reg_address": d.get("REG_ADDRESS"),
                "postcode": d.get("ADDRESS_POSTCODE"),
                "org_tel": d.get("ORG_TEL"),
                "org_fax": d.get("ORG_FAX"),
                "org_web": d.get("ORG_WEB"),
                "org_email": d.get("ORG_EMAIL"),
                "law_firm": d.get("LAW_FIRM"),
                "account_firm": d.get("ACCOUNTFIRM_NAME"),
                "profile": (d.get("ORG_PROFILE") or "").strip(),
                "found_date": (d.get("FOUND_DATE") or "")[:10] or None,
                "list_date_hint": (d.get("LISTING_DATE") or "")[:10] or None,
            })
    except Exception as e:
        result["_org_err"] = str(e)[:120]

    # ---------- 2) 财务摘要（盈利情况） ----------
    try:
        url = (_F10_WEB_HOST + "/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA"
               "&columns=ALL&filter=(SECUCODE=%22" + secucode + "%22)"
               "&sortColumns=REPORT_DATE&sortTypes=-1&pageSize=6"
               "&source=HSF10&client=PC")
        r = _get(url, config.HEADERS_EM, "datacenter-web.eastmoney.com#fin")
        data = (((r.json() or {}).get("result") or {}).get("data") or [])
        fins = []
        for d in data[:6]:
            fins.append({
                "report_date": (d.get("REPORT_DATE") or "")[:10],
                "eps": _num(d.get("EPSJB")),              # 基本每股收益
                "revenue": _num(d.get("TOTALOPERATEREVE")),
                "revenue_yoy": _num(d.get("TOTALOPERATEREVETZ")),
                "net_profit": _num(d.get("PARENTNETPROFIT")),
                "net_profit_yoy": _num(d.get("PARENTNETPROFITTZ")),
                "roe": _num(d.get("ROEJQ")),              # 净资产收益率(加权)
                "gross_margin": _num(d.get("XSMLL")),     # 销售毛利率
                "debt_ratio": _num(d.get("ZCFZL")),       # 资产负债率
                "bps": _num(d.get("BPS")),
            })
        result["finance"] = fins
    except Exception as e:
        result["_fin_err"] = str(e)[:120]

    # ---------- 3) 估值/市值快照（判断龙头体量） ----------
    try:
        q = market.quote([sym])["data"]
        if q:
            result["quote"] = {
                "name": q[0].get("name"),
                "price": q[0].get("price"),
                "change_pct": q[0].get("change_pct"),
                "pe_ttm": q[0].get("pe_ttm") or q[0].get("pe"),
                "pb": q[0].get("pb"),
                "total_mcap": q[0].get("total_mcap"),
                "float_mcap": q[0].get("float_mcap"),
                "turnover": q[0].get("turnover"),
            }
    except Exception as e:
        result["_quote_err"] = str(e)[:120]

    return result


# ============================================================
#  统一入口：自动选源 + 故障切换
# ============================================================
class MarketData:
    def __init__(self):
        self.providers = [EastmoneyProvider(), TencentProvider()]

    def quote(self, symbols):
        last_err = None
        for p in self.providers:
            try:
                data = p.quote(symbols)
                if data:
                    return {"source": p.name, "data": data}
            except Exception as e:
                last_err = "%s: %s" % (p.name, e)
                continue
        raise RuntimeError("所有数据源均失败: %s" % last_err)

    def kline(self, symbol, period="daily", adjust="qfq", limit=500):
        last_err = None
        for p in self.providers:
            try:
                data = p.kline(symbol, period, adjust, limit)
                if data:
                    return {"source": p.name, "data": data}
            except Exception as e:
                last_err = "%s: %s" % (p.name, e)
                continue
        raise RuntimeError("所有数据源均失败: %s" % last_err)

    def minute(self, symbol):
        """当日分时线（自动选源）"""
        last_err = None
        for p in self.providers:
            try:
                data = p.minute(symbol)
                if data and data.get("points"):
                    return {"source": p.name, "data": data}
            except Exception as e:
                last_err = "%s: %s" % (p.name, e)
                continue
        # 全部失败时返回空结构（非交易日/停牌时不报错）
        return {"source": "none", "data": {
            "symbol": symbol, "date": "", "prev_close": None, "points": []}}


market = MarketData()
