# -*- coding: utf-8 -*-
"""认证：JWT + sha256 加盐"""
import hashlib
import hmac
import os
import time
import base64
import json
from . import config, db


def hash_password(password, salt=None):
    salt = salt or base64.b16encode(os.urandom(8)).decode()
    h = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return "%s$%s" % (salt, h)


def verify_password(password, stored):
    try:
        salt, h = stored.split("$", 1)
    except ValueError:
        return False
    calc = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(calc, h)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def make_token(username, role, uid):
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "sub": username, "role": role, "uid": uid,
        "exp": int(time.time()) + config.JWT_EXPIRE_HOURS * 3600,
    }).encode())
    signing = ("%s.%s" % (header, payload)).encode()
    sig = _b64(hmac.new(config.JWT_SECRET.encode(), signing, hashlib.sha256).digest())
    return "%s.%s.%s" % (header, payload, sig)


def parse_token(token):
    try:
        header, payload, sig = token.split(".")
        signing = ("%s.%s" % (header, payload)).encode()
        expect = _b64(hmac.new(config.JWT_SECRET.encode(), signing, hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expect):
            return None
        data = json.loads(_unb64(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None


def ensure_admin():
    """首次运行时创建管理员账号，并为其初始化默认自选池"""
    rows = db.query("SELECT COUNT(*) AS c FROM user")
    if rows and rows[0]["c"] == 0:
        pwd = os.getenv("MH_ADMIN_PASS") or "admin123456"
        db.execute(
            "INSERT INTO user (username, password, role, created_at) VALUES (%s,%s,'admin',NOW())",
            ("admin", hash_password(pwd)),
        )
        _seed_watchlist()
        return pwd
    return None


def _seed_watchlist():
    """给 admin 灌入默认自选池（仅当为空时）"""
    try:
        row = db.query("SELECT id FROM user WHERE username='admin'")
        if not row:
            return 0
        uid = row[0]["id"]
        cnt = db.query("SELECT COUNT(*) AS c FROM watchlist WHERE user_id=%s", (uid,))
        if cnt and cnt[0]["c"] > 0:
            return 0
        n = 0
        for i, sym in enumerate(config.DEFAULT_POOL):
            db.execute(
                "INSERT IGNORE INTO watchlist (user_id, symbol, grp, sort_no, created_at) "
                "VALUES (%s,%s,'默认',%s,NOW())",
                (uid, sym, i))
            n += 1
        print("[init] 已初始化默认自选池 %d 只" % n)
        return n
    except Exception as e:
        print("[init] 自选池初始化失败:", e)
        return 0
