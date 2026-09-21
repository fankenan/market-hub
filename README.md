# Market Hub

自选股行情数据 Web 平台 —— 基于腾讯云轻量应用服务器部署的全栈项目。

后端 FastAPI 采集东方财富 / 腾讯行情数据，前端 Vue 3 提供腾讯自选股风格的看盘界面。

---

## 功能

| 模块 | 说明 |
|---|---|
| **自选** | 自选股列表，实时行情（价格/涨跌幅/成交额/换手率等），自动轮询刷新 |
| **详情页** | 分时图 + K 线（1/5/15/30/60 分、日/周/月，前复权/不复权/后复权），MA/VOL/MACD/KDJ/RSI/BOLL 指标 |
| **持仓管理** | 多笔买入自动算加权平均成本，卖出后计入总盈亏；盈亏红涨绿跌；K 线图上叠加买价黑色虚线与 B/S 买卖标记 |
| **压力支撑** | 四算法融合（5 日枢轴点 / 摆动高低点 / 整数心理关口 / MA20·MA60 均线位）推算上方压力、次压力、下方支撑、强支撑 |
| **公司信息** | 所属行业（东财 + 证监会双口径）、公司性质、实际控制人、是否龙头、6 期财务（营收/净利/同比/EPS/ROE/毛利率/负债率）与盈利评级 |
| **新上股票** | 未来 N 天内登陆 A 股的新股列表（含发行价/发行 PE/板块/主承销商），左列表右公司信息两栏联动 |

---

## 技术栈

**后端**
- Python 3.12 + FastAPI + uvicorn
- APScheduler 定时采集（盘中快照 5 秒 / 盘后日线 15:30 / 指标计算 15:50）
- MariaDB 10.11（Docker）+ PyMySQL 连接池
- 自研指标库（MACD / KDJ / RSI / BOLL 纯 Python 实现）
- sha256 加盐 + 手写 JWT 鉴权

**前端**
- Vue 3 + Vite + Vue Router
- Element Plus
- KLineCharts（K 线 / 分时）
- ECharts（部分图表）

---

## 架构

```
浏览器 (Vue3 + Element Plus + KLineCharts)
      │ HTTP :8090
FastAPI + uvicorn（systemd 托管）
  ├─ 静态前端   backend/static
  ├─ API        /api/v1/*
  └─ APScheduler 定时采集
      │ PyMySQL :3307（仅 127.0.0.1）
MariaDB 10.11（Docker 容器 market-mariadb）
      ▲
      │ HTTPS
  东方财富 push2 / 腾讯 qt.gtimg（强制 IPv4 + UA 伪装）
```

**关键设计**

- **数据源双活**：东财优先，失败自动切腾讯；按域名独立限流（1.5 秒/次）防封
- **强制 IPv4**：服务器无 IPv6 出口，代码里打了 `socket.getaddrinfo` 补丁
- **数据库隔离**：MariaDB 跑在 Docker 里，只监听 `127.0.0.1`，不碰系统库
- **服务加固**：systemd 托管，带 `NoNewPrivileges` / `ProtectSystem`

---

## 目录结构

```
market-hub/
├── backend/
│   ├── app/
│   │   ├── config.py      # 配置 + .env 加载器
│   │   ├── db.py          # 连接池 + 8 张表 DDL
│   │   ├── providers.py   # 数据源适配（东财/腾讯）+ IPv4 补丁 + F10/新股接口
│   │   ├── indicators.py  # MACD/KDJ/RSI/BOLL 纯 Python 实现
│   │   ├── auth.py        # sha256 加盐 + 手写 JWT
│   │   ├── main.py        # FastAPI 路由 + SPA 回退
│   │   └── sync.py        # 采集任务 + APScheduler
│   ├── requirements.txt
│   └── run.py             # 启动入口
├── frontend/
│   ├── src/
│   │   ├── views/         # Dashboard / Detail / Portfolio / IpoNew / Login
│   │   ├── api.js         # axios 封装（token 注入 + 401 处理）
│   │   ├── App.vue
│   │   └── main.js
│   ├── package.json
│   └── vite.config.js
└── MarketHub部署运维手册.md
```

---

## 快速开始

### 1. 配置环境变量

复制 `backend/.env.example` 为 `backend/.env` 并填入实际值：

```bash
cd backend
cp .env.example .env
```

### 2. 后端

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt

# 初始化数据库（见 db.py 中的 DDL）
.venv/bin/python run.py
```

### 3. 前端

```bash
cd frontend
npm install
npm run dev          # 开发模式
npm run build        # 生产构建 -> dist/
```

生产部署时把 `dist/` 的内容覆盖到 `backend/static/`，由 FastAPI 托管静态资源。

---

## API 一览

所有接口前缀 `/api/v1`，除 `login` / `health` 外均需 `Authorization: Bearer <token>`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/login` | 登录 |
| GET | `/auth/me` | 当前用户 |
| GET | `/quote?symbols=600519,000001` | 批量实时行情 |
| GET | `/quote/{symbol}` | 单只行情 |
| GET | `/kline?symbol=&period=&limit=` | K 线 |
| GET | `/indicator?symbol=&limit=` | 技术指标 |
| GET | `/company/{symbol}` | 公司档案 |
| GET | `/ipo/upcoming?days=31` | 未来 N 天内上市的新股 |
| GET/POST/DELETE | `/pool` | 自选池增删查 |
| GET | `/portfolio` | 持仓汇总 |
| DELETE | `/portfolio/symbol/{symbol}` | 删除某股全部持仓 |
| GET | `/sector` | 板块行情 |
| GET | `/admin/sync-status` | 采集状态 |
| POST | `/admin/sync/{task}` | 手动触发采集（admin） |
| GET | `/health` | 健康检查 |

---

## 数据源说明

本项目行情数据来自**公开的第三方接口**（东方财富、腾讯），仅供个人学习与研究使用：

- 全部请求做了限流（单域名 1.5 秒/次）与缓存，避免对源站造成压力
- 数据仅供参考，**不构成任何投资建议**
- 请勿用于商业用途；如需商用请使用官方授权数据服务

---

## 安全提示

- `.env` 与任何凭据文件均已在 `.gitignore` 中排除，**请勿提交密码到版本库**
- 生产环境建议启用 HTTPS（Nginx 反代 + Let's Encrypt），避免明文传输密码

---

## License

MIT
