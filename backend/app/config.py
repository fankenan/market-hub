# -*- coding: utf-8 -*-
"""全局配置"""
import os
import pathlib


def _load_dotenv():
    """把同目录上层的 .env 注入环境变量（不覆盖已存在的真实环境变量）。

    部署时 .env 位于 backend/.env，本文件位于 backend/app/config.py。
    优先级：真实环境变量 > .env 文件 > 代码内默认值。
    """
    for parent in (pathlib.Path(__file__).resolve().parent,
                   pathlib.Path(__file__).resolve().parent.parent):
        env_file = parent / ".env"
        if not env_file.is_file():
            continue
        try:
            for raw in env_file.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
        except OSError:
            pass
        break


_load_dotenv()

# ---------- 数据库 ----------
DB_HOST = os.getenv("MH_DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("MH_DB_PORT", "3306"))
DB_USER = os.getenv("MH_DB_USER", "mkt")
DB_PASS = os.getenv("MH_DB_PASS", "")
DB_NAME = os.getenv("MH_DB_NAME", "market_hub")

# ---------- 服务 ----------
API_HOST = os.getenv("MH_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("MH_API_PORT", "8090"))

# ---------- 鉴权 ----------
JWT_SECRET = os.getenv("MH_JWT_SECRET", "change-me-in-production")
JWT_EXPIRE_HOURS = int(os.getenv("MH_JWT_EXPIRE_HOURS", "72"))

# ---------- 采集 ----------
# 单源请求最小间隔（秒）—— 防封核心，不要调低
MIN_REQUEST_INTERVAL = float(os.getenv("MH_MIN_INTERVAL", "1.5"))
REQUEST_TIMEOUT = int(os.getenv("MH_REQ_TIMEOUT", "12"))
# 强行走 IPv4（本机 IPv6 无出口，不强制会全部超时）
FORCE_IPV4 = os.getenv("MH_FORCE_IPV4", "1") == "1"

# 盘中快照轮询间隔（秒）
SNAPSHOT_INTERVAL = int(os.getenv("MH_SNAPSHOT_INTERVAL", "5"))
# 盘后 ETL 触发时间
ETL_HOUR, ETL_MINUTE = 15, 30

# 默认自选池（首次初始化用）
DEFAULT_POOL = [
    "600000", "000001", "600519", "000858", "601318",
    "000002", "600036", "002415", "300750", "601899",
]

# ---------- 浏览器伪装（行情站会校验） ----------
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HEADERS_EM = {
    "User-Agent": UA,
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "*/*",
}
HEADERS_TX = {
    "User-Agent": UA,
    "Referer": "https://gu.qq.com/",
    "Accept": "*/*",
}
