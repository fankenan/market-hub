<template>
  <div>
    <!-- 指数条 -->
    <div class="idx-bar card">
      <div class="idx" v-for="i in indexes" :key="i.code">
        <span class="in">{{ i.name }}</span>
        <span class="ip mono" :class="cls(i.change_pct)">{{ num(i.price) }}</span>
        <span class="ic mono" :class="cls(i.change_pct)">
          {{ sign(i.change_amt) }} · {{ pct(i.change_pct) }}
        </span>
      </div>
      <span class="idx-hint" v-if="!indexes.length">指数加载中…</span>
    </div>

    <!-- 三榜单 -->
    <div class="rank-grid">
      <div class="card rk" v-for="r in ranks" :key="r.type">
        <div class="rk-head">
          <h3>{{ r.title }}</h3>
          <span class="rk-sub">{{ r.sub }}</span>
        </div>
        <div class="rk-tbl">
          <div class="rk-tr rk-th">
            <span class="c-name">股票名称</span>
            <span class="c-price">{{ r.col }}</span>
            <span class="c-pct">涨跌幅</span>
          </div>
          <div class="rk-tr" v-for="(s, idx) in r.rows" :key="s.symbol"
               @click="go(s.symbol)">
            <span class="c-name">
              <i class="rk-no" :class="{ top: idx < 3 }">{{ idx + 1 }}</i>{{ s.name }}
            </span>
            <span class="c-price mono">{{ num(s.price) }}</span>
            <span class="c-pct mono" :class="cls(s.change_pct)">
              <template v-if="r.type === 'pct'">{{ pct(s.change_pct) }}</template>
              <template v-else-if="r.type === 'vol'">{{ volTxt(s.volume) }}</template>
              <template v-else>{{ money(s.amount) }}</template>
            </span>
          </div>
          <div class="rk-empty" v-if="!r.rows.length && !loading">暂无数据</div>
        </div>
      </div>
    </div>

    <!-- 新股预告 -->
    <div class="card ipo">
      <div class="rk-head">
        <h3>新股预告</h3>
        <router-link to="/ipo" class="more">全部 →</router-link>
      </div>
      <div class="rk-tbl">
        <div class="rk-tr ipo-th">
          <span class="c-name">名称/代码</span>
          <span class="c-mid">申购日</span>
          <span class="c-mid">发行价</span>
          <span class="c-mid">上市日期</span>
        </div>
        <div class="rk-tr ipo-tr" v-for="s in ipoRows" :key="s.symbol" @click="go(s.symbol)">
          <span class="c-name">
            <b>{{ s.name }}</b><i class="ipo-code">{{ s.symbol }}</i>
          </span>
          <span class="c-mid mono">{{ s.apply_date || '—' }}</span>
          <span class="c-mid mono">{{ s.issue_price ? '¥' + num(s.issue_price) : '—' }}</span>
          <span class="c-mid">
            <template v-if="s.list_date">{{ s.list_date }}</template>
            <em class="pend" v-else-if="s.days_left != null">距上市 {{ s.days_left }} 天</em>
            <em class="pend" v-else>招股中</em>
          </span>
        </div>
        <div class="rk-empty" v-if="!ipoRows.length && !loading">近一个月暂无新股</div>
      </div>
    </div>

    <p class="tip" style="margin-top:10px">
      数据来源：东方财富 · 榜单 {{ auto ? '每 ' + interval + ' 秒自动刷新' : '已暂停' }}
      <el-switch v-model="auto" size="small" style="margin-left:8px" />
    </p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api.js'

const router = useRouter()
const indexes = ref([])
const ranks = ref([
  { type: 'pct', title: '涨跌幅榜', sub: '按涨跌幅', col: '现价', rows: [] },
  { type: 'vol', title: '成交量榜', sub: '按成交量', col: '现价', rows: [] },
  { type: 'amt', title: '成交额榜', sub: '按成交额', col: '现价', rows: [] }
])
const ipoRows = ref([])
const loading = ref(true)
const auto = ref(true)
const interval = 15
let timer = null

// ---------- 格式化（涨红跌绿） ----------
const num = (v) => (v === null || v === undefined || v === '' || isNaN(Number(v))) ? '—' : Number(v).toFixed(2)
const cls = (p) => (p > 0 ? 'up' : p < 0 ? 'down' : 'flat')
const pct = (p) => (p === null || p === undefined || p === '' || isNaN(Number(p))) ? '—' : (p > 0 ? '+' : '') + Number(p).toFixed(2) + '%'
const sign = (v) => (v > 0 ? '+' : v < 0 ? '' : '') + num(v)

function volTxt(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿手'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万手'
  return n.toFixed(0) + '手'
}
function money(v) {
  if (v === null || v === undefined || v === '' || isNaN(Number(v))) return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(0)
}

function go(sym) { router.push('/stock/' + sym) }

// ---------- 数据加载 ----------
async function loadIndex() {
  try {
    const r = await api.get('/market/index')
    indexes.value = r.data || []
  } catch (e) { /* 静默，保持旧值 */ }
}

async function loadRank(type) {
  try {
    const r = await api.get('/market/rank', { params: { type, size: 10 } })
    return r.data || []
  } catch (e) { return null }
}

async function loadIpo() {
  try {
    const r = await api.get('/ipo/upcoming', { params: { days: 31 } })
    const rows = r.data || []
    ipoRows.value = rows.slice(0, 6)
  } catch (e) { ipoRows.value = [] }
}

async function loadAll() {
  const [p, v, a] = await Promise.all([loadRank('pct'), loadRank('vol'), loadRank('amt')])
  ranks.value.forEach((rk) => {
    const rows = { pct: p, vol: v, amt: a }[rk.type]
    if (rows !== null) rk.rows = rows
  })
  loading.value = false
}

function startTimer() {
  stopTimer()
  timer = setInterval(() => {
    if (document.hidden) return
    loadIndex()
    loadAll()
  }, interval * 1000)
}
function stopTimer() { if (timer) { clearInterval(timer); timer = null } }

watch(auto, (on) => { on ? startTimer() : stopTimer() })

onMounted(async () => {
  await Promise.all([loadIndex(), loadAll(), loadIpo()])
  startTimer()
})
onUnmounted(stopTimer)
</script>

<style scoped>
/* ---- 指数条 ---- */
.idx-bar {
  display: flex; align-items: center; gap: 34px;
  padding: 10px 18px; margin-bottom: 12px; flex-wrap: wrap;
}
.idx { display: flex; align-items: baseline; gap: 8px; }
.idx .in { font-size: 13px; color: #5a6472; }
.idx .ip { font-size: 17px; font-weight: 600; }
.idx .ic { font-size: 12px; }
.idx-hint { font-size: 12px; color: #a8adb6; }

/* ---- 三榜单 ---- */
.rank-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
@media (max-width: 1000px) { .rank-grid { grid-template-columns: 1fr; } }
.rk { padding: 12px 14px; }
.rk-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 6px; }
.rk-head h3 { margin: 0; font-size: 14px; font-weight: 600; }
.rk-sub { font-size: 11px; color: #a8adb6; }
.more { margin-left: auto; font-size: 12px; color: #1485fe; text-decoration: none; }

.rk-tr {
  display: grid; grid-template-columns: 1fr 80px 86px;
  align-items: center; gap: 8px;
  padding: 5.5px 0; border-bottom: 1px dashed #f0f2f6;
  font-size: 12px; cursor: pointer;
}
.rk-tr:last-child { border-bottom: none; }
.rk-tr:hover { background: #f7f9fc; }
.rk-th { color: #8a94a6; font-size: 11px; cursor: default; }
.rk-th:hover { background: transparent; }
.c-name {
  color: #1f2d3d; white-space: nowrap; overflow: hidden;
  text-overflow: ellipsis; display: flex; align-items: center; gap: 6px;
}
.c-price, .c-pct { text-align: right; }
.c-pct { font-weight: 500; }
.rk-no {
  font-style: normal; font-size: 10px; width: 16px; height: 16px;
  border-radius: 3px; background: #eef2f7; color: #8a94a6;
  display: inline-flex; align-items: center; justify-content: center; flex: none;
}
.rk-no.top { background: #fde8e8; color: #e05656; font-weight: 700; }
.rk-empty { padding: 18px 0; text-align: center; font-size: 12px; color: #a8adb6; }

/* ---- 新股预告 ---- */
.ipo { margin-top: 12px; padding: 12px 14px; }
.ipo .rk-tr { grid-template-columns: 1.3fr 1fr 0.8fr 1fr; cursor: pointer; }
.ipo-th { color: #8a94a6; font-size: 11px; cursor: default; }
.ipo-th .c-mid, .ipo-tr .c-mid { text-align: left; }
.ipo-code { font-style: normal; font-size: 11px; color: #8a94a6; margin-left: 6px; }
.ipo-tr b { font-weight: 500; }
.pend { font-style: normal; font-size: 11px; color: #e0862a; background: #fdf3e7; border-radius: 8px; padding: 1px 7px; }

.up { color: #e03131; }
.down { color: #0ca678; }
.flat { color: #8a94a6; }
.mono { font-variant-numeric: tabular-nums; }
</style>
