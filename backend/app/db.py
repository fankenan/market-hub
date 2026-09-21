# -*- coding: utf-8 -*-
"""数据库连接与建表"""
import pymysql
from dbutils.pooled_db import PooledDB
from . import config

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        _pool = PooledDB(
            creator=pymysql,
            maxconnections=10,
            mincached=2,
            blocking=True,
            ping=1,
            host=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASS,
            database=config.DB_NAME,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    return _pool


def get_conn():
    return get_pool().connection()


def query(sql, args=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args or ())
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql, args=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            n = cur.execute(sql, args or ())
        conn.commit()
        return n
    finally:
        conn.close()


def executemany(sql, rows):
    if not rows:
        return 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            n = cur.executemany(sql, rows)
        conn.commit()
        return n
    finally:
        conn.close()


DDL = [
    # 证券基础信息
    """CREATE TABLE IF NOT EXISTS security (
        symbol      VARCHAR(16) PRIMARY KEY,
        name        VARCHAR(64),
        market      VARCHAR(8)  COMMENT 'sh/sz/bj/hk/us',
        sec_type    VARCHAR(16) COMMENT 'stock/index/fund/futures',
        updated_at  DATETIME,
        KEY idx_market (market),
        KEY idx_type (sec_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 日线
    """CREATE TABLE IF NOT EXISTS kline_daily (
        symbol      VARCHAR(16) NOT NULL,
        trade_date  DATE        NOT NULL,
        open        DECIMAL(12,3),
        high        DECIMAL(12,3),
        low         DECIMAL(12,3),
        close       DECIMAL(12,3),
        volume      BIGINT,
        amount      DECIMAL(20,2),
        PRIMARY KEY (symbol, trade_date),
        KEY idx_date (trade_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 实时快照（只留最新一条）
    """CREATE TABLE IF NOT EXISTS quote_snapshot (
        symbol      VARCHAR(16) PRIMARY KEY,
        name        VARCHAR(64),
        price       DECIMAL(12,3),
        prev_close  DECIMAL(12,3),
        open        DECIMAL(12,3),
        high        DECIMAL(12,3),
        low         DECIMAL(12,3),
        change_pct  DECIMAL(10,3),
        volume      BIGINT,
        amount      DECIMAL(20,2),
        turnover    DECIMAL(10,3),
        pe          DECIMAL(12,3),
        pb          DECIMAL(12,3),
        bid         VARCHAR(255) COMMENT '买五档 JSON',
        ask         VARCHAR(255) COMMENT '卖五档 JSON',
        updated_at  DATETIME,
        KEY idx_updated (updated_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 预计算指标
    """CREATE TABLE IF NOT EXISTS indicator_daily (
        symbol      VARCHAR(16) NOT NULL,
        trade_date  DATE        NOT NULL,
        ma5         DECIMAL(12,3),
        ma10        DECIMAL(12,3),
        ma20        DECIMAL(12,3),
        ma60        DECIMAL(12,3),
        dif         DECIMAL(12,4),
        dea         DECIMAL(12,4),
        macd        DECIMAL(12,4),
        k           DECIMAL(10,3),
        d           DECIMAL(10,3),
        j           DECIMAL(10,3),
        rsi6        DECIMAL(10,3),
        rsi14       DECIMAL(10,3),
        boll_up     DECIMAL(12,3),
        boll_mid    DECIMAL(12,3),
        boll_low    DECIMAL(12,3),
        vol_ma5     BIGINT,
        PRIMARY KEY (symbol, trade_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 用户
    """CREATE TABLE IF NOT EXISTS user (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        username    VARCHAR(32) UNIQUE NOT NULL,
        password    VARCHAR(128) NOT NULL COMMENT 'sha256 加盐',
        role        VARCHAR(16) DEFAULT 'viewer',
        created_at  DATETIME,
        last_login  DATETIME
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 自选池
    """CREATE TABLE IF NOT EXISTS watchlist (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        user_id     INT NOT NULL,
        symbol      VARCHAR(16) NOT NULL,
        grp         VARCHAR(32) DEFAULT '默认',
        sort_no     INT DEFAULT 0,
        created_at  DATETIME,
        UNIQUE KEY uk_user_symbol (user_id, symbol),
        KEY idx_user (user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 采集水位线
    """CREATE TABLE IF NOT EXISTS sync_log (
        task        VARCHAR(64) PRIMARY KEY,
        last_date   DATE,
        last_run    DATETIME,
        status      VARCHAR(16),
        message     VARCHAR(512),
        rows_ok     INT DEFAULT 0
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 持仓（同一股票可多笔买入，聚合算平均成本）
    """CREATE TABLE IF NOT EXISTS position (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        user_id     INT NOT NULL,
        symbol      VARCHAR(16) NOT NULL,
        name        VARCHAR(64) COMMENT '买入时的名称快照',
        buy_date    DATE        NOT NULL,
        buy_price   DECIMAL(12,3) NOT NULL,
        qty         INT         NOT NULL DEFAULT 100 COMMENT '股数',
        status      TINYINT     NOT NULL DEFAULT 1 COMMENT '1=持仓中 0=已卖出',
        sell_price  DECIMAL(12,3) COMMENT '卖出价（整股卖出时统一填写）',
        sell_date   DATE        COMMENT '卖出日期',
        created_at  DATETIME,
        sell_at     DATETIME    COMMENT '卖出操作时间',
        KEY idx_user_status (user_id, status),
        KEY idx_user_symbol (user_id, symbol),
        KEY idx_symbol (symbol)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",

    # 板块行情（东财行业板块）
    """CREATE TABLE IF NOT EXISTS sector_daily (
        sector_code VARCHAR(32) NOT NULL,
        trade_date  DATE        NOT NULL,
        sector_name VARCHAR(64),
        change_pct  DECIMAL(10,3),
        price       DECIMAL(12,3),
        volume      BIGINT,
        amount      DECIMAL(20,2),
        up_count    INT,
        down_count  INT,
        lead_symbol VARCHAR(16)  COMMENT '领涨股代码',
        lead_name   VARCHAR(64)  COMMENT '领涨股名称',
        lead_pct    DECIMAL(10,3) COMMENT '领涨股涨幅',
        updated_at  DATETIME,
        PRIMARY KEY (sector_code, trade_date),
        KEY idx_date (trade_date),
        KEY idx_pct (change_pct)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
]


def init_schema():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql in DDL:
                cur.execute(sql)
        conn.commit()
    finally:
        conn.close()


def log_sync(task, status, message="", rows_ok=0, last_date=None):
    execute(
        """INSERT INTO sync_log (task, last_date, last_run, status, message, rows_ok)
           VALUES (%s, %s, NOW(), %s, %s, %s)
           ON DUPLICATE KEY UPDATE last_date=VALUES(last_date), last_run=NOW(),
             status=VALUES(status), message=VALUES(message), rows_ok=VALUES(rows_ok)""",
        (task, last_date, status, message[:500], rows_ok),
    )
