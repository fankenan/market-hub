<template>
  <div>
    <div class="head">
      <div>
        <h2>自选看板</h2>
        <p class="meta">
          共 {{ rows.length }} 只 · 更新 {{ updatedAt || '—' }}
          <span class="dot" :class="{ live: auto }"></span>
          {{ auto ? '自动刷新 ' + interval + 's' : '已暂停' }}
        </p>
      </div>
      <div class="ops">
        <el-input v-model="addText" placeholder="输入代码，逗号分隔，如 600519,000858"
                  style="width: 260px" size="default" @keyup.enter="add" />
        <el-button @click="add">添加</el-button>
        <el-switch v-model="auto" active-text="自动" />
        <el-select v-model="interval" style="width: 90px" size="default">
          <el-option :value="5" label="5 秒" />
          <el-option :value="10" label="10 秒" />
          <el-option :value="30" label="30 秒" />
          <el-option :value="60" label="60 秒" />
        </el-select>
      </div>
    </div>

    <div class="card tbl">
    <el-table :data="rows" style="width: 100%" size="default"
              :row-style="{ height: '40px' }" @row-click="goDetail">
      <el-table-column prop="symbol" label="代码" width="90">
        <template #default="{ row }"><span style="font-weight:500">{{ row.symbol }}</span></template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="110">
        <template #default="{ row }"><span style="font-weight:500">{{ row.name }}</span></template>
      </el-table-column>
      <el-table-column label="最新价" width="100" align="right">
        <template #default="{ row }">
          <span class="mono" :class="cls(row.change_pct)">{{ fmt(row.price) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="涨跌幅" width="100" align="right">
        <template #default="{ row }">
          <span class="mono" :class="cls(row.change_pct)">{{ pct(row.change_pct) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="涨跌额" width="90" align="right">
        <template #default="{ row }">
          <span class="mono" :class="cls(row.change_pct)">{{ fmt(row.change_amt) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="今开" width="90" align="right">
        <template #default="{ row }"><span class="mono">{{ fmt(row.open) }}</span></template>
      </el-table-column>
      <el-table-column label="最高" width="90" align="right">
        <template #default="{ row }"><span class="mono">{{ fmt(row.high) }}</span></template>
      </el-table-column>
      <el-table-column label="最低" width="90" align="right">
        <template #default="{ row }"><span class="mono">{{ fmt(row.low) }}</span></template>
      </el-table-column>
      <el-table-column label="成交额" width="110" align="right">
        <template #default="{ row }"><span class="mono">{{ money(row.amount) }}</span></template>
      </el-table-column>
      <el-table-column label="换手" width="80" align="right">
        <template #default="{ row }"><span class="mono">{{ fmt(row.turnover) }}%</span></template>
      </el-table-column>
      <el-table-column label="市盈率" width="90" align="right">
        <template #default="{ row }"><span class="mono">{{ fmt(row.pe) }}</span></template>
      </el-table-column>
      <el-table-column label="操作" width="80" align="center">
        <template #default="{ row }">
          <el-button link type="danger" size="small" @click.stop="del(row.symbol)">移除</el-button>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <p class="tip" v-if="src">数据源：{{ src }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'

const rows = ref([])
const src = ref('')
const updatedAt = ref('')
const addText = ref('')
const auto = ref(true)
const interval = ref(10)
let timer = null
const router = useRouter()

function cls(v) { return v > 0 ? 'up' : v < 0 ? 'down' : 'flat' }
function fmt(v) { return v === null || v === undefined ? '—' : Number(v).toFixed(2) }
function pct(v) { return v === null || v === undefined ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2) + '%' }
function money(v) {
  if (!v) return '—'
  const n = Number(v)
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(2) + '万'
  return n.toFixed(0)
}

async function load() {
  try {
    const pool = await api.get('/pool')
    const syms = pool.data.map((x) => x.symbol)
    if (!syms.length) { rows.value = []; return }
    const r = await api.get('/quote', { params: { symbols: syms.join(',') } })
    src.value = r.source
    const map = {}
    r.data.forEach((q) => { map[q.symbol] = q })
    rows.value = syms.map((s) => map[s] || { symbol: s, name: pool.data.find(x => x.symbol === s)?.name })
      .filter(Boolean)
    updatedAt.value = new Date().toLocaleTimeString('zh-CN')
  } catch (e) {
    console.error(e)
  }
}

async function add() {
  const list = addText.value.split(/[,，\s]+/).filter(Boolean)
  if (!list.length) return
  await api.post('/pool', { symbols: list })
  addText.value = ''
  await load()
}

async function del(symbol) {
  await api.delete('/pool/' + symbol)
  await load()
}

function goDetail(row) { router.push('/stock/' + row.symbol) }

function restart() {
  if (timer) clearInterval(timer)
  if (auto.value) timer = setInterval(() => {
    if (document.visibilityState === 'visible') load()
  }, interval.value * 1000)
}

watch([auto, interval], restart)

onMounted(async () => { await load(); restart() })
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.head { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 14px; }
h2 { font-size: 16px; margin: 0 0 4px; font-weight: 700; }
h2::before { content: ''; display: inline-block; width: 4px; height: 14px; border-radius: 2px; background: #1485fe; margin-right: 8px; vertical-align: -1px; }
.meta { font-size: 12px; color: #8a94a6; margin: 0; display: flex; align-items: center; gap: 6px; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: #c6ccd4; display: inline-block; }
.dot.live { background: #2fa36b; }
.ops { display: flex; gap: 8px; align-items: center; }
.tbl { padding: 6px 10px; }
.tip { font-size: 11px; color: #a8adb6; margin-top: 10px; }
:deep(.el-table__row) { cursor: pointer; }
</style>
