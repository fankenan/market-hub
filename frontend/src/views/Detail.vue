<template>
  <div>
    <!-- 头部行情：左价格块 + 右关键指标网格（腾讯自选股风格） -->
    <div class="quote-head card">
      <div class="qh-left">
        <div class="name">
          <h2>{{ info.name || symbol }}</h2>
          <span class="code">{{ symbol }}</span>
        </div>
        <div class="priceline">
          <div class="big mono" :class="cls(live.change_pct)">
            {{ fmt(live.price ?? info.price) }}
          </div>
          <div class="chg">
            <div class="mono" :class="cls(live.change_pct)">{{ chgAmt(live.change_amt) }}</div>
            <div class="mono" :class="cls(live.change_pct)">{{ chgPct(live.change_pct) }}</div>
          </div>
        </div>
        <div class="live">
          <span class="live-dot" :class="{ on: polling }"></span>
          <span class="live-txt">{{ polling ? '实时刷新中' : '已暂停' }}</span>
          <span class="src" v-if="src">{{ srcLabel }}</span>
        </div>
      </div>
      <div class="qh-metrics">
        <div v-for="m in kvList" :key="m.label" class="kv">
          <span class="mk">{{ m.label }}</span>
          <b class="mv mono" :class="m.c || ''">{{ m.value }}</b>
        </div>
      </div>
    </div>

    <div class="grid">
      <div class="chart-card">
        <!-- 周期切换（含分时） -->
        <div class="toolbar">
          <el-radio-group v-model="view" size="small" @change="onViewChange">
            <el-radio-button value="minute">分时</el-radio-button>
            <el-radio-button value="1min">1分</el-radio-button>
            <el-radio-button value="5min">5分</el-radio-button>
            <el-radio-button value="15min">15分</el-radio-button>
            <el-radio-button value="30min">30分</el-radio-button>
            <el-radio-button value="60min">60分</el-radio-button>
            <el-radio-button value="daily">日K</el-radio-button>
            <el-radio-button value="weekly">周K</el-radio-button>
            <el-radio-button value="monthly">月K</el-radio-button>
          </el-radio-group>

          <el-radio-group v-if="isKline" v-model="adjust" size="small" @change="loadChart">
            <el-radio-button value="qfq">前复权</el-radio-button>
            <el-radio-button value="none">不复权</el-radio-button>
            <el-radio-button value="hfq">后复权</el-radio-button>
          </el-radio-group>

          <template v-if="isKline">
            <span class="spacer"></span>
            <span class="lbl">指标</span>
            <el-checkbox-group v-model="indicators" size="small" @change="applyIndicators">
              <el-checkbox-button value="MA">MA</el-checkbox-button>
              <el-checkbox-button value="VOL">VOL</el-checkbox-button>
              <el-checkbox-button value="MACD">MACD</el-checkbox-button>
              <el-checkbox-button value="KDJ">KDJ</el-checkbox-button>
              <el-checkbox-button value="RSI">RSI</el-checkbox-button>
              <el-checkbox-button value="BOLL">BOLL</el-checkbox-button>
            </el-checkbox-group>
          </template>
          <template v-else>
            <span class="spacer"></span>
            <span class="lbl">{{ minuteMeta }}</span>
          </template>
        </div>

        <!-- 分时图 -->
        <div v-show="!isKline" ref="minuteEl" class="chart"></div>
        <!-- K 线图 -->
        <div v-show="isKline" ref="klineEl" class="chart"></div>

        <!-- 持仓联动图例 -->
        <div class="legend" v-if="buyLine">
          <span class="lg-line"></span>
          <span class="lg-txt">{{ buyLine.label }} {{ fmt(buyLine.price) }}</span>
          <template v-if="markCount">
            <span class="lg-tag b">B</span>
            <span class="lg-txt">买入 {{ buyCount }} 次</span>
            <span class="lg-tag s" v-if="sellCount">S</span>
            <span class="lg-txt" v-if="sellCount">卖出 {{ sellCount }} 次</span>
          </template>
          <span class="lg-hint" v-if="!markCount">（该股无历史买卖日期记录）</span>
        </div>
      </div>

      <div class="side">
        <div class="panel" v-if="holding || closedRows.length">
          <div class="panel-title">我的持仓</div>
          <div class="pos-metrics">
            <div class="pm">
              <span class="k">{{ buyLine.label }}</span>
              <b class="mono">{{ fmt(buyLine.price) }}</b>
            </div>
            <div class="pm" v-if="holding">
              <span class="k">持有</span>
              <b class="mono">{{ holding.total_qty }} 股</b>
            </div>
            <div class="pm" v-if="holding">
              <span class="k">浮动盈亏</span>
              <b class="mono" :class="cls(holding.unrealized_pnl)">{{ pnl(holding.unrealized_pnl) }}</b>
            </div>
            <div class="pm" v-if="holding">
              <span class="k">盈亏比例</span>
              <b class="mono" :class="cls(holding.unrealized_pct)">{{ chgPct(holding.unrealized_pct) }}</b>
            </div>
          </div>
          <div class="pos-lots" v-if="holding && holding.lots.length">
            <div class="pl" v-for="l in holding.lots" :key="l.id">
              <span class="tag b">B</span>
              <span class="pd">{{ l.buy_date }}</span>
              <span class="mono">{{ fmt(l.buy_price) }} × {{ l.qty }}</span>
            </div>
          </div>
          <div class="pos-lots" v-if="!holding && closedRows.length">
            <div class="pl" v-for="c in closedRows.slice(0, 3)" :key="c.sell_date"
                 :class="{ muted: true }">
              <span class="tag b">B</span>
              <span class="pd">{{ c.buy_date }}</span>
              <span class="tag s">S</span>
              <span class="pd">{{ c.sell_date }}</span>
              <span class="mono" :class="cls(c.pnl)">{{ pnl(c.pnl) }}</span>
            </div>
          </div>
          <div class="tip">
            K 线中 <span class="tag b sm">B</span> 买入 <span class="tag s sm">S</span> 卖出，
            黑色虚线为{{ buyLine.label }}
          </div>
        </div>
        <div class="panel">
          <div class="panel-title">技术指标</div>
          <div class="metrics">
            <div v-for="m in metricList" :key="m.label" class="metric">
              <div class="k">{{ m.label }}</div>
              <div class="v mono">{{ m.value }}</div>
            </div>
          </div>
        </div>
        <div class="panel">
          <div class="panel-title">操作</div>
          <el-button size="small" @click="loadAll">刷新数据</el-button>
          <el-button size="small" :type="polling ? 'default' : 'primary'"
                     @click="togglePolling">
            {{ polling ? '暂停刷新' : '开始刷新' }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- ==================== 公司信息（全宽） ==================== -->
    <div class="co-card card">
      <div class="co-head">
        <div class="co-title">
          <span class="bar"></span>
          <h3>公司信息</h3>
          <span class="co-sub" v-if="co.org_name">{{ co.org_name }}</span>
        </div>
        <div class="co-chips" v-if="co.name">
          <span class="chip" v-if="co.industry_em">{{ co.industry_em.split('-')[0] }}</span>
          <span class="chip" v-if="nature">{{ nature }}</span>
          <span class="chip" v-if="leaderLabel" :class="leaderCls">{{ leaderLabel }}</span>
        </div>
      </div>

      <div v-if="loadingCo" class="co-empty">正在读取公司信息…</div>
      <div v-else-if="!co.name" class="co-empty">
        暂无该公司信息
        <span v-if="coErr" class="co-err">{{ coErr }}</span>
      </div>

      <template v-else>
        <!-- 一句话画像 -->
        <div class="co-verdict">
          <span class="v-label">公司画像</span>
          <span class="v-text">{{ coSummary }}</span>
        </div>

        <div class="co-cols">
          <!-- 左：基本信息 -->
          <div class="co-block">
            <div class="blk-t">基本信息</div>
            <div class="kv-grid">
              <div class="kv"><span>所属行业</span><b>{{ co.industry_em || '—' }}</b></div>
              <div class="kv"><span>证监会行业</span><b>{{ co.industry_csrc || '—' }}</b></div>
              <div class="kv"><span>公司性质</span><b>{{ nature }}</b></div>
              <div class="kv"><span>是否龙头</span><b :class="leaderCls">{{ leaderLabel }}</b></div>
              <div class="kv"><span>实际控制人</span><b class="ell" :title="co.actual_holder">{{ co.actual_holder || '—' }}</b></div>
              <div class="kv"><span>成立日期</span><b class="mono">{{ co.found_date || '—' }}</b></div>
              <div class="kv"><span>证券类型</span><b>{{ co.security_type || '—' }}</b></div>
              <div class="kv"><span>上市交易所</span><b>{{ co.trade_market || '—' }}</b></div>
              <div class="kv"><span>董事长</span><b>{{ co.chairman || '—' }}</b></div>
              <div class="kv"><span>法定代表人</span><b>{{ co.legal_person || '—' }}</b></div>
              <div class="kv"><span>注册资本</span><b class="mono">{{ coNum(co.reg_capital, '万元') }}</b></div>
              <div class="kv"><span>员工人数</span><b class="mono">{{ coNum(co.emp_num, '人') }}</b></div>
              <div class="kv"><span>注册地</span><b>{{ co.province || '—' }}</b></div>
              <div class="kv"><span>邮政编码</span><b class="mono">{{ co.postcode || '—' }}</b></div>
              <div class="kv"><span>总市值</span><b class="mono">{{ bigMkt }}</b></div>
              <div class="kv"><span>流通市值</span><b class="mono">{{ floatMkt }}</b></div>
              <div class="kv"><span>市盈率(TTM)</span><b class="mono">{{ coNum(co.quote && co.quote.pe_ttm) }}</b></div>
              <div class="kv"><span>市净率(PB)</span><b class="mono">{{ coNum(co.quote && co.quote.pb) }}</b></div>
              <div class="kv wide"><span>公司官网</span>
                <b>
                  <a v-if="co.org_web" :href="webUrl(co.org_web)" target="_blank" rel="noopener">{{ co.org_web }}</a>
                  <template v-else>—</template>
                </b>
              </div>
              <div class="kv wide"><span>注册地址</span><b>{{ co.reg_address || co.address || '—' }}</b></div>
            </div>
          </div>

          <!-- 右：盈利情况 -->
          <div class="co-block">
            <div class="blk-t">
              盈利情况
              <span class="blk-sub" v-if="co.finance && co.finance.length">最近 {{ co.finance.length }} 期</span>
            </div>
            <div v-if="!co.finance || !co.finance.length" class="co-empty sm">暂无财务数据</div>
            <table v-else class="fin">
              <thead>
                <tr>
                  <th>报告期</th><th>营收</th><th>同比</th>
                  <th>净利润</th><th>同比</th><th>ROE</th><th>毛利率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="f in co.finance.slice(0, 6)" :key="f.report_date">
                  <td class="mono">{{ f.report_date }}</td>
                  <td class="mono">{{ money2(f.revenue) }}</td>
                  <td class="mono" :class="cls(f.revenue_yoy)">{{ chgPct(f.revenue_yoy) }}</td>
                  <td class="mono">{{ money2(f.net_profit) }}</td>
                  <td class="mono" :class="cls(f.net_profit_yoy)">{{ chgPct(f.net_profit_yoy) }}</td>
                  <td class="mono">{{ coNum(f.roe) }}{{ f.roe != null ? '%' : '' }}</td>
                  <td class="mono">{{ coNum(f.gross_margin) }}{{ f.gross_margin != null ? '%' : '' }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="co.finance && co.finance.length" class="fin-note">
              <span class="grade" :class="profitCls">{{ profitGrade }}</span>
              {{ profitDesc }}
            </div>
          </div>
        </div>

        <!-- 公司简介 -->
        <div class="co-block" v-if="co.profile" style="margin-top:12px">
          <div class="blk-t">公司简介</div>
          <p class="co-profile">{{ co.profile }}</p>
        </div>

        <div class="co-src">
          数据来源：东方财富 F10
          <span v-if="coErr" class="co-err">（部分字段缺失：{{ coErr }}）</span>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import { init, dispose, registerOverlay } from 'klinecharts'
// ECharts 按需引入：只用到折线图 + 柱状图 + 网格/提示/图例组件，避免全量打包
import * as echarts from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import {
  GridComponent, TooltipComponent, AxisPointerComponent, MarkLineComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import api from '../api'

echarts.use([
  LineChart, BarChart,
  GridComponent, TooltipComponent, AxisPointerComponent, MarkLineComponent,
  CanvasRenderer
])

const route = useRoute()
const symbol = ref(route.params.symbol)

const info = ref({})          // 数据库里的快照
const live = ref({})          // 实时快照（轮询）
const src = ref('')
const view = ref('minute')    // 当前视图：minute 或某个 K 线周期
const adjust = ref('qfq')
const indicators = ref(['MA', 'VOL', 'MACD'])
const indRows = ref([])

// ---------- 持仓联动 ----------
const holding = ref(null)     // 当前股票的持仓中记录（来自 /portfolio）
const closedRows = ref([])    // 当前股票的已清仓记录（来自 /portfolio/closed）

// 买价参考线：持仓中且仅一笔 -> 用该笔买价（标"买价"）
//             持仓中多笔 -> 用加权平均成本（标"均价"）
//             已清仓 -> 用最后一笔清仓的均价（标"成本价"，灰色）
const buyLine = computed(() => {
  const h = holding.value
  if (h) {
    const n = (h.lots || []).length
    const multi = n > 1
    return {
      price: Number(h.avg_cost),
      label: multi ? '均价' : '买价',
      kind: multi ? 'avg' : 'buy',
      lots: h.lots || []
    }
  }
  const c = closedRows.value[0]
  if (c && c.avg_cost) {
    return {
      price: Number(c.avg_cost),
      label: '成本价',
      kind: 'closed',
      lots: c.lots || []
    }
  }
  return null
})

// 交易标记：B = 每笔买入日期，S = 每笔卖出日期（同一天多笔只留一个）
const tradeMarks = computed(() => {
  const map = new Map()
  const put = (d, type, price, qty) => {
    if (!d) return
    const key = String(d).slice(0, 10)
    const arr = map.get(key) || []
    if (!arr.some((x) => x.type === type)) arr.push({ type, price, qty })
    map.set(key, arr)
  }
  const h = holding.value
  if (h) {
    for (const l of (h.lots || [])) put(l.buy_date, 'B', l.buy_price, l.qty)
  }
  for (const c of closedRows.value) {
    for (const l of (c.lots || [])) put(l.buy_date, 'B', l.buy_price, l.qty)
    put(c.sell_date, 'S', c.sell_price, c.total_qty)
  }
  // 日期 -> 标记数组（顺序：B 在前 S 在后）
  const out = {}
  map.forEach((v, k) => {
    out[k] = v.sort((a, b) => (a.type === b.type ? 0 : a.type === 'B' ? -1 : 1))
  })
  return out
})

const minuteEl = ref(null)
const klineEl = ref(null)
let kChart = null
let mChart = null

const KLINE_PERIODS = ['1min', '5min', '15min', '30min', '60min',
                       'daily', 'weekly', 'monthly']
const isKline = computed(() => KLINE_PERIODS.includes(view.value))

// ---------- 轮询 ----------
const polling = ref(true)
let timer = null
const POLL_MS = 8000

// ---------- 格式化 ----------
function cls(v) { return v > 0 ? 'up' : v < 0 ? 'down' : 'flat' }
function fmt(v) {
  return v === null || v === undefined || v === '' ? '—' : Number(v).toFixed(2)
}
function money(v) {
  if (!v) return '—'
  const n = Number(v)
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(0)
}
function chgAmt(a) {
  return a === null || a === undefined || a === '' ? '—' : (a > 0 ? '+' : '') + Number(a).toFixed(2)
}
function chgPct(p) {
  return p === null || p === undefined || p === '' ? '—' : (p > 0 ? '+' : '') + Number(p).toFixed(2) + '%'
}
function pnl(v) {
  return v === null || v === undefined || v === '' ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2)
}

const srcLabel = computed(() => {
  const s = src.value || ''
  const map = { tencent: '腾讯行情', eastmoney: '东财行情', local_db: '本地库' }
  return map[s] || s
})

// 手数格式化：593200 -> 59.32万（单位：手）
function vol(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(0)
}
// 股本格式化：股 -> 亿股
function shares(v) {
  if (v === null || v === undefined || v === '') return '—'
  return (Number(v) / 1e8).toFixed(2) + '亿'
}

// 涨速：东财源有 speed 字段；腾讯源从分时近 5 分钟推算
const speedLive = computed(() => {
  const s = live.value.speed
  if (s !== null && s !== undefined) return Number(s)
  const pts = minuteData.value.points || []
  if (pts.length < 6) return null
  const a = pts[pts.length - 6].price
  const b = pts[pts.length - 1].price
  if (!a) return null
  return (b - a) / a * 100
})

// ---------- 压力位 / 支撑位（多算法融合） ----------
// 数据源：日K 近 120 根（多取一些给均线留出前置窗口）
const srBars = ref([])

/**
 * 枢轴点（Pivot Points，Classic）——最经典的压力支撑算法
 * P = (H+L+C)/3；R1 = 2P-L；S1 = 2P-H
 * 取最近 5 个交易日的枢轴均值，抗单日噪声
 */
function pivotLevels(bars) {
  const n = Math.min(5, bars.length)
  if (!n) return null
  let r1 = 0, s1 = 0
  for (let i = bars.length - n; i < bars.length; i++) {
    const b = bars[i]
    const p = (b.high + b.low + b.close) / 3
    r1 += 2 * p - b.low      // R1 上方压力
    s1 += 2 * p - b.high     // S1 下方支撑
  }
  return { r1: r1 / n, s1: s1 / n }
}

/**
 * 摆动高低点（Swing Highs / Lows）——找结构性压力支撑
 * 以 k 根为半窗口，找局部极值；再按与现价的距离取最近的上/下方档位
 */
function swingLevels(bars, k) {
  const highs = [], lows = []
  for (let i = k; i < bars.length - k; i++) {
    let isH = true, isL = true
    for (let j = i - k; j <= i + k; j++) {
      if (j === i) continue
      if (bars[j].high >= bars[i].high) isH = false
      if (bars[j].low <= bars[i].low) isL = false
    }
    if (isH) highs.push(bars[i].high)
    if (isL) lows.push(bars[i].low)
  }
  return { highs, lows }
}

/**
 * 整数关口（心理关口）——A 股常见的天然压力支撑
 * 按现价量级选刻度：>500 用 50 元档，>100 用 10 元档，>20 用 5 元档，其余 1 元档
 */
function roundLevels(price) {
  const step = price > 500 ? 50 : price > 100 ? 10 : price > 20 ? 5 : 1
  return {
    up: Math.ceil(price / step) * step,
    down: Math.floor(price / step) * step
  }
}

/**
 * 均线位（MA20 / MA60）——趋势型支撑压力，被跌破/站上后角色互换
 */
function maLevels(bars, period) {
  if (bars.length < period) return null
  let s = 0
  for (let i = bars.length - period; i < bars.length; i++) s += bars[i].close
  return s / period
}

const srLevels = computed(() => {
  const bars = srBars.value
  const price = Number(live.value.price ?? info.value.price)
  if (!bars.length || !price || isNaN(price)) return null

  const piv = pivotLevels(bars)
  const sw = swingLevels(bars, 5)
  const rnd = roundLevels(price)
  const ma20 = maLevels(bars, 20)
  const ma60 = maLevels(bars, 60)

  // 上方候选（> 现价）：枢轴 R1、摆动高点、整数关口、上方均线
  const ups = []
  const push = (v, src) => {
    const n = Number(v)
    if (n && !isNaN(n) && n > price * 1.001) ups.push({ v: n, src })
  }
  if (piv) push(piv.r1, '枢轴')
  sw.highs.forEach((h) => push(h, '摆动'))
  push(rnd.up, '整数')
  if (ma20 && ma20 > price) push(ma20, 'MA20')
  if (ma60 && ma60 > price) push(ma60, 'MA60')

  // 下方候选（< 现价）
  const downs = []
  const pushD = (v, src) => {
    const n = Number(v)
    if (n && !isNaN(n) && n < price * 0.999) downs.push({ v: n, src })
  }
  if (piv) pushD(piv.s1, '枢轴')
  sw.lows.forEach((l) => pushD(l, '摆动'))
  pushD(rnd.down, '整数')
  if (ma20 && ma20 < price) pushD(ma20, 'MA20')
  if (ma60 && ma60 < price) pushD(ma60, 'MA60')

  // 去重合并（1% 内视为同一档位，取更近现价的代表值，来源合并）
  const dedupe = (arr, asc) => {
    const sorted = arr.slice().sort((a, b) => asc ? a.v - b.v : b.v - a.v)
    const out = []
    for (const it of sorted) {
      const hit = out.find((o) => Math.abs(o.v - it.v) / price < 0.01)
      if (hit) { if (!hit.src.includes(it.src)) hit.src += '/' + it.src }
      else out.push({ v: it.v, src: it.src })
    }
    return out
  }
  const upList = dedupe(ups, true)     // 近 -> 远
  const downList = dedupe(downs, false)

  const near = (list, n) => (list.length >= n ? Math.round(list[n - 1].v * 100) / 100 : null)
  return {
    pressure: near(upList, 1),        // 上方压力（最近）
    pressure2: near(upList, 2),       // 上方次压力
    support: near(downList, 1),       // 下方支撑（最近）
    support2: near(downList, 2),      // 下方强支撑（次近）
    price
  }
})

// 综合压力支撑一行展示（并为一列：4 项 2 行 2 列）
const srList = computed(() => {
  const s = srLevels.value
  if (!s) {
    return [
      { label: '上方压力', value: '—', c: '' },
      { label: '下方支撑', value: '—', c: '' },
      { label: '次压力', value: '—', c: '' },
      { label: '强支撑', value: '—', c: '' }
    ]
  }
  const p = s.price
  const cl = (v) => (v === null ? '' : v > p ? 'up' : v < p ? 'down' : 'flat')
  return [
    { label: '上方压力', value: fmt(s.pressure), c: cl(s.pressure) || 'up' },
    { label: '下方支撑', value: fmt(s.support), c: cl(s.support) || 'down' },
    { label: '次压力', value: fmt(s.pressure2), c: 'up' },
    { label: '强支撑', value: fmt(s.support2), c: 'down' }
  ]
})

// 关键指标（腾讯自选股风格，四列一组，共 21 + 4 = 25 项）
const kvList = computed(() => {
  const L = live.value
  const I = info.value
  const g = (k) => (L[k] !== null && L[k] !== undefined && L[k] !== '' ? L[k] : I[k])
  const pre = g('prev_close')
  const cmp = (v) => {
    if (v === null || v === undefined || v === '' || pre === null || pre === undefined) return ''
    return Number(v) > Number(pre) ? 'up' : Number(v) < Number(pre) ? 'down' : 'flat'
  }
  const sp = speedLive.value
  const pc = (v) => (v === null || v === undefined) ? '—' : (v > 0 ? '+' : '') + fmt(v) + '%'
  return [
    { label: '最高', value: fmt(g('high')), c: cmp(g('high')) },
    { label: '今开', value: fmt(g('open')), c: cmp(g('open')) },
    { label: '最低', value: fmt(g('low')), c: cmp(g('low')) },
    { label: '昨收', value: fmt(pre), c: 'flat' },
    { label: '成交量', value: vol(g('volume')) },
    { label: '成交额', value: money(g('amount')) },
    { label: '均价', value: fmt(g('avg_price')), c: cmp(g('avg_price')) },
    { label: '量比', value: fmt(g('volume_ratio')) },
    { label: '换手', value: g('turnover') == null ? '—' : fmt(g('turnover')) + '%' },
    { label: '振幅', value: g('amplitude') == null ? '—' : fmt(g('amplitude')) + '%' },
    { label: '涨速(实)', value: sp === null ? '—' : pc(sp), c: sp > 0 ? 'up' : sp < 0 ? 'down' : '' },
    { label: '涨停', value: fmt(g('limit_up')), c: 'up' },
    { label: '跌停', value: fmt(g('limit_down')), c: 'down' },
    { label: '外盘', value: vol(g('outer')), c: 'up' },
    { label: '内盘', value: vol(g('inner')), c: 'down' },
    { label: '市盈(静)', value: fmt(g('pe_static')) },
    { label: '市盈(TTM)', value: fmt(g('pe_ttm')) },
    { label: '总市值', value: money(g('total_mcap')) },
    { label: '流通市值', value: money(g('float_mcap')) },
    { label: '总股本', value: shares(g('total_shares')) },
    { label: '流通股', value: shares(g('float_shares')) },
    // 第四列：多算法融合的压力/支撑（枢轴点 + 摆动高低点 + 整数关口 + 均线）
    ...srList.value
  ]
})

const metricList = computed(() => {
  const last = indRows.value[indRows.value.length - 1]
  if (!last) return []
  return [
    { label: 'MA5', value: fmt(last.ma5) },
    { label: 'MA10', value: fmt(last.ma10) },
    { label: 'MA20', value: fmt(last.ma20) },
    { label: 'MA60', value: fmt(last.ma60) },
    { label: 'MACD', value: fmt(last.macd) },
    { label: 'DIF', value: fmt(last.dif) },
    { label: 'DEA', value: fmt(last.dea) },
    { label: 'KDJ-K', value: fmt(last.k) },
    { label: 'KDJ-D', value: fmt(last.d) },
    { label: 'RSI6', value: fmt(last.rsi6) },
    { label: 'RSI14', value: fmt(last.rsi14) },
    { label: 'BOLL中轨', value: fmt(last.boll_mid) }
  ]
})

const minuteMeta = computed(() => {
  const pts = minuteData.value.points || []
  if (!pts.length) return '暂无分时数据'
  return '分时 ' + minuteData.value.date + '  ' + pts.length + ' 点'
})

// 图例统计
const markCount = computed(() => Object.keys(tradeMarks.value).length)
const buyCount = computed(() => {
  let n = 0
  Object.values(tradeMarks.value).forEach((arr) =>
    arr.forEach((x) => { if (x.type === 'B') n++ }))
  return n
})
const sellCount = computed(() => {
  let n = 0
  Object.values(tradeMarks.value).forEach((arr) =>
    arr.forEach((x) => { if (x.type === 'S') n++ }))
  return n
})

// ---------- K 线图 ----------
const UP = '#e64545'
const DOWN = '#2fa36b'
const FLAT = '#8a94a6'

// 自定义覆盖物：B/S 交易标记（圆角方块 + 文字）
// extendData: { type: 'B' | 'S', label: string, price: number, ts: number }
//
// ⚠️ klinecharts 9.8.10 契约要点（读源码 dist/umd/klinecharts.js 确认）：
//   1. createPointFigures 回调里的 bounding 只有 width/height 是真的，
//      top/bottom/left/right 恒为 0 —— 不能用它们做钳位，否则算出负数。
//   2. figure type 'polygon' 的 attrs.coordinates 必须是 [{x,y}] 对象数组
//      （源码 ctx.moveTo(coordinates[0].x, ...)）；传 [x,y] 数组会画出空白。
//      因此这里直接用 'rect'（attrs: {x,y,width,height}），更稳且原生支持圆角。
//   3. type 'text' 会在文字后面自动画一个背景矩形，颜色取 styles.backgroundColor；
//      不传则回退 'currentColor'，会把画布当前的蓝色带出来 —— 必须显式给色。
//   4. 'rect' 的 borderRadius 在非 Fill 样式下会被置 0，所以 fill 与圆角要配齐。
const TRADE_MARK = 'mhTradeMark'

registerOverlay({
  name: TRADE_MARK,
  totalStep: 2,
  lock: true,
  needDefaultPointFigure: false,
  needDefaultXAxisFigure: false,
  needDefaultYAxisFigure: false,
  createPointFigures: ({ overlay, coordinates, bounding }) => {
    if (!coordinates.length) return []
    const d = overlay.extendData || {}
    const isBuy = d.type === 'B'
    const color = isBuy ? UP : DOWN
    // ⚠️ 直接用框架换算好的 coordinates（point.dataIndex/value → 像素，已含
    // timestamp→dataIndex 转换）。不要自己调 xAxis.convertToPixel(ts)——
    // 9.8.10 的 x 轴 convertToPixel 接收的是 dataIndex，传时间戳会飞出画布。
    const x = coordinates[0].x
    const y = coordinates[0].y
    if (isNaN(x) || isNaN(y)) return []

    const w = 22
    const h = 16
    const PANE_W = bounding.width || 600
    const PANE_H = bounding.height || 400
    // 买：标在蜡烛下方；卖：标在蜡烛上方（用 pane 宽高做钳位，保证不出画布）
    const cy = isBuy ? Math.min(PANE_H - h / 2 - 1, y + 9 + h / 2)
                     : Math.max(h / 2 + 1, y - 9 - h / 2)
    const cx = Math.max(w / 2, Math.min(PANE_W - w / 2, x))
    const rx = cx - w / 2
    const ry = cy - h / 2

    return [
      {
        type: 'rect',
        attrs: { x: rx, y: ry, width: w, height: h },
        styles: { style: 'fill', color, borderRadius: 3 }
      },
      {
        type: 'text',
        attrs: { x: cx, y: cy, text: d.label || d.type, align: 'center', baseline: 'middle' },
        styles: { color: '#fff', size: 11, weight: 'bold', family: 'sans-serif',
                  backgroundColor: 'transparent' }
      }
    ]
  }
})

// 自定义覆盖物：买价标签（黑底白字小标签，贴在虚线上方左侧）
// extendData: { text: string, kind: string, price: number, ts: number }
const BUY_TAG = 'mhBuyTag'

registerOverlay({
  name: BUY_TAG,
  totalStep: 2,
  lock: true,
  needDefaultPointFigure: false,
  needDefaultXAxisFigure: false,
  needDefaultYAxisFigure: false,
  createPointFigures: ({ overlay, coordinates, bounding }) => {
    if (!coordinates.length) return []
    const text = (overlay.extendData && overlay.extendData.text) || ''
    // ⚠️ 直接用框架换算好的 coordinates[0].y（= 点 value 的像素位置，与虚线同一
    // 数据源，天然贴合）。bounding 只有 height/width 可用。
    const y = coordinates[0].y
    if (isNaN(y)) return []

    // 文本宽度按 11px sans-serif 估算：中文 ≈ 11px/字，数字/字母 ≈ 6.2px/字
    let textW = 0
    for (const ch of text) textW += /[\u4e00-\u9fa5]/.test(ch) ? 11 : 6.2
    const w = Math.min(Math.round(textW) + 14, 180)
    const h = 17
    const PANE_H = bounding.height || 400
    const x = 4
    const yy = Math.max(1, Math.min(PANE_H - h - 1, y - h - 3))

    return [
      {
        type: 'rect',
        attrs: { x, y: yy, width: w, height: h },
        styles: { style: 'fill', color: '#111', borderRadius: 3 }
      },
      {
        type: 'text',
        attrs: { x: x + w / 2, y: yy + h / 2, text, align: 'center', baseline: 'middle' },
        styles: { color: '#fff', size: 11, weight: 'bold', family: 'sans-serif',
                  backgroundColor: 'transparent' }
      }
    ]
  }
})

function createKline() {
  if (!klineEl.value || kChart) return
  kChart = init(klineEl.value)
  kChart.setStyles({
    grid: { horizontal: { color: '#eef0f3' }, vertical: { color: '#eef0f3' } },
    candle: {
      bar: {
        upColor: UP, downColor: DOWN, noChangeColor: FLAT,
        upBorderColor: UP, downBorderColor: DOWN, noChangeBorderColor: FLAT,
        upWickColor: UP, downWickColor: DOWN, noChangeWickColor: FLAT
      },
      priceMark: { high: { color: UP }, low: { color: DOWN } },
      tooltip: { text: { color: '#5a6472' } }
    },
    indicator: {
      bars: [{ upColor: UP, downColor: DOWN }],
      lines: [{ color: '#ba7517' }, { color: '#378add' }, { color: '#7f77dd' }]
    },
    xAxis: { axisLine: { color: '#e6e8ec' }, tickText: { color: '#8a94a6' } },
    yAxis: { axisLine: { color: '#e6e8ec' }, tickText: { color: '#8a94a6' } },
    separator: { color: '#e6e8ec' },
    crosshair: {
      horizontal: { line: { color: '#8a94a6' } },
      vertical: { line: { color: '#8a94a6' } }
    }
  })
}

function parseTs(s) {
  // 支持 "2026-09-21"、"2026-09-21 11:30"、"202609211130"
  const str = String(s)
  if (/^\d{12}$/.test(str)) {
    return new Date(`${str.slice(0,4)}/${str.slice(4,6)}/${str.slice(6,8)} ` +
                    `${str.slice(8,10)}:${str.slice(10,12)}`).getTime()
  }
  if (/^\d{8}$/.test(str)) {
    return new Date(`${str.slice(0,4)}/${str.slice(4,6)}/${str.slice(6,8)}`).getTime()
  }
  return new Date(str.replace(/-/g, '/')).getTime()
}

async function loadChart() {
  if (!kChart) return
  try {
    const r = await api.get('/kline', {
      params: {
        symbol: symbol.value, period: view.value,
        adjust: adjust.value, limit: 600
      }
    })
    src.value = r.source
    const bars = (r.data || []).map((b) => ({
      timestamp: parseTs(b.trade_date),
      open: Number(b.open), high: Number(b.high),
      low: Number(b.low), close: Number(b.close),
      volume: Number(b.volume)
    })).filter((b) => !isNaN(b.timestamp))
    bars.sort((a, b) => a.timestamp - b.timestamp)
    kChart.applyNewData(bars)
    applyIndicators()
    drawOverlays(bars)
  } catch (e) { console.error('K线加载失败', e) }
}

// ---------- K 线覆盖物：买价虚线 + B/S 标记 ----------
const OVERLAY_GROUP = 'mh_position'
// klinecharts 的 createOverlay(value, paneId)：必须显式指定 'candle_pane'（主图），
// 否则 overlay 的 paneId 为 undefined，绘制管线匹配不到面板 -> createPointFigures 永不触发
const MAIN_PANE = 'candle_pane'

function clearOverlays() {
  if (!kChart) return
  try {
    kChart.removeOverlay({ groupId: OVERLAY_GROUP })
  } catch (e) {
    try { kChart.removeOverlay() } catch (e2) {}
  }
}

// 把日期（YYYY-MM-DD）落到最接近的 K 线 dataIndex 上
function findIndexByDate(bars, date) {
  if (!bars.length || !date) return -1
  const d = String(date).slice(0, 10)
  const target = new Date(d.replace(/-/g, '/')).getTime()
  if (isNaN(target)) return -1
  // K 线周期可能是日/周/月，取「包含该日期的那根」= 最后一个 timestamp <= target
  let idx = -1
  for (let i = 0; i < bars.length; i++) {
    if (bars[i].timestamp <= target) idx = i
    else break
  }
  if (idx >= 0) return idx
  // 日期早于第一根 K 线：退回最近一根
  return bars[0].timestamp > target ? 0 : bars.length - 1
}

function drawOverlays(bars) {
  if (!kChart || !bars || !bars.length) return
  clearOverlays()

  // 1) 买价 / 均价黑色虚线（贯穿全图）
  const bl = buyLine.value
  if (bl && bl.price) {
    try {
      kChart.createOverlay({
        name: 'horizontalStraightLine',
        groupId: OVERLAY_GROUP,
        lock: true,
        points: [{ dataIndex: 0, value: bl.price }],
        styles: {
          line: { color: '#111', style: 'dashed', size: 1.2, dashedValue: [5, 4] },
          text: {
            color: '#111',
            size: 11,
            backgroundColor: 'rgba(255,255,255,.9)',
            borderColor: '#111',
            borderSize: 0.6,
            paddingLeft: 4, paddingRight: 4, paddingTop: 2, paddingBottom: 2
          }
        }
      }, MAIN_PANE)
    } catch (e) { console.warn('买价线绘制失败', e) }
    // 文字标识（画在最后一根 K 线处，"买价 1215.00" / "均价 1253.50"）
    try {
      kChart.createOverlay({
        name: BUY_TAG,
        groupId: OVERLAY_GROUP,
        lock: true,
        points: [{ dataIndex: bars.length - 1, value: bl.price }],
        extendData: {
          text: `${bl.label} ${bl.price.toFixed(2)}`,
          kind: bl.kind,
          price: bl.price,
          ts: bars[bars.length - 1].timestamp
        }
      }, MAIN_PANE)
    } catch (e) { console.warn('买价标签绘制失败', e) }
  }

  // 2) B / S 交易标记
  const marks = tradeMarks.value
  const keys = Object.keys(marks)
  if (!keys.length) return
  keys.forEach((d) => {
    const idx = findIndexByDate(bars, d)
    if (idx < 0) return
    const bar = bars[idx]
    marks[d].forEach((m) => {
      const isBuy = m.type === 'B'
      // 买标在最低价下方，卖标在最高价上方
      const price = isBuy ? bar.low : bar.high
      try {
        kChart.createOverlay({
          name: TRADE_MARK,
          groupId: OVERLAY_GROUP,
          lock: true,
          points: [{ dataIndex: idx, value: price }],
          extendData: { type: m.type, label: m.type, price, ts: bar.timestamp }
        }, MAIN_PANE)
      } catch (e) { console.warn('交易标记绘制失败', e) }
    })
  })
}

function applyIndicators() {
  if (!kChart) return
  const all = ['MA', 'VOL', 'MACD', 'KDJ', 'RSI', 'BOLL']
  all.forEach((name) => {
    try { kChart.removeIndicator('candle_pane', name) } catch (e) {}
    try { kChart.removeIndicator(name) } catch (e) {}
  })
  indicators.value.forEach((name) => {
    try {
      if (name === 'MA' || name === 'BOLL') {
        kChart.createIndicator(name, true, { id: 'candle_pane' })
      } else {
        kChart.createIndicator(name, false, {
          id: 'pane_' + name, height: name === 'VOL' ? 70 : 90
        })
      }
    } catch (e) { console.warn('指标创建失败', name, e) }
  })
}

// ---------- 分时图 ----------
const minuteData = ref({ points: [], prev_close: null, date: '' })

function createMinute() {
  if (!minuteEl.value || mChart) return
  mChart = echarts.init(minuteEl.value)
  mChart.setOption(baseMinuteOption())
  window.addEventListener('resize', resizeCharts)
}

function baseMinuteOption() {
  return {
    animation: false,
    grid: [
      { left: 58, right: 62, top: 18, height: '56%' },
      { left: 58, right: 62, top: '78%', height: '16%' }
    ],
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(255,255,255,.96)',
      borderColor: '#e6e8ec',
      textStyle: { color: '#1a1a2e', fontSize: 12 },
      formatter: (ps) => {
        if (!ps || !ps.length) return ''
        const i = ps[0].dataIndex
        const p = (minuteData.value.points || [])[i]
        if (!p) return ''
        const t = p.time.replace(/^(\d{2})(\d{2})$/, '$1:$2')
        return `${t}<br/>价格 <b>${p.price.toFixed(2)}</b><br/>` +
               `均价 ${p.avg.toFixed(2)}<br/>` +
               (p.change_pct === null ? '' :
                 `涨跌 <b>${p.change_pct > 0 ? '+' : ''}${p.change_pct}%</b><br/>`) +
               `成交量 ${p.volume}`
      }
    },
    xAxis: [
      {
        type: 'category', gridIndex: 0, boundaryGap: false,
        data: [], axisLine: { lineStyle: { color: '#e6e8ec' } },
        axisLabel: { color: '#8a94a6', fontSize: 11, interval: 29 },
        axisTick: { show: false }, splitLine: { show: false }
      },
      {
        type: 'category', gridIndex: 1, boundaryGap: false,
        data: [], axisLine: { lineStyle: { color: '#e6e8ec' } },
        axisLabel: { show: false }, axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    yAxis: [
      {
        gridIndex: 0, scale: true, position: 'left',
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: '#8a94a6', fontSize: 11,
                     formatter: (v) => v.toFixed(2) },
        splitLine: { lineStyle: { color: '#eef0f3' } }
      },
      {
        gridIndex: 0, scale: true, position: 'right',
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: {
          color: '#8a94a6', fontSize: 11,
          formatter: (v, i) => {
            const pre = minuteData.value.prev_close
            if (!pre) return ''
            return ((v - pre) / pre * 100).toFixed(2) + '%'
          }
        },
        splitLine: { show: false }
      },
      {
        gridIndex: 1, scale: true, position: 'left',
        axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: '#8a94a6', fontSize: 10 },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '价格', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: [], showSymbol: false, lineStyle: { width: 1.4, color: '#185fa5' },
        areaStyle: { color: 'rgba(24,95,165,.13)' },
        markLine: buyMarkLine()
      },
      {
        name: '均价', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: [], showSymbol: false,
        lineStyle: { width: 1.1, color: '#ba7517', type: 'solid' }
      },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 2,
        data: [],
        itemStyle: {
          color: (p) => {
            const pts = minuteData.value.points || []
            const cur = pts[p.dataIndex]
            const prev = pts[p.dataIndex - 1]
            if (!cur || !prev) return '#8a94a6'
            return cur.price >= prev.price ? UP : DOWN
          }
        }
      }
    ]
  }
}

async function loadMinute() {
  if (!mChart) return
  try {
    const r = await api.get('/minute', { params: { symbol: symbol.value } })
    const d = r.data || {}
    src.value = 'tencent'
    minuteData.value = {
      points: d.points || [],
      prev_close: d.prev_close,
      date: d.date || ''
    }
    const pts = minuteData.value.points
    const times = pts.map((p) => p.time.replace(/^(\d{2})(\d{2})$/, '$1:$2'))
    const pre = d.prev_close
    // 买价虚线需要落在可视范围内
    const bl = buyLine.value
    const bp = bl && bl.price ? [bl.price] : []

    mChart.setOption({
      xAxis: [{ data: times }, { data: times }],
      yAxis: pre ? [{
        scale: false,
        min: Math.min(pre * 0.985, ...pts.map((p) => p.price), ...bp),
        max: Math.max(pre * 1.015, ...pts.map((p) => p.price), ...bp)
      }, {}, {}] : [{ scale: true }, {}, {}],
      series: [
        { data: pts.map((p) => p.price), markLine: buyMarkLine() },
        { data: pts.map((p) => p.avg) },
        { data: pts.map((p) => p.volume) }
      ]
    }, false)
  } catch (e) { console.error('分时加载失败', e) }
}

// 分时图买价虚线（黑色虚线 + 文字标识）
function buyMarkLine() {
  const bl = buyLine.value
  if (!bl || !bl.price) return { data: [] }
  return {
    silent: true,
    symbol: ['none', 'none'],
    precision: 2,
    lineStyle: { color: '#111', type: 'dashed', width: 1.2, opacity: 0.85 },
    label: {
      show: true,
      position: 'insideEndTop',
      formatter: `${bl.label} ${bl.price.toFixed(2)}`,
      color: '#111',
      fontSize: 11,
      backgroundColor: 'rgba(255,255,255,.85)',
      padding: [2, 4],
      borderRadius: 3
    },
    data: [{ yAxis: bl.price }]
  }
}

function resizeCharts() {
  try { mChart && mChart.resize() } catch (e) {}
}

// ---------- 视图切换 ----------
async function onViewChange() {
  if (isKline.value) {
    await nextTick()
    createKline()
    await loadChart()
    kChart && kChart.resize()
  } else {
    await nextTick()
    createMinute()
    await loadMinute()
    mChart && mChart.resize()
  }
}

// ---------- 行情 ----------
async function loadQuote() {
  try {
    const r = await api.get('/quote/' + symbol.value)
    info.value = r.data || {}
  } catch (e) { console.error(e) }
}

async function loadLive() {
  try {
    const r = await api.get('/quote', { params: { symbols: symbol.value } })
    src.value = r.source
    const row = (r.data || [])[0]
    if (row) live.value = row
  } catch (e) { /* 静默 */ }
}

async function loadIndicator() {
  try {
    const r = await api.get('/indicator', {
      params: { symbol: symbol.value, limit: 300 }
    })
    indRows.value = r.data || []
  } catch (e) { console.error(e) }
}

// 持仓数据：用于买价虚线 + B/S 标记
async function loadPosition() {
  const sym = symbol.value
  const mine = (r) => String(r.symbol) === String(sym)
  try {
    const [po, pc] = await Promise.all([
      api.get('/portfolio'),
      api.get('/portfolio/closed')
    ])
    holding.value = ((po.data && po.data.open) || []).find(mine) || null
    closedRows.value = ((pc.data) || []).filter(mine)
  } catch (e) {
    holding.value = null
    closedRows.value = []
  }
}

// ---------- 轮询控制 ----------
function startPolling() {
  stopPolling()
  timer = setInterval(async () => {
    if (document.hidden) return          // 后台不刷
    await loadLive()
    if (isKline.value) {
      // 分钟级 K 线盘中变化快，一并刷新
      if (view.value.endsWith('min')) await loadChart()
    } else {
      await loadMinute()
    }
  }, POLL_MS)
}

function stopPolling() {
  if (timer) { clearInterval(timer); timer = null }
}

function togglePolling() {
  polling.value = !polling.value
  polling.value ? startPolling() : stopPolling()
}

function onVisibility() {
  if (!polling.value) return
  if (document.hidden) { stopPolling() } else { startPolling() }
}

// 压力/支撑专用的日K数据（与当前查看周期无关，固定取日K，保证算法口径稳定）
async function loadSrBars() {
  try {
    const r = await api.get('/kline', {
      params: { symbol: symbol.value, period: 'daily', adjust: 'qfq', limit: 160 }
    })
    srBars.value = (r.data || []).map((b) => ({
      high: Number(b.high), low: Number(b.low), close: Number(b.close)
    })).filter((b) => !isNaN(b.high) && !isNaN(b.low) && !isNaN(b.close))
  } catch (e) {
    srBars.value = []
  }
}

async function loadAll() {
  await Promise.all([loadQuote(), loadLive(), loadIndicator(), loadPosition(),
                     loadSrBars(), loadCompany()])
  await onViewChange()
}

// ---------- 公司信息（F10） ----------
const co = ref({})
const loadingCo = ref(false)
const coErr = ref('')

async function loadCompany() {
  loadingCo.value = true
  coErr.value = ''
  try {
    const r = await api.get('/company/' + symbol.value)
    co.value = r.data || {}
    if (r.org_err) coErr.value = r.org_err
  } catch (e) {
    co.value = {}
    coErr.value = (e.response && e.response.data && e.response.data.detail) || '公司信息获取失败'
  } finally {
    loadingCo.value = false
  }
}

// 数值格式化（空值统一显示 —）
function coNum(v, unit) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return String(v)
  const s = Math.abs(n) >= 1000
    ? n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
    : String(Math.round(n * 100) / 100)
  return unit ? s + ' ' + unit : s
}
function money2(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (Math.abs(n) >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(2)
}
function webUrl(w) {
  const s = String(w).trim()
  return /^https?:\/\//i.test(s) ? s : 'http://' + s
}

// 公司性质：依据「实际控制人」推导（东财 F10 ACTUAL_HOLDER）
const nature = computed(() => {
  const c = co.value
  const ah = String(c.actual_holder || '').trim()
  if (ah) {
    if (/国资委|国有资产|国有资|人民政府|财政部|国资|国有/.test(ah)) return '国有控股'
    if (/大学|学院|研究院|研究所|中科院/.test(ah)) return '校企控股'
    if (/外资|境外|香港|欧美|日/.test(ah)) return '外资控股'
    // 自然人名字：单个 2-4 字，或逗号/顿号/空格分隔的多个中文名
    if (/^[\u4e00-\u9fa5]{2,4}([,，、\s]+[\u4e00-\u9fa5]{2,4})*$/.test(ah)) return '民营控股(自然人)'
    if (/民营|私营/.test(ah)) return '民营控股'
    return '混合/其他'
  }
  // 无实控人数据时降级：按公司全称粗判
  if (!c.org_name) return ''
  if (/国有|国资|集团控股/.test(c.org_name)) return '国有控股'
  if (/股份有限公司/.test(c.org_name)) return '民营股份公司'
  return '股份公司'
})

// 市值展示
const bigMkt = computed(() => money2(co.value.quote && co.value.quote.total_mcap))
const floatMkt = computed(() => money2(co.value.quote && co.value.quote.float_mcap))

// 是否龙头：按 总市值 + 行业地位 + 盈利规模 综合判定（无权威口径，为推导结论）
const leaderLabel = computed(() => {
  const c = co.value
  if (!c.name) return ''
  const mcap = Number(c.quote && c.quote.total_mcap) || 0
  const fin = c.finance || []
  const latest = fin[0] || {}
  const np = Number(latest.net_profit) || 0
  const roe = Number(latest.roe) || 0

  if (mcap >= 1e11) return '行业龙头'
  if (mcap >= 2e10 && np >= 5e8 && roe >= 10) return '细分龙头'
  if (mcap >= 5e9 && np > 0) return '区域/细分领先'
  if (np > 0) return '非龙头'
  return '暂无判定'
})
const leaderCls = computed(() => {
  const l = leaderLabel.value
  if (l === '行业龙头') return 'up'
  if (l === '细分龙头' || l === '区域/细分领先') return 'warn'
  return 'flat'
})

// 盈利评级
const profitGrade = computed(() => {
  const f = co.value.finance
  if (!f || !f.length) return '—'
  let score = 0
  const l = f[0]
  if (Number(l.net_profit) > 0) score += 2
  if (Number(l.revenue_yoy) > 0) score += 1
  if (Number(l.net_profit_yoy) > 0) score += 1
  if (Number(l.roe) >= 10) score += 1
  if (f.length > 1 && Number(f[0].net_profit) > Number(f[1].net_profit)) score += 1
  if (score >= 5) return '优秀'
  if (score >= 3) return '良好'
  if (score >= 2) return '一般'
  return '偏弱'
})
const profitCls = computed(() => {
  const g = profitGrade.value
  if (g === '优秀' || g === '良好') return 'up'
  if (g === '一般') return 'warn'
  return 'down'
})
const profitDesc = computed(() => {
  const f = co.value.finance
  if (!f || !f.length) return '暂无财务数据'
  const l = f[0]
  const p = []
  p.push(Number(l.net_profit) > 0 ? '最新报告期已实现盈利' : '最新报告期尚未盈利')
  p.push('营收同比 ' + chgPct(l.revenue_yoy) + '，净利同比 ' + chgPct(l.net_profit_yoy))
  if (Number(l.roe) >= 10) p.push('ROE ' + coNum(l.roe) + '%，盈利质量较好')
  if (Number(l.debt_ratio) >= 70) p.push('资产负债率 ' + coNum(l.debt_ratio) + '%，负债偏高')
  return p.join('；') + '。'
})

// 一句话公司画像
const coSummary = computed(() => {
  const c = co.value
  if (!c.name) return ''
  const seg = []
  if (c.industry_em) seg.push(c.industry_em.split('-').slice(0, 2).join('·'))
  if (nature.value) seg.push(nature.value)
  if (c.province) seg.push(c.province + '企业')
  if (c.emp_num) seg.push('员工 ' + Number(c.emp_num).toLocaleString('zh-CN') + ' 人')
  let s = seg.join('，')
  if (c.quote && c.quote.total_mcap) s += '，总市值 ' + money2(c.quote.total_mcap)
  s += '。'
  if (leaderLabel.value && leaderLabel.value !== '暂无判定') s += leaderLabel.value + '，'
  const f = c.finance
  if (f && f.length) {
    s += '最新报告期 ' + f[0].report_date + ' 营收 ' + money2(f[0].revenue) +
      '、净利 ' + money2(f[0].net_profit) + '，盈利评级' + profitGrade.value + '。'
  }
  return s
})

onMounted(async () => {
  await nextTick()
  createMinute()
  await loadAll()
  startPolling()
  document.addEventListener('visibilitychange', onVisibility)
})

onUnmounted(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', onVisibility)
  window.removeEventListener('resize', resizeCharts)
  if (kChart) { try { dispose(klineEl.value) } catch (e) {} kChart = null }
  if (mChart) { try { mChart.dispose() } catch (e) {} mChart = null }
})

watch(() => symbol.value, loadAll)
</script>

<style scoped>
/* ---- 头部：左价格块 + 右关键指标网格 ---- */
.quote-head {
  padding: 14px 18px; margin-bottom: 12px;
  display: flex; gap: 28px; flex-wrap: wrap; align-items: stretch;
}
.qh-left { min-width: 218px; display: flex; flex-direction: column; justify-content: center; gap: 2px; }
h2 { font-size: 17px; margin: 0 0 2px; font-weight: 600; display: inline-block; }
.code { font-size: 12px; color: #8a94a6; margin-left: 6px; }
.priceline { display: flex; align-items: baseline; gap: 12px; }
.big { font-size: 34px; font-weight: 700; line-height: 1.1; }
.chg { font-size: 13px; display: flex; gap: 8px; }
.live { display: flex; align-items: center; gap: 6px; margin-top: 4px; }
.live-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #c9ced6; display: inline-block;
}
.live-dot.on { background: #2fa36b; box-shadow: 0 0 0 3px rgba(47,163,107,.15); }
.live-txt { font-size: 11px; color: #a8adb6; }
.src { font-size: 11px; color: #a8adb6; margin-left: 4px; }

.qh-metrics {
  flex: 1; min-width: 660px; max-width: 900px;
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0 20px;
  align-content: center;
  grid-auto-flow: column;
  grid-template-rows: repeat(7, auto);
}
.kv {
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 3.5px 0; border-bottom: 1px dashed #f0f2f6;
  gap: 8px;
}
.kv:nth-last-child(-n+4) { border-bottom: none; }
.mk { font-size: 12px; color: #8a94a6; white-space: nowrap; }
.mv { font-size: 13px; font-weight: 500; }

/* ---- 主体 ---- */
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 230px; gap: 12px; }
.chart-card { background: #fff; border: 1px solid #e8ecf2; border-radius: 10px; padding: 10px 12px; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.spacer { flex: 1; }
.lbl { font-size: 12px; color: #8a94a6; }
.chart { width: 100%; height: 520px; }

/* ---- 持仓联动图例 ---- */
.legend {
  display: flex; align-items: center; gap: 7px; flex-wrap: wrap;
  padding: 7px 4px 2px; border-top: 1px dashed #eef0f3; margin-top: 4px;
  font-size: 12px; color: #5a6472;
}
.lg-line {
  width: 26px; height: 0; border-top: 1.4px dashed #111; flex: none;
}
.lg-txt { font-size: 12px; color: #5a6472; }
.lg-hint { font-size: 11px; color: #a8adb6; }
.lg-tag {
  display: inline-block; min-width: 16px; text-align: center;
  font-size: 10px; font-weight: 700; color: #fff;
  border-radius: 3px; padding: 0 4px; line-height: 16px;
}
.lg-tag.b { background: #e64545; }
.lg-tag.s { background: #2fa36b; margin-left: 6px; }
.side { display: flex; flex-direction: column; gap: 12px; }
.panel { background: #fff; border: 1px solid #e8ecf2; border-radius: 10px; padding: 12px 14px; }
.panel-title { font-size: 13px; font-weight: 500; margin-bottom: 10px; }
.metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 10px; }
.metric .k { font-size: 11px; color: #8a94a6; }
.metric .v { font-size: 13px; }

/* ---- 持仓面板 ---- */
.pos-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 10px; }
.pm { display: flex; flex-direction: column; gap: 2px; }
.pm .k { font-size: 11px; color: #8a94a6; }
.pm b { font-size: 13px; }
.pos-lots {
  margin-top: 10px; padding-top: 8px; border-top: 1px dashed #f0f2f6;
  display: flex; flex-direction: column; gap: 5px;
}
.pl { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #5a6472; }
.pl.muted { color: #8a94a6; }
.pd { color: #8a94a6; }
.tag {
  display: inline-block; min-width: 15px; text-align: center;
  font-size: 10px; font-weight: 700; color: #fff;
  border-radius: 3px; padding: 0 3px; line-height: 15px;
}
.tag.b { background: #e64545; }
.tag.s { background: #2fa36b; }
.tag.sm { min-width: 13px; line-height: 13px; font-size: 9px; }
.tip { margin-top: 10px; font-size: 11px; color: #a8adb6; line-height: 1.7; }

/* ==================== 公司信息卡片 ==================== */
.co-card { margin-top: 12px; padding: 14px 18px 16px; }
.co-head { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; margin-bottom: 12px; }
.co-title { display: flex; align-items: center; gap: 9px; min-width: 0; }
.co-title .bar { width: 3px; height: 15px; border-radius: 2px; background: #1485fe; }
.co-title h3 { margin: 0; font-size: 14px; font-weight: 600; color: #0b1c33; }
.co-sub {
  font-size: 12px; color: #8a94a6;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 420px;
}
.co-chips { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  font-size: 11px; color: #5a6472; background: #f3f5f9;
  border: 1px solid #e6eaf1; border-radius: 4px; padding: 2px 9px;
}
.chip.up { color: #e64545; background: #fdeeee; border-color: #f8d4d4; }
.chip.warn { color: #d98a1a; background: #fdf6e8; border-color: #f5e3bf; }
.chip.flat { color: #8a94a6; }

.co-empty { padding: 22px; text-align: center; color: #a3adba; font-size: 13px; }
.co-empty.sm { padding: 14px; font-size: 12px; }
.co-err { color: #e64545; font-size: 11px; }

.co-verdict {
  padding: 9px 12px; border-radius: 8px; margin-bottom: 12px;
  background: linear-gradient(90deg, #f5f9ff, #fbfdff); border: 1px solid #e3edfb;
}
.v-label {
  display: inline-block; font-size: 11px; color: #1485fe; font-weight: 600;
  background: #fff; border: 1px solid #d6e6ff; border-radius: 4px;
  padding: 1px 7px; margin-right: 8px;
}
.v-text { font-size: 12.5px; color: #33404f; line-height: 1.75; }

.co-cols {
  display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); gap: 18px;
}
@media (max-width: 1100px) { .co-cols { grid-template-columns: 1fr; } }

.blk-t {
  font-size: 12.5px; font-weight: 600; color: #0b1c33; margin-bottom: 9px;
  display: flex; align-items: center; gap: 8px;
}
.blk-t::before {
  content: ''; width: 3px; height: 12px; border-radius: 2px; background: #1485fe;
}
.blk-sub { font-size: 11px; color: #a3adba; font-weight: 400; }

.kv-grid {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1px;
  background: #eef2f7; border: 1px solid #eef2f7; border-radius: 8px; overflow: hidden;
}
@media (max-width: 1400px) { .kv-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 900px) { .kv-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.kv { background: #fff; padding: 7px 10px; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.kv.wide { grid-column: span 2; }
.kv span { font-size: 11px; color: #a3adba; }
.kv b { font-size: 12.5px; color: #1a1a2e; font-weight: 600; word-break: break-all; }
.kv b a { color: #1485fe; text-decoration: none; }

.fin { width: 100%; border-collapse: collapse; font-size: 12px; }
.fin th {
  background: #f7f9fc; color: #5a6472; font-weight: 600; text-align: right;
  padding: 7px 9px; border-bottom: 1px solid #eef2f7; white-space: nowrap;
}
.fin th:first-child { text-align: left; }
.fin td { padding: 7px 9px; text-align: right; border-bottom: 1px solid #f2f5fa; color: #33404f; }
.fin td:first-child { text-align: left; color: #5a6472; }
.fin tbody tr:hover { background: #fafcff; }
.fin-note { margin-top: 9px; font-size: 11.5px; color: #5a6472; line-height: 1.7; }
.fin-note .grade {
  display: inline-block; font-weight: 700; border-radius: 4px;
  padding: 1px 8px; margin-right: 7px; font-size: 11px;
}
.fin-note .grade.up { color: #e64545; background: #fdeeee; }
.fin-note .grade.warn { color: #d98a1a; background: #fdf6e8; }
.fin-note .grade.down { color: #2fa36b; background: #eaf7f1; }
.fin-note .grade.flat { color: #8a94a6; background: #f3f5f9; }

.co-profile {
  margin: 0; font-size: 12.5px; line-height: 1.85; color: #44506b;
  text-align: justify; max-height: 132px; overflow-y: auto;
}
.co-src { margin-top: 14px; padding-top: 9px; border-top: 1px dashed #eef2f7; font-size: 11px; color: #a3adba; }
</style>
