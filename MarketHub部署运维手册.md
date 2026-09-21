# Market Hub 部署运维手册

> 行情数据 Web 平台 · 腾讯云轻量应用服务器
> 部署完成时间：2026-09-21

---

## 一、快速信息

| 项目 | 值 |
|---|---|
| 访问地址 | `http://<SERVER_IP>:8090` |
| 登录账号 | `admin` |
| 登录密码 | 见服务器 `backend/.env` 或部署时自行设定 |
| 服务器 IP | `<SERVER_IP>` |
| 登录方式 | **SSH 密钥**（密码登录已关闭） |
| 项目目录 | `/opt/market-hub/` |
| 服务名 | `market-hub.service` |

> ⚠️ 首次访问需在云厂商控制台开放 8090 端口（详见第五章）

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────┐
│  浏览器                                              │
│  Vue3 + Element Plus + KLineCharts                  │
└────────────────────┬────────────────────────────────┘
                     │ HTTP :8090
┌────────────────────▼────────────────────────────────┐
│  FastAPI + uvicorn（systemd 托管）                   │
│  ├─ 静态前端  /opt/market-hub/backend/static        │
│  ├─ API       /api/v1/*                             │
│  └─ APScheduler 定时采集                             │
│      · 盘中快照   每 5 秒                            │
│      · 盘后日线   15:30                              │
│      · 指标计算   15:50                              │
└────────────────────┬────────────────────────────────┘
                     │ PyMySQL :3307（仅 127.0.0.1）
┌────────────────────▼────────────────────────────────┐
│  Docker 容器 market-mariadb                          │
│  MariaDB 10.11 · utf8mb4 · 数据卷 market_hub_dbdata  │
└─────────────────────────────────────────────────────┘
                     ▲
                     │ HTTPS
        ┌────────────┴────────────┐
        │ 东财 push2 / 腾讯 qt.gtimg │
        │ （强制 IPv4 + UA 伪装）    │
        └──────────────────────────┘
```

**关键设计**

- **数据源双活**：东财优先，失败自动切腾讯，单源限流 1.5 秒/次
- **强制 IPv4**：服务器无 IPv6 出口，代码里打了 `socket.getaddrinfo` 补丁
- **数据库隔离**：MariaDB 跑在 Docker 里，完全不碰系统库
- **只监听内网**：3307 绑定 `127.0.0.1`，外网无法直连数据库

---

## 三、目录结构

```
/opt/market-hub/
├── backend/
│   ├── app/
│   │   ├── config.py      # 配置 + .env 加载器
│   │   ├── db.py          # 连接池 + 8 张表 DDL
│   │   ├── providers.py   # 数据源适配（东财/腾讯）+ IPv4 补丁
│   │   ├── indicators.py  # MACD/KDJ/RSI/BOLL 纯 Python 实现
│   │   ├── auth.py        # sha256 加盐 + 手写 JWT
│   │   ├── main.py        # FastAPI 路由 + SPA 回退
│   │   └── sync.py        # 采集任务 + APScheduler
│   ├── .venv/             # Python 虚拟环境
│   ├── .env               # 环境配置（权限 600）
│   ├── run.py             # 启动入口
│   └── static/            # 前端构建产物
├── frontend/              # 前端源码（含 dist）
└── verify_all.py          # 全接口自检脚本
```

---

## 四、数据库

**8 张表**

| 表名 | 用途 |
|---|---|
| `security` | 证券基础信息（代码/名称/市场/类型） |
| `kline_daily` | 日线 K 线（开高低收/量/额） |
| `quote_snapshot` | 实时快照（只留最新一条） |
| `indicator_daily` | 预计算指标（MA/MACD/KDJ/RSI/BOLL） |
| `user` | 用户表（sha256 加盐密码） |
| `watchlist` | 自选池 |
| `sync_log` | 采集水位线 |
| `sector_daily` | 板块行情 |

**连接信息**

```
主机 127.0.0.1   端口 3307
库   market_hub  用户 mkt
密码 <配置在 backend/.env 的 MH_DB_PASS>
```

---

## 五、⚠️ 首次访问：开放 8090 端口

服务只在服务器内部可达，**必须**在云厂商控制台放行：

1. 打开轻量应用服务器控制台
2. 找到目标实例 → 点 **「防火墙」** 标签
3. **「添加规则」**：

| 字段 | 值 |
|---|---|
| 应用类型 | 自定义 |
| 协议 | TCP |
| 端口 | `8090` |
| 来源 | `0.0.0.0/0` |
| 策略 | 允许 |
| 备注 | Market Hub |

> 服务器本机 ufw 已放行 8090。云厂商控制台的防火墙是**独立的另一层**，两层都通才能访问。

---

## 六、日常运维

```bash
# 服务状态 / 启停 / 重启
systemctl status market-hub
systemctl restart market-hub
systemctl stop market-hub

# 查看日志（实时）
journalctl -u market-hub -f
journalctl -u market-hub -n 100 --no-pager

# 数据库
docker logs -f market-mariadb
docker exec -it market-mariadb mysql -umkt -p market_hub

# 手动触发采集
curl -X POST http://127.0.0.1:8090/api/v1/admin/sync/daily     -H "Authorization: Bearer $TOKEN"
curl -X POST http://127.0.0.1:8090/api/v1/admin/sync/snapshot  -H "Authorization: Bearer $TOKEN"
curl -X POST http://127.0.0.1:8090/api/v1/admin/sync/indicator -H "Authorization: Bearer $TOKEN"

# 全接口自检
cd /opt/market-hub/backend && .venv/bin/python /opt/market-hub/verify_all.py
```

---

## 七、更新代码后重新部署

**改后端**

```bash
# 本地上传 app/*.py 到 /opt/market-hub/backend/app/
cd /opt/market-hub/backend && .venv/bin/python -m py_compile app/main.py
systemctl restart market-hub
```

**改前端**

```bash
# 1. 上传源码到 /opt/market-hub/frontend/
# 2. 在服务器上构建
cd /opt/market-hub/frontend
npm install --no-audit --no-fund
npm run build

# 3. 部署产物
rm -rf /opt/market-hub/backend/static/*
cp -r /opt/market-hub/frontend/dist/* /opt/market-hub/backend/static/

# 4. 重启
systemctl restart market-hub
```

> 不要在本地构建 —— 本地没有 `node_modules`，服务器上才是构建环境。

---

## 八、API 一览

所有接口前缀 `/api/v1`，除 `login` / `health` 外均需 `Authorization: Bearer <token>`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | 登录，返回 `{code, data:{token, username, role}}` |
| GET | `/auth/me` | 当前用户 |
| GET | `/quote?symbols=600519,000001` | 批量实时行情 |
| GET | `/quote/{symbol}` | 单只行情（优先进库） |
| GET | `/kline?symbol=&period=&limit=` | K 线 |
| GET | `/indicator?symbol=&limit=` | 技术指标 |
| GET | `/company/{symbol}` | 公司档案（行业/性质/实控人/财务） |
| GET | `/ipo/upcoming?days=31` | 未来 N 天内上市的新股 |
| GET | `/pool` | 自选池 |
| POST | `/pool` | 添加自选 |
| DELETE | `/pool/{symbol}` | 删除自选 |
| GET | `/portfolio` | 持仓汇总 |
| DELETE | `/portfolio/symbol/{symbol}` | 删除某股全部持仓 |
| GET | `/sector` | 板块行情 |
| GET | `/admin/sync-status` | 采集状态 + 数据量 |
| POST | `/admin/sync/{task}` | 手动触发（admin） |
| GET | `/health` | 健康检查（无需鉴权） |

---

## 九、安全须知

**已完成的加固**

- ✅ SSH 改密钥登录，`PasswordAuthentication no`
- ✅ root 密码更换为 24 位强密码
- ✅ 清理全服的失效公钥
- ✅ 数据库仅监听 `127.0.0.1:3307`
- ✅ MariaDB 跑在 Docker 里，与系统库隔离
- ✅ 服务以 systemd 托管，带 `NoNewPrivileges` / `ProtectSystem` 加固

**待处理事项**

1. **轮换历史密码** —— 项目早期曾有密码明文落盘，服务器也遭受过持续暴力破解。建议轮换所有复用过的旧密码，并避免任何密码进入版本库。

2. **建议加 HTTPS** —— 当前是明文 HTTP，密码在传输中未加密。方案：
   - 有域名 → Certbot 申请 Let's Encrypt 证书 + Nginx 反代
   - 无域名 → 至少限制来源 IP

---

## 十、本次部署修复的 Bug 清单

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | 连错数据库 | `config.py` 只读 `os.getenv`，**没人加载 `.env`** | 加零依赖 `.env` 加载器 |
| 2 | 容器启动失败 | `--character-set-server` 传给了 `docker run` 而非镜像后 | 参数移到镜像名之后 |
| 3 | 数据库拒绝连接 | 缺 `mkt@localhost` / `mkt@127.0.0.1` 授权 | 补齐账号授权 |
| 4 | 接口 500 | `JSONResponse` 不支持 `default=` 参数 | 改 `json.dumps(default=...)` + `Response` |
| 5 | 接口 500 | `Decimal` / `datetime` 无法 JSON 序列化 | 统一 `_json_default` 转换器 |
| 6 | `/sector` 500 | `sector_daily` 表在 DDL 中漏建 | 补建表结构 |
| 7 | `/pool` 500 | SQL 引用 `s.name` 但没 JOIN `security` | 改 `COALESCE(q.name, s.name)` + 补 JOIN |
| 8 | 自选池为空 | `sync_snapshot` 用 `DEFAULT_POOL` 采集但不写 `watchlist` | 加幂等初始化 |
| 9 | 子路由刷新 404 | SPA 缺路由回退 | 加 catch-all 回退 `index.html` |
| 10 | **登录页无限刷新** | `api.js` 用 `location.hash` 判断（history 模式恒为真）→ 401 强制跳转 → 重新加载 → 再 401 | 改 `pathname` 判断 + `location.replace` + 防重入标志 |
| 11 | **登录页无限刷新** | `App.vue` 在登录页也请求 `/auth/me` → 401 → 跳转循环 | 登录页不渲染布局、不请求 `/auth/me` |
| 12 | 登录成功却不跳转 | `Login.vue` 取 `r.data.token`，但拦截器已解包为 `r.data` | 改取 `r.data.token`（兼容 `r.token`） |

---

*文档生成：2026-09-21 · Market Hub v1.0*
